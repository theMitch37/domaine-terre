"""Embouchures réelles depuis HydroRIVERS (10/11/2026, Maxime : « prends ces meilleures données »).

Le tracé Natural Earth des fleuves (fleuves.json) s'arrête souvent avant la mer : au Gange, l'Hooghly finit 60 km
avant la côte. HydroRIVERS v1.0 (HydroSHEDS, WWF / McGill, licence libre avec attribution) donne le réseau complet,
chaque tronçon connaissant celui d'aval (NEXT_DOWN) et s'il finit dans un bassin fermé (ENDORHEIC).

Pour chaque embouchure restée à terre (bout le plus bas d'un tracé, sans autre cours d'eau à moins de 8 blocs, sous
300 m d'altitude, pas déjà en mer) : le tronçon HydroRIVERS le plus gros (débit moyen) à moins de 5 km, puis la
chaîne des tronçons d'aval jusqu'au bout. Gardé seulement s'il finit à la mer (pas endoréique) et si le chemin fait
moins de 400 km. Le chemin, simplifié (~2 blocs), est ajouté au bout du tracé. Rien n'est touché d'autre.

Usage (GitHub Actions, internet) : python3 outils/fleuves_hydro.py <dossier des .shp HydroRIVERS ou RiverATLAS>
Écrit src/main/resources/domaine_terre/carte/fleuves.json (corrigé) et outils/donnees/fleuves_hydro.json (ajouts).
"""
import glob, json, os, sys, time
import numpy as np
from scipy.spatial import cKDTree
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import terre_py as T

ICI = os.path.dirname(os.path.abspath(__file__))
F = os.path.join(ICI, "../src/main/resources/domaine_terre/carte/fleuves.json")
SORTIE = os.path.join(ICI, "donnees/fleuves_hydro.json")
INDEX = os.path.join(ICI, "../lieux/src/main/resources/domaine_terre_lieux/tuiles/index.txt")
B = T.BPD
MPB = 60.0 / B
RAYON = 0.05                      # degrés (~5 km) pour trouver le tronçon HydroRIVERS
LONG_MAX = 400.0                  # km
SIMPLE = 2.0 / B                  # tolérance de simplification (2 blocs)

t0 = time.time()
t = json.load(open(F, encoding="utf-8"))
lieux = {tuple(map(int, l.split())) for l in open(INDEX) if l.strip()}

# --- embouchures à traiter
pts, own = [], []
for k, o in enumerate(t):
    for q in np.array(o["p"]).reshape(-1, 2):
        pts.append(q)
        own.append(k)
pts, own = np.array(pts), np.array(own)
arbre = cKDTree(pts * B)
bouts = []
for k, o in enumerate(t):
    p = np.array(o["p"]).reshape(-1, 2)
    if len(p) < 2:
        continue
    a = T.relief(p[[0, -1], 0], p[[0, -1], 1])
    fin = bool(a[1] <= a[0])
    m = p[-1] if fin else p[0]
    if min(a) > 300:
        continue
    d, idx = arbre.query(m * B, k=30)
    if any(own[i] != k and dd < 8 for dd, i in zip(d, idx)):
        continue                                  # confluence
    d0 = float(T.distance_cote(np.array([m[0] * B]), np.array([-m[1] * B]))[0]) / MPB
    if d0 <= 0:
        continue                                  # déjà en mer
    bouts.append((k, fin, float(m[0]), float(m[1]), d0))
print(f"{len(bouts)} embouchures à terre à examiner ({time.time() - t0:.0f} s)", flush=True)

# --- HydroRIVERS (tronçons d'un bassin de plus de 200 km² seulement : les cours d'eau du mod sont grands)
import pyogrio
from shapely import STRtree, LineString, Point, get_coordinates
ids, aval, endo, debit, geoms = [], [], [], [], []
for shp in sorted(glob.glob(os.path.join(sys.argv[1], "**", "*.shp"), recursive=True)):
    champs = {c.upper(): c for c in pyogrio.read_info(shp)["fields"]}
    q = champs.get("DIS_AV_CMS") or champs.get("DIS_M3_PYR") or champs["UPLAND_SKM"]
    df = pyogrio.read_dataframe(shp, columns=[champs["HYRIV_ID"], champs["NEXT_DOWN"], champs["ENDORHEIC"], q,
                                              champs["UPLAND_SKM"]], where=f"{champs['UPLAND_SKM']} > 200")
    ids.append(df[champs["HYRIV_ID"]].to_numpy())
    aval.append(df[champs["NEXT_DOWN"]].to_numpy())
    endo.append(df[champs["ENDORHEIC"]].to_numpy())
    debit.append(df[q].to_numpy())
    geoms.extend(df.geometry.values)
    print(os.path.basename(shp), len(df), "tronçons", flush=True)
ids, aval, endo, debit = (np.concatenate(v) for v in (ids, aval, endo, debit))
geoms = np.array(geoms, dtype=object)
rang = {int(i): n for n, i in enumerate(ids)}
arbre_h = STRtree(geoms)
print(f"{len(ids)} tronçons chargés ({time.time() - t0:.0f} s)", flush=True)

ajouts, rapport = {}, {"sans tronçon": 0, "endoréique": 0, "trop long": 0, "lieu": 0, "pas en mer": 0, "ok": 0}
for k, fin, lo, la, d0 in bouts:
    pt = Point(lo, la)
    cand = arbre_h.query(pt.buffer(RAYON))
    cand = [c for c in cand if geoms[c].distance(pt) <= RAYON]
    if not cand:
        rapport["sans tronçon"] += 1
        continue
    c = max(cand, key=lambda c: debit[c])
    chemin, n, longueur, ok = [], c, 0.0, True
    premier = True
    while True:
        g = geoms[n]
        xy = get_coordinates(g)
        # sens d'écoulement : le bout le plus proche du tronçon d'aval (ou, faute d'aval, le plus loin de l'amont)
        nd = int(aval[n])
        if nd in rang:
            ga = geoms[rang[nd]]
            if Point(xy[0]).distance(ga) < Point(xy[-1]).distance(ga):
                xy = xy[::-1]
        elif chemin:
            if np.hypot(*(xy[0] - chemin[-1])) > np.hypot(*(xy[-1] - chemin[-1])):
                xy = xy[::-1]
        if premier:                                # depuis le point projeté sur le premier tronçon
            ls = LineString(xy)
            s = ls.project(pt)
            cum = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(xy, axis=0).T))])
            xy = np.vstack([np.array(ls.interpolate(s).coords), xy[cum > s]])
            premier = False
        chemin.extend(xy.tolist())
        longueur += float(np.hypot(*np.diff(xy, axis=0).T).sum()) * 111.0
        if longueur > LONG_MAX:
            ok = False
            rapport["trop long"] += 1
            break
        nd = int(aval[n])
        if nd == 0 or nd not in rang:
            if endo[n]:
                ok = False
                rapport["endoréique"] += 1
            break
        n = rang[nd]
    if not ok or len(chemin) < 2:
        continue
    ligne = LineString(chemin).simplify(SIMPLE)
    xy = get_coordinates(ligne)
    # le bout doit être en mer (ou à moins de 64 blocs : fleuves_mer.py finit)
    fx, fz = xy[-1, 0] * B, -xy[-1, 1] * B
    if float(T.distance_cote(np.array([fx]), np.array([fz]))[0]) / MPB > 64:
        rapport["pas en mer"] += 1
        continue
    if any((int(np.floor(x * B / 512)), int(np.floor(-y * B / 512))) in lieux for x, y in xy):
        rapport["lieu"] += 1
        continue
    # on coupe le chemin dès qu'il entre en mer franche (6 blocs au large)
    garde = [xy[0]]
    for x, y in xy[1:]:
        garde.append((x, y))
        if float(T.distance_cote(np.array([x * B]), np.array([-y * B]))[0]) / MPB < -6:
            break
    xy = np.array(garde)[1:]                       # le premier point est le bout actuel (projeté)
    if len(xy) == 0:
        continue
    plat = [round(float(v), 4) for q in xy for v in q]
    ajouts[k] = {"fin": fin, "p": plat, "nom": t[k]["n"]}
    o = t[k]
    if fin:
        o["p"] = o["p"] + plat
    else:
        rev = [round(float(v), 4) for q in xy[::-1] for v in q]
        o["p"] = rev + o["p"]
    rapport["ok"] += 1

os.makedirs(os.path.dirname(SORTIE), exist_ok=True)
json.dump(ajouts, open(SORTIE, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
json.dump(t, open(F, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("bilan :", rapport, f"({time.time() - t0:.0f} s)")

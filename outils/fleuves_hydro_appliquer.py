"""Pose les cours d'aval HydroRIVERS / RiverATLAS dans fleuves.json, avec des règles (10/11/2026).

outils/donnees/fleuves_hydro.json (fait par fleuves_hydro.py dans GitHub Actions) donne, pour chaque embouchure restée à
terre, le vrai cours d'aval jusqu'à la mer. Vérification du 10/11 : la moitié de ces chemins sont ceux d'un affluent
(Ping, Teesta, Donets, Gila…) qui descendent ensuite le long du fleuve principal, déjà tracé dans le mod : un second
lit parallèle. Règles :
  - le chemin s'arrête dès qu'il touche un autre cours d'eau du mod (à 4 blocs) : c'est la confluence ;
  - sinon il doit finir en mer (côte fine) ;
  - aucun pas de plus de 40 km (un trou dans les données, pas un cours d'eau) ;
  - rien dans les tuiles d'un lieu.

Usage : python3 outils/fleuves_hydro_appliquer.py   (part de fleuves.json tel qu'il est ; idempotent)
"""
import json, os, sys
import numpy as np
from scipy.spatial import cKDTree
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import terre_py as T

ICI = os.path.dirname(os.path.abspath(__file__))
F = os.path.join(ICI, "../src/main/resources/domaine_terre/carte/fleuves.json")
H = os.path.join(ICI, "donnees/fleuves_hydro.json")
INDEX = os.path.join(ICI, "../lieux/src/main/resources/domaine_terre_lieux/tuiles/index.txt")
B = T.BPD
MPB = 60.0 / B
CONFLUENCE = 4.0                # blocs
PAS_MAX = 40.0                  # km : le chemin suit les tronçons liés (pas de trou) ; simplifié à 2 blocs, un bief
                                # droit peut être long (Saint-Laurent au lac Saint-Pierre : 30 km, 11/11/2026)

t = json.load(open(F, encoding="utf-8"))
ajouts = json.load(open(H, encoding="utf-8"))
lieux = {tuple(map(int, l.split())) for l in open(INDEX) if l.strip()}

# points de tous les tracés, densifiés à 2 blocs (pour trouver un autre cours d'eau le long du chemin)
pts, own = [], []
for k, o in enumerate(t):
    p = np.array(o["p"]).reshape(-1, 2) * [B, -B]
    for a, b in zip(p[:-1], p[1:]):
        n = max(1, int(np.hypot(*(b - a)) / 2))
        for s in np.linspace(0, 1, n, endpoint=False):
            pts.append(a + (b - a) * s)
            own.append(k)
    pts.append(p[-1])
    own.append(k)
pts, own = np.array(pts), np.array(own)
arbre = cKDTree(pts)

bilan = {"confluence": 0, "mer": 0, "trou": 0, "ni mer ni confluence": 0, "lieu": 0, "déjà fait": 0}
for ks, v in ajouts.items():
    k = int(ks)
    o = t[k]
    chemin = np.array(v["p"]).reshape(-1, 2)              # de l'embouchure actuelle vers l'aval
    bout = np.array(o["p"][-2:] if v["fin"] else o["p"][:2])
    if o.get("hy") or np.hypot(*(bout - chemin[0])) > 0.5:
        bilan["déjà fait"] += 1
        continue
    xy = chemin * [B, -B]
    garde, fin_ok = [], None
    for q in xy:
        voisins = arbre.query_ball_point(q, CONFLUENCE)
        if any(own[i] != k for i in voisins):
            garde.append(q)
            fin_ok = "confluence"
            break
        garde.append(q)
        if float(T.distance_cote(np.array([q[0]]), np.array([q[1]]))[0]) < 0:
            fin_ok = "mer"
            break
    if fin_ok is None and float(T.distance_cote(np.array([xy[-1][0]]), np.array([xy[-1][1]]))[0]) < 2.0:
        fin_ok = "mer"                            # au bord de la mer du mod (fleuves_mer.py finit, ≤ 64 blocs)
    if fin_ok is None:
        bilan["ni mer ni confluence"] += 1
        continue
    g = np.array([np.array(bout) * [B, -B]] + garde)
    pas_km = np.hypot(*np.diff(g, axis=0).T) * 0.25
    # le premier lien va du bout du tracé au tronçon le plus proche (jusqu'à 5 km) puis au point suivant
    if pas_km[0] > 2 * PAS_MAX or (len(pas_km) > 1 and pas_km[1:].max() > PAS_MAX):
        bilan["trou"] += 1
        continue
    if any((int(np.floor(x / 512)), int(np.floor(z / 512))) in lieux for x, z in g):
        bilan["lieu"] += 1
        continue
    plat = [round(float(c), 4) for x, z in garde for c in (x / B, -z / B)]
    if v["fin"]:
        o["p"] = o["p"] + plat
    else:
        o["p"] = [round(float(c), 4) for x, z in garde[::-1] for c in (x / B, -z / B)] + o["p"]
    o["hy"] = 1                                   # posé (ignoré par le jeu) : pas deux fois
    bilan[fin_ok] += 1

json.dump(t, open(F, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("cours d'aval HydroRIVERS posés :", bilan)

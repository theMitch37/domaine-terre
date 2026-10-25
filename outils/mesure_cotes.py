"""Mesure du coût d'un trait de côte haute résolution pour Terre (étape B de la « mer fidèle »).

Lancé par .github/workflows/mesure-cotes.yml (les données ne se téléchargent pas depuis le poste de travail).
Usage : python outils/mesure_cotes.py <dossier GSHHS_shp> <ne_10m_land.shp> <sortie.txt>

Compare Natural Earth 10m (côte actuelle du mod) et GSHHG « high » et « full » :
- nombre de polygones et de points, longueur des côtes ;
- îles par taille (1 bloc = 250 m x 250 m = 0,0625 km² à l'échelle 1:250) ;
- taille d'une carte fine des côtes : tuiles de 256 x 256 cases traversées par la côte, à 1 et 2 blocs par case,
  en masque 1 bit et en distance signée sur un octet (bande de ±16 blocs), compressées (zlib), d'après un
  échantillon de tuiles réellement rastérisées.
"""
import glob, math, os, sys, time, zlib
import numpy as np
import pyogrio
import shapely
from matplotlib.path import Path
from scipy import ndimage

BPD = 445.28                     # blocs par degré (1:250)
R = 6371.0


def charger(chemins):
    geoms = []
    for c in chemins:
        _, _, wkb, _ = pyogrio.raw.read(c, columns=[])
        geoms.extend(g for g in shapely.from_wkb(wkb) if g is not None)
    return geoms


def anneaux(geoms):
    for g in geoms:
        for p in getattr(g, "geoms", [g]):
            yield np.asarray(p.exterior.coords)
            for i in p.interiors:
                yield np.asarray(i.coords)


def longueur_km(xy):
    lon, lat = np.radians(xy[:, 0]), np.radians(xy[:, 1])
    dl = np.diff(lon); dl = (dl + np.pi) % (2 * np.pi) - np.pi
    dx = dl * np.cos((lat[1:] + lat[:-1]) / 2); dy = np.diff(lat)
    return float(np.hypot(dx, dy).sum() * R)


def aire_km2(p):
    lat = np.radians(p.centroid.y)
    return p.area * (111.32 ** 2) * math.cos(lat)


def stats(nom, geoms, f):
    polys = [p for g in geoms for p in getattr(g, "geoms", [g])]
    n_pts = sum(len(a) for a in anneaux(geoms))
    L = sum(longueur_km(a) for a in anneaux(geoms))
    aires = np.array([aire_km2(p) for p in polys])
    f.write(f"\n== {nom}\n")
    f.write(f"polygones {len(polys)} | points {n_pts} | côtes {L:,.0f} km = {L * 4:,.0f} blocs\n")
    for seuil, txt in ((0.0625, "≥ 1 bloc"), (1.0, "≥ 16 blocs (1 km²)"), (25.0, "≥ 400 blocs (25 km²)")):
        f.write(f"  îles et terres {txt} : {int((aires >= seuil).sum())}\n")
    f.flush()
    return polys, L


def tuiles_cote(geoms, cases_par_bloc, taille=256):
    """Indices des tuiles (taille x taille cases) traversées par la côte."""
    pas = taille / (BPD * cases_par_bloc)            # degrés par tuile
    t = set()
    for a in anneaux(geoms):
        # densifier : au moins 4 points par tuile (vectorisé : les côtes « full » ont des millions de points)
        d = np.diff(a, axis=0)
        n = np.maximum(1, np.ceil(np.hypot(d[:, 0], d[:, 1]) / (pas / 4))).astype(int)
        i = np.repeat(np.arange(len(d)), n)
        k = np.arange(len(i)) - np.repeat(np.cumsum(n) - n, n)
        u = (k / n[i])[:, None]
        xy = a[:-1][i] + d[i] * u
        tx = np.floor((xy[:, 0] + 180) / pas).astype(np.int64); ty = np.floor((90 - xy[:, 1]) / pas).astype(np.int64)
        t.update(np.unique(tx * 100000 + ty).tolist())
    t = {(int(v // 100000), int(v % 100000)) for v in t}
    return t, pas


def raster_tuile(arbre, polys, tx, ty, pas, taille):
    lon0, lat0 = -180 + tx * pas, 90 - ty * pas
    boite = shapely.box(lon0, lat0 - pas, lon0 + pas, lat0)
    m = np.zeros((taille, taille), bool)
    c = (np.arange(taille) + 0.5) / taille * pas
    X, Y = np.meshgrid(lon0 + c, lat0 - c)
    pts = np.c_[X.ravel(), Y.ravel()]
    for i in arbre.query(boite):
        p = polys[i].intersection(boite)                 # découpé à la tuile : un continent entier serait trop lent
        if p.is_empty:
            continue
        for q in getattr(p, "geoms", [p]):
            if q.geom_type != "Polygon":
                continue
            dedans = Path(np.asarray(q.exterior.coords)).contains_points(pts)
            for h in q.interiors:
                dedans &= ~Path(np.asarray(h.coords)).contains_points(pts)
            m |= dedans.reshape(taille, taille)
    return m


def taille_carte(nom, geoms, polys, f, cases_par_bloc, taille=256, echantillon=40):
    t0 = time.time()
    tuiles, pas = tuiles_cote(geoms, cases_par_bloc, taille)
    arbre = shapely.STRtree(polys)
    rng = np.random.default_rng(1)
    choix = [list(tuiles)[i] for i in rng.choice(len(tuiles), min(echantillon, len(tuiles)), replace=False)]
    b1, b8 = [], []
    for tx, ty in choix:
        m = raster_tuile(arbre, polys, tx, ty, pas, taille)
        b1.append(len(zlib.compress(np.packbits(m).tobytes(), 9)))
        sd = ndimage.distance_transform_edt(m) - ndimage.distance_transform_edt(~m)
        sd = np.clip(np.round(sd / cases_par_bloc * 8), -127, 127).astype(np.int8)    # 1/8 de bloc, ±16 blocs
        b8.append(len(zlib.compress(sd.tobytes(), 9)))
    n = len(tuiles)
    f.write(f"  carte {cases_par_bloc} case(s)/bloc, tuiles {taille}² ({pas:.3f}°) traversées par la côte : {n}\n")
    f.write(f"    masque 1 bit compressé : {np.mean(b1) * n / 1e6:,.1f} Mo | distance signée 1 octet : "
            f"{np.mean(b8) * n / 1e6:,.1f} Mo   (échantillon {len(choix)} tuiles, {time.time() - t0:.0f} s)\n")
    f.flush()


def main():
    dos, ne, sortie = sys.argv[1:4]
    with open(sortie, "w") as f:
        f.write("Mesure des côtes haute résolution (étape B, Terre 0.3.2)\n")
        geoms = charger([ne])
        polys, _ = stats("Natural Earth 10m (côte actuelle)", geoms, f)
        taille_carte("NE", geoms, polys, f, 0.5)
        for res, nom in (("h", "GSHHG high"), ("f", "GSHHG full")):
            chemins = sorted(glob.glob(os.path.join(dos, res, f"GSHHS_{res}_L1.shp"))) + \
                      sorted(glob.glob(os.path.join(dos, res, f"GSHHS_{res}_L5.shp")))
            geoms = charger(chemins)
            polys, _ = stats(nom, geoms, f)
            for cpb in (0.5, 1):
                taille_carte(nom, geoms, polys, f, cpb)
    print(open(sortie).read())


if __name__ == "__main__":
    main()

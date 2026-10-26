"""Mesure pour l'étape C1 : altitude de surface des lacs GSHHG (niveau 2) lue dans Copernicus DEM GLO-90 (AWS Open Data,
lecture partielle des tuiles COG). Sur un modèle de surface, l'eau d'un lac est à l'altitude de sa surface.
Lancé par .github/workflows/mesure-lacs.yml.

Usage : python outils/mesure_lacs_dem.py <dossier GSHHS_shp> <sortie.txt>
"""
import glob, math, os, sys
import numpy as np
import pyogrio, shapely
import rasterio

URL = "https://copernicus-dem-90m.s3.amazonaws.com/{n}/{n}.tif"
CONNUS = [  # nom, lat, lon, altitude réelle (m)
    ("Léman", 46.45, 6.55, 372), ("Lac Supérieur", 47.7, -87.5, 183), ("Baïkal", 53.5, 108.0, 456),
    ("Titicaca", -15.9, -69.4, 3812), ("Victoria", -1.0, 33.0, 1134), ("Ladoga", 61.0, 31.5, 5),
    ("Caspienne", 42.0, 50.5, -28), ("Lac d'Annecy", 45.86, 6.17, 447), ("Lac de Garde", 45.65, 10.68, 65),
    ("Mer Morte", 31.5, 35.5, -430), ("Tanganyika", -6.0, 29.6, 773), ("Lac Majeur", 45.95, 8.65, 193),
    ("Lac Balaton", 46.83, 17.73, 104), ("Lac du Bourget", 45.73, 5.87, 231), ("Lac de Constance", 47.6, 9.4, 395),
    ("Loch Ness", 57.3, -4.45, 16), ("Lac de Serre-Ponçon", 44.53, 6.35, 780), ("Lac de Sainte-Croix", 43.77, 6.20, 477),
]


def nom_tuile(lat, lon):
    la, lo = math.floor(lat), math.floor(lon)
    ns = f"N{la:02d}" if la >= 0 else f"S{-la:02d}"
    ew = f"E{lo:03d}" if lo >= 0 else f"W{-lo:03d}"
    return f"Copernicus_DSM_COG_30_{ns}_00_{ew}_00_DEM"


_ouvertes = {}


def altitude(lat, lon):
    n = nom_tuile(lat, lon)
    if n not in _ouvertes:
        try:
            _ouvertes[n] = rasterio.open(URL.format(n=n))
        except Exception as e:
            _ouvertes[n] = None
    ds = _ouvertes[n]
    if ds is None:
        return np.nan
    r, c = ds.index(lon, lat)
    v = ds.read(1, window=((r, r + 1), (c, c + 1)))
    return float(v[0, 0]) if v.size else np.nan


def points_dedans(p, n=25, graine=1):
    """Points au hasard à l'intérieur du lac, loin du rivage (au moins un quart de la plus grande distance)."""
    rng = np.random.default_rng(graine)
    x0, y0, x1, y1 = p.bounds
    pts = []
    interieur = p.buffer(-0.25 * max(min(x1 - x0, y1 - y0), 1e-4) * 0.25)
    cible = interieur if not interieur.is_empty else p
    for _ in range(4000):
        x, y = rng.uniform(x0, x1), rng.uniform(y0, y1)
        if shapely.contains_xy(cible, x, y):
            pts.append((y, x))
            if len(pts) >= n:
                break
    if not pts:
        c = p.representative_point(); pts = [(c.y, c.x)]
    return pts


def main():
    dos, sortie = sys.argv[1:3]
    _, _, wkb, _ = pyogrio.raw.read(sorted(glob.glob(os.path.join(dos, "f", "GSHHS_f_L2.shp")))[0])
    lacs = [q for g in shapely.from_wkb(wkb) if g is not None for q in getattr(g, "geoms", [g])]
    arbre = shapely.STRtree(lacs)
    with open(sortie, "w") as f:
        f.write("Altitude de surface des lacs : Copernicus DEM GLO-90 à l'intérieur du lac GSHHG (médiane, écart des points)\n")
        for nom, la, lo, vrai in CONNUS:
            idx = arbre.query(shapely.Point(lo, la), predicate="within")
            if len(idx) == 0:
                f.write(f"  {nom:22s} réel {vrai:5d} m | absent de GSHHG\n"); continue
            p = lacs[idx[0]]
            v = np.array([altitude(y, x) for y, x in points_dedans(p)])
            v = v[np.isfinite(v)]
            if not len(v):
                f.write(f"  {nom:22s} réel {vrai:5d} m | modèle illisible\n"); continue
            f.write(f"  {nom:22s} réel {vrai:5d} m | modèle médiane {np.median(v):7.1f} m, min {v.min():7.1f}, "
                    f"max {v.max():7.1f} ({len(v)} points)\n")
            f.flush()
    print(open(sortie).read())


if __name__ == "__main__":
    main()

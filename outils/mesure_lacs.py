"""Mesure pour l'étape C1 (lacs en altitude) : les lacs GSHHG (niveau 2) et l'altitude de leur surface lue dans la
carte de relief du mod (ETOPO 2022, 3'). Lancé par .github/workflows/mesure-cotes.yml.

Usage : python outils/mesure_lacs.py <GSHHS_shp> <sortie.txt>
- nombre de lacs par taille (1 bloc = 0,0625 km² à 1:250) ;
- altitude de surface estimée (médiane et minimum du relief sous le lac) pour des lacs connus, à comparer au réel ;
- répartition des altitudes.
"""
import glob, math, os, sys
import numpy as np
import pyogrio
import shapely
from PIL import Image

RACINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
RELIEF = os.path.join(RACINE, "src/main/resources/domaine_terre/carte/relief.png")
CONNUS = [  # nom, lat, lon, altitude réelle (m)
    ("Léman", 46.45, 6.55, 372), ("Lac Supérieur", 47.7, -87.5, 183), ("Baïkal", 53.5, 108.0, 456),
    ("Titicaca", -15.9, -69.4, 3812), ("Victoria", -1.0, 33.0, 1134), ("Ladoga", 61.0, 31.5, 5),
    ("Caspienne", 42.0, 50.5, -28), ("Lac de Sainte-Croix", 43.77, 6.20, 477), ("Lac d'Annecy", 45.86, 6.17, 447),
    ("Lac de Garde", 45.65, 10.68, 65), ("Mer Morte", 31.5, 35.5, -430), ("Tanganyika", -6.0, 29.6, 773),
    ("Lac Majeur", 45.95, 8.65, 193), ("Lac Balaton", 46.83, 17.73, 104),
]


def main():
    dos, sortie = sys.argv[1:3]
    meta, _, wkb, _ = pyogrio.raw.read(sorted(glob.glob(os.path.join(dos, "f", "GSHHS_f_L2.shp")))[0])
    lacs = [g for g in shapely.from_wkb(wkb) if g is not None]
    lacs = [p for g in lacs for p in getattr(g, "geoms", [g])]
    rel = np.array(Image.open(RELIEF), dtype=np.float64) - 11000
    H, W = rel.shape

    def alt_sous(p):
        x0, y0, x1, y1 = p.bounds
        i0, i1 = int((x0 + 180) / 360 * W), int(math.ceil((x1 + 180) / 360 * W))
        j0, j1 = int((90 - y1) / 180 * H), int(math.ceil((90 - y0) / 180 * H))
        ii, jj = np.meshgrid(np.arange(i0, i1 + 1), np.arange(j0, j1 + 1))
        lon = (ii + 0.5) / W * 360 - 180; lat = 90 - (jj + 0.5) / H * 180
        dedans = shapely.contains_xy(p, lon, lat)
        if not dedans.any():
            c = p.representative_point(); i = int((c.x + 180) / 360 * W); j = int((90 - c.y) / 180 * H)
            v = rel[min(j, H - 1), i % W]
            return v, v, 1
        v = rel[np.clip(jj[dedans], 0, H - 1), ii[dedans] % W]
        return float(np.median(v)), float(v.min()), int(dedans.sum())

    aires = np.array([p.area * 111.32 ** 2 * math.cos(math.radians(p.centroid.y)) for p in lacs])
    with open(sortie, "w") as f:
        f.write(f"Lacs GSHHG full (niveau 2) : {len(lacs)}\n")
        for s, t in ((0.0625, "≥ 1 bloc"), (1, "≥ 1 km² (16 blocs)"), (25, "≥ 25 km²"), (1000, "≥ 1 000 km²")):
            f.write(f"  {t} : {int((aires >= s).sum())}\n")
        f.write("\nLacs connus : altitude réelle / médiane du relief sous le lac / minimum / cases 3'\n")
        arbre = shapely.STRtree(lacs)
        for nom, la, lo, vrai in CONNUS:
            idx = arbre.query(shapely.Point(lo, la), predicate="within")
            if len(idx) == 0:
                f.write(f"  {nom:22s} réel {vrai:5d} m | absent de GSHHG\n"); continue
            p = lacs[idx[0]]
            med, mn, n = alt_sous(p)
            f.write(f"  {nom:22s} réel {vrai:5d} m | médiane {med:7.0f} | min {mn:7.0f} | {n} cases | "
                    f"{aires[idx[0]]:,.0f} km²\n")
        gros = [i for i in np.argsort(-aires) if aires[i] >= 25]
        alts = np.array([alt_sous(lacs[i])[0] for i in gros])
        f.write(f"\nAltitude médiane estimée des {len(gros)} lacs ≥ 25 km² :\n")
        for a, b in ((-1e9, 0), (0, 200), (200, 500), (500, 1000), (1000, 2000), (2000, 1e9)):
            f.write(f"  {a:>6.0f} à {b:<6.0f} m : {int(((alts >= a) & (alts < b)).sum())}\n")
    print(open(sortie).read())


if __name__ == "__main__":
    main()

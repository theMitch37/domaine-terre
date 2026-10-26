"""Mesure pour l'étape C1 (lacs en altitude) : HydroLAKES v1.0 (Messager et al. 2016, CC-BY 4.0).
Lancé par .github/workflows/mesure-lacs.yml.

Usage : python outils/mesure_hydrolakes.py <HydroLAKES_polys_v10.shp> <sortie.txt>
- nombre de lacs par taille (1 bloc = 0,0625 km² à 1:250) ;
- lacs connus : altitude de surface, profondeur moyenne, hauteur en y avec la courbe du mod, exutoire ;
- répartition des altitudes ; taille de la carte des lacs au bloc près (cases, tuiles 256²).
"""
import math, sys
import numpy as np
import pyogrio

CONNUS = [  # nom, lat, lon, altitude réelle (m)
    ("Léman", 46.45, 6.55, 372), ("Lac Supérieur", 47.7, -87.5, 183), ("Baïkal", 53.5, 108.0, 456),
    ("Titicaca", -15.9, -69.4, 3812), ("Victoria", -1.0, 33.0, 1134), ("Ladoga", 61.0, 31.5, 5),
    ("Caspienne", 42.0, 50.5, -28), ("Lac de Sainte-Croix", 43.77, 6.20, 477), ("Lac d'Annecy", 45.86, 6.17, 447),
    ("Lac de Garde", 45.65, 10.68, 65), ("Mer Morte", 31.5, 35.5, -430), ("Tanganyika", -6.0, 29.6, 773),
    ("Lac Majeur", 45.95, 8.65, 193), ("Lac Balaton", 46.83, 17.73, 104), ("Lac du Bourget", 45.73, 5.87, 231),
    ("Lac de Serre-Ponçon", 44.53, 6.35, 780), ("Lac de Constance", 47.6, 9.4, 395), ("Loch Ness", 57.3, -4.45, 16),
]


def blocs(a):
    """Terrain.blocsDepuisAltitude (terre)."""
    if a <= 500: return 64 + a / 500 * 16
    if a <= 2000: return 80 + (a - 500) / 1500 * 60
    return 140 + min((a - 2000) / 6800, 1) * 160


def main():
    shp, sortie = sys.argv[1:3]
    info = pyogrio.read_info(shp)
    cols = ["Hylak_id", "Lake_name", "Lake_type", "Lake_area", "Depth_avg", "Elevation", "Pour_long", "Pour_lat"]
    meta, fid, geom, champs = pyogrio.raw.read(shp, columns=cols, read_geometry=False)
    d = dict(zip(meta["fields"], champs))
    aire = np.asarray(d["Lake_area"], float); alt = np.asarray(d["Elevation"], float)
    prof = np.asarray(d["Depth_avg"], float); typ = np.asarray(d["Lake_type"], int)
    plon = np.asarray(d["Pour_long"], float); plat = np.asarray(d["Pour_lat"], float)
    with open(sortie, "w") as f:
        f.write(f"HydroLAKES : {len(aire)} lacs ; champs : {list(meta['fields'])}\n")
        f.write(f"Couche : {info.get('features')} entités, {info.get('crs')}\n\n")
        for s in (0.0625, 0.25, 0.5, 1, 5, 25, 1000):
            k = aire >= s
            f.write(f"  ≥ {s:>7} km² ({s / 0.0625:>6.0f} blocs) : {int(k.sum()):8d} lacs, "
                    f"{aire[k].sum() / 0.0625 / 1e6:6.1f} M blocs de surface\n")
        f.write(f"\nTypes (1 lac, 2 réservoir, 3 lac régulé) parmi ≥ 0,5 km² : "
                f"{np.bincount(typ[aire >= 0.5], minlength=4)[1:].tolist()}\n")
        f.write("\nLacs connus (le plus grand lac HydroLAKES dont l'exutoire est à < 0,6° du point) :\n")
        for nom, la, lo, vrai in CONNUS:
            dist = np.hypot((plon - lo) * math.cos(math.radians(la)), plat - la)
            k = np.flatnonzero(dist < 0.6)
            if len(k) == 0:
                f.write(f"  {nom:22s} réel {vrai:5d} m | introuvable\n"); continue
            i = k[np.argmax(aire[k])]
            f.write(f"  {nom:22s} réel {vrai:5d} m | HydroLAKES « {d['Lake_name'][i]} » alt {alt[i]:6.0f} m, "
                    f"prof. moy. {prof[i]:6.1f} m, {aire[i]:9.1f} km², type {typ[i]} -> y {blocs(max(alt[i], 0)):6.1f}\n")
        k = aire >= 0.5
        f.write(f"\nAltitude de surface des {int(k.sum())} lacs ≥ 0,5 km² :\n")
        for a, b in ((-1e9, 0), (0, 200), (200, 500), (500, 1000), (1000, 2000), (2000, 4000), (4000, 1e9)):
            f.write(f"  {a:>6.0f} à {b:<6.0f} m : {int((k & (alt >= a) & (alt < b)).sum())}\n")
        f.write(f"\nProfondeur moyenne (≥ 0,5 km²) : médiane {np.median(prof[k]):.1f} m, 90e centile "
                f"{np.percentile(prof[k], 90):.1f} m, max {prof[k].max():.0f} m\n")
    print(open(sortie).read())


if __name__ == "__main__":
    main()

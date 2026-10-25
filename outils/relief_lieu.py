"""Découpe le relief Copernicus DEM GLO-30 (30 m) autour d'un lieu, pour l'addon Lieux.

Lancé dans GitHub Actions (le shell local n'a pas internet) : le résultat, petit, est ajouté au dépôt.
Usage : python outils/relief_lieu.py <dalle.tif> [<dalle2.tif> ...] <nom> <ouest> <est> <sud> <nord>
Sortie : outils/donnees/relief_<nom>.npz  (E = altitude int16 en m, lon0/lat0 = coin nord-ouest, pas en degrés)
"""
import sys
import numpy as np
import rasterio
from rasterio.merge import merge

*dalles, nom, o, e, s, n = sys.argv[1:]
o, e, s, n = map(float, (o, e, s, n))
srcs = [rasterio.open(d) for d in dalles]
a, tr = merge(srcs, bounds=(o, s, e, n))
a = a[0]
pas_lon, pas_lat = tr.a, -tr.e
print(f"{nom} : {a.shape[1]} x {a.shape[0]} points, pas {pas_lon * 3600:.2f}\" x {pas_lat * 3600:.2f}\", "
      f"altitude {np.nanmin(a):.0f} à {np.nanmax(a):.0f} m")
np.savez_compressed(f"outils/donnees/relief_{nom}.npz", E=np.round(a).astype(np.int16),
                    lon0=tr.c, lat0=tr.f, pas_lon=pas_lon, pas_lat=pas_lat)

"""Découpe la couverture du sol ESA WorldCover 2021 (10 m) autour d'un lieu, pour l'addon Lieux.

Classes : 10 arbres, 20 arbustes, 30 herbe, 40 cultures, 50 bâti, 60 sol nu, 70 neige et glace, 80 eau permanente,
90 zones humides, 95 mangroves, 100 mousses et lichens. Lancé dans GitHub Actions (lecture à distance, par fenêtre).
Usage : python outils/couverture_lieu.py <nom> <ouest> <est> <sud> <nord> [--pas=N]   (pas : 3 -> 30 m)
Sortie : outils/donnees/couverture_<nom>.npz (C = classe uint8, lon0/lat0 = coin nord-ouest, pas en degrés)
"""
import math, sys
import numpy as np
import rasterio
from rasterio.windows import from_bounds

args = [x for x in sys.argv[1:] if not x.startswith("--pas=")]
pas = int(next((x[6:] for x in sys.argv[1:] if x.startswith("--pas=")), "3"))
nom, o, e, s, n = args[0], *map(float, args[1:5])
URL = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_{}_Map.tif"
res = 1 / 12000                                             # 10 m = 0,3"
W, H = int(round((e - o) / res / pas)), int(round((n - s) / res / pas))
C = np.zeros((H, W), np.uint8)
for la in range(int(math.floor(s / 3)) * 3, int(math.ceil(n / 3)) * 3, 3):
    for lo in range(int(math.floor(o / 3)) * 3, int(math.ceil(e / 3)) * 3, 3):
        code = f"{'N' if la >= 0 else 'S'}{abs(la):02d}{'E' if lo >= 0 else 'W'}{abs(lo):03d}"
        b = (max(o, lo), max(s, la), min(e, lo + 3), min(n, la + 3))
        if b[0] >= b[2] or b[1] >= b[3]:
            continue
        with rasterio.open("/vsicurl/" + URL.format(code)) as src:
            w = from_bounds(*b, transform=src.transform)
            i0, j0 = int(round((b[0] - o) / res / pas)), int(round((n - b[3]) / res / pas))
            i1, j1 = int(round((b[2] - o) / res / pas)), int(round((n - b[1]) / res / pas))
            a = src.read(1, window=w, out_shape=(j1 - j0, i1 - i0), resampling=rasterio.enums.Resampling.mode)
            C[j0:j1, i0:i1] = a
        print(f"  {code} : fenêtre {b}")
vals, nb = np.unique(C, return_counts=True)
print(f"{nom} : {W} x {H} points, classes {dict(zip(vals.tolist(), nb.tolist()))}")
np.savez_compressed(f"outils/donnees/couverture_{nom}.npz", C=C, lon0=o, lat0=n, pas_lon=res * pas, pas_lat=res * pas)

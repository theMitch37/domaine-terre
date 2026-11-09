"""Aperçu de l'échelle 1:30 (09/11/2026) : Copernicus GLO-30 rééchantillonné à 1 point par bloc (30 m), même
projection que le mod (lon = x / BPD, lat = -z / BPD). Écrit <sortie>/<zone>.npz (alt en mètres, float32, NaN = mer).

Usage : python outils/apercu_130.py <dossier_tif> <sortie>   (zones ci-dessous)
"""
import os, sys, math
import numpy as np
import rasterio
from rasterio.merge import merge
from rasterio.enums import Resampling
from rasterio.warp import reproject
from rasterio.transform import from_origin

BPD = 111320 / 30
ZONES = {                     # nom : (lat centre, lon centre, taille en blocs)
    "jungfrau": (46.575, 7.94, 1024),
    "cervin": (45.99, 7.70, 768),
    "grand_canyon": (36.10, -112.10, 1024),
    "gullfoss": (64.327, -20.12, 512),
    "everest": (27.988, 86.925, 1024),
    "everest_large": (27.988, 86.925, 1340),   # même emprise que la zone de banc himalaya_everest (~160 blocs au 1:250)
    "grand_canyon_large": (36.10, -112.10, 2134),   # même emprise que la zone de banc grand_canyon (256 blocs au 1:250)
}


def nom(lat, lon):
    ns = f"N{lat:02d}" if lat >= 0 else f"S{-lat:02d}"
    ew = f"E{lon:03d}" if lon >= 0 else f"W{-lon:03d}"
    return f"Copernicus_DSM_COG_10_{ns}_00_{ew}_00_DEM"


def cadre(lat, lon, t):
    x0 = math.floor(lon * BPD) - t // 2
    z0 = math.floor(-lat * BPD) - t // 2
    return x0, z0, x0 / BPD, (x0 + t) / BPD, -(z0 + t) / BPD, -z0 / BPD   # x0, z0, ouest, est, sud, nord


if __name__ == "__main__":
    if sys.argv[1] == "--dalles":
        s = set()
        for la, lo, t in ZONES.values():
            _, _, o, e, su, n = cadre(la, lo, t)
            for a in range(math.floor(su), math.floor(n) + 1):
                for b in range(math.floor(o), math.floor(e) + 1):
                    s.add(nom(a, b))
        print("\n".join(sorted(s)))
        sys.exit()
    dossier, sortie = sys.argv[1], sys.argv[2]
    os.makedirs(sortie, exist_ok=True)
    for z, (la, lo, t) in ZONES.items():
        x0, z0, o, e, s, n = cadre(la, lo, t)
        srcs = []
        for a in range(math.floor(s), math.floor(n) + 1):
            for b in range(math.floor(o), math.floor(e) + 1):
                p = os.path.join(dossier, nom(a, b) + ".tif")
                if os.path.exists(p):
                    srcs.append(rasterio.open(p))
        m = 4 / BPD
        mos, tr = merge(srcs, bounds=(o - m, s - m, e + m, n + m), nodata=np.nan, dtype="float32")
        out = np.full((t, t), np.nan, np.float32)
        reproject(mos[0], out, src_transform=tr, src_crs="EPSG:4326", src_nodata=np.nan,
                  dst_transform=from_origin(o, n, 1 / BPD, 1 / BPD), dst_crs="EPSG:4326", dst_nodata=np.nan,
                  resampling=Resampling.bilinear)
        np.savez_compressed(os.path.join(sortie, z + ".npz"), alt=out, x0=x0, z0=z0)
        print(z, out.shape, np.nanmin(out), np.nanmax(out), flush=True)

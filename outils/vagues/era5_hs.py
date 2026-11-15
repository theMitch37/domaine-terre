"""Échantillons ERA5 de hauteur significative des vagues (Hs : vagues du vent + houle), 1991-2020, un tous les 2 jours
(heure qui tourne : 0, 6, 12, 18 h UTC), copie publique ARCO d'ERA5 (Google Cloud, sans clé ; Copernicus / ECMWF,
crédit obligatoire). Chaque échantillon est ramené à 0,5° (moyenne des cases de mer de 2 x 2) et rangé par mois de
l'année : <sortie>/<mois>.npy (float16 [n, 360, 720], ligne 0 = 90° N, colonne 0 = 0° E comme ERA5 ; NaN = terre ou banquise).

Usage : python3 outils/vagues/era5_hs.py <sortie>
"""
import concurrent.futures as cf, datetime as dt, os, sys, urllib.request
import numcodecs, numpy as np

URL = ("https://storage.googleapis.com/gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3/"
       "significant_height_of_combined_wind_waves_and_swell/{}.0.0")
T0 = dt.datetime(1900, 1, 1)
OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)
blosc = numcodecs.Blosc()


def dates():
    out, d, k = [], dt.datetime(1991, 1, 1), 0
    while d.year <= 2020:
        out.append(d + dt.timedelta(hours=6 * (k % 4)))
        d += dt.timedelta(days=2)
        k += 1
    return out


def lire(x):
    h = int((x - T0).total_seconds() // 3600)
    for essai in range(4):
        try:
            with urllib.request.urlopen(URL.format(h), timeout=60) as r:
                b = r.read()
            a = np.frombuffer(blosc.decode(b), "<f4").reshape(721, 1440)[:720].reshape(360, 2, 720, 2)
            with np.errstate(all="ignore"):
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    m = np.nanmean(a, axis=(1, 3))
            return x, m.astype(np.float16)
        except Exception as e:                    # réseau : on réessaie
            err = e
    print("manquant", x, err, flush=True)
    return x, None


par_mois = {m: [] for m in range(1, 13)}
ds = dates()
with cf.ThreadPoolExecutor(12) as ex:
    for i, (x, a) in enumerate(ex.map(lire, ds)):
        if a is not None:
            par_mois[x.month].append(a)
        if i % 500 == 0:
            print(f"{i}/{len(ds)}", flush=True)
for m, l in par_mois.items():
    np.save(os.path.join(OUT, f"{m:02d}.npy"), np.stack(l))
print("fini", sum(len(l) for l in par_mois.values()), "échantillons")

"""Réduit la carte de couverture du sol Copernicus Global Land Service LC100 (2019, 100 m) à la grille du mod
(3', 7200 x 3600), en classes IGBP (celles de MODIS MCD12C1), pour outils/carte_biomes.py.

Source : Buchhorn, M. et al. Copernicus Global Land Service: Land Cover 100m: collection 3: epoch 2019: Globe.
Zenodo, doi:10.5281/zenodo.3939050. Licence CC BY 4.0.
Fichier : PROBAV_LC100_global_v3.0.1_2019-nrt_Discrete-Classification-map_EPSG-4326.tif

Usage : python outils/couverture_sol.py <fichier LC100.tif> <sortie.png>
Sortie : PNG 8 bits, 0 = inconnu / mer, 1..17 = classe IGBP.
Hors de l'emprise de la carte (au nord de 80° N, au sud de 60° S) : neige et glace (15).
"""
import sys

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.windows import from_bounds
from PIL import Image

W, H = 7200, 3600
SOUS = 5                 # échantillons par pixel 3' dans chaque direction (25 votes)
BANDE = 10               # lignes de sortie lues à la fois

# Copernicus LC100 -> IGBP
LUT = np.zeros(256, np.uint8)
LUT[111] = 1             # forêt fermée sempervirente de conifères
LUT[112] = 2             # forêt fermée sempervirente de feuillus
LUT[113] = 3             # forêt fermée caduque de conifères (mélèzes)
LUT[114] = 4             # forêt fermée caduque de feuillus
LUT[115] = 5             # forêt fermée mixte
LUT[116] = 5             # forêt fermée, type inconnu
LUT[121:127] = 8         # forêts ouvertes -> savanes boisées
LUT[20] = 6              # fourrés (fermés : en steppe chaude ils donnent une savane, pas un désert)
LUT[30] = 10             # végétation herbacée
LUT[100] = 10            # mousses et lichens (toundra : le climat fera le reste)
LUT[40] = 12             # cultures
LUT[50] = 13             # villes
LUT[60] = 16             # sol nu ou clairsemé
LUT[70] = 15             # neige et glace
LUT[80] = 17             # eau permanente
LUT[90] = 11             # zones humides herbacées

src_path, sortie = sys.argv[1], sys.argv[2]
out = np.full((H, W), 0, np.uint8)
lat_haut = 90.0 - (np.arange(H)) * 0.05

with rasterio.open(src_path) as ds:
    b = ds.bounds
    print("source :", ds.width, "x", ds.height, "emprise", b)
    y_n = int(round((90.0 - b.top) / 0.05))
    y_s = int(round((90.0 - b.bottom) / 0.05))
    out[:y_n] = 15
    out[y_s:] = 15
    for y0 in range(y_n, y_s, BANDE):
        y1 = min(y0 + BANDE, y_s)
        haut, bas = 90.0 - y0 * 0.05, 90.0 - y1 * 0.05
        win = from_bounds(-180.0, bas, 180.0, haut, ds.transform)
        a = ds.read(1, window=win, out_shape=((y1 - y0) * SOUS, W * SOUS), resampling=Resampling.nearest,
                    boundless=True, fill_value=0)
        c = LUT[a].reshape(y1 - y0, SOUS, W, SOUS)
        comptes = np.stack([(c == k).sum(axis=(1, 3), dtype=np.int16) for k in range(18)], axis=0)
        # l'eau, les villes et l'inconnu ne gagnent que s'il n'y a rien d'autre
        terre_n = comptes[1:13].sum(0) + comptes[14:17].sum(0)
        faibles = terre_n > 0
        for k in (0, 13, 17):
            comptes[k][faibles] = -1
        out[y0:y1] = np.argmax(comptes, axis=0).astype(np.uint8)
        if (y0 - y_n) % 200 == 0:
            print(f"  {haut:6.1f}° ...", flush=True)

Image.fromarray(out).save(sortie, optimize=True)
print("OK", sortie, np.bincount(out.ravel(), minlength=18).tolist())

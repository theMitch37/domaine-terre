"""Réduit la carte Köppen-Geiger (Beck et al. 2023, 1991-2020, 1 km) à la grille du mod (3', 7200 x 3600).
Sortie : src/main/resources/domaine_terre/carte/climat.png (0 = mer, 1..30 = classe Köppen)"""
import numpy as np
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
im = Image.open("donnees/koppen_0p00833.tif")
a = np.array(im, dtype=np.uint8)            # 21600 x 43200
f = 6
b = a.reshape(3600, f, 7200, f)
# classe majoritaire par bloc 6x6 (en ignorant la mer = 0 quand il y a de la terre)
out = np.zeros((3600, 7200), np.uint8)
best = np.zeros((3600, 7200), np.int16)
for c in range(1, 31):
    n = (b == c).sum(axis=(1, 3), dtype=np.int16)
    m = n > best
    out[m] = c; best[m] = n[m]
Image.fromarray(out).save("src/main/resources/domaine_terre/carte/climat.png", optimize=True)
print("OK", np.bincount(out.ravel(), minlength=31).tolist())

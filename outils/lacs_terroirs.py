"""Donne aux lacs intérieurs le terroir et le climat de la terre la plus proche.

Sur terroirs.png, l'eau vaut 0 (= table « mer » : biomes et faune marins, plages vanilla).
Toute étendue d'eau qui ne touche pas l'océan mondial devient un lac : elle prend le terroir
(et la classe Köppen sur climat.png) du pixel de terre le plus proche, avec le bit 128 levé
(« lac de ce terroir ») : le mod y choisit des biomes de terre, jamais d'océan ni de plage.
Les mers fermées très étendues (Caspienne, mer Noire) restent des mers.

Usage : python lacs_terroirs.py <dossier carte>   (réécrit terroirs.png et climat.png)
"""
import sys
import numpy as np
from PIL import Image
from scipy import ndimage

SEUIL_MER_FERMEE = 8000   # pixels (~180 000 km²) : au-delà, une mer fermée reste une mer

dossier = sys.argv[1]
ter = np.array(Image.open(f"{dossier}/terroirs.png"))
cli = np.array(Image.open(f"{dossier}/climat.png"))
H, W = ter.shape

eau = ter == 0
lab, n = ndimage.label(eau, structure=np.ones((3, 3)))
# raccord est-ouest (la carte fait le tour du globe)
paires = set()
for y in range(H):
    a, b = lab[y, 0], lab[y, W - 1]
    if a and b and a != b:
        paires.add((min(a, b), max(a, b)))
parent = list(range(n + 1))
def racine(i):
    while parent[i] != i:
        parent[i] = parent[parent[i]]
        i = parent[i]
    return i
for a, b in paires:
    ra, rb = racine(a), racine(b)
    if ra != rb:
        parent[max(ra, rb)] = min(ra, rb)
lab = np.array([racine(i) for i in range(n + 1)])[lab]

tailles = np.bincount(lab.ravel())
tailles[0] = 0
ocean = int(np.argmax(tailles))
lacs = eau & (lab != ocean) & (tailles[lab] < SEUIL_MER_FERMEE)
print(f"{n} étendues d'eau, océan = {tailles[ocean]} px, lacs convertis = {int(lacs.sum())} px "
      f"dans {len(np.unique(lab[lacs]))} étendues")

# terre la plus proche (indices du plus proche pixel non-eau)
_, (iy, ix) = ndimage.distance_transform_edt(eau, return_indices=True)
ter2 = ter.copy()
ter2[lacs] = ter[iy[lacs], ix[lacs]] | 0x80
terre_cli = cli > 0
_, (cy, cx) = ndimage.distance_transform_edt(~terre_cli, return_indices=True)
cli2 = cli.copy()
cli2[lacs] = cli[cy[lacs], cx[lacs]]

Image.fromarray(ter2).save(f"{dossier}/terroirs.png", optimize=True)
Image.fromarray(cli2).save(f"{dossier}/climat.png", optimize=True)

def px(lon, lat):
    return int((90 - lat) / 180 * H), int((lon + 180) / 360 * W)
for nom, lon, lat in [("lac Mead", -114.45, 36.13), ("lac Supérieur", -87.5, 47.7), ("lac Victoria", 33.0, -1.0),
                      ("Baïkal", 108.0, 53.5), ("Caspienne", 51.0, 42.0), ("mer Noire", 34.0, 43.0)]:
    y, x = px(lon, lat)
    print(f"{nom:14s} terroir {ter[y, x]:2d} -> {ter2[y, x] & 0x7F:2d}{' (lac)' if ter2[y, x] & 0x80 else ''}   climat {cli[y, x]:2d} -> {cli2[y, x]:2d}")

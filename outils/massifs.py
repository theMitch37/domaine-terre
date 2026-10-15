"""Élargit les chaînes de montagnes du relief (« visuellement exact » plutôt que topographique).
Garde l'emplacement et la hauteur des sommets, mais épaissit la base des massifs.
Entrées : donnees/altitude_3min.npy, carte/cotes.png  ->  sortie : carte/relief.png
"""
import numpy as np
from PIL import Image

R = 4          # rayon d'élargissement en pixels (1 px = 3' ≈ 5,6 blocs en 1:1000)
CARTE = "src/main/resources/domaine_terre/carte/"

alt = np.load("donnees/altitude_3min.npy").astype(np.float32)
cotes = np.array(Image.open(CARTE + "cotes.png")).astype(np.float32)
terre = cotes > 128
# îles agrandies (pas de relief réel) : petit dôme qui monte doucement depuis la côte, max 250 m
dome = 1 + np.minimum((cotes - 128) / 4.0 * 15.0, 250.0)
alt = np.where(terre, np.where(alt < 1, dome, alt), np.minimum(alt, -1))

# 1) dilatation en disque (maximum local), longitude bouclée
dil = alt.copy()
for dy in range(-R, R + 1):
    for dx in range(-R, R + 1):
        if dx * dx + dy * dy > R * R:
            continue
        s = np.roll(np.roll(alt, dy, axis=0), dx, axis=1)
        np.maximum(dil, s, out=dil)

# 2) adoucissement (trois flous boîte successifs ≈ gaussien)
def flou(a, r):
    for axe in (0, 1):
        c = np.cumsum(np.pad(a, [(r + 1, r) if i == axe else (0, 0) for i in range(2)], mode="edge"), axis=axe)
        a = (np.take(c, range(2 * r + 1, c.shape[axe]), axis=axe) - np.take(c, range(0, c.shape[axe] - 2 * r - 1), axis=axe)) / (2 * r + 1)
    return a
massif = dil
for _ in range(3):
    massif = flou(massif, 2)

# 3) mélange : seulement en montagne (au-dessus de ~800 m), jamais sous le relief réel, jamais en mer
w = np.clip((massif - 800) / 1500, 0, 1)
nouveau = np.maximum(alt, alt + (massif - alt) * w)
nouveau = np.where(terre, nouveau, alt)
Image.fromarray(np.clip(np.round(nouveau) + 11000, 0, 65535).astype(np.uint16)).save(CARTE + "relief.png", optimize=True)
print("massifs élargis :", int((nouveau - alt > 50).sum()), "pixels relevés")

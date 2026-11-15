"""Climat des vagues pour Domaine Weather (méthode validée par Maxime le 15/11/2026 : « vagues par région »).

Entrée : les échantillons ERA5 de era5_hs.py (Hs, 1991-2020, 0,5°, rangés par mois).
Sortie : meteo/src/main/resources/domaine_weather/houle.bin : 24 couches de 360 x 720 octets (ligne 0 = 89,75° N,
colonne 0 = 179,75° O, centres des cases de 0,5° ; ERA5 commence à 0° E et est tourné d'un demi-tour) : couches 0-11 = Hs moyenne de janvier à décembre, couches 12-23 =
Hs « de tempête » (90e centile) de janvier à décembre. Un octet = Hs / 0,05 m (0 à 12,75 m). La mer est prolongée sur
les terres (plus proche case de mer), pour qu'une côte, un lac relié à la mer ou une case mal tombée aient une valeur.
Léger lissage (sigma 0,7 case) sur la mer seulement. Banquise (case de mer sans valeur ce mois-là) : 0.

Contrôle : relancé sur les mêmes échantillons, il redonne exactement le même fichier (md5 affiché).
Usage : python3 outils/vagues/houle_climat.py <echantillons> [--cartes <dossier>]
"""
import argparse, hashlib, os

import numpy as np
from scipy import ndimage

ICI = os.path.dirname(os.path.abspath(__file__))
SORTIE = os.path.join(ICI, "../../meteo/src/main/resources/domaine_weather/houle.bin")
PAS = 0.05                                          # mètres par unité de l'octet
MOIS = ["janv", "févr", "mars", "avr", "mai", "juin", "juil", "août", "sept", "oct", "nov", "déc"]

# points de contrôle : lat, lon, et valeur typique connue (m) en janvier / juillet, ordre de grandeur seulement
REPERES = {
    "golfe de Gascogne": (45.0, -5.0, 3.5, 1.5),
    "Atlantique nord (50 N 30 O)": (50.0, -30.0, 4.5, 2.0),
    "mer du Nord": (56.0, 3.0, 2.5, 1.2),
    "Méditerranée (golfe du Lion)": (42.0, 5.0, 1.5, 0.8),
    "Méditerranée orientale": (34.0, 25.0, 1.2, 0.9),
    "Caraïbes": (15.0, -75.0, 1.8, 1.8),
    "Pacifique tropical": (0.0, -140.0, 2.0, 2.0),
    "cap Horn / passage de Drake": (-58.0, -66.0, 4.0, 4.5),
    "Bonne-Espérance": (-36.0, 19.0, 2.8, 3.5),
    "quarantièmes (45 S 90 E)": (-45.0, 90.0, 4.0, 5.5),
    "mer d'Arabie (mousson)": (15.0, 63.0, 1.5, 3.5),
    "mer de Barents": (74.0, 35.0, 3.0, 1.5),
}


def calculer(dossier):
    moy, p90 = [], []
    for m in range(1, 13):
        a = np.load(os.path.join(dossier, f"{m:02d}.npy")).astype(np.float32)
        with np.errstate(all="ignore"):
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                moy.append(np.nanmean(a, axis=0))
                p90.append(np.nanpercentile(a, 90, axis=0))
    couches = np.stack(moy + p90)                    # [24, 360, 720]
    # ERA5 commence à 0° E : on tourne pour que la colonne 0 soit 180° O, comme la carte du mod
    couches = np.roll(couches, 360, axis=-1)
    # mer = eau libre au moins un mois ; une case de mer sans valeur un mois donné = banquise ce mois-là : pas de vagues
    mer = ~np.all(np.isnan(couches), axis=0)
    couches = np.where(np.isnan(couches) & mer[None], 0.0, couches)
    # mer prolongée sur la terre (plus proche case de mer, en tenant compte du tour du monde)
    rep = np.concatenate([mer[:, -40:], mer, mer[:, :40]], axis=1)
    _, (iy, ix) = ndimage.distance_transform_edt(~rep, return_indices=True)
    iy, ix = iy[:, 40:-40], (ix[:, 40:-40] - 40) % 720
    out = np.empty_like(couches)
    for k in range(24):
        c = couches[k][iy, ix]
        # lissage léger, puis on remet les cases de terre (copie de la mer voisine)
        cl = ndimage.gaussian_filter(np.concatenate([c[:, -8:], c, c[:, :8]], axis=1), 0.7, mode="nearest")[:, 8:-8]
        out[k] = np.where(mer, cl, c)
    q = np.clip(np.round(out / PAS), 0, 255).astype(np.uint8)
    return q, mer


def valeur(q, k, lat, lon):
    y = int((90.0 - lat) / 0.5)
    x = int((lon + 180.0) / 0.5) % 720
    return q[k, min(359, max(0, y)), x] * PAS


def cartes(q, mer, dossier):
    from PIL import Image
    os.makedirs(dossier, exist_ok=True)
    pal = np.array([[8, 29, 88], [37, 52, 148], [34, 94, 168], [29, 145, 192], [65, 182, 196], [127, 205, 187],
                    [199, 233, 180], [237, 248, 177], [254, 224, 139], [253, 174, 97], [244, 109, 67], [215, 48, 39],
                    [165, 0, 38]], np.float32)
    for k in list(range(12)):
        for nom, c in (("moyenne", q[k]), ("tempete", q[12 + k])):
            hs = c * PAS
            t = np.clip(hs / 8.0, 0, 1) * (len(pal) - 1)
            i0 = np.floor(t).astype(int)
            i1 = np.minimum(i0 + 1, len(pal) - 1)
            f = (t - i0)[..., None]
            rgb = pal[i0] * (1 - f) + pal[i1] * f
            rgb[~mer] = [70, 70, 70]
            Image.fromarray(rgb.astype(np.uint8)).resize((1440, 720), Image.NEAREST).save(
                os.path.join(dossier, f"houle_{nom}_{k + 1:02d}.png"))


def main():
    a = argparse.ArgumentParser()
    a.add_argument("echantillons")
    a.add_argument("--cartes")
    o = a.parse_args()
    q, mer = calculer(o.echantillons)
    os.makedirs(os.path.dirname(SORTIE), exist_ok=True)
    b = q.tobytes()
    open(SORTIE, "wb").write(b)
    print(f"houle.bin : {len(b)} octets, md5 {hashlib.md5(b).hexdigest()}")
    print(f"{'repère':32s} {'janv. (m)':>14s} {'juil. (m)':>14s}   tempête janv./juil.   (attendu janv./juil.)")
    for nom, (lat, lon, ej, ejl) in REPERES.items():
        print(f"{nom:32s} {valeur(q, 0, lat, lon):14.2f} {valeur(q, 6, lat, lon):14.2f}   "
              f"{valeur(q, 12, lat, lon):6.2f} / {valeur(q, 18, lat, lon):5.2f}        ({ej} / {ejl})")
    if o.cartes:
        cartes(q, mer, o.cartes)


if __name__ == "__main__":
    main()

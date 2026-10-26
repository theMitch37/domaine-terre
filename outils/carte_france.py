"""Carte vue de dessus d'une région du monde Terre (1:250), depuis la prévision Python (terre_py : relief, côtes,
fleuves, lacs au bloc près) et les tuiles sculptées : relief ombré, mer, lacs, fleuves, grille des tuiles 512 x 512,
tuiles sculptées en couleur avec le nom de leurs lieux. Pas d'arbres ni de végétation (hasard du jeu).

Usage : python3 outils/carte_france.py <sortie.png> [pas en blocs par pixel, défaut 3] [lon0 lon1 lat0 lat1]
"""
import os, sys, time
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import terre_py as T
import tuiles as tu

FRANCE = (-5.3, 9.7, 41.25, 51.2)


def couleur_terre(h):
    """Couleur selon la hauteur (y) : plaines vertes, collines, roche, neige."""
    pts = [(63, (196, 186, 140)), (65, (120, 168, 82)), (75, (104, 156, 70)), (90, (132, 160, 84)),
           (110, (150, 146, 96)), (140, (138, 120, 96)), (170, (130, 126, 122)), (200, (168, 168, 168)),
           (230, (238, 240, 244)), (320, (255, 255, 255))]
    ys = np.array([p[0] for p in pts], float); cs = np.array([p[1] for p in pts], float)
    return np.stack([np.interp(h, ys, cs[:, k]) for k in range(3)], -1)


def couleur_mer(h):
    t = np.clip((62 - h) / 40.0, 0, 1)[..., None]
    return np.array([86, 150, 210]) * (1 - t) + np.array([22, 52, 112]) * t


def calcul(lon0, lon1, lat0, lat1, pas):
    x0, x1 = int(np.floor(lon0 * T.BPD)), int(np.ceil(lon1 * T.BPD))
    z0, z1 = int(np.floor(-lat1 * T.BPD)), int(np.ceil(-lat0 * T.BPD))
    W, D = (x1 - x0) // pas, (z1 - z0) // pas
    h = np.zeros((D, W)); sd = np.zeros((D, W)); eau = np.zeros((D, W), np.int8)   # 1 mer, 2 lac, 3 fleuve
    B = 512 // pas
    t0 = time.time()
    for j0 in range(0, D, B):
        for i0 in range(0, W, B):
            j1, i1 = min(j0 + B, D), min(i0 + B, W)
            X, Z = np.meshgrid(x0 + pas * np.arange(i0, i1) + pas // 2, z0 + pas * np.arange(j0, j1) + pas // 2)
            X = X.astype(float); Z = Z.astype(float)
            s = T.distance_cote(X, Z)
            hb, _ = T.hauteur_base(X, Z)
            riv, d, hw, _, _ = T.rivieres(X, Z)
            lac, dl = T.lacs_proches(X, Z)
            h[j0:j1, i0:i1] = hb; sd[j0:j1, i0:i1] = s
            e = np.zeros(X.shape, np.int8)
            e[s < 0] = 1
            e[(s >= 0) & riv & (hb < 62.5)] = 3
            e[(lac > 0) & (dl > 0)] = 2
            eau[j0:j1, i0:i1] = e
        print(f"  lignes {j1}/{D} ({time.time() - t0:.0f} s)", flush=True)
    return x0, z0, W, D, h, sd, eau


def dessiner(sortie, lon0, lon1, lat0, lat1, pas):
    x0, z0, W, D, h, sd, eau = calcul(lon0, lon1, lat0, lat1, pas)
    # tuiles sculptées : hauteurs et classes des lieux
    haut, sommet, typ, lieu = tu.lire_zone(x0, z0, W * pas, D * pas)
    haut = haut[pas // 2::pas, pas // 2::pas][:D, :W]; typ = typ[pas // 2::pas, pas // 2::pas][:D, :W]
    sculpte = haut != tu.VIDE
    h = np.where(sculpte, haut / 16.0, h)
    eau = np.where(sculpte & (h < 62.5), 1, np.where(sculpte, 0, eau))
    cl = typ & 15
    col = couleur_terre(h)
    col = np.where((eau == 0)[..., None] & (sd >= 0)[..., None] & (sd * T.BPD / 60 < 2.5)[..., None] & (h < 66)[..., None],
                   np.array([214, 200, 150]), col)                                           # plages
    roche = sculpte & ((cl == 1) | (cl == 4) | (cl == 5)) & ((typ & 16) > 0)
    col = np.where((sculpte & np.isin(cl, [6, 10, 2]))[..., None], np.array([226, 210, 160]), col)  # dune, sable, plage
    col = np.where((sculpte & (cl == 7))[..., None], np.array([150, 150, 140]), col)               # tangue
    col = np.where(roche[..., None], np.array([225, 225, 220]), col)                               # falaises
    gz, gx = np.gradient(h * 0.6 / pas)
    ombre = np.clip(1.0 + (gx - gz) * 0.9, 0.45, 1.5)[..., None]
    col = col * ombre
    col = np.where((eau == 1)[..., None], couleur_mer(h), col)
    col = np.where((eau == 2)[..., None], np.array([70, 140, 205]), col)
    col = np.where((eau == 3)[..., None], np.array([70, 140, 205]), col)
    img = Image.fromarray(np.clip(col, 0, 255).astype(np.uint8))
    dr = ImageDraw.Draw(img, "RGBA")
    # grille des tuiles (512 blocs) : traits fins ; tuiles sculptées : cadre orange plein
    t = 512
    for tx in range(x0 // t, (x0 + W * pas) // t + 2):
        x = (tx * t - x0) / pas
        dr.line([(x, 0), (x, D)], fill=(255, 255, 255, 55), width=1)
    for tz in range(z0 // t, (z0 + D * pas) // t + 2):
        z = (tz * t - z0) / pas
        dr.line([(0, z), (W, z)], fill=(255, 255, 255, 55), width=1)
    try:
        police = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", max(12, 54 // pas))
        petite = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", max(10, 36 // pas))
    except OSError:
        police = petite = ImageFont.load_default()
    noms = {}
    for tx, tz in tu.index():
        a, b = (tx * t - x0) / pas, (tz * t - z0) / pas
        if b + t / pas < 0 or a + t / pas < 0 or a > W or b > D:
            continue
        dr.rectangle([a, b, a + t / pas, b + t / pas], outline=(255, 140, 0, 255), width=2, fill=(255, 140, 0, 40))
        for n in tu.Tuile.lire(tx, tz).lieux:
            noms.setdefault(n, []).append((a + t / pas / 2, b + t / pas / 2))
    beaux = {"etretat": "Étretat", "mont_saint_michel": "Mont-Saint-Michel", "pilat": "Dune du Pilat",
             "moher": "Moher", "douvres": "Douvres"}
    for n, pts in noms.items():
        cx = sum(p[0] for p in pts) / len(pts); cy = min(p[1] for p in pts) - 6
        texte = beaux.get(n, n)
        bb = dr.textbbox((cx, cy), texte, font=police, anchor="mb")
        dr.rectangle([bb[0] - 4, bb[1] - 2, bb[2] + 4, bb[3] + 2], fill=(255, 255, 255, 200))
        dr.text((cx, cy), texte, font=police, fill=(150, 70, 0), anchor="mb")
    legende = (f"Monde Terre 1:250 — prévision au bloc près (relief, côtes, fleuves, lacs), 1 pixel = {pas} blocs — "
               f"grille : tuiles de 512 blocs ; en orange : tuiles sculptées")
    bb = dr.textbbox((10, D - 10), legende, font=petite, anchor="ld")
    dr.rectangle([bb[0] - 6, bb[1] - 4, bb[2] + 6, bb[3] + 4], fill=(255, 255, 255, 210))
    dr.text((10, D - 10), legende, font=petite, fill=(30, 30, 30), anchor="ld")
    img.save(sortie, optimize=True)
    print("écrit", sortie, img.size, flush=True)


if __name__ == "__main__":
    a = sys.argv[1:]
    pas = int(a[1]) if len(a) > 1 else 3
    zone = tuple(map(float, a[2:6])) if len(a) >= 6 else FRANCE
    dessiner(a[0], *zone, pas)

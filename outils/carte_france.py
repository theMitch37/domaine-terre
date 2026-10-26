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


_BIOMES = None


def biome(X, Z):
    """Biome fixe de la carte du mod (biomes.png, index dans biomes.json ; 0 = aucun), lu au plus proche comme
    CarteTerre.biome (le jeu décale le point de lecture d'un bruit : les frontières y sont plus irrégulières)."""
    global _BIOMES
    if _BIOMES is None:
        from PIL import Image as I
        _BIOMES = np.array(I.open(os.path.join(T.CARTE, "biomes.png")))
    Hh, Ww = _BIOMES.shape
    lon, lat = X / T.BPD, -Z / T.BPD
    gx = np.floor((lon + 180) / 360 * Ww - 0.5 + 0.5).astype(int) % Ww
    gy = np.clip(np.floor((90 - lat) / 180 * Hh - 0.5 + 0.5).astype(int), 0, Hh - 1)
    return _BIOMES[gy, gx]


# couleurs des blocs sur les cartes du jeu (MapColor)
HERBE, FEUILLES, SABLE, PIERRE, NEIGE, EAU = (127, 178, 56), (0, 124, 0), (247, 233, 163), (112, 112, 112), (255, 255, 255), (64, 64, 255)
TERRE, PODZOL, ORANGE, CALCAIRE, GLACE, ARGILE = (151, 109, 77), (129, 86, 49), (216, 127, 51), (209, 177, 161), (160, 160, 255), (164, 168, 184)
# biome : (part d'arbres, sol, arbres enneigés)
STYLE = {"plains": (0.04, HERBE, 0), "sunflower_plains": (0.03, HERBE, 0), "forest": (0.80, HERBE, 0),
         "birch_forest": (0.78, HERBE, 0), "flower_forest": (0.65, HERBE, 0), "dark_forest": (0.95, HERBE, 0),
         "taiga": (0.80, PODZOL, 0), "old_growth_pine_taiga": (0.88, PODZOL, 0), "old_growth_spruce_taiga": (0.88, PODZOL, 0),
         "snowy_taiga": (0.60, NEIGE, 1), "snowy_plains": (0.02, NEIGE, 1), "grove": (0.55, NEIGE, 1), "meadow": (0.03, HERBE, 0),
         "cherry_grove": (0.55, HERBE, 0), "windswept_hills": (0.12, HERBE, 0), "windswept_forest": (0.55, HERBE, 0),
         "snowy_slopes": (0.0, NEIGE, 1), "frozen_peaks": (0.0, GLACE, 1), "jagged_peaks": (0.0, NEIGE, 1),
         "stony_peaks": (0.0, PIERRE, 0), "desert": (0.0, SABLE, 0), "badlands": (0.0, ORANGE, 0),
         "wooded_badlands": (0.30, ORANGE, 0), "eroded_badlands": (0.0, ORANGE, 0), "savanna": (0.12, HERBE, 0),
         "savanna_plateau": (0.12, HERBE, 0), "windswept_savanna": (0.10, HERBE, 0), "jungle": (0.95, HERBE, 0),
         "sparse_jungle": (0.55, HERBE, 0), "bamboo_jungle": (0.95, HERBE, 0), "swamp": (0.55, HERBE, 0),
         "mangrove_swamp": (0.80, HERBE, 0)}


def hasard(X, Z, graine):
    v = (X.astype(np.int64) * 73856093) ^ (Z.astype(np.int64) * 19349663) ^ (graine * 83492791)
    return ((v * 2654435761) & 0xFFFFFF) / float(0xFFFFFF)


def style_minecraft(h, eau, niv, bio, sd, X, Z, sculpte, typ, pas):
    """Couleurs façon carte Minecraft : un bloc par pixel (le dessus de la colonne), ombre selon le voisin au nord
    (plus haut 255, pareil 220, plus bas 180), eau en damier selon la profondeur."""
    import json
    noms = json.load(open(os.path.join(T.CARTE, "biomes.json")))
    D, W = h.shape
    part = np.zeros((D, W)); sol = np.zeros((D, W, 3)); neige = np.zeros((D, W), bool)
    sol[:] = HERBE
    for i, n in enumerate(noms):
        if n in STYLE:
            m = bio == i + 1                                             # 0 = aucun, k = k-ième de biomes.json
            a, c, sn = STYLE[n]
            part[m] = a; sol[m] = c; neige[m] = sn
    # hauteur : roche puis neige en haute montagne, pas d'arbres au-dessus de la limite des arbres
    haut = h >= 175
    sol = np.where((h >= 150)[..., None] & ~neige[..., None], np.array(PIERRE), sol)
    sol = np.where(haut[..., None], np.array(NEIGE), sol)
    part = np.where(h >= 150, part * np.clip((175 - h) / 25, 0, 1), part)
    plage = (sd >= 0) & (sd * T.BPD / 60 < 3) & (h < 66)
    sol = np.where(plage[..., None], np.array(SABLE), sol)
    part = np.where(plage, 0, part)
    arbre = hasard(X, Z, 7) < part
    col = np.where(arbre[..., None], np.where(neige[..., None], np.array(NEIGE), np.array(FEUILLES)), sol)
    # lieux sculptés
    cl = typ & 15
    col = np.where((sculpte & np.isin(cl, [2, 6, 10]))[..., None], np.array(SABLE), col)
    col = np.where((sculpte & (cl == 7))[..., None], np.array(ARGILE), col)
    gz, gx = np.gradient(h / pas)
    falaise = sculpte & ((typ & 16) > 0) & np.isin(cl, [1, 3, 4, 5]) & (np.hypot(gx, gz) > 2.0)
    col = np.where(falaise[..., None], np.array(CALCAIRE), col)
    # relief : comme la carte du jeu, comparé au voisin du nord (en blocs de hauteur, un pixel = pas blocs)
    hb = np.floor(h)
    nord = np.vstack([hb[:1], hb[:-1]])
    f = np.where(hb > nord, 1.0, np.where(hb == nord, 220 / 255, 180 / 255))
    col = col * f[..., None]
    # eau : profondeur en damier (MapColor de l'eau)
    dans = eau > 0
    prof = np.maximum(niv - hb, 0)
    v = prof * 0.1 + ((np.arange(W)[None, :] + np.arange(D)[:, None]) & 1) * 0.2
    fe = np.where(v < 0.5, 1.0, np.where(v > 0.9, 180 / 255, 220 / 255))
    col = np.where(dans[..., None], np.array(EAU) * fe[..., None], col)
    return col


def calcul(lon0, lon1, lat0, lat1, pas):
    x0, x1 = int(np.floor(lon0 * T.BPD)), int(np.ceil(lon1 * T.BPD))
    z0, z1 = int(np.floor(-lat1 * T.BPD)), int(np.ceil(-lat0 * T.BPD))
    W, D = (x1 - x0) // pas, (z1 - z0) // pas
    h = np.zeros((D, W)); sd = np.zeros((D, W)); eau = np.zeros((D, W), np.int8)   # 1 mer, 2 lac, 3 fleuve
    niv = np.full((D, W), 62.0); bio = np.zeros((D, W), np.int16)
    B = 512 // pas
    t0 = time.time()
    for j0 in range(0, D, B):
        for i0 in range(0, W, B):
            j1, i1 = min(j0 + B, D), min(i0 + B, W)
            X, Z = np.meshgrid(x0 + pas * np.arange(i0, i1) + pas // 2, z0 + pas * np.arange(j0, j1) + pas // 2)
            X = X.astype(float); Z = Z.astype(float)
            s = T.distance_cote(X, Z)
            hb, _ = T.hauteur_base(X, Z)
            riv, d, hw, _, _, weau = T.rivieres(X, Z)
            lac, dl = T.lacs_proches(X, Z)
            h[j0:j1, i0:i1] = hb; sd[j0:j1, i0:i1] = s
            e = np.zeros(X.shape, np.int8)
            e[s < 0] = 1
            e[(s >= 0) & riv & (hb < weau - 0.5)] = 3                    # lit sous le niveau du cours d'eau
            e[(lac > 0) & (dl > 0)] = 2
            eau[j0:j1, i0:i1] = e
            c = T._carte_lacs()
            if c:
                nl = np.minimum(T.niveau_lac(c["alt"][lac]), c["plafond"][lac]) - 1
                niv[j0:j1, i0:i1] = np.where(e == 2, nl, np.where(e == 3, weau - 1, 62))
            bio[j0:j1, i0:i1] = biome(X, Z)
        print(f"  lignes {j1}/{D} ({time.time() - t0:.0f} s)", flush=True)
    return x0, z0, W, D, h, sd, eau, niv, bio


def dessiner(sortie, lon0, lon1, lat0, lat1, pas):
    x0, z0, W, D, h, sd, eau, niv, bio = calcul(lon0, lon1, lat0, lat1, pas)
    # tuiles sculptées : hauteurs et classes des lieux
    haut, sommet, typ, lieu = tu.lire_zone(x0, z0, W * pas, D * pas)
    haut = haut[pas // 2::pas, pas // 2::pas][:D, :W]; typ = typ[pas // 2::pas, pas // 2::pas][:D, :W]
    sculpte = haut != tu.VIDE
    h = np.where(sculpte, haut / 16.0, h)
    eau = np.where(sculpte & (h < 62.5), 1, np.where(sculpte, 0, eau))
    Xp, Zp = np.meshgrid(x0 + pas * np.arange(W) + pas // 2, z0 + pas * np.arange(D) + pas // 2)
    niv = np.where(sculpte & (eau == 1), 62, niv)
    col = style_minecraft(h, eau, niv, bio, sd, Xp, Zp, sculpte, typ, pas)
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
        police = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18 if pas >= 2 else 14)
        petite = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12 if pas >= 2 else 9)
    except OSError:
        police = petite = ImageFont.load_default()
    noms = {}
    for tx, tz in tu.index():
        a, b = (tx * t - x0) / pas, (tz * t - z0) / pas
        if b + t / pas < 0 or a + t / pas < 0 or a > W or b > D:
            continue
        dr.rectangle([a, b, a + t / pas, b + t / pas], outline=(255, 140, 0, 255), width=2)
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

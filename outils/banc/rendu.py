"""Rendu isométrique des VRAIS blocs générés par le banc d'essai (outils/banc/serveur.py).

Usage : python3 outils/banc/rendu.py <lieu.npz> <image.png> [px_par_bloc] [--nord] [--carte] [x0 x1 z0 z1]
Couleurs approchées par bloc (pas de textures ni de lumière). Vue depuis le sud-est, ou le nord-ouest avec --nord.
--carte : vue du dessus ombrée (contrôle du plan seulement : une forme se juge en perspective).
"""
import sys, zlib
import numpy as np
from PIL import Image, ImageDraw

COUL = {
    "air": None, "cave_air": None, "void_air": None,
    "water": (54, 96, 196), "lava": (220, 100, 20), "ice": (150, 180, 240),
    "stone": (125, 125, 125), "cobblestone": (120, 120, 120), "mossy_cobblestone": (100, 120, 90),
    "granite": (149, 103, 85), "diorite": (188, 188, 188), "andesite": (136, 136, 137), "tuff": (108, 109, 102),
    "calcite": (223, 224, 220), "deepslate": (80, 80, 84), "cobbled_deepslate": (77, 77, 80), "dripstone_block": (134, 107, 92),
    "grass_block": (106, 150, 66), "dirt": (134, 96, 67), "coarse_dirt": (119, 85, 59), "podzol": (91, 63, 24),
    "rooted_dirt": (144, 103, 76), "mud": (60, 57, 61), "packed_mud": (142, 106, 79), "clay": (160, 166, 179),
    "gravel": (131, 127, 126), "sand": (219, 207, 163), "red_sand": (190, 102, 33), "sandstone": (216, 203, 155),
    "smooth_sandstone": (223, 214, 170), "terracotta": (152, 94, 67), "white_terracotta": (210, 178, 161),
    "red_terracotta": (143, 61, 46), "orange_terracotta": (161, 83, 37), "light_gray_terracotta": (135, 107, 98),
    "brown_terracotta": (77, 51, 35), "snow": (240, 250, 250), "snow_block": (240, 250, 250), "powder_snow": (245, 250, 250),
    "moss_block": (89, 109, 45), "oak_log": (109, 85, 50), "spruce_log": (58, 37, 16), "birch_log": (216, 215, 210),
    "dark_oak_log": (60, 46, 26), "oak_leaves": (60, 110, 40), "spruce_leaves": (45, 80, 50), "birch_leaves": (90, 130, 60),
    "dark_oak_leaves": (50, 90, 30), "jungle_leaves": (50, 120, 30), "acacia_leaves": (80, 120, 40), "azalea_leaves": (90, 120, 50),
    "coal_ore": (100, 100, 100), "iron_ore": (140, 125, 115), "copper_ore": (125, 120, 105), "magma_block": (140, 60, 20),
    "obsidian": (20, 18, 30), "bedrock": (60, 60, 60), "netherrack": (100, 40, 40),
}
FLUIDE = {"water", "bubble_column", "seagrass", "tall_seagrass", "kelp", "kelp_plant"}
PLANTES = ("grass", "tall_grass", "fern", "large_fern", "dandelion", "poppy", "flower", "tulip", "daisy", "orchid",
           "allium", "bluet", "cornflower", "lily", "dead_bush", "sugar_cane", "sweet_berry", "mushroom", "vine",
           "glow_lichen", "pumpkin", "melon", "torch", "carpet", "petals", "sapling", "bush", "lichen", "rail", "wheat",
           "carrots", "potatoes", "beetroots", "hanging_roots", "moss_carpet", "pointed_dripstone", "button", "pressure_plate")


def couleur(nom):
    c = nom.split(":")[-1]
    if c in COUL: return COUL[c]
    if c in FLUIDE: return COUL["water"]
    if c.endswith("_leaves"): return (60, 110, 40)
    if c.endswith("_log") or c.endswith("_wood"): return (100, 75, 45)
    if "planks" in c or "fence" in c or "stairs" in c or "slab" in c or "door" in c: return (160, 120, 75)
    h = zlib.crc32(c.encode())
    return (110 + h % 90, 100 + (h >> 8) % 90, 100 + (h >> 16) % 90)          # bloc inconnu : couleur stable


def classes(noms):
    """0 = vide (air, plantes), 1 = eau, 2 = solide."""
    k = np.zeros(len(noms), np.uint8)
    for i, n in enumerate(noms):
        c = n.split(":")[-1]
        if c in ("air", "cave_air", "void_air") or any(p in c for p in PLANTES): k[i] = 0
        elif c in FLUIDE: k[i] = 1
        else: k[i] = 2
    return k


def rendu(npz, out, K=3, nord=False, carte=False, fenetre=None):
    d = np.load(npz)
    noms = [str(n) for n in d["noms"]]; B = d["blocs"]; x0, y0, z0 = int(d["x0"]), int(d["y0"]), int(d["z0"])
    if fenetre:
        a, b, c, e = fenetre
        B = B[c - z0:e - z0, :, a - x0:b - x0]; x0, z0 = a, c
    if nord:
        B = B[::-1, :, ::-1]
    kl = classes(noms)[B]                                      # [z, y, x]
    cols = np.array([couleur(n) or (0, 0, 0) for n in noms], float)
    D, H, W = B.shape
    solide = kl == 2
    vide = ~solide
    if carte:
        top = np.zeros((D, W), int); col = np.zeros((D, W, 3))
        for y in range(H):
            m = kl[:, y, :] > 0
            top[m] = y; col[m] = cols[B[:, y, :][m]]
        gz, gx = np.gradient(top.astype(float))
        o = np.clip(1 + (gx - gz) * 0.12, 0.4, 1.4)[..., None]
        Image.fromarray(np.clip(col * o, 0, 255).astype(np.uint8)).resize((W * K, D * K), Image.NEAREST).save(out)
        print("écrit", out); return
    haut_solide = np.zeros_like(solide); haut_solide[:, :-1, :] = vide[:, 1:, :]
    sud = np.zeros_like(solide); sud[:-1] = vide[1:]; sud[-1] = True
    est = np.zeros_like(solide); est[:, :, :-1] = vide[:, :, 1:]; est[:, :, -1] = True
    eau_surface = (kl == 1) & np.concatenate([kl[:, 1:, :] == 0, np.ones((D, 1, W), bool)], axis=1)
    ymin = int(np.argmax((solide | (kl == 1)).any(axis=(0, 2)))); ymax = H - 1 - int(np.argmax((kl > 0).any(axis=(0, 2))[::-1]))
    sx = lambda i, j: (i - j + D) * K
    sy = lambda i, j, y: (i + j) * K / 2 + (ymax + 2 - y) * K
    img = Image.new("RGB", (int((W + D) * K) + 2, int((W + D) * K / 2 + (ymax - ymin + 6) * K) + 2), (165, 200, 235))
    dr = ImageDraw.Draw(img)
    vis = solide & (haut_solide | sud | est) | eau_surface
    vis[:, :max(ymin - 1, 0), :] = False
    zz, yy, xx = np.nonzero(vis)
    ordre = np.lexsort((yy, xx + zz))
    for n in ordre:
        j, y, i = zz[n], yy[n], xx[n]
        c = cols[B[j, y, i]]
        f = lambda k: tuple(int(v) for v in np.clip(c * k, 0, 255))
        if kl[j, y, i] == 1:
            dr.polygon([(sx(i, j), sy(i, j, y)), (sx(i + 1, j), sy(i + 1, j, y)), (sx(i + 1, j + 1), sy(i + 1, j + 1, y)),
                        (sx(i, j + 1), sy(i, j + 1, y))], fill=f(1.0))
            continue
        if sud[j, y, i]:
            dr.polygon([(sx(i, j + 1), sy(i, j + 1, y)), (sx(i + 1, j + 1), sy(i + 1, j + 1, y)),
                        (sx(i + 1, j + 1), sy(i + 1, j + 1, y - 1)), (sx(i, j + 1), sy(i, j + 1, y - 1))], fill=f(0.62))
        if est[j, y, i]:
            dr.polygon([(sx(i + 1, j), sy(i + 1, j, y)), (sx(i + 1, j + 1), sy(i + 1, j + 1, y)),
                        (sx(i + 1, j + 1), sy(i + 1, j + 1, y - 1)), (sx(i + 1, j), sy(i + 1, j, y - 1))], fill=f(0.80))
        if haut_solide[j, y, i]:
            dr.polygon([(sx(i, j), sy(i, j, y)), (sx(i + 1, j), sy(i + 1, j, y)), (sx(i + 1, j + 1), sy(i + 1, j + 1, y)),
                        (sx(i, j + 1), sy(i, j + 1, y))], fill=f(1.0))
    img.save(out)
    print("écrit", out, img.size)


if __name__ == "__main__":
    a = [v for v in sys.argv[1:] if not v.startswith("--")]
    fen = list(map(int, a[3:7])) if len(a) >= 7 else None
    rendu(a[0], a[1], int(a[2]) if len(a) > 2 else 3, "--nord" in sys.argv, "--carte" in sys.argv, fen)

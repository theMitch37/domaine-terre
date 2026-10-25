"""Rendu isométrique de contrôle d'un lieu en grille (lieux_cotiers.py) : relit les mêmes données que le jeu.

Le relief est exact (hors grottes, arbres, minerais) ; les couleurs suivent les palettes de LieuGrille.java (approchées).
Usage : python3 outils/rendu_grille.py <lieu> <sortie.png> [pixels_par_bloc] [--nord] [x0 x1 z0 z1]
"""
import sys
import numpy as np
from PIL import Image, ImageDraw

COUL = {"calcite": (223, 224, 220), "diorite": (188, 188, 188), "tuff": (108, 109, 102), "gravel": (131, 127, 126),
        "grass": (110, 150, 70), "dirt": (134, 96, 67), "stone": (125, 125, 125), "water": (55, 95, 190),
        "deepslate": (80, 80, 84), "packed_mud": (142, 106, 79), "cobbled_deepslate": (77, 77, 80),
        "sand": (219, 207, 163), "sandstone": (216, 203, 155), "mud": (60, 57, 61), "granite": (149, 103, 85)}
PALETTE = {"etretat": "craie", "douvres": "craie_pure", "moher": "moher", "pilat": "dune", "mont_saint_michel": "baie"}
PLATEAU, PLAGE, FOND, ROC, AIGUILLE, DUNE, VASE, CHENAL, PRE = 1, 2, 3, 4, 5, 6, 7, 8, 9


def h2(x, z, s=0):
    return ((x * 73856093) ^ (z * 19349663) ^ (s * 83492791)) & 1023


def bloc(pal, cl, x, y, z, top, dessus):
    """Copie (approchée pour les taches) de LieuGrille.strate / dessus."""
    if cl == 0:
        return "grass" if dessus else ("dirt" if y >= top - 3 else "stone")
    if pal in ("craie", "craie_pure"):
        if cl in (PLAGE, FOND): return "gravel"
        if cl == PLATEAU and dessus: return "grass"
        if cl == PLATEAU and y >= top - 2: return "dirt"
        pas = 5 if pal == "craie" else 8
        if (y - 63) % pas == 0 and h2(x, z, y) % 7: return "tuff"
        return "diorite" if h2(x // 3, z // 3, y // 4) % 5 == 0 else "calcite"
    if pal == "moher":
        if cl in (PLAGE, FOND): return "stone"
        if cl == PLATEAU and dessus: return "grass"
        if cl == PLATEAU and y >= top - 2: return "dirt"
        return ["deepslate", "deepslate", "tuff", "packed_mud", "tuff", "cobbled_deepslate"][(y // 2) % 6]
    if pal == "dune":
        return "sand" if y >= top - 6 else "sandstone"
    if pal == "baie":
        if cl == ROC: return "grass" if (dessus and h2(x, z) % 3 == 0) else ("granite" if h2(x // 2, z // 2, y // 3) % 3 else "stone")
        if cl == PRE: return "grass" if dessus else "dirt"
        if cl == VASE and dessus: return "mud"
        return "sand" if y >= 58 else "stone"
    return "stone"


def rendu(nom, out, K=4, nord=False, fenetre=None):
    d = np.load(f"/tmp/lieu_{nom}.npz")
    X, Z, y, typ, sommet, vox = d["X"], d["Z"], d["y"], d["typ"], d["sommet"], d["vox"]
    Y = np.floor(y).astype(int)
    if fenetre:
        x0, x1, z0, z1 = fenetre
        sel = (slice(z0 - int(Z[0, 0]), z1 - int(Z[0, 0])), slice(x0 - int(X[0, 0]), x1 - int(X[0, 0])))
        X, Z, Y, typ, sommet = X[sel], Z[sel], Y[sel], typ[sel], sommet[sel]
    cl = typ & 15
    pal = PALETTE[nom]
    solide = {}
    for (vx, vy, vz, c) in vox:
        solide[(vx, vz)] = solide.get((vx, vz), []) + [(vy, c)]
    if nord:
        X, Z, Y, cl, sommet = (a[::-1, ::-1] for a in (X, Z, Y, cl, sommet))
    Hh, Ww = Y.shape
    ymin, ymax = int(Y.min()) - 2, max(int(Y.max()), max([v[1] for v in vox], default=0)) + 2
    sx = lambda i, j: (i - j + Hh) * K
    sy = lambda i, j, yy: (i + j) * K / 2 + (ymax - yy) * K
    img = Image.new("RGB", (int((Ww + Hh) * K) + 2, int((Ww + Hh) * K / 2 + (ymax - ymin) * K) + 2), (165, 200, 235))
    dr = ImageDraw.Draw(img)
    Yp = np.pad(Y, ((0, 1), (0, 1)), constant_values=ymin)

    def cube(i, j, yy, nom_bloc, faces=(True, True, True)):
        c = np.array(COUL[nom_bloc], float)
        f = lambda k: tuple(int(v) for v in np.clip(c * k, 0, 255))
        if faces[0]:
            dr.polygon([(sx(i, j + 1), sy(i, j + 1, yy)), (sx(i + 1, j + 1), sy(i + 1, j + 1, yy)),
                        (sx(i + 1, j + 1), sy(i + 1, j + 1, yy - 1)), (sx(i, j + 1), sy(i, j + 1, yy - 1))], fill=f(0.62))
        if faces[1]:
            dr.polygon([(sx(i + 1, j), sy(i + 1, j, yy)), (sx(i + 1, j + 1), sy(i + 1, j + 1, yy)),
                        (sx(i + 1, j + 1), sy(i + 1, j + 1, yy - 1)), (sx(i + 1, j), sy(i + 1, j, yy - 1))], fill=f(0.80))
        if faces[2]:
            dr.polygon([(sx(i, j), sy(i, j, yy)), (sx(i + 1, j), sy(i + 1, j, yy)), (sx(i + 1, j + 1), sy(i + 1, j + 1, yy)),
                        (sx(i, j + 1), sy(i, j + 1, yy))], fill=f(1.0))

    for _, i, j in sorted(((i + j), i, j) for j in range(Hh) for i in range(Ww)):
        yy0 = Y[j, i]; x, z = int(X[j, i]), int(Z[j, i]); c = cl[j, i]; top = sommet[j, i]
        yn = min(Yp[j + 1, i], Yp[j, i + 1])
        for yy in range(max(yn + 1, ymin), yy0 + 1):
            cube(i, j, yy, bloc(pal, c, x, yy, z, top, yy == yy0), (True, True, False))
        if yy0 < 62:
            cube(i, j, 62, "water", (False, False, True))
        else:
            cube(i, j, yy0, bloc(pal, c, x, yy0, z, top, True), (False, False, True))
        for (vy, vc) in sorted(solide.get((x, z), [])):
            if vy > yy0:
                cube(i, j, vy, bloc(pal, vc, x, vy, z, 999, False))
    img.save(out)
    print("écrit", out)


if __name__ == "__main__":
    a = [v for v in sys.argv[1:] if not v.startswith("--")]
    fen = list(map(int, a[3:7])) if len(a) >= 7 else None
    rendu(a[0], a[1], int(a[2]) if len(a) > 2 else 4, "--nord" in sys.argv, fen)

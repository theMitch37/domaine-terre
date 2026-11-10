"""Rendu en perspective des gorges du Verdon (copie Python de Verdon.java : à garder synchronisée).

Approximation : le terrain du mod est relu dans relief.png (bicubique) avec un bruit approché ;
pas de végétation, de grottes ni d'éclairage. Vue depuis le sud (ou le nord avec --nord), en hauteur.
Usage : python3 outils/rendu_verdon.py <x0> <x1> <z0> <z1> <sortie.png> [pixels_par_bloc] [--nord]
        (coordonnées de blocs en 1:250 ; toute la gorge : 2770 2870 -19500 -19440)
"""
import gzip, os, struct, sys
import numpy as np
from PIL import Image
from scipy import ndimage

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BPD = 445.28
raw = gzip.open("lieux/src/main/resources/domaine_terre_lieux/verdon.bin").read()
lon0, lat0, pl, pa, W, H = struct.unpack("<4d2i", raw[:40]); n = W * H
G = [np.frombuffer(raw[40 + 2 * n * i:40 + 2 * n * (i + 1)], "<i2").reshape(H, W).astype(float) for i in range(6)]
REL = np.array(Image.open("src/main/resources/domaine_terre/carte/relief.png"), dtype=np.float64) - 11000

# ---- constantes (identiques à Verdon.java)
FOND, PIED = 57.0, 62.5
W_V, W_A = 13.0, 8.0
FONDU = 0.03
NIV_LAC = 473.0           # lac de Sainte-Croix (m)
BASSIN = 30.0             # rayon (blocs) de la cuvette du lac
PROFIL_T = [1.00, 1.00, 0.74, 0.62, 0.54, 0.54, 0.30, 0.0]   # falaises : marches verticales (t répété)
PROFIL_G = [0.00, 0.50, 0.62, 0.66, 0.66, 0.95, 1.00, 1.0]

def lis(t):
    t = np.clip(t, 0, 1); return t * t * (3 - 2 * t)
def blocs(a):
    import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from terre_py import blocs as b      # même courbe que le mod (10/11/2026)
    return b(a)
def bruit(X, Z, ech, graine):
    r = np.random.default_rng(graine); g = r.standard_normal((64, 64))
    g = ndimage.gaussian_filter(g, 1.0, mode="wrap"); g /= g.std()
    return ndimage.map_coordinates(g, [(Z / ech) % 64, (X / ech) % 64], order=3, mode="grid-wrap") * 0.5
def profil(t):
    """Comme Verdon.profil : le premier segment qui contient t l'emporte."""
    g = np.ones_like(t)
    for i in reversed(range(len(PROFIL_T) - 1)):
        t0, t1 = PROFIL_T[i], PROFIL_T[i + 1]
        if t0 == t1: continue
        m = (t <= t0) & (t >= t1)
        g = np.where(m, PROFIL_G[i] + (PROFIL_G[i + 1] - PROFIL_G[i]) * (t0 - t) / (t0 - t1), g)
    return g

def modele(X, Z):
    lon = X / BPD; lat = -Z / BPD
    fx = (lon - lon0) / pl - .5; fy = (lat0 - lat) / pa - .5
    s = lambda g: ndimage.map_coordinates(g, [fy, fx], order=1, mode="nearest")
    e, p, D, S, A, L = (s(g) for g in G)
    # terrain du mod : relief.png à 3' (bicubique) + détail
    gx = (lon + 180) * 20 - .5; gy = (90 - lat) * 20 - .5
    alt = ndimage.map_coordinates(REL, [gy, gx], order=3)
    h = blocs(np.maximum(alt, 1)) + bruit(X, Z, 48, 11) * 2.0 + bruit(X, Z, 13, 12) * 0.6
    dv = D * 1e-5 * BPD; da = A * 1e-5 * BPD; lb = L * 1e-5 * BPD; sb = S * 1e-4 * BPD
    reb = blocs(p)
    inten = 1 - lis((sb - 118) / 30)
    pres_v = 1 - lis((sb - 140) / 40)
    inten_a = lis((lat - 43.712) / 0.012)
    pres_a = lis((lat - 43.700) / 0.010)

    def branche(dist, w0, inten, pres, graine):
        vv = 1 - lis(inten / 0.6)
        w = w0 * (np.maximum(inten, 0.7) + 1.6 * vv)   # la vallée en V s'élargit (sinon des lames)
        plancher = np.minimum(4.0, w * 0.3)
        # bruit à grande échelle seulement : les parois sont presque verticales, un bruit fin y ferait des aiguilles
        d = dist + bruit(X, Z, w0 * 0.8, graine) * w * 0.20 + bruit(X, Z, 25, graine + 1) * w * 0.12
        d = np.where(dist < plancher, dist, np.maximum(d, plancher))
        t = d / w
        g = profil(np.clip(t, 0, 1))
        g = g + (np.clip((1 - t) / 0.85, 0, 1) - g) * vv
        k = lis((t - 0.80) / 0.15)
        plafond = h + (1 - k) * np.clip(reb - h, 0, 12)
        y = np.where(t <= 1, np.minimum(plafond, reb - g * (reb - PIED)), h)
        lit = 1 - lis((dist - 2.4) / 1.2)
        y = y + (FOND - y) * lit
        return h + (y - h) * pres, t, pres
    yv, tv, pv = branche(dv, W_V, inten, pres_v, 1)
    ya, ta, pa_ = branche(da, W_A, inten_a, pres_a, 3)
    y = np.minimum(yv, ya)
    # lac de Sainte-Croix
    # le lac est au niveau de la mer (y 62) au lieu de sa vraie hauteur (y ~79) : la cuvette autour reprend le
    # relief réel abaissé d'autant, puis rejoint le terrain du mod
    fond_lac = 62 - np.minimum(7, 1.5 + (-lb) * 0.6)
    cuvette = np.maximum(blocs(e) - (blocs(NIV_LAC) - 63.5), 63.5)
    rive = cuvette + (h - cuvette) * lis(lb / BASSIN)
    ylac = np.minimum(np.where(lb < 0, fond_lac, rive), h)
    y = np.minimum(y, ylac)
    bord = np.minimum(np.minimum(lon - lon0, lon0 + W * pl - lon), np.minimum(lat0 - lat, lat - (lat0 - H * pa)))
    f = lis(bord / FONDU)
    y = h + (y - h) * f
    gorge = ((tv < 1.1) & (pv > 0.3)) | ((ta < 1.1) & (pa_ > 0.3))    # dansGorge (colonnes recolorées)
    taillee = gorge & (np.minimum(tv, ta) <= 1.0) & (y < h - 0.5)    # approx. de hauteurNette non NaN
    return y, gorge, reb, h, taillee

def bruit3(x, y, z, graine):
    """Bruit lisse 3D approché (remplace ImprovedNoise pour le rendu)."""
    r = np.random.default_rng(graine); g = r.standard_normal((32, 32, 32))
    g = ndimage.gaussian_filter(g, 1.0, mode="wrap"); g /= g.std()
    return ndimage.map_coordinates(g, [np.atleast_1d(z) % 32, np.atleast_1d(y) % 32, np.atleast_1d(x) % 32],
                                   order=1, mode="grid-wrap") * 0.5

# couleurs approchées des blocs
COUL = {"calcite": (223, 224, 220), "diorite": (188, 188, 188), "andesite": (136, 136, 137), "tuff": (108, 109, 102),
        "white_terracotta": (210, 178, 161), "stone": (125, 125, 125), "gravel": (131, 127, 126), "grass": (110, 150, 70),
        "dirt": (134, 96, 67), "water": (60, 190, 175)}

def bloc(x, y, z, reb):
    """Copie de Verdon.strate : nom du bloc à (x, y, z) sous un rebord à y = reb."""
    if y <= 61:
        return "gravel" if y >= 57 else "stone"
    f = np.clip((reb - y) / (reb - PIED), 0, 1)
    n = bruit3(x / 2.5, y / 14.0, z / 2.5, 21)[0]          # coulures : étirées à la verticale
    m = bruit3(x / 9.0, y / 6.0, z / 9.0, 22)[0]            # taches de diorite
    if 0.50 <= f < 0.70:
        base = "stone" if m > 0.1 else "andesite"
    elif f >= 0.70:
        base = "diorite" if m > -0.1 else "stone"
    else:
        base = "calcite" if m < 0.2 else "diorite"
    if n > 0.42: return "white_terracotta"
    if n < -0.52: return "andesite" if f < 0.5 else "tuff"
    return base

def sommet(x, y, z, reb):
    """Copie de Verdon.sommet : les vires (pentes douces) sont herbeuses."""
    f = np.clip((reb - y) / (reb - PIED), 0, 1)
    if 0.50 <= f < 0.72 and y > 63: return "grass"
    return bloc(x, y, z, reb)

def rendu_iso(Y, gorge, reb, h, taillee, x0, z0, out, K=4, nord=False):
    """Vue isométrique depuis le sud-est : chaque bloc visible est dessiné (dessus + faces sud et est)."""
    from PIL import ImageDraw
    Hh, Ww = Y.shape
    if nord:     # vue depuis le nord-ouest : on tourne la zone de 180°
        Y, gorge, reb, h, taillee = (a[::-1, ::-1] for a in (Y, gorge, reb, h, taillee))
    vx = (lambda i: x0 + Ww - 1 - i) if nord else (lambda i: x0 + i)
    vz = (lambda j: z0 + Hh - 1 - j) if nord else (lambda j: z0 + j)
    ymin, ymax = int(Y.min()) - 2, int(Y.max()) + 2
    sx = lambda i, j: (i - j + Hh) * K
    sy = lambda i, j, y: (i + j) * K / 2 + (ymax - y) * K
    img = Image.new("RGB", (int((Ww + Hh) * K) + 2, int((Ww + Hh) * K / 2 + (ymax - ymin) * K) + 2), (165, 200, 235))
    d = ImageDraw.Draw(img)
    Yp = np.pad(Y, ((0, 1), (0, 1)), mode="constant", constant_values=ymin)
    ordre = sorted(((i + (Hh - 1 - j)), i, j) for j in range(Hh) for i in range(Ww))
    # dessin du fond vers l'avant : du nord-ouest au sud-est (i = x croissant, j = z croissant)
    for j in range(Hh):
        for i in range(Ww):
            pass
    cases = sorted(((i + j), i, j) for j in range(Hh) for i in range(Ww))
    def col(i, j, x, yy, z, y):
        sol = ("grass" if yy == y else "dirt") if yy >= y - 3 else "stone"
        if not gorge[j, i]: return sol
        # terre gardée : 2 blocs sous le rebord, ou dessus d'une colonne non taillée (Verdon.garderSol)
        if yy >= y - 3 and (yy >= reb[j, i] - 2 or not taillee[j, i]): return sol
        return sommet(x, yy, z, reb[j, i]) if yy == y else bloc(x, yy, z, reb[j, i])
    def coul(nom, k):
        c = np.array(COUL[nom]) * k; return tuple(int(v) for v in np.clip(c, 0, 255))
    for _, i, j in cases:
        y = int(Y[j, i]); x, z = vx(i), vz(j)
        gz = gorge[j, i]
        # faces sud (vers j+1) et est (vers i+1), du sol des voisins jusqu'au sommet
        for (di, dj, k) in ((0, 1, 0.62), (1, 0, 0.80)):
            yn = int(Yp[j + dj, i + di]) if (j + dj < Hh and i + di < Ww) else ymin
            for yy in range(max(yn + 1, ymin), y + 1):
                nom = col(i, j, x, yy, z, y)
                if dj:   # face sud : parallélogramme entre (i,j+1)-(i+1,j+1)
                    pts = [(sx(i, j + 1), sy(i, j + 1, yy)), (sx(i + 1, j + 1), sy(i + 1, j + 1, yy)),
                           (sx(i + 1, j + 1), sy(i + 1, j + 1, yy - 1)), (sx(i, j + 1), sy(i, j + 1, yy - 1))]
                else:    # face est : entre (i+1,j)-(i+1,j+1)
                    pts = [(sx(i + 1, j), sy(i + 1, j, yy)), (sx(i + 1, j + 1), sy(i + 1, j + 1, yy)),
                           (sx(i + 1, j + 1), sy(i + 1, j + 1, yy - 1)), (sx(i + 1, j), sy(i + 1, j, yy - 1))]
                d.polygon(pts, fill=coul(nom, k))
        nom = col(i, j, x, y, z, y)
        if y < 62:
            nom, y = "water", 62
        top = [(sx(i, j), sy(i, j, y)), (sx(i + 1, j), sy(i + 1, j, y)), (sx(i + 1, j + 1), sy(i + 1, j + 1, y)), (sx(i, j + 1), sy(i, j + 1, y))]
        d.polygon(top, fill=coul(nom, 1.0))
    img.save(out)

if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    x0, x1, z0, z1 = map(int, a[:4]); out = a[4]; K = int(a[5]) if len(a) > 5 else 3
    X, Z = np.meshgrid(np.arange(x0, x1), np.arange(z0, z1))
    y, gorge, reb, h, taillee = modele(X.astype(float), Z.astype(float))
    Y = np.floor(y)
    rendu_iso(Y, gorge, reb, h, taillee, x0, z0, out, K=K, nord="--nord" in sys.argv)
    print("écrit", out, "| sol", Y.min(), "à", Y.max(), "| terrain du mod", h.min().round(), "à", h.max().round())

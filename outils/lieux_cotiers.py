"""Génère les lieux côtiers de l'addon Lieux (lot 1) : Étretat, Moher, Douvres, dune du Pilat, baie du Mont-Saint-Michel.

Méthode « lieu en grille » : toute la forme est calculée ici, au bloc près en 1:250, sur le trait de côte EXACT du mod
(copie Python dans terre_py.py). Java (LieuGrille) ne fait que relire les grilles : le rendu de contrôle
(outils/rendu_grille.py) montre donc exactement ce que le jeu produira, hors grottes, arbres et minerais.

Sortie : lieux/src/main/resources/domaine_terre_lieux/<lieu>.bin (format ReliefLieu, 3 grilles int16) :
  0 DELTA = (y visé - y du terrain du mod) x 16   ; 1 SOMMET = y du dessus des couches x 16 ;
  2 TYPE  = classe de matériau (bits 0-3) + 16 taillée + 32 remblai + 64 biome + 128 inondé
et, pour les arches, <lieu>.vox : blocs en surplomb (x, y, z en int32 puis classe en int8), en 1:250.
Usage : python3 outils/lieux_cotiers.py [lieu ...]
"""
import gzip, os, struct, sys
import numpy as np
from scipy import ndimage
from matplotlib.path import Path
import terre_py as T

SORTIE = os.path.join(T.RACINE, "lieux/src/main/resources/domaine_terre_lieux/")
BPD = T.BPD
# classes de matériau (Java : LieuGrille.Classe)
PLATEAU, PLAGE, FOND, ROC, AIGUILLE, DUNE, VASE, CHENAL, PRE, SABLE = 1, 2, 3, 4, 5, 6, 7, 8, 9, 10
TAILLEE, REMBLAI, BIOME, INONDE = 16, 32, 64, 128


def bruit(X, Z, echelle, graine):
    """Bruit lisse ~[-1, 1] en coordonnées de blocs (déterministe)."""
    r = np.random.default_rng(graine); g = r.standard_normal((96, 96))
    g = ndimage.gaussian_filter(g, 1.2, mode="wrap"); g /= np.abs(g).max() * 0.7
    return ndimage.map_coordinates(g, [(Z / echelle) % 96, (X / echelle) % 96], order=3, mode="grid-wrap")


def grille(lon0, lon1, lat0, lat1):
    x0, x1 = int(np.floor(lon0 * BPD)), int(np.ceil(lon1 * BPD))
    z0, z1 = int(np.floor(-lat1 * BPD)), int(np.ceil(-lat0 * BPD))
    X, Z = np.meshgrid(np.arange(x0, x1, dtype=float), np.arange(z0, z1, dtype=float))
    return X, Z, x0, z0


def bord_zone(X, Z, marge):
    """Distance (blocs) au bord de la zone, pour le fondu vers le terrain du mod."""
    H, W = X.shape
    jj, ii = np.mgrid[0:H, 0:W]
    return np.minimum(np.minimum(ii, W - 1 - ii), np.minimum(jj, H - 1 - jj)) / marge


def bloc_de(lat, lon):
    return np.array([lon * BPD, -lat * BPD])


def ecrire(nom, X, Z, x0, z0, y, h, sommet, typ, vox=None):
    H, W = X.shape
    lon0, lat0, pas = (x0 - 0.5) / BPD, (-z0 + 0.5) / BPD, 1 / BPD
    delta = np.clip(np.round((y - h) * 16), -32000, 32000)
    blob = struct.pack("<4d2i", lon0, lat0, pas, pas, W, H)
    for g in (delta, np.round(sommet * 16), typ):
        blob += np.asarray(g).astype("<i2").tobytes()
    with gzip.open(SORTIE + nom + ".bin", "wb", 9) as f:
        f.write(blob)
    if vox is not None and len(vox):
        v = np.asarray(vox)
        with gzip.open(SORTIE + nom + ".vox", "wb", 9) as f:
            f.write(struct.pack("<i", len(v)))
            for (x, yy, z, c) in v:
                f.write(struct.pack("<3ib", int(x), int(yy), int(z), int(c)))
    np.savez_compressed(f"/tmp/lieu_{nom}.npz", X=X, Z=Z, y=y, h=h, sommet=sommet, typ=typ,
                        vox=np.asarray(vox if vox is not None else np.zeros((0, 4)), int))
    print(f"{nom} : {W} x {H} blocs, sol {y.min():.0f} à {y.max():.0f}, "
          f"{int(((typ & TAILLEE) > 0).sum())} colonnes taillées, {0 if vox is None else len(vox)} blocs en surplomb")


def finir_types(typ, travail, marge_biome=6):
    """Biome = zone de travail élargie : Minecraft ne lance la sculpture que dans les chunks qui contiennent le biome."""
    typ = typ.copy()
    typ[ndimage.binary_dilation(travail, iterations=marge_biome)] |= BIOME
    return typ


# ---------------------------------------------------------------- falaises de bord de mer

def falaise(X, Z, h, sd, haut, pied, graine, retour=55.0):
    """
    Falaise verticale sur le trait de côte du mod : plage de `pied` blocs, falaise de `haut` blocs au-dessus de l'eau
    (tableau, varie le long de la côte), plateau qui redescend vers le terrain du mod sur `retour` blocs.
    La hauteur réelle (~100-200 m) ne ferait que 3 à 6 blocs dans le mod : elle est exagérée, comme la largeur du Verdon.
    """
    db = sd * BPD / 60.0                                       # distance à la côte en blocs (positive à terre)
    e = db - pied - (bruit(X, Z, 9.0, graine) * 1.6 + bruit(X, Z, 3.5, graine + 1) * 0.5) * (pied > 0.5)
    sommet_falaise = 63.0 + haut
    y = h.copy()
    terre = db >= 0
    plateau = terre & (e >= 0)
    hp = np.maximum(h, 64.0)
    y = np.where(plateau, np.maximum(h, sommet_falaise - T.lisse(e / retour) * (sommet_falaise - hp)), y)
    plage = terre & (e < 0)
    y = np.where(plage, 63.2 + T.lisse(db / max(pied, 0.1)) * 0.9, y)
    y = np.where(db < 0, np.minimum(h, 62.4), y)
    typ = np.zeros(X.shape, np.int32)
    typ[plateau] = PLATEAU
    typ[plage] = PLAGE
    typ[(db < 0) & (db > -6)] = FOND
    taille = (np.abs(e) < 3.5) | plage | ((db < 0) & (db > -5))
    typ[taille] |= TAILLEE
    typ[plateau & (e >= 3.5) & (e < 12)] |= REMBLAI
    sommet = np.where(plateau, sommet_falaise, 63.0)
    return y, typ, sommet, db, e


def appliquer_fondu(y, h, X, Z, marge):
    f = T.lisse(bord_zone(X, Z, marge))
    return h + (y - h) * f, f


def point_cote(db, X, Z, lat, lon, cible):
    """Colonne la plus proche de (lat, lon) où la distance à la côte vaut `cible` blocs (± 0,7)."""
    p = bloc_de(lat, lon)
    d = np.hypot(X - p[0], Z - p[1]) + np.where(np.abs(db - cible) < 0.7, 0, 1e6)
    j, i = np.unravel_index(np.argmin(d), d.shape)
    return np.array([X[j, i], Z[j, i]])


def normale_mer(db, X, Z, p):
    """Direction (unitaire) vers le large au point p : -gradient de la distance à la côte, lissé."""
    gz, gx = np.gradient(ndimage.gaussian_filter(db, 3))
    j, i = int(p[1] - Z[0, 0]), int(p[0] - X[0, 0])
    n = -np.array([gx[j, i], gz[j, i]])
    return n / (np.linalg.norm(n) + 1e-9)


def aiguille(X, Z, y, typ, sommet, c, rayon, haut, pointe=0.25):
    """Piton dans la mer (Aiguille d'Étretat, stacks) : colonne évasée à la base, pointue en haut."""
    r = np.hypot(X - c[0], Z - c[1]) / rayon
    prof = 63.0 + haut * np.clip(1 - r, 0, 1) ** pointe * (r < 1)
    m = (r < 1) & (prof > y)
    y = np.where(m, prof, y)
    typ = np.where(m, AIGUILLE | TAILLEE, typ)
    sommet = np.where(m, prof, sommet)
    return y, typ, sommet


def arche(c, n, longueur, larg, sommet_haut, voute, classe=AIGUILLE):
    """
    Arche (Porte d'Aval, Manneporte) : un pont de roche part de la falaise en c, vers le large (n), sur `longueur`
    blocs ; dessous, une voûte de `voute` blocs au-dessus de l'eau. Renvoie les blocs en surplomb et le pilier.
    """
    t = np.array([-n[1], n[0]])
    vox = []
    for s in np.arange(0, longueur + 0.5, 0.5):
        u = s / longueur
        haut_s = sommet_haut - 3.0 * u                         # le dessus descend un peu vers le large
        bas_s = 63.0 + voute * np.sin(np.pi * min(u / 0.85, 1.0))
        if u > 0.85:
            bas_s = 60.0                                       # pilier jusque dans l'eau
        for w in np.arange(-larg, larg + 0.5, 0.5):
            px, pz = c + n * s + t * w
            for yy in range(int(np.floor(bas_s)), int(np.floor(haut_s)) + 1):
                vox.append((int(np.floor(px)), yy, int(np.floor(pz)), classe))
    return sorted(set(vox))


def etretat():
    X, Z, x0, z0 = grille(0.07, 0.42, 49.64, 49.80)
    h, sd = T.hauteur_base(X, Z)
    lon = X / BPD
    # la valleuse d'Étretat (la ville, ~0,21° E) coupe la falaise entre l'Aval (sud-ouest) et l'Amont (nord-est)
    haut = 27.0 * (1 - T.lisse(1 - np.abs(lon - 0.2125) / 0.0075))
    y, typ, sommet, db, e = falaise(X, Z, h, sd, haut, pied=2.0, graine=11)
    vox = []
    # Porte d'Aval (et l'Aiguille juste au large), puis la Manneporte. En vrai elles ne sont qu'à 850 m (3-4 blocs) :
    # la Manneporte est décalée à ~14 blocs le long de la côte, sinon les deux arches se chevauchent.
    c1 = point_cote(db, X, Z, 49.7076, 0.1965, 3.5)
    n1 = normale_mer(db, X, Z, c1)
    t1 = np.array([-n1[1], n1[0]])
    if t1[0] > 0:
        t1 = -t1                                                  # vers le sud-ouest
    p2 = c1 + t1 * 14
    c2 = point_cote(db, X, Z, -p2[1] / BPD, p2[0] / BPD, 3.5)
    for (c, L, w, v, nom) in [(c1, 9, 1.5, 12, "Porte d'Aval"), (c2, 11, 2.0, 15, "Manneporte")]:
        n = normale_mer(db, X, Z, c)
        terre = c - n * 3
        top = float(y[int(terre[1] - z0), int(terre[0] - x0)])
        vox += arche(c - n * 1.0, n, L, w, top, v)
        print(f"  {nom} : falaise en {c}, vers {n.round(2)}, sommet y {top:.0f}")
    pa = c1 + n1 * 15 + t1 * 3
    y, typ, sommet = aiguille(X, Z, y, typ, sommet, pa, 3.2, 21.0)
    print(f"  Aiguille : {pa.round(1)}")
    y, f = appliquer_fondu(y, h, X, Z, 14)
    travail = (typ & (TAILLEE | REMBLAI)) > 0
    typ = finir_types(typ, travail & (f > 0.2))
    ecrire("etretat", X, Z, x0, z0, y, h, sommet, typ, vox)


def moher():
    X, Z, x0, z0 = grille(-9.56, -9.30, 52.86, 53.08)
    h, sd = T.hauteur_base(X, Z)
    lat = -Z / BPD
    # 120 m au sud (Hag's Head), 214 m au nord, près de la tour d'O'Brien
    haut = (26.0 + 10.0 * T.lisse((lat - 52.935) / 0.04)) * T.lisse((53.06 - lat) / 0.03) * T.lisse((lat - 52.885) / 0.02)
    y, typ, sommet, db, e = falaise(X, Z, h, sd, haut, pied=0.0, graine=21)
    # Branaunmore, le piton au pied de la tour d'O'Brien
    c = point_cote(db, X, Z, 52.9719, -9.4265, -5.0)
    y, typ, sommet = aiguille(X, Z, y, typ, sommet, c, 3.6, 28.0, pointe=0.12)
    print(f"  Branaunmore : {c}")
    y, f = appliquer_fondu(y, h, X, Z, 14)
    typ = finir_types(typ, ((typ & (TAILLEE | REMBLAI)) > 0) & (f > 0.2))
    ecrire("moher", X, Z, x0, z0, y, h, sommet, typ)


def douvres():
    X, Z, x0, z0 = grille(1.12, 1.46, 51.03, 51.21)
    h, sd = T.hauteur_base(X, Z)
    lon = X / BPD
    # falaises de Folkestone à Kingsdown, coupées par la vallée de la Dour (ville de Douvres)
    haut = 24.0 * (1 - T.lisse(1 - np.abs(lon - 1.312) / 0.008)) * (1 - T.lisse((lon - 1.405) / 0.03))
    y, typ, sommet, db, e = falaise(X, Z, h, sd, haut, pied=1.5, graine=31)
    y, f = appliquer_fondu(y, h, X, Z, 14)
    typ = finir_types(typ, ((typ & (TAILLEE | REMBLAI)) > 0) & (f > 0.2))
    ecrire("douvres", X, Z, x0, z0, y, h, sommet, typ)


# ---------------------------------------------------------------- dune du Pilat

def pilat():
    X, Z, x0, z0 = grille(-1.32, -1.11, 44.44, 44.74)
    h, sd = T.hauteur_base(X, Z)
    db = sd * BPD / 60.0
    lat = -Z / BPD
    # 2,7 km x 500 m x 105 m en vrai : 11 x 2 blocs, invisible. Exagérée : ~60 x 40 blocs, 28 de haut.
    H, crete, sous_vent = 26.0, 20.0, 10.0
    # longue crête parallèle à l'océan (~90 blocs), un peu plus haute au sud comme la vraie
    long = T.lisse((0.10 - np.abs(lat - 44.589)) / 0.03) * (0.85 + 0.15 * T.lisse((44.62 - lat) / 0.06))
    face = np.where(db < crete, T.lisse((db - 1.5) / (crete - 1.5)) ** 1.3, 1 - T.lisse((db - crete) / sous_vent))
    face = np.where(db < 1.5, 0, face)
    ondule = 1 + 0.08 * bruit(X, Z, 14, 41)
    dune = H * long * face * ondule
    y = np.where(db >= 0, np.maximum(h, h + dune), h)
    typ = np.zeros(X.shape, np.int32)
    sable = (dune > 0.6) & (db >= 0)
    typ[sable] = DUNE | TAILLEE
    sommet = y.copy()
    y, f = appliquer_fondu(y, h, X, Z, 12)
    typ = finir_types(typ, sable & (f > 0.2))
    ecrire("pilat", X, Z, x0, z0, y, h, sommet, typ)


# ---------------------------------------------------------------- baie du Mont-Saint-Michel

BAIE = [(48.715, -1.843), (48.676, -1.851), (48.640, -1.830), (48.603, -1.776), (48.608, -1.704), (48.615, -1.640),
        (48.620, -1.570), (48.624, -1.530), (48.620, -1.497), (48.632, -1.465), (48.660, -1.420), (48.684, -1.392),
        (48.690, -1.440), (48.683, -1.479), (48.705, -1.500), (48.727, -1.520), (48.750, -1.560), (48.800, -1.575),
        (48.835, -1.597)]
COUESNON = [(48.600, -1.512), (48.624, -1.514), (48.645, -1.522), (48.665, -1.540), (48.685, -1.585), (48.705, -1.660),
            (48.730, -1.760)]
SEE_SELUNE = [(48.668, -1.400), (48.670, -1.440), (48.664, -1.480), (48.662, -1.525)]


def distance_polyligne(X, Z, pts):
    P = np.array([bloc_de(la, lo) for la, lo in pts])
    d = np.full(X.shape, 1e9)
    for a, b in zip(P, P[1:]):
        ab = b - a; L2 = ab @ ab
        u = np.clip(((X - a[0]) * ab[0] + (Z - a[1]) * ab[1]) / L2, 0, 1)
        d = np.minimum(d, np.hypot(X - a[0] - u * ab[0], Z - a[1] - u * ab[1]))
    return d


def mont_saint_michel():
    X, Z, x0, z0 = grille(-1.90, -1.34, 48.57, 48.86)
    h, sd = T.hauteur_base(X, Z)
    poly = Path(np.array([bloc_de(la, lo) for la, lo in BAIE]))
    dedans = poly.contains_points(np.c_[X.ravel(), Z.ravel()]).reshape(X.shape)
    d_dedans = ndimage.distance_transform_edt(dedans)
    d_dehors = ndimage.distance_transform_edt(~dedans)
    bouche = distance_polyligne(X, Z, [BAIE[-1], BAIE[0]])         # ouverture sur la mer (Granville - Grouin)
    # estran : sable à y 63 (marée basse), qui plonge vers la mer près de l'ouverture
    estran = 63.0 - 6.0 * (1 - T.lisse(bouche / 35.0))
    # chenaux du Couesnon et de la Sée-Sélune, qui serpentent ; flaques dans le sable
    serp = bruit(X, Z, 18, 51) * 3.0
    d_ch = np.minimum(distance_polyligne(X, Z, COUESNON), distance_polyligne(X, Z, SEE_SELUNE)) + serp
    chenal = d_ch < 2.6
    flaque = bruit(X, Z, 6, 52) > 0.62
    y = np.where(dedans, estran, h)
    y = np.where(dedans & (chenal | flaque), np.minimum(y, 60.5), y)
    # rivage : prés salés plats puis remontée vers le terrain du mod
    rive = ~dedans & (d_dehors < 14) & (h > 63.6)
    y = np.where(rive, 64.0 + (h - 64.0) * T.lisse((d_dehors - 3) / 11), y)
    typ = np.zeros(X.shape, np.int32)
    # vasières en taches, surtout le long des rives ; sable ailleurs
    vase = (bruit(X, Z, 7, 54) + 0.9 * (1 - T.lisse(d_dedans / 12.0))) > 0.75
    typ[dedans] = np.where(vase[dedans], VASE, SABLE)
    typ[dedans & (chenal | flaque)] = CHENAL
    typ[rive & (d_dehors < 4)] = PRE
    sommet = np.full(X.shape, 63.0)
    # le Mont (granite, 80 m, ~1 km) et Tombelaine, exagérés : rocher de 16 blocs de large, 24 de haut
    for (la, lo, R, Hm) in [(48.6361, -1.5115, 8.0, 24.0), (48.6757, -1.5669, 4.5, 9.0)]:
        c = bloc_de(la, lo)
        r = np.hypot(X - c[0], Z - c[1]) / R
        prof = 63.0 + Hm * np.clip(1 - r * r, 0, 1) ** 0.55
        prof += bruit(X, Z, 3, 53) * 1.2 * (r < 0.8)
        m = (r < 1) & (prof > y)
        y = np.where(m, prof, y)
        typ = np.where(m, ROC, typ)
        sommet = np.where(m, prof, sommet)
    travail = dedans | (typ == PRE) | (typ == ROC) | (rive & (d_dehors < 14))
    typ[travail] |= TAILLEE
    typ[dedans] |= INONDE
    y, f = appliquer_fondu(y, h, X, Z, 14)
    typ = finir_types(typ, travail & (f > 0.2))
    ecrire("mont_saint_michel", X, Z, x0, z0, y, h, sommet, typ)


LIEUX = {"etretat": etretat, "moher": moher, "douvres": douvres, "pilat": pilat, "mont_saint_michel": mont_saint_michel}

if __name__ == "__main__":
    for n in (sys.argv[1:] or LIEUX):
        LIEUX[n]()

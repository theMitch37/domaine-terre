"""Génère les lieux côtiers de l'addon Lieux (lot 1) : Étretat, Moher, Douvres, dune du Pilat, baie du Mont-Saint-Michel.

Méthode « lieu en grille » : toute la forme est calculée ici, au bloc près en 1:250, sur le trait de côte EXACT du mod
(copie Python dans terre_py.py). Java (LieuGrille) ne fait que relire les grilles : le rendu outils/rendu_grille.py
montre la forme exacte ; le banc d'essai (outils/banc) montre le vrai jeu, hasard vanilla compris.

Sortie : lieux/src/main/resources/domaine_terre_lieux/<lieu>.bin (format ReliefLieu, 4 grilles int16) :
  0 DELTA = (y visé - y du terrain du mod) x 16 ; 1 SOMMET = haut de falaise (repère des couches) x 16 ;
  2 TYPE  = classe (bits 0-3) + 16 taillée + 32 remblai + 64 biome + 128 inondé ; 3 POIDS = emprise x 1000
et <lieu>.vox : blocs à creuser (arches) : x, y, z (int32) puis classe 0 (int8), en 1:250.

Règles apprises au premier essai (25/10) :
- jamais de niveau pile sur un entier (y 63,0) : il hésite entre deux blocs (créneaux, labyrinthes) -> niveaux en x,5 ;
- pas de fin de lieu par simple fondu au bord du rectangle : chaque lieu a une vraie fin (falaise qui s'abaisse) ;
- la hauteur d'une falaise suit une abscisse le long de la côte (creux, fins), pas une coordonnée x ou z ;
- le plateau derrière une falaise redescend en pente douce (~1 bloc pour 4), sinon pyramide à gradins ;
- les arches sont CREUSÉES dans un promontoire plein (bloc .vox de classe 0), jamais construites en l'air.
Usage : python3 outils/lieux_cotiers.py [lieu ...]
"""
import gzip, os, struct, sys
import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree
from matplotlib.path import Path
from skimage import measure
import terre_py as T

SORTIE = os.path.join(T.RACINE, "lieux/src/main/resources/domaine_terre_lieux/")
BPD = T.BPD
# classes de matériau (Java : LieuGrille)
CREUSE, PLATEAU, PLAGE, FOND, ROC, AIGUILLE, DUNE, VASE, CHENAL, PRE, SABLE = 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10
TAILLEE, REMBLAI, BIOME, INONDE = 16, 32, 64, 128
lisse = T.lisse


# ---------------------------------------------------------------- outils communs

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
    H, W = X.shape
    jj, ii = np.mgrid[0:H, 0:W]
    return np.minimum(np.minimum(ii, W - 1 - ii), np.minimum(jj, H - 1 - jj)) / marge


def bloc_de(lat, lon):
    return np.array([lon * BPD, -lat * BPD])


def courbe(s, points):
    """Profil lisse le long de la côte : points = [(s, valeur)], interpolation en S entre les points."""
    s = np.asarray(s, float); v = np.full(s.shape, points[0][1], float)
    for (s0, v0), (s1, v1) in zip(points, points[1:]):
        m = (s >= s0) & (s <= s1)
        v = np.where(m, v0 + (v1 - v0) * lisse((s - s0) / max(s1 - s0, 1e-6)), v)
    return np.where(s > points[-1][0], points[-1][1], v)


class Cote:
    """Trait de côte du mod dans la zone : abscisse le long de la côte (blocs) pour chaque colonne."""

    def __init__(self, X, Z, db, depart):
        cs = measure.find_contours(db, 0.0)
        c = max(cs, key=len)                                           # (ligne, colonne)
        pts = np.c_[X[0, 0] + c[:, 1], Z[0, 0] + c[:, 0]]
        p0 = bloc_de(*depart)
        if np.hypot(*(pts[-1] - p0)) < np.hypot(*(pts[0] - p0)):
            pts = pts[::-1]
        L = np.r_[0, np.cumsum(np.hypot(*np.diff(pts, axis=0).T))]
        self.pts, self.L = pts, L
        arbre = cKDTree(pts)
        _, i = arbre.query(np.c_[X.ravel(), Z.ravel()])
        # lissée : l'abscisse saute dans les criques (point le plus proche qui change de côté)
        self.s = ndimage.gaussian_filter(L[i].reshape(X.shape), 4)
        self.arbre = arbre

    def s_de(self, lat, lon):
        _, i = self.arbre.query(bloc_de(lat, lon))
        return float(self.L[i])

    def point(self, s):
        i = int(np.clip(np.searchsorted(self.L, s), 0, len(self.L) - 1))
        return self.pts[i]


def ecrire(nom, X, Z, x0, z0, y, h, sommet, typ, creux=None):
    H, W = X.shape
    lon0, lat0, pas = (x0 - 0.5) / BPD, (-z0 + 0.5) / BPD, 1 / BPD
    delta = np.clip(np.round((y - h) * 16), -32000, 32000)
    agit = (np.abs(y - h) > 0.2) | ((typ & (TAILLEE | REMBLAI | INONDE)) > 0)
    poids = np.clip(ndimage.gaussian_filter(ndimage.binary_dilation(agit, iterations=4).astype(float), 3) * 1.6, 0, 1)
    poids *= lisse(bord_zone(X, Z, 10))
    blob = struct.pack("<4d2i", lon0, lat0, pas, pas, W, H)
    for g in (delta, np.round(sommet * 16), typ, np.round(poids * 1000)):
        blob += np.asarray(g).astype("<i2").tobytes()
    with gzip.open(SORTIE + nom + ".bin", "wb", 9) as f:
        f.write(blob)
    vox = sorted(set(creux or []))
    chemin_vox = SORTIE + nom + ".vox"
    if vox:
        with gzip.open(chemin_vox, "wb", 9) as f:
            f.write(struct.pack("<i", len(vox)))
            for (x, yy, z, c) in vox:
                f.write(struct.pack("<3ib", int(x), int(yy), int(z), int(c)))
    elif os.path.exists(chemin_vox):
        os.remove(chemin_vox)
    np.savez_compressed(f"/tmp/lieu_{nom}.npz", X=X, Z=Z, y=y, h=h, sommet=sommet, typ=typ, poids=poids,
                        vox=np.asarray(vox if vox else np.zeros((0, 4)), int))
    # contrôles : hauteurs pile sur un entier (créneaux), écart au terrain du mod au bord de la zone
    frac = np.abs(y - np.round(y))
    plats = int(((frac < 0.02) & ((typ & TAILLEE) > 0)).sum())
    bord = bord_zone(X, Z, 1) < 3
    print(f"{nom} : {W} x {H} blocs, sol {y.min():.1f} à {y.max():.1f}, {int(((typ & TAILLEE) > 0).sum())} taillées, "
          f"{len(vox)} blocs creusés | contrôles : {plats} colonnes taillées sur un entier, "
          f"écart max au bord {np.abs(y - h)[bord].max():.2f}")


def finir_types(typ, travail, marge_biome=7):
    """Biome = zone de travail élargie : Minecraft ne lance la sculpture que dans les chunks qui contiennent le biome."""
    typ = typ.copy()
    typ[ndimage.binary_dilation(travail, iterations=marge_biome)] |= BIOME
    return typ


# ---------------------------------------------------------------- falaises de bord de mer

def falaise(X, Z, h, db, s, haut, pied, graine, amp=2.5, retour=120.0, plongeante=False):
    """
    Falaise verticale le long du trait de côte du mod.
    haut : hauteur de la falaise au-dessus de la mer (tableau, suit l'abscisse s : creux de vallées, fins progressives).
    pied : largeur de la plage (blocs) entre la mer et la falaise ; 0 avec plongeante=True : la falaise tombe dans l'eau.
    amp  : découpe du trait de falaise (criques, contreforts).
    La hauteur réelle (~100-200 m) ne ferait que 3 à 6 blocs dans le mod : elle est exagérée (comme la largeur du Verdon),
    et le plateau qui la porte redescend vers le terrain du mod en pente douce sur `retour` blocs.
    Renvoie y, typ, sommet, e (distance au trait de falaise, + vers la terre).
    """
    # versants des valleuses adoucis vers l'intérieur des terres (sinon des tranchées étroites)
    haut = ndimage.gaussian_filter(haut, 3.0)
    irr = (bruit(X, Z, 17, graine) * amp + bruit(X, Z, 6.5, graine + 1) * amp * 0.3)
    e = db - pied - irr
    haute = haut > 2.5
    ztop = 63.5 + haut
    # plateau : rejoint le terrain du mod en pente douce ; rebord légèrement arrondi
    plat = h + np.maximum(0.0, ztop - h) * (1 - lisse(e / retour))
    plat -= 1.1 * (1 - lisse(e / 3.0)) * haute
    y = np.where(e >= 0, np.maximum(h, plat), h)
    terre = db >= 0
    plage = terre & (e < 0)
    if plongeante:
        y = np.where(e < 0, np.minimum(h, 58.5), y)
    else:
        y = np.where(plage, 63.5 + 0.6 * lisse(db / np.maximum(pied, 0.5)), y)
        # platier rocheux au pied, sous 1 à 2 blocs d'eau, puis le fond naturel
        mer = db < 0
        y = np.where(mer, np.minimum(h, np.where(db > -6, 61.4 - 0.15 * (-db), h)), y)
    typ = np.zeros(X.shape, np.int32)
    typ[e >= 0] = PLATEAU
    typ[plage] = PLAGE
    typ[(db < 0) & (db > -7)] = FOND
    if plongeante:
        typ[(e < 0) & (e > -7)] = FOND
    typ[(db < 0) | (plongeante & (e < 0))] |= INONDE
    face = (np.abs(e) < 2.5) & haute
    taille = face | plage | ((db < 0) & (db > -6)) | (plongeante & (e < 0) & (e > -6))
    typ[taille] |= TAILLEE
    typ[(e >= 2.5) & (e < 14) & haute] |= REMBLAI
    sommet = np.where(e >= -3, ztop, 63.0)
    return y, typ, sommet, e


def promontoire(X, Z, y, typ, sommet, p0, n, L, larg, top, pente_bout=2.0):
    """Langue de falaise qui avance dans la mer (Porte d'Aval, Manneporte) : pleine, parois verticales."""
    t = np.array([-n[1], n[0]])
    u = (X - p0[0]) * n[0] + (Z - p0[1]) * n[1]
    v = (X - p0[0]) * t[0] + (Z - p0[1]) * t[1]
    demi = larg / 2 * (1 - 0.3 * np.clip(u / L, 0, 1))
    dedans = (u >= -3) & (u <= L) & (np.abs(v) <= demi) & (np.hypot(np.maximum(u - (L - demi), 0), v) <= demi)
    ht = top - pente_bout * np.clip(u / L, 0, 1)
    y = np.where(dedans, np.maximum(y, ht), y)
    typ = np.where(dedans, (typ & ~15 & ~INONDE) | PLATEAU | TAILLEE, typ)
    sommet = np.where(dedans, top, sommet)
    return y, typ, sommet, (u, v, demi)


def arche(X, Z, x0, z0, p0, n, L, u0, u1, larg, haut_trou):
    """Trou d'arche à travers un promontoire, entre u0 et u1 le long de l'axe ; voûte arrondie."""
    t = np.array([-n[1], n[0]])
    creux = []
    for u in np.arange(u0, u1 + 0.01, 0.25):
        k = (u - u0) / (u1 - u0)
        voute = 63 + haut_trou * np.sqrt(max(np.sin(np.pi * k), 0.0))
        for w in np.arange(-larg, larg + 0.01, 0.25):
            px, pz = p0 + n * u + t * w
            for yy in range(57, int(np.floor(voute)) + 1):
                creux.append((int(np.floor(px)), yy, int(np.floor(pz)), CREUSE))
    return creux


def aiguille(X, Z, y, typ, sommet, c, rayon, haut, pointe=0.35):
    """Piton isolé dans la mer : évasé à la base, effilé en haut."""
    r = np.hypot(X - c[0], Z - c[1]) / rayon
    prof = 63.5 + haut * np.clip(1 - r, 0, 1) ** pointe
    m = (r < 1) & (prof > y)
    y = np.where(m, prof, y)
    typ = np.where(m, AIGUILLE | TAILLEE, typ)
    sommet = np.where(m, prof, sommet)
    return y, typ, sommet


def normale(db, X, Z, p):
    gz, gx = np.gradient(ndimage.gaussian_filter(db, 4))
    j, i = int(round(p[1] - Z[0, 0])), int(round(p[0] - X[0, 0]))
    n = -np.array([gx[j, i], gz[j, i]])
    return n / (np.linalg.norm(n) + 1e-9)


def sur_falaise(e, X, Z, lat, lon):
    """Colonne du trait de falaise (e ~ 0) la plus proche de (lat, lon)."""
    p = bloc_de(lat, lon)
    d = np.hypot(X - p[0], Z - p[1]) + np.where(np.abs(e) < 0.8, 0, 1e6)
    j, i = np.unravel_index(np.argmin(d), d.shape)
    return np.array([X[j, i], Z[j, i]])


def fin_de_lieu(y, h, typ, X, Z, marge=12):
    """Sécurité : le lieu rejoint le terrain du mod au bord de la zone (il doit déjà être fini bien avant)."""
    f = lisse(bord_zone(X, Z, marge))
    return h + (y - h) * f, f


# ---------------------------------------------------------------- Étretat

def etretat():
    X, Z, x0, z0 = grille(-0.08, 0.48, 49.56, 49.84)
    h, sd = T.hauteur_base(X, Z)
    db = sd * BPD / 60.0
    cote = Cote(X, Z, db, (49.58, 0.0))                             # abscisse du sud-ouest au nord-est
    S = cote.s
    v, fin = cote.s_de(49.7085, 0.2105), cote.L[-1]
    # En vrai, Manneporte, Porte d'Aval, la ville et Porte d'Amont tiennent en 3 km (12 blocs) : les distances le long
    # de la côte sont étirées autour de la ville, comme les hauteurs. Côte d'Albâtre : falaises sur toute la zone,
    # creusées de valleuses, qui s'abaissent aux deux bouts.
    haut = courbe(S, [(0, 0), (15, 0), (40, 21), (v - 30, 26), (v - 12, 27), (v - 4, 2), (v + 4, 2), (v + 12, 25),
                      (v + 45, 25), (v + 56, 16), (v + 64, 16), (v + 78, 24), (fin - 30, 23), (fin - 12, 0)])
    y, typ, sommet, e = falaise(X, Z, h, db, S, haut, pied=2.0, graine=11)
    creux = []
    j_h = lambda p: float(haut[int(round(p[1] - z0)), int(round(p[0] - x0))])
    # Manneporte, Porte d'Aval (et l'Aiguille au large de sa pointe), Porte d'Amont : promontoires pleins, percés
    for (ds, L, larg, (u0, u1, lt, htrou), tourne, nom) in [
            (-46, 13, 11, (4.5, 10.5, 7, 16), 0.0, "Manneporte"),
            (-21, 15, 9, (7.0, 12.0, 6, 14), -0.35, "Porte d'Aval"),
            (+21, 9, 8, (3.0, 7.0, 5, 10), 0.15, "Porte d'Amont")]:
        q = cote.point(v + ds)
        p0 = sur_falaise(e, X, Z, -q[1] / BPD, q[0] / BPD)
        n = normale(db, X, Z, p0)
        n = n + np.array([-n[1], n[0]]) * tourne
        n /= np.linalg.norm(n)
        top = 63.5 + j_h(p0)
        y, typ, sommet, _ = promontoire(X, Z, y, typ, sommet, p0 - n * 2, n, L + 2, larg, top)
        creux += arche(X, Z, x0, z0, p0 - n * 2, n, L + 2, u0 + 2, u1 + 2, lt / 2 + 1.5, htrou)
        print(f"  {nom} : base {p0}, axe {n.round(2)}, haut y {top:.1f}")
        if nom == "Porte d'Aval":
            t = np.array([-n[1], n[0]])
            c = p0 + n * (L + 8) + t * 4.0
            y, typ, sommet = aiguille(X, Z, y, typ, sommet, c, 3.0, 19.0)
            print(f"  Aiguille : {c.round(1)}")
    y, f = fin_de_lieu(y, h, typ, X, Z)
    travail = ((typ & (TAILLEE | REMBLAI)) > 0) & (f > 0.2)
    typ = finir_types(typ, travail)
    ecrire("etretat", X, Z, x0, z0, y, h, sommet, typ, creux)


# ---------------------------------------------------------------- Moher

def moher():
    X, Z, x0, z0 = grille(-9.62, -9.28, 52.84, 53.10)
    h, sd = T.hauteur_base(X, Z)
    db = sd * BPD / 60.0
    cote = Cote(X, Z, db, (52.86, -9.50))                           # du sud (Hag's Head) vers le nord
    S = cote.s
    s_tour = cote.s_de(52.9719, -9.4265)
    s_fin = cote.L[-1]
    # 8 km en vrai (32 blocs) : allongée le long de la côte, sinon un bloc trapu ; 120 m au sud, 214 m au nord
    haut = courbe(S, [(0, 0), (25, 0), (50, 20), (s_tour - 30, 25), (s_tour + 5, 30), (s_tour + 45, 29),
                      (s_fin - 20, 0)])
    y, typ, sommet, e = falaise(X, Z, h, db, S, haut, pied=0.0, graine=21, amp=3.5, plongeante=True)
    # Branaunmore : piton au pied de la tour d'O'Brien, séparé de la falaise par un chenal d'au moins 7 blocs
    p = sur_falaise(e, X, Z, *(lambda q: (-q[1] / BPD, q[0] / BPD))(cote.point(s_tour)))
    n = normale(db, X, Z, p)
    c = p + n * 11.5
    top = 63.5 + float(haut[int(round(p[1] - z0)), int(round(p[0] - x0))]) - 4
    r = np.hypot(X - c[0], Z - c[1])
    m = r < 4.0
    y = np.where(m, top - 1.5 * (r / 4.0) ** 4, y)
    typ = np.where(m, PLATEAU | TAILLEE, typ)
    sommet = np.where(m, top, sommet)
    print(f"  Branaunmore : {c.round(1)}, haut y {top:.1f}")
    y, f = fin_de_lieu(y, h, typ, X, Z)
    typ = finir_types(typ, ((typ & (TAILLEE | REMBLAI)) > 0) & (f > 0.2))
    ecrire("moher", X, Z, x0, z0, y, h, sommet, typ)


# ---------------------------------------------------------------- Douvres

def douvres():
    X, Z, x0, z0 = grille(1.05, 1.52, 51.00, 51.24)
    h, sd = T.hauteur_base(X, Z)
    db = sd * BPD / 60.0
    cote = Cote(X, Z, db, (51.07, 1.10))                            # d'ouest (Folkestone) en est (Kingsdown)
    S = cote.s
    d, fin = cote.s_de(51.122, 1.312), cote.L[-1]
    # ~100 m, faîte ondulé : falaise de Shakespeare à l'ouest, vallée de la Dour (la ville), combes sèches,
    # baie de St Margaret ; distances étirées le long de la côte comme à Étretat
    haut = courbe(S, [(0, 0), (15, 0), (40, 20), (d - 40, 23), (d - 22, 18), (d - 12, 21), (d - 7, 0), (d + 7, 0),
                      (d + 13, 22), (d + 30, 24), (d + 40, 15), (d + 50, 24), (d + 62, 22), (fin - 22, 8),
                      (fin - 10, 0)])
    y, typ, sommet, e = falaise(X, Z, h, db, S, haut, pied=1.5, graine=31, amp=1.6)
    y, f = fin_de_lieu(y, h, typ, X, Z)
    typ = finir_types(typ, ((typ & (TAILLEE | REMBLAI)) > 0) & (f > 0.2))
    ecrire("douvres", X, Z, x0, z0, y, h, sommet, typ)


# ---------------------------------------------------------------- dune du Pilat

def pilat():
    X, Z, x0, z0 = grille(-1.34, -1.08, 44.42, 44.76)
    h, sd = T.hauteur_base(X, Z)
    db = sd * BPD / 60.0
    lat = -Z / BPD
    # 2,7 km x 500 m x 105 m en vrai (11 x 2 blocs !) : exagérée à ~150 x 75 blocs, 19 de haut.
    # Face à l'océan : longue pente douce ; côté forêt : pente raide (talus d'éboulement du sable).
    H = 19.0
    s = (lat - 44.589) * BPD                                         # blocs, + vers le nord
    longueur = lisse((78 - np.abs(s + 6 * np.sign(s))) / 30)        # fins progressives
    hauteur = H * longueur * (0.92 + 0.08 * lisse((-s + 20) / 60))   # un peu plus haute au sud, comme la vraie
    pied = 6.0 + 3.0 * bruit(X, Z, 23, 41)                           # plage au pied
    crete = pied + 50.0 + 6.0 * bruit(X, Z, 40, 42) + 4.0 * np.sin(s / 21.0)
    u = db - pied
    vent = lisse(np.clip(u / (crete - pied), 0, 1)) ** 0.9            # pente au vent, convexe près de la crête
    abri = 1 - lisse(np.clip((db - crete) / 19.0, 0, 1)) ** 0.7        # face sous le vent, raide
    forme = np.where(db < crete, vent, abri) * (u > 0)
    ondes = 0.45 * bruit(X, Z, 5.0, 43) * (db < crete) * forme       # rides du vent
    dune = hauteur * forme + ondes * longueur
    y = np.where(db >= 0, h + np.maximum(dune, 0), h)
    plage = (db >= 0) & (u <= 0)
    y = np.where(plage, np.minimum(np.maximum(y, 63.5 + 0.5 * lisse(db / 4)), 64.4), y)
    typ = np.zeros(X.shape, np.int32)
    # tout le versant au vent est en sable jusqu'à la crête (sinon un anneau d'herbe au pied de la dune)
    sable = (db >= 0) & (longueur > 0.05) & (((u > 0) & (db < crete + 2)) | (dune > 0.4))
    typ[sable] = DUNE | TAILLEE
    typ[plage] = SABLE | TAILLEE
    typ[db < 0] |= INONDE
    sommet = y.copy()
    y, f = fin_de_lieu(y, h, typ, X, Z)
    typ = finir_types(typ, (sable | plage) & (f > 0.2))
    ecrire("pilat", X, Z, x0, z0, y, h, sommet, typ)


# ---------------------------------------------------------------- baie du Mont-Saint-Michel

RIVAGE = [(48.735, -1.845), (48.690, -1.851), (48.655, -1.842), (48.628, -1.812), (48.612, -1.770), (48.611, -1.720),
          (48.616, -1.655), (48.620, -1.590), (48.622, -1.540), (48.619, -1.505), (48.627, -1.470), (48.648, -1.432),
          (48.673, -1.400), (48.690, -1.420), (48.687, -1.462), (48.700, -1.495), (48.722, -1.518), (48.752, -1.556),
          (48.800, -1.575), (48.838, -1.598)]
COUESNON = [(48.598, -1.512), (48.616, -1.513), (48.630, -1.518), (48.648, -1.528), (48.668, -1.548), (48.690, -1.590),
            (48.712, -1.650), (48.735, -1.735)]
SEE_SELUNE = [(48.672, -1.405), (48.672, -1.440), (48.668, -1.478), (48.672, -1.520), (48.684, -1.560)]


def distance_polyligne(X, Z, pts):
    P = np.array([bloc_de(la, lo) for la, lo in pts])
    d = np.full(X.shape, 1e9); s_pt = np.zeros(X.shape)
    acc = 0.0
    for a, b in zip(P, P[1:]):
        ab = b - a; L2 = ab @ ab; L = np.sqrt(L2)
        u = np.clip(((X - a[0]) * ab[0] + (Z - a[1]) * ab[1]) / L2, 0, 1)
        di = np.hypot(X - a[0] - u * ab[0], Z - a[1] - u * ab[1])
        m = di < d
        d = np.where(m, di, d); s_pt = np.where(m, acc + u * L, s_pt)
        acc += L
    return d, s_pt


def mont_saint_michel():
    X, Z, x0, z0 = grille(-1.93, -1.33, 48.57, 48.87)
    h, sd = T.hauteur_base(X, Z)
    # le rivage de la baie, lissé (spline) : pas de segments droits
    P = np.array([bloc_de(la, lo) for la, lo in RIVAGE])
    tt = np.r_[0, np.cumsum(np.hypot(*np.diff(P, axis=0).T))]
    fin = np.linspace(0, tt[-1], 600)
    lisse_p = np.c_[np.interp(fin, tt, ndimage.gaussian_filter1d(P[:, 0], 1.2)),
                    np.interp(fin, tt, ndimage.gaussian_filter1d(P[:, 1], 1.2))]
    ferme = np.r_[lisse_p, lisse_p[:1]]
    dedans = Path(ferme).contains_points(np.c_[X.ravel(), Z.ravel()]).reshape(X.shape)
    d_rive = ndimage.distance_transform_edt(dedans)                  # distance au rivage, dans la baie
    d_ouvert = distance_polyligne(X, Z, [RIVAGE[-1], RIVAGE[0]])[0]  # distance à l'ouverture sur la mer
    # estran : sable sec à y 63,5 près du fond de la baie, qui descend doucement vers le large (bords lobés)
    lobes = 14 * bruit(X, Z, 26, 51) + 6 * bruit(X, Z, 9, 52)
    # marée basse : sable sur presque toute la baie, il ne s'enfonce sous l'eau qu'en approchant du large
    vers_large = np.clip((38 - d_ouvert + lobes) / 40, 0, 1)         # 0 au fond de la baie, 1 près de l'ouverture
    estran = 63.6 - 4.2 * lisse(vers_large) ** 1.4
    # chenaux qui serpentent (Couesnon, Sée-Sélune), plus larges vers le large
    chenal = np.zeros(X.shape, bool); fond_chenal = np.full(X.shape, 99.0)
    for riv, g in ((COUESNON, 53), (SEE_SELUNE, 54)):
        d, sp = distance_polyligne(X, Z, riv)
        meandre = 5.0 * np.sin(sp / 13.0 + g) + 2.5 * bruit(X, Z, 15, g)
        # méandre : on décale la distance avec un bruit le long du cours
        d2, _ = distance_polyligne(X + meandre * 0.7, Z + meandre * 0.5, riv)
        larg = 1.6 + 2.2 * lisse(sp / 220)
        c = (d2 < larg) & dedans
        chenal |= c
        fond_chenal = np.where(c, np.minimum(fond_chenal, 60.4 - 0.8 * lisse(sp / 220)), fond_chenal)
    # mares : grandes et rares (pas de damier)
    mare = (bruit(X, Z, 11, 55) > 0.62) & (vers_large > 0.15) & dedans
    mare = ndimage.binary_opening(mare, iterations=2)
    # herbus (prés salés) le long du rivage sud, avec leur bord irrégulier
    herbus = dedans & (d_rive < 9 + 6 * bruit(X, Z, 19, 56)) & (vers_large < 0.55)
    y = np.where(dedans, estran, h)
    y = np.where(dedans & mare, np.minimum(y, 61.5), y)
    y = np.where(chenal, np.minimum(y, fond_chenal), y)
    y = np.where(herbus & ~chenal, 63.7 + 0.3 * lisse(d_rive / 4), y)
    # la côte autour : rien ne change hors de la baie, sauf un raccord doux là où le terrain est plus bas
    d_dehors = ndimage.distance_transform_edt(~dedans)
    raccord = ~dedans & (d_dehors < 10) & (h < 64.0) & (sd >= 0)        # seulement la terre ferme du mod
    y = np.where(raccord, np.maximum(h, 63.7), y)
    typ = np.zeros(X.shape, np.int32)
    tangue = (bruit(X, Z, 10, 57) > 0.35) & (vers_large > 0.1)
    typ[dedans] = np.where(tangue[dedans], VASE, SABLE)
    typ[dedans & (mare | chenal)] = CHENAL
    typ[herbus & ~chenal] = PRE
    sommet = np.full(X.shape, 63.0)
    # le Mont (granite, 80 m) et Tombelaine, exagérés : roc de ~16 blocs, 22 de haut, flancs raides
    for (la, lo, R, Hm, rx) in [(48.6361, -1.5115, 8.5, 22.0, 1.15), (48.6757, -1.5669, 4.5, 8.0, 1.3)]:
        c = bloc_de(la, lo)
        r = np.hypot((X - c[0]) / rx, Z - c[1]) / R
        prof = 63.6 + Hm * np.clip(1 - r ** 2.2, 0, 1) ** 0.6 + bruit(X, Z, 3.5, 58) * 1.0 * (r < 0.85)
        m = (r < 1) & (prof > y)
        y = np.where(m, prof, y)
        typ = np.where(m, ROC, typ)
        sommet = np.where(m, prof, sommet)
    travail = dedans | (typ == ROC) | raccord
    typ[travail] |= TAILLEE
    typ[dedans] |= INONDE
    y, f = fin_de_lieu(y, h, typ, X, Z)
    typ = finir_types(typ, travail & (f > 0.2))
    ecrire("mont_saint_michel", X, Z, x0, z0, y, h, sommet, typ)


LIEUX = {"etretat": etretat, "moher": moher, "douvres": douvres, "pilat": pilat, "mont_saint_michel": mont_saint_michel}

if __name__ == "__main__":
    for n in (sys.argv[1:] or LIEUX):
        LIEUX[n]()

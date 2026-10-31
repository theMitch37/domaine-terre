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
import tuiles as tu

SORTIE = os.path.join(T.RACINE, "lieux/src/main/resources/domaine_terre_lieux/")
BPD = T.BPD
# classes de matériau (Java : LieuGrille)
CREUSE, PLATEAU, PLAGE, FOND, ROC, AIGUILLE, DUNE, VASE, CHENAL, PRE, SABLE = 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10
NEIGE, GLACE, EBOULIS, MOUSSE, LIT = 11, 12, 13, 14, 15            # lot 2 (montagne)
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

    def distance_troncon(self, X, Z, s0, s1):
        """Distance (blocs) de chaque colonne au tronçon de côte entre les abscisses s0 et s1 : sert à borner un lieu
        (l'abscisse lissée saute d'une rive à l'autre en mer, elle ne convient pas pour ça)."""
        m = (self.L >= s0) & (self.L <= s1)
        return cKDTree(self.pts[m]).query(np.c_[X.ravel(), Z.ravel()])[0].reshape(X.shape)

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
                f.write(struct.pack("<3iB", int(x), int(yy), int(z), int(c)))
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


def en_tuiles(nom, X, Z, y, h, sommet, typ, sd, vox=None, marge=10, limite=None, eau=None, garder_fleuves=True):
    """Écrit un lieu dans les tuiles (outils/tuiles.py) : colonnes sculptées = ce que le lieu change (hauteur, taille,
    remblai, biome) élargi de `marge` blocs ; au-delà, terrain calculé. Contrôle que les colonnes sculptées
    rejoignent le terrain calculé à leur bord et ne touchent pas le bord de la zone."""
    # jamais dans la vallée d'un fleuve : le Python ne copie pas son profil, la tuile l'effacerait
    # (garder_fleuves=False : le lieu reprend lui-même le cours d'eau du mod — même terrain h et même eau — pour s'y
    # raccorder, comme la Hvítá de Gullfoss qui se jette dans la Þjórsá)
    hors_fleuve = T.influence_fleuves(X, Z) > 3 if garder_fleuves else np.ones(X.shape, bool)
    limite = hors_fleuve if limite is None else (limite & hors_fleuve)
    # le lieu s'arrête là (fleuves, îles, autres côtes) : il y redescend au terrain calculé sur 30 blocs, sans coupure
    w = lisse(ndimage.distance_transform_edt(limite) / 30.0)
    attenue = (w < 0.999) & (np.abs(y - h) > 1.0) & ((typ & TAILLEE) > 0)
    if attenue.any():
        print(f"  ATTENTION : {int(attenue.sum())} colonnes taillées abaissées par la limite (élargir les bornes ?)")
    y = h + (y - h) * w
    typ = np.where(limite, typ, 0)
    role = (typ & (TAILLEE | REMBLAI | BIOME)) > 0
    y = np.where(~role & (np.abs(y - h) < 0.15), h, y)          # restes de fondu (< 0,15 bloc) : terrain calculé
    change = (np.abs(y - h) > 0.01) | role
    # jamais dans la vallée d'un fleuve, même par la marge : une colonne de lieu y couperait le cours d'eau (le lieu
    # l'emporte sur le fleuve en jeu) ; le lieu y est déjà redescendu au terrain calculé
    actif = ndimage.binary_dilation(change, iterations=marge) & hors_fleuve
    typ = np.where(actif & (sd < 0), typ | INONDE, typ)          # la mer d'un lieu reste en eau (aquifère au niveau de la mer)
    typ = np.where(actif, typ, 0)
    if eau is not None:                                         # eau du lieu (lot 2) : seulement sur ses colonnes
        perdue = np.isfinite(eau) & ~actif
        if perdue.any():
            print(f"  ATTENTION : {int(perdue.sum())} colonnes d'eau hors des colonnes sculptées (ignorées)")
        eau = np.where(actif, eau, np.nan)
    ecrites = tu.poser(nom, int(X[0, 0]), int(Z[0, 0]), y, sommet, typ, actif, eau=eau)
    vox = sorted(set(vox or []))
    chemin_vox = SORTIE + nom + ".vox"
    if vox:
        with gzip.GzipFile(chemin_vox, "wb", 9, mtime=0) as f:
            f.write(struct.pack("<i", len(vox)))
            for (x, yy, z, c) in vox:
                f.write(struct.pack("<3iB", int(x), int(yy), int(z), int(c)))
    elif os.path.exists(chemin_vox):
        os.remove(chemin_vox)
    if os.path.exists(SORTIE + nom + ".bin"):
        os.remove(SORTIE + nom + ".bin")                         # ancien format (grille lon/lat)
    np.savez_compressed(f"/tmp/lieu_{nom}.npz", X=X, Z=Z, y=y, h=h, sommet=sommet, typ=typ, poids=actif.astype(float),
                        vox=np.asarray(vox if vox else np.zeros((0, 4)), int),
                        eau=eau if eau is not None else np.full(X.shape, np.nan))
    if limite is not None:                                      # coupure franche là où la limite tranche le lieu ?
        coupe = limite & ndimage.binary_dilation(~limite)
        print(f"  coupure à la limite (fleuves, bornes) : écart max {np.abs(y - h)[coupe].max() if coupe.any() else 0:.2f}")
    bord_actif = actif & ndimage.binary_dilation(~actif)
    frac = np.abs(y - np.round(y))
    print(f"{nom} (tuiles {ecrites}) : {int(actif.sum())} colonnes, sol {y.min():.1f} à {y.max():.1f}, "
          f"{int(((typ & TAILLEE) > 0).sum())} taillées, {len(vox)} blocs creusés | contrôles : écart au bord des colonnes "
          f"sculptées {np.abs(y - h)[bord_actif].max():.3f}, actif au bord de la zone {int(actif[bord_zone(X, Z, 1) < 2].sum())}, "
          f"{int(((frac < 0.02) & ((typ & TAILLEE) > 0) & (np.abs(y - h) > 0.01)).sum())} colonnes taillées sur un entier")
    return typ, actif


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
    # ... et l'a rejoint AVANT le bord de la zone : sinon fin_de_lieu le rabattait en 12 blocs (talus d'herbe raide)
    retour = np.clip(e + bord_zone(X, Z, 1) - 16, 30, retour)
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
    # toute paroi raide porte les couches de la falaise (sinon pierre nue ou escalier d'herbe là où le trait est oblique)
    gz, gx = np.gradient(y)
    raide = ndimage.binary_dilation((np.hypot(gx, gz) > 1.4) & (haut > 2.5) & (e > -4), iterations=1)
    typ[raide & (typ & 15 == PLATEAU)] |= TAILLEE
    typ[(e >= 2.5) & (e < 14) & haute] |= REMBLAI
    # hors des tronçons de falaise, la côte reste celle du terrain calculé (pas de platier ni de plage taillés
    # tout le long de la zone : ils sortaient du lieu jusqu'au bord de la zone)
    hors = (haut <= 0.5) & ((e < 0) | (db < 0))
    y = np.where(hors, h, y)
    typ = np.where(hors, typ & INONDE, typ)
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


def parois(y, typ, haut_min=66.0):
    """Après fin_de_lieu : toute paroi raide et haute porte les couches de la falaise (taillée, classe plateau).
    Sinon, là où la falaise sort de la zone ou rejoint un relief du mod, une paroi de pierre nue ou d'herbe en escalier."""
    gz, gx = np.gradient(y)
    raide = ndimage.binary_dilation((np.hypot(gx, gz) > 1.4) & (y > haut_min), iterations=1)
    cl = typ & 15
    haut_fond = raide & (cl == FOND) & (y > 62.5)
    typ = np.where(haut_fond, (typ & ~15) | PLATEAU, typ)
    typ = np.where(raide & ((typ & 15) == PLATEAU), typ | TAILLEE, typ)
    return typ


def fin_de_lieu(y, h, typ, X, Z, marge=12):
    """Sécurité : le lieu rejoint le terrain du mod au bord de la zone (il doit déjà être fini bien avant)."""
    f = lisse(bord_zone(X, Z, marge))
    return h + (y - h) * f, f


# ---------------------------------------------------------------- Étretat

def etretat():
    """Étretat sur la côte d'Albâtre, en tuiles (26/10). La falaise commence au cap de la Hève (au-dessus du Havre,
    comme en vrai), se creuse aux vraies valleuses (Étretat, Yport, Fécamp), remonte au cap Fagnet puis s'abaisse vers
    Saint-Pierre-en-Port : plus de fin coupée par le bord de la zone. Les distances le long de la côte sont étirées
    autour d'Étretat (Manneporte, Porte d'Aval, Porte d'Amont tiennent en 3 km, soit 12 blocs)."""
    X, Z, x0, z0 = grille(-0.12, 0.62, 49.42, 49.95)
    h, sd = T.hauteur_base(X, Z)
    db = sd * BPD / 60.0
    cote = Cote(X, Z, db, (49.58, 0.0))                             # abscisse du sud-ouest au nord-est
    S = cote.s
    hv, v = cote.s_de(49.512, 0.067), cote.s_de(49.7085, 0.2105)
    yp, fe, fa = cote.s_de(49.737, 0.315), cote.s_de(49.757, 0.374), cote.s_de(49.767, 0.39)
    haut = courbe(S, [(hv - 22, 0), (hv - 6, 16), (hv + 10, 21), (v - 30, 26), (v - 12, 27), (v - 4, 2), (v + 4, 2),
                      (v + 12, 25), (yp - 9, 25), (yp - 3, 3), (yp + 3, 3), (yp + 9, 23), (fe - 9, 24), (fe - 3, 2),
                      (fe + 4, 2), (fa, 19), (fa + 20, 17), (fa + 45, 8), (fa + 65, 0)])
    d_cote = cote.arbre.query(np.c_[X.ravel(), Z.ravel()])[0].reshape(X.shape)
    y, typ, sommet, e = falaise(X, Z, h, db, S, haut, pied=2.0, graine=11, retour=150.0)
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
    typ = parois(y, typ)
    travail = ((typ & (TAILLEE | REMBLAI)) > 0) & (f > 0.2)
    typ = finir_types(typ, travail)
    limite = cote.distance_troncon(X, Z, hv - 40, fa + 85) < 175
    en_tuiles("etretat", X, Z, y, h, sommet, typ, sd, vox=creux, limite=limite)


# ---------------------------------------------------------------- Moher

def moher():
    """Falaises de Moher, en tuiles (26/10). 8 km en vrai (32 blocs). La falaise naît dans la baie de Liscannor,
    monte à Hag's Head (120 m), culmine près de la tour d'O'Brien (214 m), redescend vers Doolin puis continue,
    plus basse, le long de la côte du Burren jusqu'à Fanore : plus de pan posé à pleine hauteur qui s'arrête net."""
    X, Z, x0, z0 = grille(-9.75, -9.05, 52.80, 53.22)
    h, sd = T.hauteur_base(X, Z)
    db = sd * BPD / 60.0
    cote = Cote(X, Z, db, (52.86, -9.50))                           # du sud (Spanish Point) vers le nord
    S = cote.s
    s_hag, s_tour, s_doolin = cote.s_de(52.95, -9.47), cote.s_de(52.9719, -9.4265), cote.s_de(53.017, -9.40)
    s_fanore = cote.s_de(53.12, -9.29)
    # au nord de Doolin (décidé avec Maxime le 26/10) : la côte rocheuse du Burren garde une falaise plus basse
    # jusqu'à Fanore, qui s'abaisse peu à peu ; la côte elle-même ne bouge pas (exagération des distances)
    haut = courbe(S, [(s_hag - 45, 0), (s_hag - 22, 9), (s_hag, 20), (s_tour - 5, 25), (s_tour + 5, 30),
                      (s_tour + 16, 28), (s_doolin - 4, 17), (s_doolin + 14, 11), (s_doolin + 45, 10),
                      (s_fanore - 8, 5), (s_fanore + 14, 0)])
    # seulement la côte principale (pas les îles d'Aran ni les îlots)
    d_cote = cote.arbre.query(np.c_[X.ravel(), Z.ravel()])[0].reshape(X.shape)
    haut = haut * (1 - lisse((d_cote - 18) / 10))
    y, typ, sommet, e = falaise(X, Z, h, db, S, haut, pied=0.0, graine=21, amp=3.5, retour=150.0, plongeante=True)
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
    typ = parois(y, typ)
    typ = finir_types(typ, ((typ & (TAILLEE | REMBLAI)) > 0) & (f > 0.2))
    limite = cote.distance_troncon(X, Z, s_hag - 70, s_fanore + 40) < 175
    en_tuiles("moher", X, Z, y, h, sommet, typ, sd, limite=limite)


# ---------------------------------------------------------------- Douvres

def douvres():
    """Falaises blanches de Douvres, en tuiles (26/10). ~100 m, faîte ondulé : la falaise commence à Folkestone
    (la côte plus à l'ouest est basse), falaise de Shakespeare, trouée de la Dour (la ville), falaises de l'est,
    baie de St Margaret, puis elle s'abaisse jusqu'à Kingsdown et Deal (côte basse)."""
    X, Z, x0, z0 = grille(0.95, 1.62, 50.95, 51.42)
    h, sd = T.hauteur_base(X, Z)
    db = sd * BPD / 60.0
    cote = Cote(X, Z, db, (51.07, 1.00))                            # d'ouest (Hythe) en est puis au nord (Deal)
    S = cote.s
    F, D, M, K = (cote.s_de(51.08, 1.17), cote.s_de(51.122, 1.312), cote.s_de(51.15, 1.385), cote.s_de(51.18, 1.40))
    haut = courbe(S, [(F - 24, 0), (F - 6, 6), (F + 11, 17), (F + 40, 22), (D - 35, 23), (D - 18, 19), (D - 10, 21),
                      (D - 6, 0), (D + 6, 0), (D + 12, 22), (D + 27, 24), (M - 5, 16), (M, 15), (M + 7, 20),
                      (K - 3, 13), (K + 7, 5), (K + 17, 0)])
    y, typ, sommet, e = falaise(X, Z, h, db, S, haut, pied=1.5, graine=31, amp=1.6, retour=150.0)
    y, f = fin_de_lieu(y, h, typ, X, Z)
    typ = parois(y, typ)
    typ = finir_types(typ, ((typ & (TAILLEE | REMBLAI)) > 0) & (f > 0.2))
    en_tuiles("douvres", X, Z, y, h, sommet, typ, sd)


# ---------------------------------------------------------------- dune du Pilat

def pilat():
    """Dune du Pilat, en tuiles (26/10) : une longue crête parallèle à la côte, de la passe du bassin d'Arcachon vers
    le sud, haute au Pilat puis abaissée en cordon dunaire (les dunes des Landes continuent vers le sud) au lieu
    de finir net. Face océan longue et douce, face forêt raide (pente d'éboulement du sable), crête vive.
    En vrai 2,9 km x 600 m x 105 m (12 x 2,5 blocs !) : ~320 x 90 blocs, 22 de haut au plus.
    Zone large (240 x 380) : la dune ne touche jamais le bord, rien n'est coupé en ligne droite."""
    x0, z0, W, D = -660, -19900, 240, 380
    X, Z = np.meshgrid(np.arange(x0, x0 + W, dtype=float), np.arange(z0, z0 + D, dtype=float))
    h, sd = T.hauteur_base(X, Z)
    db = sd * BPD / 60.0                                               # blocs depuis l'eau, + dans les terres
    # axe de la côte océane : x de la première terre depuis l'ouest, ligne par ligne, lissé
    terre = sd >= 0
    xc = np.array([X[k, np.argmax(terre[k])] if terre[k].any() else np.nan for k in range(D)])
    ok = ~np.isnan(xc); xc = np.interp(np.arange(D), np.flatnonzero(ok), xc[ok])
    xc = ndimage.gaussian_filter1d(xc, 10, mode="nearest")
    n = X - xc[:, None]                                                # blocs depuis l'axe de la côte, + vers l'est
    s = -44.589 * BPD - Z                                              # blocs le long de la côte, + vers le nord
    # hauteur de crête le long de la côte : bout nord raide face à la passe, plus haute au sud, puis cordon
    Hs = courbe(-s, [(-18, 0.0), (12, 17.0), (30, 20.0), (45, 18.5), (80, 22.0), (110, 19.5), (150, 11.0),
                     (200, 6.0), (250, 3.5), (300, 0.0)])
    Hs = Hs * (1 + 0.06 * bruit(X, Z, 60, 51))
    b = 7.0 + 2.0 * bruit(X, Z, 30, 52)                                # plage au pied
    larg_vent = 2.6 * Hs + 6.0                                         # face océan
    larg_abri = 1.25 * Hs + 3.0                                        # face forêt (~37°)
    nc = b + larg_vent + 3.0 * np.sin(s / 37.0) + 2.0 * bruit(X, Z, 45, 53)   # crête
    u = np.clip((n - b) / np.maximum(nc - b, 1), 0, 1)
    vent = 0.7 * u ** 1.3 + 0.3 * lisse(u)
    v = np.clip((n - nc) / np.maximum(larg_abri, 1), 0, 1)
    abri = (1 - v) ** 1.2
    forme = np.where(n < nc, vent, abri) * (n > b)
    rides = 0.35 * bruit(X, Z, 5.0, 54) * (n < nc) * forme * lisse(Hs / 4)
    dune = np.maximum(Hs * forme + rides, 0)
    y = np.where(terre, h + dune, h)
    typ = np.zeros(X.shape, np.int32)
    long_dune = Hs > 0.8
    plage = terre & long_dune & (db < b)
    y = np.where(plage, np.minimum(np.maximum(y, 63.5 + 0.4 * lisse(db / 4)), 64.4), y)
    # versant au vent en sable de la plage à la crête (sinon une bande d'herbe entre la plage et la dune)
    sable = terre & long_dune & ((dune > 0.3) | ((db >= b) & (n < nc))) & ~plage
    typ[sable] = DUNE | TAILLEE
    typ[plage] = SABLE | TAILLEE
    typ = finir_types(typ, sable | plage)
    sommet = y.copy()
    # colonnes sculptées de la tuile : le lieu et sa marge (biome compris) ; au-delà, terrain calculé
    actif = ndimage.binary_dilation(sable | plage | (dune > 0.02), iterations=10) & terre
    typ[~actif] = 0
    ecrites = tu.poser("pilat", x0, z0, y, sommet, typ, actif)
    np.savez_compressed("/tmp/lieu_pilat.npz", X=X, Z=Z, y=y, h=h, sommet=sommet, typ=typ, poids=actif.astype(float),
                        vox=np.zeros((0, 4), int))
    # contrôles : la dune ne touche pas le bord de la zone ; au bord des colonnes sculptées, y = terrain calculé
    bord_actif = actif & ndimage.binary_dilation(~actif & terre)
    frac = np.abs(y - np.round(y))
    print(f"pilat (tuiles {ecrites}) : {int(actif.sum())} colonnes, sol {y[terre].min():.1f} à {y.max():.1f}, "
          f"{int(((typ & TAILLEE) > 0).sum())} taillées | contrôles : écart au bord des colonnes sculptées "
          f"{np.abs(y - h)[bord_actif].max():.3f}, actif au bord de la zone {int(actif[bord_zone(X, Z, 1) < 2].sum())}, "
          f"{int(((frac < 0.02) & ((typ & TAILLEE) > 0)).sum())} colonnes taillées sur un entier")


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
    """Baie du Mont-Saint-Michel, en tuiles (26/10), sur la VRAIE baie (côte GSHHG) : plus de rivage dessiné à la main,
    ni de mer tenue de force, ni de ceinture de polders (ils compensaient le relief vanilla trop haut et la mer qui
    sortait de l'eau, réglés le 25-26/10). La baie = la mer en deçà de la ligne pointe du Grouin - Granville.
    Marée basse : estran de sable et de tangue, chenaux qui serpentent (Couesnon, Sée-Sélune), herbus, le Mont et
    Tombelaine (granite, exagérés)."""
    X, Z, x0, z0 = grille(-1.93, -1.30, 48.50, 48.87)
    h, sd = T.hauteur_base(X, Z)
    # ouverture de la baie : de la pointe du Grouin à la pointe du Roc (Granville) ; la baie est du côté du Mont
    a, b, mont = bloc_de(48.716, -1.843), bloc_de(48.834, -1.612), bloc_de(48.6361, -1.5115)
    t = (b - a) / np.linalg.norm(b - a); nrm = np.array([-t[1], t[0]])
    if (mont - a) @ nrm < 0:
        nrm = -nrm
    cote_baie = (X - a[0]) * nrm[0] + (Z - a[1]) * nrm[1]          # blocs depuis la ligne d'ouverture, + dans la baie
    mer = sd < 0
    lab, n = ndimage.label(mer & (cote_baie > 0))
    j0, i0 = int(round(mont[1] - z0)), int(round(mont[0] - x0))
    # la baie : la mer intérieure reliée au Mont (le Mont lui-même peut être une petite île de la carte)
    k = lab[max(j0 - 6, 0):j0 + 7, max(i0 - 6, 0):i0 + 7]
    k = np.bincount(k[k > 0]).argmax() if (k > 0).any() else 0
    dedans = lab == k if k else mer & (cote_baie > 0)
    # la côte GSHHG suit ici la pleine mer de trop près : le fond de la baie (grèves autour du Mont, à sec seulement à
    # marée basse) y est de la terre. On y ajoute la grève relevée sur la vraie géographie (RIVAGE), lissée.
    P = np.array([bloc_de(la, lo) for la, lo in RIVAGE])
    tt = np.r_[0, np.cumsum(np.hypot(*np.diff(P, axis=0).T))]
    fin = np.linspace(0, tt[-1], 600)
    lisse_p = np.c_[np.interp(fin, tt, ndimage.gaussian_filter1d(P[:, 0], 1.2)),
                    np.interp(fin, tt, ndimage.gaussian_filter1d(P[:, 1], 1.2))]
    greve = Path(np.r_[lisse_p, lisse_p[:1]]).contains_points(np.c_[X.ravel(), Z.ravel()]).reshape(X.shape)
    dedans = ndimage.binary_closing(dedans | (greve & (cote_baie > 0)), iterations=2) & (cote_baie > 0)
    d_rive = ndimage.distance_transform_edt(dedans)                  # distance au rivage, dans la baie
    d_ouvert = np.maximum(cote_baie, 0)                              # distance à l'ouverture sur la mer
    # estran : sable sec à y 63,5 près du fond de la baie, qui descend doucement vers le large (bords lobés)
    lobes = 14 * bruit(X, Z, 26, 51) + 6 * bruit(X, Z, 9, 52)
    vers_large = np.clip((38 - d_ouvert + lobes) / 40, 0, 1)         # 0 au fond de la baie, 1 près de l'ouverture
    estran = 63.6 - 4.2 * lisse(vers_large) ** 1.4
    # chenaux qui serpentent (Couesnon, Sée-Sélune), plus larges vers le large
    chenal = np.zeros(X.shape, bool); fond_chenal = np.full(X.shape, 99.0)
    for riv, g in ((COUESNON, 53), (SEE_SELUNE, 54)):
        d, sp = distance_polyligne(X, Z, riv)
        meandre = 5.0 * np.sin(sp / 13.0 + g) + 2.5 * bruit(X, Z, 15, g)
        d2, _ = distance_polyligne(X + meandre * 0.7, Z + meandre * 0.5, riv)
        larg = 1.6 + 2.2 * lisse(sp / 220)
        c = (d2 < larg) & dedans
        chenal |= c
        fond_chenal = np.where(c, np.minimum(fond_chenal, 60.4 - 0.8 * lisse(sp / 220)), fond_chenal)
    # mares : grandes et rares (pas de damier)
    mare = (bruit(X, Z, 11, 55) > 0.62) & (vers_large > 0.15) & dedans
    mare = ndimage.binary_opening(mare, iterations=2)
    # herbus (prés salés) le long du rivage, avec leur bord irrégulier
    herbus = dedans & (d_rive < 9 + 6 * bruit(X, Z, 19, 56)) & (vers_large < 0.55) & (d_ouvert > 24)
    y = np.where(dedans, np.maximum(estran, h), h)                   # l'estran ne creuse jamais sous le fond réel
    y = np.where(dedans & mare, np.minimum(y, 61.5), y)
    y = np.where(chenal, np.minimum(y, fond_chenal), y)
    y = np.where(herbus & ~chenal, 63.55 + 0.3 * lisse(d_rive / 4), y)  # jamais pile 64
    # vers le large, l'estran rejoint le fond réel en pente douce (pas de marche à la sortie de la baie)
    fondu = lisse(np.clip((cote_baie - 2) / 25, 0, 1))
    y = np.where(dedans, h + (y - h) * fondu, y)
    typ = np.zeros(X.shape, np.int32)
    tangue = (bruit(X, Z, 10, 57) > 0.35) & (vers_large > 0.1)
    typ[dedans] = np.where(tangue[dedans], VASE, SABLE)
    typ[dedans & (mare | chenal)] = CHENAL
    typ[herbus & ~chenal] = PRE
    sommet = np.full(X.shape, 63.0)
    # le Mont (granite, 80 m) et Tombelaine, exagérés : roc de ~16 blocs, 22 de haut, flancs raides
    roc = np.zeros(X.shape, bool)
    for (la, lo, R, Hm, rx) in [(48.6361, -1.5115, 8.5, 22.0, 1.15), (48.6757, -1.5669, 4.5, 8.0, 1.3)]:
        c = bloc_de(la, lo)
        r = np.hypot((X - c[0]) / rx, Z - c[1]) / R
        prof = 63.6 + Hm * np.clip(1 - r ** 2.2, 0, 1) ** 0.6 + bruit(X, Z, 3.5, 58) * 1.0 * (r < 0.85)
        m = (r < 1) & (prof > y)
        y = np.where(m, prof, y)
        typ = np.where(m, ROC, typ)
        sommet = np.where(m, prof, sommet)
        roc |= m
    travail = (dedans & (fondu > 0.05)) | roc
    typ[travail] |= TAILLEE
    typ[dedans] |= INONDE
    typ = finir_types(typ, travail)
    en_tuiles("mont_saint_michel", X, Z, y, h, sommet, typ, sd)


LIEUX = {"etretat": etretat, "moher": moher, "douvres": douvres, "pilat": pilat, "mont_saint_michel": mont_saint_michel}

if __name__ == "__main__":
    for n in (sys.argv[1:] or LIEUX):
        LIEUX[n]()

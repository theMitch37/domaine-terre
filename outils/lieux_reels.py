"""Lieux du lot 2 sur le RELIEF RÉEL (Copernicus DEM GLO-30, outils/donnees/relief_<lieu>.npz, et la grande grille
à 90 m relief_<lieu>_large.npz ; workflow « Relief des lieux ») : Gavarnie, Cervin, Tre Cime, Plitvice, Geiranger,
Preikestolen. (Gullfoss et Skógafoss, trop fins pour le modèle, restent dessinés : outils/lieux_montagne.py.)

Principe (27/10) :
- ZOOM uniforme : le relief réel est agrandi k fois autour d'un point d'ancrage qui reste à sa place dans le monde ;
  sur une bande de ~40 blocs au bord (bord irrégulier), le lieu rejoint le terrain du mod. Le fish-eye essayé avant
  (agrandi au centre, comprimé dans un anneau) faisait des cercles concentriques et tordait les fjords : abandonné ;
- fjords : l'ancrage est la jonction du fjord avec la mer du mod, si bien que le fjord agrandi en part dans la même
  direction ; la mer est ce qui reste sous le niveau de la mer après le raccord, reliée à la mer du mod (un bras
  coupé par le bord est rouvert par un détroit) ;
- hauteur : courbe du mod (blocs depuis l'altitude) sur le relief lissé + relief local exagéré de v blocs par mètre ;
  montagnes recalées en bloc sur la hauteur moyenne du mod au bord (ni marche ni fossé) ;
- l'eau : lacs = surfaces planes du modèle (Plitvice), cascades le long de la pente réelle (Sept Sœurs, Grande
  Cascade de Gavarnie), chaire de Preikestolen et Tre Cime sculptées à leur vraie place.
Usage : python3 outils/lieux_reels.py [lieu ...] [--apercu]
"""
import os, sys
import numpy as np
from scipy import ndimage
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import terre_py as T
import lieux_montagne as M
from lieux_montagne import crete
from lieux_cotiers import (bruit, bloc_de, lisse, PLATEAU, PLAGE, FOND, ROC, PRE, NEIGE, GLACE, EBOULIS, MOUSSE,
                           LIT, TAILLEE, BIOME, INONDE)

BPD = T.BPD
DONNEES = os.path.join(T.RACINE, "outils/donnees/")


class Grille:
    """Une grille d'altitudes (m) régulière en lon/lat."""

    def __init__(self, chemin):
        d = np.load(chemin)
        self.E = d["E"].astype(np.float64)
        self.lon0, self.lat0 = float(d["lon0"]), float(d["lat0"])
        self.plon, self.plat = float(d["pas_lon"]), float(d["pas_lat"])
        self.lisses = {}

    def indices(self, lon, lat):
        return (self.lat0 - lat) / self.plat - 0.5, (lon - self.lon0) / self.plon - 0.5

    def dedans(self, lon, lat, marge=2):
        r, c = self.indices(lon, lat)
        return (r > marge) & (r < self.E.shape[0] - 1 - marge) & (c > marge) & (c < self.E.shape[1] - 1 - marge)

    def ech(self, lon, lat, sigma_m=0.0, ordre=1):
        g = self.E
        if sigma_m > 0:
            if sigma_m not in self.lisses:
                sy = sigma_m / (self.plat * 111320)
                sx = sigma_m / (self.plon * 111320 * np.cos(np.radians(self.lat0)))
                self.lisses[sigma_m] = ndimage.gaussian_filter(self.E, (sy, sx), mode="nearest")
            g = self.lisses[sigma_m]
        r, c = self.indices(lon, lat)
        return ndimage.map_coordinates(g, [r, c], order=ordre, mode="nearest")


class Relief:
    """Modèle numérique de terrain d'un lieu : grille fine (30 m) autour du site et, si elle existe, grande grille
    (90 m, relief_<lieu>_large.npz) pour l'anneau de la loupe."""

    def __init__(self, nom):
        self.fin = Grille(DONNEES + f"relief_{nom}.npz")
        large = DONNEES + f"relief_{nom}_large.npz"
        self.large = Grille(large) if os.path.exists(large) else None
        self.E, self.lon0, self.lat0, self.plon, self.plat = (self.fin.E, self.fin.lon0, self.fin.lat0, self.fin.plon,
                                                              self.fin.plat)

    def indices(self, lon, lat):
        return self.fin.indices(lon, lat)

    def fin_valide(self, lon, lat):
        """Hors des dalles téléchargées, la grille fine vaut 0 (bandes vides) : on y prend la grande grille, sauf en
        mer où les deux valent 0."""
        if not hasattr(self, "_val"):
            self._val = (self.fin.E != 0).astype(np.float64)
        r, c = self.fin.indices(lon, lat)
        v = ndimage.map_coordinates(self._val, [r, c], order=1, mode="nearest")
        return (v > 0.99) | (self.large.ech(lon, lat) <= 0.5)

    def couvre(self, lon, lat):
        m = self.fin.dedans(lon, lat)
        return m | self.large.dedans(lon, lat) if self.large is not None else m

    def ech(self, lon, lat, sigma_m=0.0, ordre=1):
        """Altitude interpolée (grille fine, sinon la grande) ; sigma_m > 0 : relief lissé."""
        if sigma_m > 0 and self.large is not None:
            return self.large.ech(lon, lat, sigma_m, ordre)
        v = self.fin.ech(lon, lat, sigma_m, ordre)
        if self.large is None:
            return v
        m = self.fin.dedans(lon, lat) & self.fin_valide(lon, lat)
        if m.all():
            return v
        return np.where(m, v, self.large.ech(lon, lat, 0.0, ordre))

    def plats(self, min_cases=30):
        """Surfaces d'eau aplanies par Copernicus (lacs, mer) : étiquettes et altitude de chacune (grille fine)."""
        E = self.E
        eq = np.ones(E.shape, bool)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                eq &= np.roll(np.roll(E, dy, 0), dx, 1) == E
        lab, n = ndimage.label(eq)
        tailles = ndimage.sum(np.ones_like(E), lab, range(1, n + 1))
        garder = np.flatnonzero(tailles >= min_cases) + 1
        lab = np.where(np.isin(lab, garder), lab, 0)
        lab = ndimage.grey_dilation(lab, size=3) * (ndimage.grey_dilation(lab, size=3) > 0)
        niveaux = {int(k): float(np.median(E[lab == k])) for k in np.unique(lab) if k}
        return lab, niveaux


class Zoom:
    """Zoom uniforme : le relief réel est agrandi k fois autour d'un point d'ancrage A (lat_a, lon_a), qui reste à sa
    place dans le monde ; le lieu couvre le rectangle [x0, x1] x [z0, z1] (blocs, relatifs à A) et rejoint le terrain
    du mod (à la position même des colonnes) sur une bande de « fondu » blocs le long du bord.
    Pas de fish-eye : celui-ci écrasait le relief dans l'anneau (cercles concentriques, fjords tordus en anneau).
    Pour un fjord, A est pris à la jonction avec la mer du mod : le fjord agrandi part de là dans la même direction que
    celui du mod, et l'eau se raccorde d'elle-même."""

    def __init__(self, lat_a, lon_a, k, x0, x1, z0, z1, fondu=40, iso=True):
        c = bloc_de(lat_a, lon_a)
        self.c, self.k, self.lat_c, self.lon_c, self.fondu = c, k, lat_a, lon_a, fondu
        xs = np.arange(int(np.floor(c[0] + x0)), int(np.floor(c[0] + x1)), dtype=float)
        zs = np.arange(int(np.floor(c[1] + z0)), int(np.floor(c[1] + z1)), dtype=float)
        self.X, self.Z = np.meshgrid(xs, zs)
        self.f0 = np.cos(np.radians(lat_a)) if iso else 1.0
        self.Xr = c[0] + (self.X - c[0]) / (k * self.f0)
        self.Zr = c[1] + (self.Z - c[1]) / k
        self.lo, self.la = self.Xr / BPD, -self.Zr / BPD
        self.h, self.sd = T.hauteur_base(self.X, self.Z)
        self.hr, self.sdr = self.h, self.sd
        H, W = self.X.shape
        jj, ii = np.mgrid[0:H, 0:W]
        self.de = np.minimum(np.minimum(ii, W - 1 - ii), np.minimum(jj, H - 1 - jj)).astype(float)
        # bord irrégulier (pas de raccord en ligne droite le long du rectangle)
        self.den = np.maximum(self.de - 14 * (0.5 + 0.5 * bruit(self.X, self.Z, 22, 977)), 0)
        self.t = 1 - lisse(np.clip(self.den / fondu, 0, 1))

    def vers_blocs(self, lat, lon):
        return np.array([self.c[0] + (lon * BPD - self.c[0]) * self.k * self.f0,
                         self.c[1] + (-lat * BPD - self.c[1]) * self.k])

    def couvert(self, R, marge=3):
        return R.couvre(self.lo, self.la)

    def raccord(self, y_reel, cov, terre=None, sigma=40.0):
        """Correction douce du relief agrandi vers le terrain du mod : l'écart (mod - lieu) mesuré sur la bande du
        bord est prolongé vers l'intérieur par une moyenne pondérée très lissée ; ajoutée au relief, elle le fait
        rejoindre le mod sans marche ni fossé, et sans toucher au relief local (pentes, pitons). terre : où l'appliquer
        (pas à la mer, dont le niveau ne bouge pas)."""
        terre = np.ones(y_reel.shape, bool) if terre is None else terre
        a = lisse(np.clip((self.den - 4) / (self.fondu - 4), 0, 1))
        bande = cov & (a > 0.05) & (a < 0.95) & terre & (self.h > 63.5)
        num = ndimage.gaussian_filter(np.where(bande, self.h - y_reel, 0.0), sigma)
        den = ndimage.gaussian_filter(bande.astype(float), sigma)
        moy = float(np.mean((self.h - y_reel)[bande])) if bande.any() else 0.0
        D = np.where(den > 1e-3, num / np.maximum(den, 1e-3), moy)
        D = D * np.clip(den / 0.02, 0, 1) + moy * (1 - np.clip(den / 0.02, 0, 1))
        print(f"  raccord au mod : écart moyen {moy:+.1f} blocs (de {D[terre].min():+.1f} à {D[terre].max():+.1f})")
        return np.where(terre, y_reel + D, y_reel)

    def melange(self, y_reel, cov, recale=False):
        """Relief réel agrandi à l'intérieur, terrain du mod sur la bande du bord. recale : le relief du lieu est
        décalé (en bloc) à la hauteur moyenne du mod sur la bande du bord, pour que le raccord ne fasse ni marche ni
        fossé tout autour."""
        a = np.where(cov, lisse(np.clip((self.den - 4) / (self.fondu - 4), 0, 1)), 0.0)
        a = ndimage.gaussian_filter(a, 2.0)
        if recale:
            bande = cov & (a > 0.1) & (a < 0.9) & (self.h > 63.5) & (y_reel > 63.5)
            dy = float(np.median((self.h - y_reel)[bande]))
            y_reel = y_reel + dy
            print(f"  relief recalé de {dy:+.1f} blocs sur le mod")
        return y_reel * a + self.h * (1 - a), a

    def emprise(self, fleuves=True):
        """Part du lieu (classes du sol) : 1 à l'intérieur, 0 au bord."""
        w = 1 - self.t
        return M.loin_des_fleuves(self.X, self.Z, w) if fleuves else w

    def bord(self):
        """Dernier raccord au terrain du mod (10 blocs), à 13 blocs du bord de la zone (marge des colonnes sculptées : 10)."""
        return lisse(np.clip((self.de - 13) / 10, 0, 1))


def couverture(nom, lon, lat):
    """Couverture du sol ESA WorldCover (outils/donnees/couverture_<nom>.npz) aux positions réelles : 70 = neige et
    glace, 80 = eau, 10 = arbres, 60 = sol nu, 30 = herbe."""
    d = np.load(DONNEES + f"couverture_{nom}.npz")
    C = d["C"]
    i = np.clip(((lon - float(d["lon0"])) / float(d["pas_lon"])).astype(int), 0, C.shape[1] - 1)
    j = np.clip(((float(d["lat0"]) - lat) / float(d["pas_lat"])).astype(int), 0, C.shape[0] - 1)
    return C[j, i]


def relief_exagere(R, lo, la, v, sigma_m=1500.0, dy=0.0):
    E = R.ech(lo, la)
    Es = R.ech(lo, la, sigma_m)
    return T.blocs(Es) + dy + (E - Es) * v, E, Es


def classes_montagne(X, Z, y, E, neige=3000.0, glace=None, eboulis=(2300.0, 3300.0), herbe_max=2600.0, roc=1.0,
                     pente_glace=0.55, pente_neige=0.9, pente_herbe=0.6):
    pl = M.pente_locale(y)
    lisse_y = ndimage.gaussian_filter(y, 1.5)
    rugo = np.abs(y - lisse_y)
    typ = np.full(X.shape, PRE | TAILLEE, np.int32)
    typ[(E > herbe_max) | (pl > pente_herbe)] = EBOULIS | TAILLEE
    typ[(E > eboulis[1]) & (pl <= roc)] = EBOULIS | TAILLEE
    n = (E > neige + 120 * bruit(X, Z, 9, 901)) & (pl <= pente_neige)
    typ[n] = NEIGE | TAILLEE
    if glace is not None:
        typ[(E > glace + 80 * bruit(X, Z, 11, 902)) & (pl < pente_glace) & (rugo < 0.35 + 0.3 * pente_glace)] = GLACE | TAILLEE
    typ[pl > roc] = ROC | TAILLEE
    typ[n & (pl > roc) & (pl <= pente_neige)] = NEIGE | TAILLEE
    return typ


def finir_loupe(nom, L, y, typ, eau, palette, roc=1.0, w_typ=None, garder_fleuves=True, vox=None):
    """Écriture d'un lieu à la loupe : y est déjà raccordé (relief réel -> terrain du mod) ; dernier fondu au bord
    et loin des vallées des cours d'eau du mod ; le sol redevient celui du mod vers le bord."""
    X, Z, h, sd = L.X, L.Z, L.h, L.sd
    wy = np.minimum(L.bord(), M.loin_des_fleuves(X, Z, np.ones(X.shape))) if garder_fleuves else L.bord()
    wy = np.where(np.isfinite(eau), 1.0, wy)
    y = h + (y - h) * wy
    w = L.emprise(garder_fleuves) if w_typ is None else w_typ
    pl = M.pente_locale(y)
    vers_mod = (w < 0.55 + 0.3 * bruit(X, Z, 7, 990)) & (pl <= roc) & ~np.isfinite(eau) & ((typ & 15) != FOND)
    typ = np.where(vers_mod, PRE | TAILLEE, typ)
    typ = typ | BIOME
    typ[(wy < 0.02) & ~np.isfinite(eau)] = 0
    sommet = y.copy()
    return M.ecrire(nom, X, Z, y, h, sommet, typ, sd, eau, palette, garder_fleuves=garder_fleuves, vox=vox)


# blocs particuliers posés par le lieu (fichier .vox, classe >= 100 : voir LieuGrille.poser)
VOX_LAVE, VOX_FUMEROLLE, VOX_GEYSER, VOX_MAGMA = 100, 101, 102, 103


def cratere(X, Z, y, c, r, prof, rebord=3.0, graine=0, ovale=1.0):
    """Cratère : rebord relevé, parois raides, fond plat ; rend y, masque intérieur, masque du fond, y du fond."""
    dx, dz = X - c[0], (Z - c[1]) * ovale
    rr = np.hypot(dx, dz) / (r * (1 + 0.08 * bruit(X, Z, 4, graine)))
    yc = float(np.median(y[rr < 1.3]))
    haut_rebord = yc + rebord
    fond_y = np.floor(haut_rebord - prof) + 0.6
    paroi = np.clip((1 - rr) / 0.45, 0, 1)
    y_in = haut_rebord - (haut_rebord - fond_y) * lisse(paroi) + 0.6 * bruit(X, Z, 2, graine + 1)
    anneau = np.clip(1 - np.abs(rr - 1.05) / 0.5, 0, 1)
    y = np.where(rr < 1.0, y_in, np.maximum(y, y + (haut_rebord - y) * lisse(anneau)))
    return y, rr < 1.0, rr < 0.55, fond_y


def reprendre_riviere(L, y, seuil=0.3):
    """Une rivière du mod qui traverse le lieu agrandi n'y est pas à sa place (elle couperait le relief d'une
    tranchée droite) : le lieu la reprend (écrire avec garder_fleuves=False). Il garde son lit et sa vallée sur la
    bande du bord (là où le lieu redevient le terrain du mod) et la fait naître d'une vasque au pied des montagnes
    agrandies. Rend y, eau, (niveau de la vasque, colonnes de lit) ou None sans rivière."""
    X, Z = L.X, L.Z
    eau = np.full(X.shape, np.nan)
    pres, d_r, hw, _, _, w_r = T.rivieres(X, Z)
    lit = pres & (d_r <= hw)
    if not lit.any():
        return y, eau, None
    # le lit s'amincit en pointe vers l'amont (pas de bout coupé net)
    effile = np.clip((L.t - seuil) / 0.25, 0, 1)
    aval = pres & (d_r <= np.maximum(hw * effile, 0.6 * (effile > 0))) & (L.t > seuil)
    eau_mod = np.where(aval, w_r.astype(float), np.nan)
    d_l = ndimage.distance_transform_edt(~aval)
    y = np.where(d_l < 40, np.minimum(y, L.h + (y - L.h) * lisse(np.clip((d_l - 2) / 30, 0, 1))), y)
    garde = aval                     # jusqu au bord : le lit du lieu continue celui du mod
    eau = np.where(garde, eau_mod, eau)
    # tronçons gardés d'une même rivière du mod (reliés dans le mod à travers la zone) : la rivière qui entre dans
    # le lieu en ressort ; on la fait couler de l'un à l'autre par le fond des vallées agrandies (sinon elle se
    # perdrait dans la montagne). Un tronçon seul naît d'une vasque.
    lab, n = ndimage.label(garde, structure=np.ones((3, 3)))
    riv_lab, _ = ndimage.label(lit | garde, structure=np.ones((3, 3)))
    bouts = []                                                  # (rivière, niveau du bout intérieur, j, i)
    for k in range(1, n + 1):
        ja, ia = np.nonzero(lab == k)
        ka = int(np.argmin(L.t[ja, ia]))
        bouts.append((int(riv_lab[ja[ka], ia[ka]]), float(eau_mod[ja[ka], ia[ka]]), ja[ka], ia[ka]))
    relies = set()
    for r in {b_[0] for b_ in bouts}:
        br = sorted([b_ for b_ in bouts if b_[0] == r], key=lambda b_: -b_[1])
        for amont, aval_ in zip(br[:-1], br[1:]):
            p0 = np.array([X[amont[2], amont[3]], Z[amont[2], amont[3]]])
            p1 = np.array([X[aval_[2], aval_[3]], Z[aval_[2], aval_[3]]])
            tr = talweg(y, p0, p1, X, Z)
            y, eau, tr, _, _, Lr, _ = riviere_sur_relief(X, Z, y, eau, tr, amont[1], lambda s_: np.full(np.shape(s_), 2.2),
                                                         prof=1.2, niv_min=aval_[1], pente=0.8, large=30)
            relies |= {(amont[2], amont[3]), (aval_[2], aval_[3])}
            print(f"  rivière du mod reliée à travers le lieu : y {amont[1]:.0f} -> {aval_[1]:.0f} sur {Lr:.0f} blocs")
    for (_, niv, j, i) in bouts:
        if (j, i) in relies:
            continue
        src = np.hypot(X - X[j, i], Z - Z[j, i]) < 1.8
        eau = np.where(src, niv, eau)
        y = np.where(src, np.minimum(y, niv - 2.0), y)
    return y, eau, (float(np.nanmax(eau)), int(garde.sum()))


def cervin():
    """Cervin (4 478 m) sur le relief réel, agrandi 4 fois au centre (loupe) : la vraie pyramide, ses arêtes (Hörnli,
    Zmutt, Lion, Furggen), ses faces et les glaciers autour ; relief local exagéré. Au bord, le relief du mod."""
    R = Relief("cervin")
    L = Zoom(45.9763, 7.6586, 4.0, -190, 190, -135, 85, fondu=45)
    y_r, E, Es = relief_exagere(R, L.lo, L.la, v=0.048, sigma_m=1800.0)
    y_r = L.raccord(y_r, L.couvert(R))
    y, a = L.melange(y_r, L.couvert(R))
    typ = classes_montagne(L.X, L.Z, y, np.where(a > 0.05, E, 0), neige=3150, glace=2750, eboulis=(2400, 3300),
                           herbe_max=2550, roc=1.1, pente_glace=1.0, pente_neige=1.3)
    print(f"cervin : sommet y {y.max():.0f} (relief réel {E.max():.0f} m)")
    return finir_loupe("cervin", L, y, typ, np.full(L.X.shape, np.nan), "CERVIN", roc=1.1)


def glacier_vivant(X, Z, y, G, graine=0, profondeur=3.0, pas_crev=6.5):
    """Surface d'un glacier : crevasses en travers de l'écoulement (sillons d'un bloc, 3 à 5 de profondeur) là où la
    pente tire la glace, séracs en blocs dans les chutes de séracs (pente forte). G : masque du glacier."""
    ys = ndimage.gaussian_filter(y, 8.0)
    gz, gx = np.gradient(ys)
    n = np.hypot(gx, gz) + 1e-9
    ux, uz = -gx / n, -gz / n                                  # vers l'aval
    pl = M.pente_locale(ndimage.gaussian_filter(y, 1.0))
    interieur = ndimage.distance_transform_edt(G) > 2.5
    phi = (X * ux + Z * uz) / pas_crev + 0.35 * bruit(X, Z, 9, graine + 1) + 0.15 * bruit(X, Z, 3, graine + 2)
    sillon = (phi - np.floor(phi)) < 0.16
    crev = G & interieur & sillon & (pl > 0.22) & (bruit(X, Z, 5, graine + 3) > -0.25)
    prof = profondeur + 2.0 * (bruit(X, Z, 4, graine + 4) > 0.2)
    y = np.where(crev, y - prof, y)
    # séracs : la glace se casse en blocs de 3 x 3 décalés de 0 à 4 blocs
    cel = (np.floor(X / 3) * 7919 + np.floor(Z / 3) * 104729 + graine) % 997 / 997.0
    serac = G & interieur & (pl > 1.25) & (bruit(X, Z, 6, graine + 5) > -0.2)
    y = np.where(serac, y + np.floor(cel * 5) - 2.0, y)
    return y, crev, serac


def mer_de_glace():
    """Mer de Glace (massif du Mont-Blanc) sur le relief réel agrandi 4 fois : le glacier (masque glace d'ESA
    WorldCover) descend des Grandes Jorasses et du col du Géant jusqu'au Montenvers, entre les Aiguilles de Chamonix et
    les Drus ; crevasses en travers, séracs du Géant, langue couverte d'éboulis, moraines latérales du relief réel.
    Les rivières du mod qui traversent la zone (Arve, Doire) sont reprises : elles naissent sur la bande du bord."""
    R = Relief("mer_de_glace")
    L = Zoom(45.885, 6.935, 4.0, -235, 125, -200, 200, fondu=45)    # à l est, le Cervin (x 3224)
    X, Z = L.X, L.Z
    v = 0.04
    y_r, E, Es = relief_exagere(R, L.lo, L.la, v=v, sigma_m=1800.0)
    C = couverture("mer_de_glace", L.lo, L.la)
    # la surface d'un glacier est lisse et bombée : sur la glace, le relief local est pris lissé (plus de bosses du
    # modèle exagérées)
    Eg = R.ech(L.lo, L.la, 250.0)
    glace0 = ndimage.gaussian_filter((C == 70).astype(float), 1.5)
    y_r = y_r + (T.blocs(Es) + (Eg - Es) * v - y_r) * glace0
    y_r = L.raccord(y_r, L.couvert(R))
    y, a = L.melange(y_r, L.couvert(R))
    G = (C == 70) & (a > 0.3)
    G = ndimage.binary_opening(G, iterations=1)
    lab, n = ndimage.label(G)
    if n:
        t_ = ndimage.sum(np.ones(G.shape), lab, range(1, n + 1))
        G = np.isin(lab, np.flatnonzero(t_ >= 40) + 1)
    y, crev, serac = glacier_vivant(X, Z, y, G, graine=1200)
    y, eau, riv = reprendre_riviere(L, y, seuil=0.45)
    Ea = np.where(a > 0.05, E, 0)
    typ = classes_montagne(X, Z, y, Ea, neige=99999, glace=None, eboulis=(2300, 3500), herbe_max=2300, roc=1.25,
                           pente_herbe=1.0)
    pl = M.pente_locale(y)
    # sous 2 100 m, les versants sont boisés (forêts de la vallée de Chamonix) : herbe sauf les vraies falaises
    typ[(Ea > 0) & (Ea < 2100 + 100 * bruit(X, Z, 9, 1211)) & (pl < 1.6)] = PRE | TAILLEE
    typ[G] = GLACE | TAILLEE                                            # glace nue (zone d'ablation)
    typ[G & (Ea > 2800 + 120 * bruit(X, Z, 10, 1210)) & (pl < 1.3)] = NEIGE | TAILLEE   # névés (zone d'accumulation)
    typ[G & (Ea < 1750) & ~crev] = EBOULIS | TAILLEE                    # langue noire de débris
    typ[G & (pl > 1.7) & ~serac] = ROC | TAILLEE
    typ[np.isfinite(eau)] = LIT | TAILLEE
    print(f"mer_de_glace : glacier {int(G.sum())} colonnes, {int(crev.sum())} de crevasses, {int(serac.sum())} de séracs, "
          f"sommets jusqu'à y {y.max():.0f}" + (f", rivière du mod reprise ({riv[1]} colonnes)" if riv else ""))
    return finir_loupe("mer_de_glace", L, y, typ, eau, "GRANITE", roc=1.25, garder_fleuves=False)


def jokulsarlon():
    """Jökulsárlón (Islande) sur le relief réel agrandi 4 fois (zoom « carte » ancré sur l'embouchure, comme un
    fjord) : la lagune glaciaire au niveau de la mer, reliée à l'océan par la Jökulsá ; le front du Breiðamerkurjökull
    qui vêlera dans la lagune, ses moraines sombres ; des icebergs dans la lagune et échoués sur la plage de sable
    noir (Diamond Beach) ; sandur noir et mousses autour."""
    R = Relief("jokulsarlon")
    C_ = lambda L_: couverture("jokulsarlon", L_.lo, L_.la)
    L, E, y, eau, F = fjord_reel(R, 64.045, -16.177, 4.0, -250, 125, -220, 95, v=0.05, sigma_m=900.0, fondu=65,
                                 eau_reelle=lambda L_: C_(L_) == 80)
    X, Z = L.X, L.Z
    C = C_(L)
    a = L.bord()
    # le mod (relief lissé à 3') monte vite de la côte au Vatnajökull : le lieu agrandi, resté bas, y ferait un trou
    # bordé de murs. Les terres du lieu sont relevées vers le mod en s'éloignant de l'eau (la côte et la lagune restent
    # au niveau de la mer) : le glacier monte vers l'intérieur, comme en vrai mais plus vite
    dW0 = ndimage.distance_transform_edt(~F)
    terre = ~F
    ecart = np.where(terre, L.h - y, 0.0)
    poids_ = ndimage.gaussian_filter(terre.astype(float), 25) + 1e-6
    D = ndimage.gaussian_filter(ecart, 25) / poids_
    # 11/11/2026 : le relevé ne dépasse jamais le terrain du mod (ni le terrain d'avant) : lissé sur 25 blocs, il
    # débordait dans la bande de raccord, où le lieu rejoint déjà le mod, et y faisait une crête de 4 à 10 blocs le
    # long des bords de la zone (un cadre rectangulaire autour du lieu)
    y = np.where(terre, np.minimum(y + np.maximum(D, 0) * lisse(np.clip((dW0 - 3) / 45, 0, 1)), np.maximum(y, L.h)), y)
    # au large, le fond de la mer du mod (pas de cuvette rectangulaire plus profonde que lui)
    au_large = F & (ndimage.distance_transform_edt(L.sd >= 0) <= 15)
    dRive = ndimage.distance_transform_edt(F)
    fond_cote = np.minimum(61.9 - 0.35 * dRive, np.where(L.sd < 0, np.maximum(L.h, 40.0), 61.9))
    # (11/11/2026 : effacé vers le bord de la zone ; il y faisait une marche de 18 blocs sous la mer)
    y = np.where(au_large, y + (np.maximum(y, np.minimum(fond_cote, 61.9)) - y) * a, y)
    # lagune / mer : la lagune est l'eau du lieu qui n'est pas la mer du mod au large
    dIn = ndimage.distance_transform_edt(F)
    lagune = F & (L.sd >= 0)
    # glacier : glace (couverture) ; son front domine la lagune de 6 à 9 blocs
    G = (C == 70) & ~F
    # 08/11/2026 : le glacier s'arrêtait net au bord du lieu (mur de glace face au terrain du mod) ; il finit
    # maintenant en bordure irrégulière, 30 à 55 blocs avant le bord de la zone, sur sa moraine
    # 11/11/2026 (« glacier carré ») : cette bordure suivait le bord de la zone à 42-54 blocs, donc en lignes droites
    # parallèles à ses côtés. Elle ondule maintenant fort (lobes de 20 à 80 blocs) et ses coins sont arrondis.
    G &= L.de > 40.0 + 22.0 * (0.5 + 0.5 * bruit(X, Z, 22, 1305)) + 5.0 * bruit(X, Z, 7, 1307)
    G = ndimage.binary_opening(G, iterations=4)
    dW = ndimage.distance_transform_edt(~F)
    # 11/11/2026 (« glacier carré » : plateau de glace aux flancs verticaux) : la glace s'amincit vers ses bords sur
    # terre (langue bombée qui se pose sur sa moraine) ; seul le front dans la lagune reste une falaise
    dBord = ndimage.distance_transform_edt(G | (F & (dW <= 2)))
    amincit = lisse(np.clip((dBord - 1) / 14.0, 0, 1))
    surface = 69.0 + 1.5 * bruit(X, Z, 5, 1301) + 0.12 * np.maximum(dW - 1, 0)
    y = np.where(G, y + np.maximum(surface - y, 0) * amincit, y)
    y, crev, serac = glacier_vivant(X, Z, y, G, graine=1300, profondeur=2.0, pas_crev=5.0)
    # icebergs : blocs de glace dans la lagune (plus gros près du front), quelques-uns échoués sur la plage
    rng = np.random.default_rng(1302)
    ice = np.zeros(X.shape, bool)
    dG = ndimage.distance_transform_edt(~G)
    jj, ii = np.nonzero(lagune & (dIn > 1.5))
    n_ib = 0
    if len(jj):
        for k in rng.choice(len(jj), size=min(len(jj), 140), replace=False):
            j, i = jj[k], ii[k]
            pres = np.clip(1 - dG[j, i] / 120, 0.15, 1)
            if rng.random() > 0.35 + 0.65 * pres:
                continue
            r = 1.0 + rng.random() * (1.5 + 3.0 * pres)
            hgt = 1.0 + rng.random() * (1.5 + 4.5 * pres)
            nn = np.hypot((X - X[j, i]) / r, (Z - Z[j, i]) / (r * (0.6 + 0.8 * rng.random())))
            m = (nn < 1) & F
            y = np.where(m, np.maximum(y, 63.0 + hgt * (1 - 0.5 * nn ** 2) + 0.4 * bruit(X, Z, 1.5, 1303)), y)
            ice |= m
            n_ib += 1
    # plage noire au bord de la mer, icebergs échoués (Diamond Beach)
    plage = ~F & ~G & (dW <= 7) & (L.sd < 6) & (y < 66)
    jp, ip = np.nonzero(plage & (dW <= 2))
    for k in (rng.choice(len(jp), size=min(len(jp), 45), replace=False) if len(jp) else []):
        r = 0.8 + rng.random() * 1.4
        m = np.hypot(X - X[jp[k], ip[k]], Z - Z[jp[k], ip[k]]) < r
        y = np.where(m, np.maximum(y, 64.0 + 0.5 + rng.random() * 1.8), y)
        ice |= m
    eau = np.where(ice, np.nan, eau)
    pl = M.pente_locale(y)
    typ = np.full(X.shape, PLAGE | TAILLEE, np.int32)                   # sandur : sable et graviers noirs
    typ[(C == 100) | ((C == 30) & (bruit(X, Z, 6, 1304) > -0.3))] = MOUSSE | TAILLEE
    typ[(C == 30) & (y > 75)] = PRE | TAILLEE
    typ[(pl > 0.9) & ~G] = EBOULIS | TAILLEE
    typ[(pl > 1.4) & ~G] = ROC | TAILLEE
    # 08/11/2026 : en montant vers le Vatnajökull, la neige comme sur le terrain du mod autour (le lieu restait vert
    # jusqu'à son bord, face aux plaines enneigées : un carré vert visible de loin)
    typ[~G & (y > 95.0 + 10.0 * bruit(X, Z, 12, 1306)) & (pl < 1.4)] = NEIGE | TAILLEE
    typ[G] = GLACE | TAILLEE
    typ[G & (C != 70)] = EBOULIS | TAILLEE                              # moraines médianes sombres
    typ[plage] = PLAGE | TAILLEE
    typ[F] = FOND | TAILLEE
    typ[ice] = GLACE | TAILLEE
    print(f"jokulsarlon : lagune {int(lagune.sum())} colonnes, glacier {int(G.sum())}, {n_ib} icebergs, "
          f"plage {int(plage.sum())}, sommets y {y.max():.0f}")
    return finir_loupe("jokulsarlon", L, y, typ, eau, "ISLANDE", roc=1.4)


def chaussee():
    """Chaussée des Géants (Irlande du Nord) sur le relief réel de la côte d'Antrim agrandi 5 fois (zoom « carte »
    ancré sur la Chaussée, comme un fjord) : falaises de basalte exagérées, et la Chaussée sculptée à sa place :
    ~40 000 colonnes hexagonales en vrai, ici des prismes de 3 blocs qui descendent en gradins du pied de la falaise
    jusque sous la mer (les dernières affleurent), fentes entre les colonnes."""
    R = Relief("chaussee")
    L, E, y, eau, F = fjord_reel(R, 55.2408, -6.5116, 5.0, -210, 210, -130, 115, v=0.16, sigma_m=600.0, fondu=45, fond_mod=True, raccord=True,
                                 eau_reelle=lambda L_: couverture("chaussee", L_.lo, L_.la) == 80)
    X, Z = L.X, L.Z
    C = couverture("chaussee", L.lo, L.la)
    # falaises : là où les terres sont hautes près de la mer, le rivage tombe à pic (orgues de basalte) au lieu de
    # descendre en pente douce ; les baies basses gardent leurs plages
    dF = ndimage.distance_transform_edt(~F)
    terre = ~F
    # la côte d'Antrim est un plateau de basalte de 60 à 100 m qui tombe dans la mer : hauteurs doublées près de la mer
    amp = 1.0 + 1.0 * lisse(np.clip(1 - dF / 90, 0, 1)) * (1 - L.t)
    y = np.where(terre, 63.6 + (y - 63.6) * amp, y)
    haut_int = ndimage.gaussian_filter(ndimage.maximum_filter(np.where(terre, y, 0), size=17), 3)
    marge_f = np.clip((haut_int - 63.0 - 5.0) / 4.0, 0, 1)
    y = np.where(terre, y + (np.maximum(haut_int - 1.5 + 1.0 * bruit(X, Z, 4, 1402), y) - y) * marge_f *
                 lisse(np.clip(1 - (dF - 1) / 9, 0, 1)) * (L.bord() > 0.3), y)
    # rivage le plus proche de la vraie Chaussée, et la direction du large
    q = L.vers_blocs(55.2408, -6.5116)
    jj, ii = np.nonzero(~F & (dF <= 1.0))
    pts = np.c_[X[jj, ii], Z[jj, ii]]
    p0 = pts[int(np.argmin(np.hypot(pts[:, 0] - q[0], pts[:, 1] - q[1])))]
    gz, gx = np.gradient(ndimage.gaussian_filter(dF, 3))
    j0, i0 = int(p0[1] - Z[0, 0]), int(p0[0] - X[0, 0])
    n = -np.array([gx[j0, i0], gz[j0, i0]]); n /= np.linalg.norm(n) + 1e-9          # vers le large
    t = np.array([-n[1], n[0]])
    u = (X - p0[0]) * n[0] + (Z - p0[1]) * n[1]
    v = (X - p0[0]) * t[0] + (Z - p0[1]) * t[1]
    # la Chaussée : une langue de colonnes qui part du pied de la falaise vers le large
    lg = 26.0
    larg_l = 9.0 * np.clip(1.1 - (u + 3) / (lg + 8), 0.3, 1) + 3.0 * bruit(X, Z, 6, 1401) + 1.5 * bruit(X, Z, 2.5, 1403)
    langue = (u > -3) & (u < lg + 3 * bruit(X, Z, 4, 1404)) & (np.abs(v - 4.0 * np.sin(u / 9.0)) < larg_l)
    # réseau hexagonal (prismes d'environ 3 blocs) : centre de colonne le plus proche
    sz = 1.65
    qf = (2 / 3 * X) / sz
    rf = (-1 / 3 * X + np.sqrt(3) / 3 * Z) / sz
    xc, zc = qf, rf
    yc = -xc - zc
    rx, rz, ry = np.round(xc), np.round(zc), np.round(yc)
    dx_, dz_, dy_ = np.abs(rx - xc), np.abs(rz - zc), np.abs(ry - yc)
    fx = (dx_ > dz_) & (dx_ > dy_)
    fz = ~fx & (dz_ > dy_)
    rx = np.where(fx, -rz - ry, rx)
    rz = np.where(fz, -rx - ry, rz)
    cx = sz * 1.5 * rx
    cz = sz * np.sqrt(3) * (rz + rx / 2)
    dc = np.hypot(X - cx, Z - cz)
    fente = dc > sz * 0.93                                     # bord du prisme : fente entre colonnes
    graine = (rx * 7919 + rz * 104729) % 1009 / 1009.0
    uc = (cx - p0[0]) * n[0] + (cz - p0[1]) * n[1]
    haut = 63.0 + 8.0 * (1 - np.clip((uc + 3) / (lg + 2), 0, 1)) ** 1.4 - 2.4 + 2.6 * graine
    haut = np.floor(haut) + 0.6
    haut = np.where(fente, haut - 1.0, haut)
    # au pied de la falaise, la Chaussée s'adosse à des colonnes plus hautes (les marches du départ)
    pied = (u <= -3) & (u > -9) & (np.abs(v) < 11) & ~F
    y = np.where(langue, haut, y)
    y = np.where(pied, np.maximum(y, np.floor(70.0 + 3.0 * graine + 0.5 * (-u - 3))) + 0.6, y)
    y = np.where(pied & fente, y - 1.0, y)
    emerge = langue & (haut > 63.0)
    sous = langue & ~emerge
    y = np.where(sous, np.minimum(y, 61.6), y)                # sous l'eau : au moins un bloc d'eau dessus
    F = (F | sous) & ~emerge
    eau = np.where(sous & (L.bord() > 0.02), 63.0, np.where(emerge, np.nan, eau))
    pl = M.pente_locale(y)
    typ = np.full(X.shape, PRE | TAILLEE, np.int32)
    typ[(C == 60) | (pl > 0.9)] = EBOULIS | TAILLEE
    typ[pl > 1.3] = ROC | TAILLEE                                      # orgues des falaises
    typ[~F & (dF <= 2.5) & (y < 66.5)] = PLAGE | TAILLEE                # galets noirs
    typ[langue | pied] = ROC | TAILLEE
    typ[F] = FOND | TAILLEE
    print(f"chaussee : {int(emerge.sum())} colonnes émergées, {int(sous.sum())} sous l'eau, falaises jusqu'à y "
          f"{y.max():.0f}, vers le large {n.round(2)}")
    return finir_loupe("chaussee", L, y, typ, eau, "CHAUSSEE", roc=1.3)


def meteores():
    """Météores (Thessalie) sur le relief réel agrandi 8 fois : les pitons de conglomérat (repérés par le relief local
    du modèle, > 25 m au-dessus des alentours lissés) ont des parois verticales et des sommets en dôme, 20 à 50 blocs
    au-dessus de la plaine de Kalambaka ; vallées boisées autour. Aucun monastère (sites naturels seulement)."""
    R = Relief("meteores")
    L = Zoom(39.7217, 21.6306, 8.0, -170, 170, -140, 140, fondu=45)
    X, Z = L.X, L.Z
    E = R.ech(L.lo, L.la)
    Es = R.ech(L.lo, L.la, 450.0)
    Eb = R.ech(L.lo, L.la, 1800.0)
    rel = E - Es
    base = T.blocs(Eb) + (Es - Eb) * 0.05 + np.minimum(rel, 0) * 0.05
    # pitons : relief local fort, parois verticales (saut franc au bord), dôme au sommet
    coeur = np.hypot(X - L.c[0], Z - L.c[1]) < 125
    P = coeur & (rel > 25.0)
    P = ndimage.binary_opening(ndimage.binary_closing(P, iterations=1), iterations=1)
    lab, n = ndimage.label(P)
    if n:
        t_ = ndimage.sum(np.ones(P.shape), lab, range(1, n + 1))
        P = np.isin(lab, np.flatnonzero(t_ >= 14) + 1)
    dP = ndimage.distance_transform_edt(P)
    dome = np.minimum(dP, 4.0) / 4.0
    piton = base + 7.0 + np.maximum(rel, 0) * 0.17 + 1.5 * dome + 0.8 * bruit(X, Z, 3, 1501)
    y_r = np.where(P, piton, base + np.maximum(rel, 0) * 0.04)
    # éboulis au pied des parois
    dPo = ndimage.distance_transform_edt(~P)
    y_r = np.where(~P & (dPo < 5), y_r + (5 - dPo) * 0.6, y_r)
    y_r = L.raccord(y_r, L.couvert(R))
    y, a = L.melange(y_r, L.couvert(R))
    pl = M.pente_locale(y)
    typ = np.full(X.shape, PRE | TAILLEE, np.int32)
    typ[(pl > 1.0)] = EBOULIS | TAILLEE
    typ[~P & (dPo < 4) & (dPo > 0)] = EBOULIS | TAILLEE
    typ[P] = ROC | TAILLEE
    typ[P & (pl < 0.6) & (dP > 2.5) & (bruit(X, Z, 3, 1502) > 0.1)] = PRE | TAILLEE      # touffes sur les dômes
    print(f"meteores : {n} pitons, {int(P.sum())} colonnes de rocher, sommets jusqu'à y {y.max():.0f} "
          f"(plaine ~y {np.median(y[~P]):.0f})")
    return finir_loupe("meteores", L, y, typ, np.full(X.shape, np.nan), "CONGLOMERAT", roc=1.2)


def fumerolles(X, Z, y, masque, n, rng, typ=None):
    """n fumerolles (blocs qui fument) prises au hasard dans le masque, entourées de soufre (classe MOUSSE de la
    palette VOLCAN)."""
    vox = []
    jj, ii = np.nonzero(masque)
    if len(jj) == 0:
        return vox, typ
    for k in rng.choice(len(jj), size=min(n, len(jj)), replace=False):
        j, i = jj[k], ii[k]
        vox.append((int(X[j, i]), int(np.floor(y[j, i])), int(Z[j, i]), VOX_FUMEROLLE))
        if typ is not None:
            m = (np.hypot(X - X[j, i], Z - Z[j, i]) < 1.0 + 0.6 * rng.random()) & masque   # 04/11 : taches plus petites
            typ[m] = MOUSSE | TAILLEE
    return vox, typ


def volcan_classes(X, Z, y, E, C, pl, nu_au_dessus, roc=1.4):
    """Sol d'un volcan : coulées (sol nu des cartes) en basalte noir, cendres et scories sur le cône, forêts plus bas."""
    typ = np.full(X.shape, PRE | TAILLEE, np.int32)
    typ[(C == 60) | (E > nu_au_dessus + 150 * bruit(X, Z, 8, 1601))] = EBOULIS | TAILLEE
    coulee = (C == 60) & (bruit(X, Z, 5, 1602) > -0.6)
    typ[coulee & (E < nu_au_dessus + 300)] = FOND | TAILLEE
    typ[pl > roc] = ROC | TAILLEE
    return typ


def etna():
    """Etna sur le relief réel agrandi 2,5 fois : le grand cône, la Valle del Bove, les coulées de lave récentes en
    basalte noir (sol nu d'ESA WorldCover), les cônes adventifs ; au sommet, les cratères (Voragine et Bocca Nuova
    réunis, Nord-Est, Sud-Est) agrandis, un lac de lave au fond du cratère Sud-Est, des fumerolles et du soufre."""
    R = Relief("etna")
    # volcan au bord de la mer : traité comme une côte (la mer agrandie rejoint celle du mod), vraies proportions
    # ancré sur la côte ionienne (Riposto) : la côte agrandie suit celle du mod ; le volcan est à ~180 blocs à l ouest ; au nord, la mer Tyrrhénienne du mod borne la zone
    L, E, y, eau, F = fjord_reel(R, 37.735, 15.203, 2.5, -345, 50, -150, 175, v=0.03, sigma_m=2500.0, fondu=50, raccord=True,
                                 fond_mod=True,
                                 iso=True)
    X, Z = L.X, L.Z
    a = L.bord()
    # 04/11 (test en jeu) : cône trop bruité (marches d'un bloc partout) : relief adouci sur l'emprise du lieu
    y = y + (ndimage.gaussian_filter(y, 1.6) - y) * a
    C = couverture("etna", L.lo, L.la)
    rng = np.random.default_rng(1600)
    vox = []
    # les cratères sommitaux sont à moins d'un kilomètre les uns des autres : agrandis, ils se chevaucheraient ; on
    # garde leur disposition (Nord-Est au nord-nord-est, Sud-Est au sud-est du cratère central) en les écartant
    c0 = L.vers_blocs(37.7508, 14.9928)
    crateres = [(c0, 8.5, 15.0, 1610), (c0 + np.array([8.0, -15.5]), 6.0, 12.0, 1620),
                (c0 + np.array([14.0, 13.0]), 7.0, 10.0, 1630)]
    dedans = np.zeros(X.shape, bool); bords = np.zeros(X.shape, bool)
    for c, r, prof, g in crateres:
        y, inter, fond, fy = cratere(X, Z, y, c, r, prof, rebord=3.0, graine=g)
        dedans |= inter
        rr = np.hypot(X - c[0], Z - c[1]) / r
        bords |= (rr > 0.75) & (rr < 1.35)
        if g == 1630:                                  # cratère Sud-Est : lac de lave
            lac = rr < 0.42
            y = np.where(rr < 0.52, fy, y)                     # fond bien plat autour du lac (la lave n'en sort pas)
            n0 = int(np.floor(fy))
            for j, i in zip(*np.nonzero(lac)):
                # la lave remplace le dessus du fond (à niveau : elle ne déborde pas), sur du magma
                vox.append((int(X[j, i]), n0 - 1, int(Z[j, i]), VOX_MAGMA))
                vox.append((int(X[j, i]), n0, int(Z[j, i]), VOX_LAVE))
    pl = M.pente_locale(y)
    typ = volcan_classes(X, Z, y, np.where(a > 0.05, E, 0), C, pl, nu_au_dessus=2300)
    typ[dedans] = EBOULIS | TAILLEE
    typ[F] = FOND | TAILLEE
    v_, typ = fumerolles(X, Z, y, bords & (pl < 2.0), 28, rng, typ)
    vox += v_
    print(f"etna : sommet y {y.max():.0f}, 3 cratères, lac de lave de {sum(1 for v in vox if v[3] == VOX_LAVE)} "
          f"blocs, {len(v_)} fumerolles")
    return finir_loupe("etna", L, y, typ, eau, "VOLCAN", roc=1.4, vox=vox)


def vesuve():
    """Vésuve sur le relief réel agrandi 5 fois : le Gran Cono dans la caldeira du Somma (Valle del Gigante entre
    les deux), le cratère agrandi (~18 blocs, parois raides), des fumerolles et du soufre sur ses parois ; cendres
    et scories sur le cône, forêts sur le Somma. Pas de lave (le volcan dort depuis 1944)."""
    R = Relief("vesuve")
    # ancré sur la côte du golfe de Naples (Torre del Greco) : le volcan est à ~140 blocs au nord-est
    L, E, y, eau, F = fjord_reel(R, 40.776, 14.370, 5.0, -90, 270, -280, 35, v=0.075, sigma_m=5000.0, fondu=45, raccord=True,
                                 fond_mod=True,
                                 iso=True)
    X, Z = L.X, L.Z
    a = L.bord()
    # 04/11 (test en jeu) : cône trop bruité (marches d'un bloc partout) : relief adouci sur l'emprise du lieu
    y = y + (ndimage.gaussian_filter(y, 1.6) - y) * a
    C = couverture("vesuve", L.lo, L.la)
    rng = np.random.default_rng(1700)
    c = L.vers_blocs(40.8213, 14.4261)
    y, inter, fond, fy = cratere(X, Z, y, c, 9.5, 20.0, rebord=2.0, graine=1710)
    rr = np.hypot(X - c[0], Z - c[1]) / 9.5
    pl = M.pente_locale(y)
    typ = volcan_classes(X, Z, y, np.where(a > 0.05, E, 0), C, pl, nu_au_dessus=700)
    typ[inter] = EBOULIS | TAILLEE
    typ[F] = FOND | TAILLEE
    vox, typ = fumerolles(X, Z, y, (rr > 0.45) & (rr < 1.0) & (pl < 2.5), 16, rng, typ)
    print(f"vesuve : sommet y {y.max():.0f}, cratère fond y {fy:.0f}, {len(vox)} fumerolles")
    return finir_loupe("vesuve", L, y, typ, eau, "VOLCAN", roc=1.4, vox=vox)


def fingal():
    """Île de Staffa (Hébrides), trop petite pour le mod (moins d'un bloc à 1:250) : construite à taille de jeu
    (70 x 34 blocs), plateau d'herbe à y ~78 sur des falaises d'orgues de basalte verticales ; au sud, l'entrée de la
    grotte de Fingal (creusée par outils/grottes.py) et une plate-forme de colonnes au ras de l'eau."""
    c = bloc_de(56.4335, -6.3395)
    X, Z, _ = M.zone(56.4335, -6.3395, 85, 145)
    h, sd = T.hauteur_base(X, Z)
    a = np.radians(12)
    u = (X - c[0]) * np.cos(a) + (Z - c[1]) * np.sin(a)          # est-ouest (petit axe)
    v = -(X - c[0]) * np.sin(a) + (Z - c[1]) * np.cos(a)         # nord-sud (grand axe, sud = v > 0)
    nn = np.hypot(u / 17.0, v / 35.0) + 0.06 * bruit(X, Z, 5, 1801)
    ile = nn < 1.0
    plateau = 77.6 + 2.0 * bruit(X, Z, 12, 1802) - 3.0 * np.clip(v / 35.0, 0, 1)
    # autour de l'île, le fond descend de 58 au pied des falaises jusqu'au fond du mod (rejoint à nn = 3,5)
    fond = 58.0 + (np.minimum(h, 58.0) - 58.0) * lisse(np.clip((nn - 1.0) / 2.5, 0, 1))
    y = np.where(ile, plateau, np.minimum(fond, 61.4))
    # plate-forme de colonnes au pied de la falaise sud et est (la « chaussée » de Staffa)
    gradin = ~ile & (nn < 1.12) & (v > 5)
    cel = (np.floor(X / 2) * 7919 + np.floor(Z / 2) * 104729) % 997 / 997.0
    y = np.where(gradin, 63.0 + np.floor(cel * 2.0) + 0.6, y)
    sous = ~ile & ~gradin & (nn < 3.6) & (sd < 0)
    eau = np.where(sous, 63.0, np.nan)
    # entrée de la grotte : le point le plus au sud de l'île, direction vers le nord (l'intérieur)
    jj, ii = np.nonzero(ile)
    k = int(np.argmax(v[jj, ii] - 3 * np.abs(u[jj, ii])))
    e = np.array([X[jj[k], ii[k]], Z[jj[k], ii[k]]])
    d = -np.array([-np.sin(a), np.cos(a)])                       # vers le nord (v décroissant)
    typ = np.full(X.shape, FOND | TAILLEE, np.int32)
    typ[ile] = PRE | TAILLEE
    typ[ile & (ndimage.distance_transform_edt(ile) < 2.5)] = ROC | TAILLEE
    typ[gradin] = ROC | TAILLEE
    print(f"fingal : île de {int(ile.sum())} colonnes, plateau y {plateau[ile].mean():.0f}, entrée de la grotte en {e}")
    w = np.where(sous | ile | gradin, 1.0, 0.0)
    y = h + (y - h) * w
    typ = np.where(w > 0, typ | BIOME, 0)
    res = M.ecrire("fingal", X, Z, y, h, y.copy(), typ, sd, np.where(w > 0, eau, np.nan), "CHAUSSEE")
    g = dict(np.load("/tmp/lieu_fingal.npz"))
    g.update(entree_x=e[0], entree_z=e[1], dir_x=d[0], dir_z=d[1])
    np.savez_compressed("/tmp/lieu_fingal.npz", **g)
    return res


def capri():
    """Capri sur le relief réel agrandi 4 fois (l'île n'est qu'un point dans le mod) : falaises calcaires, le Monte
    Solaro, les Faraglioni ; sur la côte nord-ouest, l'entrée de la grotte bleue (creusée par outils/grottes.py)."""
    R = Relief("capri")
    L, E, y, eau, F = fjord_reel(R, 40.548, 14.235, 4.0, -150, 150, -66, 90, v=0.07, sigma_m=800.0, fondu=30,
                                 iso=True, fond_mod=True)
    X, Z = L.X, L.Z
    C = couverture("capri", L.lo, L.la)
    terre = ~F
    dF = ndimage.distance_transform_edt(terre)
    # falaises : la côte tombe à pic dans la mer
    haut_int = ndimage.gaussian_filter(ndimage.maximum_filter(np.where(terre, y, 0), size=9), 2)
    y = np.where(terre, y + (np.maximum(haut_int - 1.0, y) - y) * lisse(np.clip(1 - (dF - 1) / 6, 0, 1)) *
                 np.clip((haut_int - 70) / 6, 0, 1), y)
    q = L.vers_blocs(40.5605, 14.2056)
    jj, ii = np.nonzero(terre & (dF <= 1.0))
    pts = np.c_[X[jj, ii], Z[jj, ii]]
    e = pts[int(np.argmin(np.hypot(pts[:, 0] - q[0], pts[:, 1] - q[1])))]
    gz, gx = np.gradient(ndimage.gaussian_filter(dF, 3))
    j0, i0 = int(e[1] - Z[0, 0]), int(e[0] - X[0, 0])
    d = np.array([gx[j0, i0], gz[j0, i0]]); d /= np.linalg.norm(d) + 1e-9      # vers l'intérieur de l'île
    pl = M.pente_locale(y)
    typ = np.full(X.shape, PRE | TAILLEE, np.int32)
    typ[(C == 60) | (pl > 0.9)] = EBOULIS | TAILLEE
    typ[pl > 1.3] = ROC | TAILLEE
    typ[F] = FOND | TAILLEE
    print(f"capri : île de {int(terre.sum())} colonnes, sommet y {y.max():.0f}, grotte bleue en {e}, vers {d.round(2)}")
    res = finir_loupe("capri", L, y, typ, eau, "CALCAIRE", roc=1.3)
    g = dict(np.load("/tmp/lieu_capri.npz"))
    g.update(grotte_x=e[0], grotte_z=e[1], grotte_dx=d[0], grotte_dz=d[1])
    np.savez_compressed("/tmp/lieu_capri.npz", **g)
    return res


def tre_cime():
    """Tre Cime di Lavaredo : le relief réel des Dolomites de Sexten (agrandi 6 fois, relief local exagéré) porte les
    trois tours, trop fines pour le modèle à 30 m (il n'en voit qu'une arête à 2 700 m) : elles sont sculptées à
    leur vraie place — Cima Ovest, Cima Grande, Cima Piccola — parois verticales de ~40 blocs au-dessus de leurs
    pierriers, séparées par d'étroites forcelle."""
    R = Relief("tre_cime")
    lat_c, lon_c, k = 46.6188, 12.3020, 6.0
    L = Zoom(lat_c, lon_c, k, -180, 180, -175, 175, fondu=45)
    X, Z, c = L.X, L.Z, L.c
    y_r, E, Es = relief_exagere(R, L.lo, L.la, v=0.060, sigma_m=1200.0)
    y_r = L.raccord(y_r, L.couvert(R))
    y, a_ = L.melange(y_r, L.couvert(R))
    E = np.where(a_ > 0.05, E, 0)
    # la rivière du mod (qui naît, sur la carte du mod, au pied nord des tours) : le lieu la reprend
    y, eau, torrent = reprendre_riviere(L, y)
    # socle des tours : on aplanit l'arête du modèle (elle sera remplacée par les tours) en pierriers
    tours = [(46.6184, 12.2967, 5.5, 4.2, 40.0, -0.20, 911), (46.6189, 12.3023, 6.5, 4.6, 44.0, -0.15, 912),
             (46.6197, 12.3068, 4.2, 3.4, 33.0, -0.25, 913)]
    pied = np.zeros(X.shape); dans = np.zeros(X.shape, bool)
    base_t = []
    for (tla, tlo, ru, rv, H, a, g) in tours:
        p = L.vers_blocs(tla, tlo)
        ca, sa = np.cos(a), np.sin(a)
        u = (X - p[0]) * ca + (Z - p[1]) * sa; v = -(X - p[0]) * sa + (Z - p[1]) * ca
        nn = (np.abs(u / ru) ** 3 + np.abs(v / rv) ** 3) ** (1 / 3) + 0.07 * bruit(X, Z, 2.5, g)
        j, i = int(round(p[1] - Z[0, 0])), int(round(p[0] - X[0, 0]))
        b = float(np.median(y[max(j - 6, 0):j + 7, max(i - 6, 0):i + 7]))
        base_t.append(b)
        # pierriers : cônes clairs autour du pied
        cone = np.clip(1 - (nn - 1) / 1.6, 0, 1)
        pied = np.maximum(pied, cone * (bruit(X, Z, 3, g + 20) > -0.4))
        y = np.where(nn < 2.4, y + (b + 4 * lisse(cone) + 1.2 * bruit(X, Z, 3, g + 30) - y) * lisse(np.clip((2.4 - nn) / 1.0, 0, 1)), y)
        # tour à gradins : fût principal, vires (épaulements) à mi-hauteur et au pied, sommet en dôme fracturé
        top = b + H - 4.0 * nn ** 2 + 1.5 * bruit(X, Z, 2.0, g + 10)
        vire = b + H * (0.62 + 0.06 * bruit(X, Z, 3.0, g + 40))
        socle = b + H * (0.30 + 0.06 * bruit(X, Z, 3.0, g + 50))
        yt = np.where(nn < 0.72, top, np.where(nn < 0.88, np.minimum(top, vire), np.minimum(top, socle)))
        yt = np.where(nn > 0.97, b + 4 + (socle - b - 4) * lisse(np.clip((1 - nn) / 0.03, 0, 1)), yt)
        m = nn < 1.0
        y = np.where(m, np.maximum(y, yt), y)
        dans |= m
    typ = classes_montagne(X, Z, y, E, neige=2850, glace=None, eboulis=(2300, 2900), herbe_max=2450, roc=1.3,
                           pente_herbe=1.1)
    typ[np.isfinite(eau)] = LIT | TAILLEE
    typ[(pied > 0.05) & ~dans] = EBOULIS | TAILLEE
    typ[dans] = ROC | TAILLEE
    typ[dans & (M.pente_locale(y) < 0.8)] = NEIGE | TAILLEE
    print(f"tre_cime : tours de y {min(base_t):.0f} à y {y.max():.0f}" +
          (f", rivière du mod reprise (eau {torrent[0]:.0f}, {torrent[1]} colonnes de lit)" if torrent else ""))
    return finir_loupe("tre_cime", L, y, typ, eau, "DOLOMIE", roc=1.3, garder_fleuves=False)


def gavarnie():
    """Cirque de Gavarnie sur le relief réel (agrandi 5 fois, relief local exagéré) : l'amphithéâtre calcaire, ses
    gradins et ses crêtes à 3 000 m. La Grande Cascade descend la paroi du fond depuis le rebord du Marboré, en une
    suite de chutes, puis le gave de Pau coule au nord dans le fond du cirque jusqu'à une vasque vers le village."""
    R = Relief("gavarnie")
    L = Zoom(42.700, -0.010, 5.0, -180, 180, -180, 180, fondu=45)
    X, Z = L.X, L.Z
    y_r, E, Es = relief_exagere(R, L.lo, L.la, v=0.04, sigma_m=1800.0)
    y_r = L.raccord(y_r, L.couvert(R))
    y, a = L.melange(y_r, L.couvert(R))
    T_ = L.vers_blocs(42.6855, -0.012)
    B_ = L.vers_blocs(42.6975, -0.012)
    N_ = L.vers_blocs(42.733, -0.008)
    tr = np.vstack([talweg(y, T_, B_, X, Z), talweg(y, B_, N_, X, Z)[1:]])
    Ltr = float(len(tr))
    y, eau, tr, d_t, s_t, L_t, niv = riviere_sur_relief(
        X, Z, y, np.full(X.shape, np.nan), tr, 999.0, lambda s_: 0.9 + 1.4 * np.clip(s_ / Ltr, 0, 1),
        prof=1.0, pas_min=4, lissage=1.5, pente=1.2, large=10)
    n0 = float(niv(np.array([0.0]))[0]); n1 = float(niv(np.array([L_t]))[0])
    src = np.hypot(X - tr[1][0], Z - tr[1][1]) < 2.4
    eau = np.where(src & ~np.isfinite(eau), n0, eau); y = np.where(src, np.minimum(y, n0 - 2.0), y)
    rl = np.hypot(X - tr[-3][0], Z - tr[-3][1]) / 6.0
    et = rl < 1
    eau = np.where(et, n1, eau); y = np.where(et, np.minimum(y, n1 - 1.6 - lisse(1 - rl)), y)
    typ = classes_montagne(X, Z, y, np.where(a > 0.05, E, 0), neige=2800, glace=None, eboulis=(2000, 3000),
                           herbe_max=2300, roc=1.35, pente_neige=1.0, pente_herbe=1.2)
    typ[np.isfinite(eau)] = LIT | TAILLEE
    print(f"gavarnie : crêtes jusqu'à y {y.max():.0f}, cascade de y {n0:.0f}, gave jusqu'à y {n1:.0f} ({L_t:.0f} blocs)")
    return finir_loupe("gavarnie", L, y, typ, eau, "CALCAIRE", roc=1.35)


def talweg(y, depart, arrivee, X, Z):
    """Chemin le plus bas entre deux points (blocs) sur la grille y : le fond de la vallée."""
    from skimage.graph import route_through_array
    cout = 1.0 + np.maximum(y - ndimage.minimum_filter(y, 9), 0) ** 1.5 + 0.02 * (y - y.min())
    p0 = (int(round(depart[1] - Z[0, 0])), int(round(depart[0] - X[0, 0])))
    p1 = (int(round(arrivee[1] - Z[0, 0])), int(round(arrivee[0] - X[0, 0])))
    pts, _ = route_through_array(cout, p0, p1, fully_connected=True, geometric=True)
    pts = np.array(pts, float)
    return np.c_[X[0, 0] + pts[:, 1], Z[0, 0] + pts[:, 0]]


def riviere_sur_relief(X, Z, y, eau, trace, depart_niv, larg, prof=1.5, pas_min=6, lissage=3.0, niv_min=-1e9, pente=0.9, large=60):
    """Cours d'eau qui suit le relief le long d'un tracé : son niveau descend avec le fond de la vallée, par marches
    d'un bloc au moins tous les pas_min blocs ; jamais il ne remonte."""
    tr = M.lisser_trace(trace, max(len(trace), 100), lissage)
    d, s, L = M.polyligne(X, Z, tr)
    ss = np.linspace(0, L, len(tr))
    j = np.clip(np.round(tr[:, 1] - Z[0, 0]).astype(int), 0, X.shape[0] - 1)
    i = np.clip(np.round(tr[:, 0] - X[0, 0]).astype(int), 0, X.shape[1] - 1)
    fond = ndimage.minimum_filter(y, 5)[j, i]
    n = np.maximum(np.minimum.accumulate(np.minimum(np.floor(fond + 0.2), depart_niv)), niv_min)
    niv = lambda s_: np.interp(s_, ss, n)
    y, eau, d, s, L = M.creuser_riviere(X, Z, y, eau, tr, niv, larg, prof=prof, pente=pente, large=large)
    return y, eau, tr, d, s, L, niv


def plitvice():
    """Lacs de Plitvice sur le relief réel (agrandi 4 fois) : la vallée barrée par le travertin. Les seize lacs sont
    retrouvés en « noyant » le vrai fond de la vallée jusqu'à leur vraie altitude (Prošćansko 636 m … Novakovića
    Brod 503 m) : chaque lac prend la forme réelle de la vallée à son niveau, et là où il touche le lac suivant, l'eau
    déborde sur toute la largeur du barrage (cascades). Altitudes exagérées par une courbe qui donne 2 à 4 blocs à
    chaque barrage ; les lacs du bas sont au fond du canyon ; le Veliki slap (78 m) tombe du plateau dans le
    bassin de Sastavci, où naît la Korana."""
    R = Relief("plitvice")
    lat_c, lon_c, k = 44.8810, 15.6050, 7.0
    L_ = Zoom(lat_c, lon_c, k, -175, 115, -220, 165, fondu=40)
    X, Z, c, h, sd = L_.X, L_.Z, L_.c, L_.h, L_.sd
    E = R.ech(L_.lo, L_.la)
    cov = L_.couvert(R)
    # altitudes des surfaces planes du modèle (Copernicus aplanit les lacs : 638, 629, 615, 586, 553, 536, 527, 480 m)
    # et quelques barrages intermédiaires (petits lacs que le modèle ne voit pas)
    niveaux = [638, 629, 615, 600, 586, 570, 553, 545, 536, 527, 516, 505, 480]
    # talweg réel du Prošćansko à Sastavci, puis la Korana vers le nord
    p0 = L_.vers_blocs(44.8580, 15.5985)
    p1 = L_.vers_blocs(44.9035, 15.6095)
    p2 = L_.vers_blocs(44.9150, 15.6120)
    tr = np.vstack([talweg(E, p0, p1, X, Z), talweg(E, p1, p2, X, Z)[1:]])
    tr = M.lisser_trace(tr, 500, 2.0)
    d0, s0, L = M.polyligne(X, Z, tr)
    ss = np.linspace(0, L, len(tr))
    jt = np.clip(np.round(tr[:, 1] - Z[0, 0]).astype(int), 0, X.shape[0] - 1)
    it = np.clip(np.round(tr[:, 0] - X[0, 0]).astype(int), 0, X.shape[1] - 1)
    Et = np.minimum.accumulate(ndimage.minimum_filter(E, 5)[jt, it])
    s_lac = [float(ss[np.argmax(Et <= n + 0.5)]) if (Et <= n + 0.5).any() else L for n in niveaux]
    for i in range(1, len(s_lac)):
        s_lac[i] = max(s_lac[i], s_lac[i - 1] + 3.0)
    # courbe d'altitude : chaque barrage fait 2 à 4 blocs (le Veliki slap à part), le reste en pente douce
    y_l = [100.0]
    for a, b2 in zip(niveaux[:-1], niveaux[1:]):
        y_l.append(y_l[-1] - (np.clip(round((a - b2) * 0.13), 2, 3) if b2 > 480 else 5))
    anc_E = np.array(niveaux[::-1], float); anc_y = np.array(y_l[::-1]) - 0.5
    f = np.interp(E, anc_E, anc_y)
    f = np.where(E > anc_E[-1], anc_y[-1] + (E - anc_E[-1]) * 0.07, f)
    f = np.where(E < anc_E[0], anc_y[0] + (E - anc_E[0]) * 0.10, f)
    # raccord au mod : la vallée des lacs (dont les niveaux sont fixés en marches) est décalée d'un seul bloc entier ;
    # la correction variable ne s'applique qu'au-delà de 60 blocs du talweg
    D = L_.raccord(f, cov) - f
    Dm = float(np.round(np.mean(D[d0 < 60])))
    Dm = max(Dm, 66.0 - y_l[-1])                       # le lac le plus bas reste au-dessus de la mer (aquifère)
    D2 = Dm + (D - Dm) * lisse(np.clip((d0 - 60) / 60, 0, 1))
    f = f + D2
    y_l = [v + Dm for v in y_l]
    y, a_ = L_.melange(f, cov)
    # les lacs : du plus bas au plus haut, chaque lac prend les colonnes de la vallée sous son niveau, à partir de
    # son début le long du talweg (le barrage du lac d'aval reçoit ainsi l'eau du lac d'amont : cascades)
    lac = np.full(X.shape, -1)
    couloir = d0 < 60
    for i in range(len(niveaux) - 1, -1, -1):
        n = niveaux[i]
        cand = couloir & (E <= n + 0.4) & (s0 >= s_lac[i] - 2) & (lac < 0)
        if i + 2 < len(niveaux):
            cand &= s0 < s_lac[i + 2] + 4
        lab, nl = ndimage.label(cand)
        if nl == 0:
            continue
        # la partie reliée au talweg
        ok = np.unique(lab[jt[(ss >= s_lac[i] - 2)], it[(ss >= s_lac[i] - 2)]])
        lac = np.where(np.isin(lab, ok[ok > 0]), i, lac)
    eau = np.where(lac >= 0, np.array(y_l)[np.maximum(lac, 0)].round(), np.nan)
    dans = lac >= 0
    d_rive = ndimage.distance_transform_edt(dans)
    prof = np.minimum(1.0 + 0.45 * d_rive, 6.0)
    y = np.where(dans, np.minimum(y, eau - 1.15 - prof + 1.0), y)
    # îlots de travertin moussus le long des barrages (entre les filets d'eau)
    barrage = np.zeros(X.shape, bool)
    for dj, di in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        ev = np.roll(np.roll(eau, dj, 0), di, 1)
        barrage |= dans & np.isfinite(ev) & (ev < eau)
    ile = ndimage.binary_dilation(barrage, iterations=1) & dans & (bruit(X, Z, 2.6, 401) > 0.25)
    ile &= ~barrage | (bruit(X, Z, 2.0, 402) > 0.1)
    y = np.where(ile, eau + 0.25, y)
    eau = np.where(ile, np.nan, eau)
    # Veliki slap : la Plitvica arrive de l'ouest sur le plateau et tombe dans le bassin de Sastavci
    sast = tr[int(np.argmin(np.abs(ss - s_lac[-1])))]
    q0 = sast + np.array([-75.0, 4.0])
    lip = sast + np.array([-5.0, 0.0])
    tr2 = np.vstack([talweg(y, q0, lip, X, Z), [sast]])
    yb = y.copy()
    y, eau2, tr2, d2, s2, L2, niv2 = riviere_sur_relief(X, Z, y, np.full(X.shape, np.nan), tr2, 999.0,
                                                         lambda s_: np.full(np.shape(s_), 1.7), prof=1.0)
    # le ruisseau s'arrête au bord du canyon : son dernier bief touche l'eau de Sastavci (chute)
    eau2 = np.where(np.isfinite(eau), np.nan, eau2)
    y = np.where(np.isfinite(eau) & ~np.isfinite(eau2), np.minimum(y, yb), y)
    eau = np.where(np.isfinite(eau2), eau2, eau)
    niv_p = float(niv2(np.array([L2 - 6]))[0])
    src = np.hypot(X - tr2[3][0], Z - tr2[3][1]) < 3.0
    eau = np.where(src & ~np.isfinite(eau), float(niv2(np.array([0.0]))[0]), eau)
    y = np.where(src, np.minimum(y, eau - 2.2), y)
    # la Korana : au-delà de Sastavci, le long du talweg, puis un étang au bout
    kor = (s0 > s_lac[-1]) & (d0 < 3.2) & ~np.isfinite(eau) & (s0 < L - 9)
    nk = float(y_l[-1])
    eau = np.where(kor, nk, eau); y = np.where(kor, np.minimum(y, nk - 2.0), y)
    rl = np.hypot(X - tr[-12][0], Z - tr[-12][1]) / 7.0
    et = rl < 1
    eau = np.where(et, nk, eau); y = np.where(et, np.minimum(y, nk - 1.8 - lisse(1 - rl)), y)
    # 04/11 (test en jeu : pics de pierre) : le modèle de surface (arbres compris) agrandi 7 fois hérissait les
    # versants ; adoucis loin de l'eau (les rives qui retiennent les lacs ne bougent pas)
    loin = ndimage.distance_transform_edt(~(np.isfinite(eau) | ile)) > 3
    ylisse = ndimage.gaussian_filter(y, 2.2)
    y = np.where(loin, ylisse, y)
    w = np.maximum(L_.emprise(), np.where(np.isfinite(eau) | ile, 1.0, 0.0))
    pl = M.pente_locale(y)
    typ = np.full(X.shape, PLATEAU | TAILLEE, np.int32)
    typ[pl > 1.2] = ROC | TAILLEE
    rive = ndimage.binary_dilation(np.isfinite(eau), iterations=1) & ~np.isfinite(eau)
    typ[rive & (bruit(X, Z, 4, 403) > -0.2)] = MOUSSE | TAILLEE
    typ[ile] = MOUSSE | TAILLEE
    typ[np.isfinite(eau)] = LIT | TAILLEE
    print(f"plitvice : {int(len(np.unique(lac[lac >= 0])))} lacs de y {y_l[0]:.0f} à {y_l[-1]:.0f}, "
          f"Veliki slap de y {niv_p:.0f} à {nk:.0f}, talweg {L:.0f} blocs")
    return finir_loupe("plitvice", L_, y, typ, eau, "TRAVERTIN", roc=1.2, w_typ=w)


def fjord_reel(R, lat_a, lon_a, k, x0, x1, z0, z1, v=0.03, sigma_m=900.0, fondu=40, eau_reelle=None, iso=False,
               raccord=False, fond_mod=False):
    """Fjord sur le relief réel agrandi k fois (zoom « carte », comme le mod) depuis A, sa jonction avec la mer du mod.
    Mer = altitude <= 0 du modèle ; hauteurs = courbe du mod sur le relief lissé + relief local exagéré, si bien que
    les montagnes du lieu rejoignent celles du mod. Sur la bande du bord, l'eau est la réunion de la mer du lieu et
    de celle du mod, gardée seulement si elle rejoint la mer du mod hors du lieu (pas de bassin isolé)."""
    L = Zoom(lat_a, lon_a, k, x0, x1, z0, z1, fondu=fondu, iso=iso)
    E = R.ech(L.lo, L.la)
    cov = L.couvert(R)
    mer_r = (E <= 0.5) & cov
    if eau_reelle is not None:                                  # lagunes au niveau de la mer (couverture du sol)
        er = eau_reelle(L) & cov
        # les chenaux réels de 1-2 blocs (embouchure sous un pont, diagonales) restent ouverts
        mer_r |= ndimage.binary_dilation(er, structure=np.ones((3, 3))) & ndimage.binary_dilation(
            er | mer_r, structure=np.ones((3, 3)), iterations=1) & (ndimage.uniform_filter(er.astype(float), 5) > 0.2)
    lab, n = ndimage.label(mer_r)
    if n:
        tailles = ndimage.sum(np.ones_like(E), lab, range(1, n + 1))
        mer_r = np.isin(lab, np.flatnonzero(tailles >= 40) + 1)
    Es = R.ech(L.lo, L.la, sigma_m)
    yt = T.blocs(np.maximum(Es, 0)) + (np.maximum(E, 0) - np.maximum(Es, 0)) * v
    dIn = ndimage.distance_transform_edt(mer_r)
    fond_r = 61.6 - np.minimum(1.0 + 2.2 * dIn, 22.0) + 0.8 * bruit(L.X, L.Z, 7, 940)
    y_r = np.where(mer_r, fond_r, np.maximum(yt, 64.0))
    if raccord:
        # les terres rejoignent le mod sans marche ; la correction s'éteint vers la côte (qui reste au niveau de la mer)
        dmer = ndimage.distance_transform_edt(~mer_r)
        y_c = L.raccord(y_r, cov, terre=~mer_r)
        y_r = np.where(mer_r, y_r, np.maximum(y_r + (y_c - y_r) * lisse(np.clip((dmer - 2) / 25, 0, 1)), 64.0))
    # mélange avec le terrain du mod vers le bord : la mer est ce qui reste sous le niveau de la mer, reliée à la mer
    # du mod hors du lieu (un bras du fjord agrandi qui sort du lieu loin de la mer du mod remonte en vallée)
    y, a = L.melange(y_r, cov)
    mer = y < 62.9
    # chaque mer du mod qui entre par le bord rejoint le fjord : sinon un bras agrandi s'arrête à côté du bras du mod
    # (le monde est coupé pour un bateau) ; on creuse un détroit par le chemin le plus bas
    from skimage.graph import route_through_array
    lab, n = ndimage.label(mer)
    tailles = ndimage.sum(mer_r, lab, range(1, n + 1)) if n else []
    if n:
        princ = int(np.argmax(tailles)) + 1
        bords, nb = ndimage.label((L.de < 3) & (L.sd < 0))
        cout = 1.0 + 0.5 * np.maximum(y - 62.0, 0) ** 1.5
        for b in range(1, nb + 1):
            cel = np.argwhere(bords == b)
            if len(cel) < 4 or (lab[bords == b] == princ).any():
                continue
            jm, im = np.argwhere(lab == princ).T
            j0, i0 = cel[len(cel) // 2]
            k_ = int(np.argmin(np.hypot(jm - j0, im - i0)))
            if np.hypot(jm[k_] - j0, im[k_] - i0) > 90:
                continue                                      # autre bras de mer, loin du fjord : il reste à part
            ch, _ = route_through_array(cout, (j0, i0), (jm[k_], im[k_]), fully_connected=True, geometric=True)
            trace = np.zeros(mer.shape, bool)
            trace[tuple(np.array(ch).T)] = True
            detroit = ndimage.distance_transform_edt(~trace) <= 3.2
            y = np.where(detroit, np.minimum(y, 60.5 + 0.6 * bruit(L.X, L.Z, 4, 944)), y)
            mer |= detroit
            print(f"  détroit creusé vers la mer du mod au bord ({len(ch)} blocs)")
        lab, n = ndimage.label(mer)
    dehors = lab[(L.de < 2) & (L.sd < 0)]
    reliee = np.isin(lab, np.unique(dehors[dehors > 0]))
    # une grande lagune réelle au niveau de la mer, coupée de la mer par un chenal trop fin pour la grille, est
    # rouverte : chenal par le chemin le plus bas jusqu'à la mer reliée
    if eau_reelle is not None and reliee.any():
        cout = 1.0 + 0.5 * np.maximum(y - 62.0, 0) ** 1.5
        jm, im = np.nonzero(reliee)
        tl = ndimage.sum(np.ones(mer.shape), lab, range(1, n + 1))
        for kk in (np.argsort(tl)[::-1] + 1):
            comp = lab == kk
            if comp.sum() < 1500 or (comp & reliee).any():
                continue
            jc, ic = np.argwhere(comp)[len(np.argwhere(comp)) // 2]
            k_ = int(np.argmin(np.hypot(jm - jc, im - ic)))
            ch, _ = route_through_array(cout, (jc, ic), (jm[k_], im[k_]), fully_connected=True, geometric=True)
            trace = np.zeros(mer.shape, bool)
            trace[tuple(np.array(ch).T)] = True
            chenal = ndimage.distance_transform_edt(~trace) <= 2.0
            y = np.where(chenal, np.minimum(y, 60.8), y)
            reliee |= comp | chenal
            mer = mer | chenal
            print(f"  lagune de {int(comp.sum())} colonnes rouverte vers la mer ({len(ch)} blocs de chenal)")
        lab, n = ndimage.label(mer)
        dehors = lab[(L.de < 2) & (L.sd < 0)]
        reliee = np.isin(lab, np.unique(dehors[dehors > 0]))
    mer = reliee
    rive = lisse(np.clip(ndimage.distance_transform_edt(~mer) / 3, 0, 1))
    y = np.where(mer, np.minimum(y, 61.9), np.maximum(y, 63.6 + 1.2 * rive))
    if fond_mod:
        # au large, le fond de la mer du mod (pas de cuvette plus profonde que lui, qui dessinerait le rectangle du
        # lieu) ; près des côtes du lieu, le fond descend en pente depuis le rivage
        dRive = ndimage.distance_transform_edt(mer)
        plancher = np.where(L.sd < 0, np.maximum(L.h, 40.0), 61.9 - 0.35 * dRive)
        plancher = ndimage.gaussian_filter(plancher, 2.0)
        y = np.where(mer, np.maximum(y, np.minimum(plancher, 61.9)), y)
        # au moins deux blocs d eau sur la mer du lieu (sur un seul bloc, près de la côte du mod, le jeu
        # laissait quelques colonnes à sec, couvertes d'herbe)
        y = np.where(mer, np.minimum(y, 60.9), y)
    eau = np.where(mer & (L.bord() > 0.02), 63.0, np.nan)
    print(f"  fjord : {int(mer_r.sum())} colonnes de mer du relief, {int(mer.sum())} en eau, ancrage {L.c.round(1)}")
    return L, E * (a > 0.05), y, eau, mer


def geiranger():
    """Geirangerfjord sur le relief réel (agrandi 3 fois, comme la carte du mod), parois exagérées ; les Sept Sœurs
    (sept filets d'eau côte à côte) tombent de la paroi nord, le Prétendant de la paroi sud, à leur vraie place."""
    R = Relief("geiranger")
    L, E, y, eau, F = fjord_reel(R, 62.112, 6.950, 3.0, -30, 380, -120, 110, v=0.042, sigma_m=1500.0, raccord=True)
    X, Z, c, h, sd = L.X, L.Z, L.c, L.h, L.sd
    def chutes(cible, n, ecart, haut, larg=1.0, long_=9):
        """n filets d'eau côte à côte qui descendent la paroi en cascades jusqu'au fjord : ils partent d'un petit
        bassin sur le plateau, là où la paroi atteint la hauteur voulue (rebord à u_l blocs du rivage)."""
        nonlocal y, eau, F
        dF = ndimage.distance_transform_edt(~F)
        bord = ~F & (dF <= 1.0)
        jj, ii = np.nonzero(bord)
        pts = np.c_[X[jj, ii], Z[jj, ii]]
        p0 = pts[int(np.argmin(np.hypot(pts[:, 0] - cible[0], pts[:, 1] - cible[1])))]
        vois = pts[np.hypot(pts[:, 0] - p0[0], pts[:, 1] - p0[1]) < 14]
        t = np.linalg.svd(vois - vois.mean(0))[2][0]
        gz, gx = np.gradient(ndimage.gaussian_filter(dF, 2))
        j0, i0 = int(p0[1] - Z[0, 0]), int(p0[0] - X[0, 0])
        nrm = np.array([gx[j0, i0], gz[j0, i0]]); nrm /= np.linalg.norm(nrm) + 1e-9      # vers l'intérieur des terres
        u = (X - p0[0]) * nrm[0] + (Z - p0[1]) * nrm[1]
        v = (X - p0[0]) * t[0] + (Z - p0[1]) * t[1]
        demi = (n - 1) / 2 * ecart + larg / 2 + 1.5
        bande = np.abs(v) <= demi
        prof_ = [np.median(y[bande & (np.abs(u - uu) < 0.5)]) if (bande & (np.abs(u - uu) < 0.5)).any() else 0
                 for uu in range(0, 30)]
        ok = [uu for uu in range(2, 30) if prof_[uu] >= haut]
        u_l = ok[0] if ok else int(np.argmax(prof_))
        e_ = float(np.floor(min(haut, prof_[u_l] - 0.5)))
        # chaque filet descend la paroi en cascade : une colonne d'eau par bloc, à la hauteur de la paroi (jamais
        # plus haute vers le fjord), dans un sillon tenu de part et d'autre ; en haut, un petit lit sur le plateau
        y0 = y.copy()
        for kk in range(n):
            vk = v - (kk - (n - 1) / 2) * ecart
            tor = (np.abs(vk) <= larg * 0.5 + 0.3) & (u >= -0.5) & (u <= u_l + long_) & ~F
            berge = (np.abs(vk) > larg * 0.5 + 0.3) & (np.abs(vk) <= larg * 0.5 + 2.0) & (u >= 0.5) & (u <= u_l + long_ + 1.5) & ~F
            prof_k = np.array([np.median(y0[tor & (np.abs(u - uu) < 0.5)]) if (tor & (np.abs(u - uu) < 0.5)).any()
                               else e_ for uu in range(0, int(u_l + long_) + 3)])
            niv = np.minimum(np.floor(prof_k), e_)
            niv = np.maximum.accumulate(niv)
            niv[u_l:] = e_
            uc = np.clip(np.round(u).astype(int), 0, len(niv) - 1)
            lv = niv[uc].astype(float)
            eau = np.where(tor, lv, eau)
            y = np.where(tor, lv - 1.9, y)
            y = np.where(berge, np.maximum(y, lv + 0.4), y)
        src = bande & (u > u_l + long_ - 0.5) & (u <= u_l + long_ + 2.5) & (np.abs(v) <= demi - 1.5) & ~F
        eau = np.where(src, e_, eau)
        y = np.where(src, e_ - 2.2, y)
        autour = bande & (u > u_l + long_ - 2) & (u <= u_l + long_ + 4) & ~F & ~src & ~np.isfinite(eau)
        y = np.where(autour, np.maximum(y, e_ + 0.4), y)
        return [e_, u_l]
    soeurs = L.vers_blocs(62.1066, 7.0943)
    h1 = chutes(soeurs, 7, 2.6, 63 + 28)
    friaren = L.vers_blocs(62.1030, 7.0965)
    h2 = chutes(friaren, 1, 0, 63 + 24, larg=2.0)
    pl = M.pente_locale(y)
    typ = np.full(X.shape, PLATEAU | TAILLEE, np.int32)
    typ[(pl < 1.0) & (bruit(X, Z, 6, 941) > 0.35)] = MOUSSE | TAILLEE
    typ[pl > 1.15] = ROC | TAILLEE
    typ[(pl < 0.8) & (E > 1250)] = NEIGE | TAILLEE
    typ[F] = FOND | TAILLEE
    typ[np.isfinite(eau) & ~F] = LIT | TAILLEE
    print(f"geiranger : fjord {int(F.sum())} colonnes, parois jusqu'à y {y.max():.0f}, Sept Sœurs de y {h1[0]:.0f} (rebord à {h1[1]} blocs), "
          f"Prétendant de y {h2[0]:.0f} (rebord à {h2[1]} blocs)")
    return finir_loupe("geiranger", L, y, typ, eau, "GNEISS", roc=1.15)


def preikestolen():
    """Preikestolen sur le relief réel du Lysefjord (loupe x4, comme la carte du mod), parois exagérées ; la
    « chaire » (table de rocher de 25 x 25 m, 604 m au-dessus de l'eau, fendue à l'arrière) est sculptée à sa vraie
    place : ~9 x 8 blocs, trois faces à pic sur le fjord."""
    R = Relief("preikestolen")
    L, E, y, eau, F = fjord_reel(R, 58.907, 6.089, 3.0, -30, 270, -250, 40, v=0.05, sigma_m=1500.0, raccord=True)
    X, Z = L.X, L.Z
    dF = ndimage.distance_transform_edt(~F)
    q = L.vers_blocs(58.9864, 6.1903)
    bord = ~F & (dF <= 1.0)
    jj, ii = np.nonzero(bord)
    pts = np.c_[X[jj, ii], Z[jj, ii]]
    p0 = pts[int(np.argmin(np.hypot(pts[:, 0] - q[0], pts[:, 1] - q[1])))]
    gz, gx = np.gradient(ndimage.gaussian_filter(dF, 2))
    j0, i0 = int(p0[1] - Z[0, 0]), int(p0[0] - X[0, 0])
    n = -np.array([gx[j0, i0], gz[j0, i0]]); n /= np.linalg.norm(n) + 1e-9          # vers le fjord
    t = np.array([-n[1], n[0]])
    ui = -((X - p0[0]) * n[0] + (Z - p0[1]) * n[1])                 # vers l'intérieur des terres
    v = (X - p0[0]) * t[0] + (Z - p0[1]) * t[1]
    # le plateau au-dessus de la paroi (relief réel, 600-700 m), au moins la hauteur de la chaire (604 m)
    plat = (ui > 9) & (ui < 17) & (np.abs(v) < 6)
    H = float(np.floor(max(T.blocs(604.0) + 4.0, np.median(y[plat])))) + 0.6
    c0 = 3.0                                                        # ligne de la paroi verticale
    wv = 1 - lisse(np.clip((np.abs(v) - 11) / 5, 0, 1))
    wu = 1 - lisse(np.clip((ui - c0 - 14) / 10, 0, 1))
    cible = H + 0.25 * np.maximum(ui - c0, 0) + 0.5 * bruit(X, Z, 3, 952)
    dessus = (ui >= c0) & (wv * wu > 0)
    y = np.where(dessus, y + (np.maximum(y, cible) - y) * wv * wu, y)
    # la chaire : ~8 x 5 blocs en avant de la paroi, à pic sur trois côtés, fendue à l'arrière
    nn = (np.abs((ui - (c0 - 2.2)) / 2.6) ** 4 + np.abs(v / 3.9) ** 4) ** 0.25
    table = (nn < 1.0) & (ui < c0 + 0.5)
    y = np.where(table, H, y)
    fente = (ui >= c0 + 0.5) & (ui < c0 + 1.5) & (np.abs(v) < 3.4)
    y = np.where(fente, H - 7.0, y)
    # devant la paroi : le fjord, profond
    devant = (ui < c0) & (wv > 0.5) & ~table & (ui > -12)
    F2 = F | devant
    dIn = ndimage.distance_transform_edt(F2)
    y = np.where(devant & ~F, 61.6 - np.minimum(1.0 + 2.2 * dIn, 18.0), y)
    eau = np.where(F2 & (L.bord() > 0.02), 63.0, eau)
    pl = M.pente_locale(y)
    typ = np.full(X.shape, PLATEAU | TAILLEE, np.int32)
    typ[(pl < 1.0) & (bruit(X, Z, 6, 951) > 0.25)] = MOUSSE | TAILLEE
    typ[pl > 1.15] = ROC | TAILLEE
    typ[table | fente | (dessus & (wv * wu > 0.5) & (ui < c0 + 6))] = ROC | TAILLEE
    typ[F2] = FOND | TAILLEE
    haut_t = H
    print(f"preikestolen : table y {haut_t:.1f} ({haut_t - 63:.0f} blocs au-dessus de l'eau), face vers {n.round(2)}")
    return finir_loupe("preikestolen", L, y, typ, eau, "GNEISS", roc=1.15)


LIEUX = {"fingal": fingal, "capri": capri, "etna": etna, "vesuve": vesuve, "meteores": meteores, "chaussee": chaussee, "mer_de_glace": mer_de_glace, "jokulsarlon": jokulsarlon, "gavarnie": gavarnie, "cervin": cervin, "tre_cime": tre_cime, "plitvice": plitvice, "geiranger": geiranger, "preikestolen": preikestolen}

if __name__ == "__main__":
    noms = [a for a in sys.argv[1:] if not a.startswith("--")]
    for n in (noms or LIEUX):
        LIEUX[n]()

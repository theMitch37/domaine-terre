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
        m = self.fin.dedans(lon, lat)
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

    def melange(self, y_reel, cov, recale=False):
        """Relief réel agrandi à l'intérieur, terrain du mod sur la bande du bord. recale : le relief du lieu est
        décalé (en bloc) à la hauteur moyenne du mod sur la bande du bord, pour que le raccord ne fasse ni marche ni
        fossé tout autour."""
        a = np.where(cov, lisse(np.clip((self.den - 4) / (self.fondu - 4), 0, 1)), 0.0)
        a = ndimage.gaussian_filter(a, 2.0)
        if recale:
            bande = cov & (a > 0.1) & (a < 0.9)
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


def finir_loupe(nom, L, y, typ, eau, palette, roc=1.0, w_typ=None, garder_fleuves=True):
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
    return M.ecrire(nom, X, Z, y, h, sommet, typ, sd, eau, palette, garder_fleuves=garder_fleuves)


def cervin():
    """Cervin (4 478 m) sur le relief réel, agrandi 4 fois au centre (loupe) : la vraie pyramide, ses arêtes (Hörnli,
    Zmutt, Lion, Furggen), ses faces et les glaciers autour ; relief local exagéré. Au bord, le relief du mod."""
    R = Relief("cervin")
    L = Zoom(45.9763, 7.6586, 4.0, -190, 190, -135, 85, fondu=45)
    y_r, E, Es = relief_exagere(R, L.lo, L.la, v=0.048, sigma_m=1800.0)
    y, a = L.melange(y_r, L.couvert(R), recale=True)
    typ = classes_montagne(L.X, L.Z, y, np.where(a > 0.05, E, 0), neige=3150, glace=2750, eboulis=(2400, 3300),
                           herbe_max=2550, roc=1.1, pente_glace=1.0, pente_neige=1.3)
    print(f"cervin : sommet y {y.max():.0f} (relief réel {E.max():.0f} m)")
    return finir_loupe("cervin", L, y, typ, np.full(L.X.shape, np.nan), "CERVIN", roc=1.1)


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
    y, a_ = L.melange(y_r, L.couvert(R), recale=True)
    E = np.where(a_ > 0.05, E, 0)
    # la rivière du mod (qui naît, sur la carte du mod, au pied nord des tours) : le lieu la reprend ; il garde son lit
    # près du bord (avec sa vallée) et la fait naître d'une vasque au pied des montagnes agrandies
    eau = np.full(X.shape, np.nan)
    eau_mod, _ = M.fleuve_du_mod(X, Z, L.h)
    lit = np.isfinite(eau_mod)
    torrent = None
    if lit.any():
        aval = lit & (L.t > 0.3)
        jl, il = np.nonzero(lit)
        kq = int(np.argmin(np.abs(L.t[jl, il] - 0.3)))
        Q = np.array([X[jl[kq], il[kq]], Z[jl[kq], il[kq]]])
        w_q = float(eau_mod[jl[kq], il[kq]])
        d_l = ndimage.distance_transform_edt(~aval)
        y = np.where(d_l < 40, np.minimum(y, L.h + (y - L.h) * lisse(np.clip((d_l - 2) / 30, 0, 1))), y)
        eau = np.where(aval & (L.bord() > 0.02), eau_mod, eau)
        # source : une vasque au bout amont du lit gardé (le torrent sort du pied des montagnes)
        ja, ia = np.nonzero(aval & (L.bord() > 0.02))
        ka = int(np.argmin(L.t[ja, ia]))
        src = np.hypot(X - X[ja[ka], ia[ka]], Z - Z[ja[ka], ia[ka]]) < 3.2
        eau = np.where(src, w_q, eau); y = np.where(src, np.minimum(y, w_q - 2.0), y)
        n0, L_t = w_q, int(aval.sum())
        torrent = (n0, w_q, L_t)
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
          (f", rivière du mod reprise (eau {torrent[1]:.0f}, {torrent[2]} colonnes de lit)" if torrent else ""))
    return finir_loupe("tre_cime", L, y, typ, eau, "DOLOMIE", roc=1.3, garder_fleuves=False)


def gavarnie():
    """Cirque de Gavarnie sur le relief réel (agrandi 5 fois, relief local exagéré) : l'amphithéâtre calcaire, ses
    gradins et ses crêtes à 3 000 m. La Grande Cascade descend la paroi du fond depuis le rebord du Marboré, en une
    suite de chutes, puis le gave de Pau coule au nord dans le fond du cirque jusqu'à une vasque vers le village."""
    R = Relief("gavarnie")
    L = Zoom(42.700, -0.010, 5.0, -180, 180, -180, 180, fondu=45)
    X, Z = L.X, L.Z
    y_r, E, Es = relief_exagere(R, L.lo, L.la, v=0.04, sigma_m=1800.0)
    y, a = L.melange(y_r, L.couvert(R), recale=True)
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


def fjord_reel(R, lat_a, lon_a, k, x0, x1, z0, z1, v=0.03, sigma_m=900.0, fondu=40):
    """Fjord sur le relief réel agrandi k fois (zoom « carte », comme le mod) depuis A, sa jonction avec la mer du mod.
    Mer = altitude <= 0 du modèle ; hauteurs = courbe du mod sur le relief lissé + relief local exagéré, si bien que
    les montagnes du lieu rejoignent celles du mod. Sur la bande du bord, l'eau est la réunion de la mer du lieu et
    de celle du mod, gardée seulement si elle rejoint la mer du mod hors du lieu (pas de bassin isolé)."""
    L = Zoom(lat_a, lon_a, k, x0, x1, z0, z1, fondu=fondu, iso=False)
    E = R.ech(L.lo, L.la)
    cov = L.couvert(R)
    mer_r = (E <= 0.5) & cov
    lab, n = ndimage.label(mer_r)
    if n:
        tailles = ndimage.sum(np.ones_like(E), lab, range(1, n + 1))
        mer_r = np.isin(lab, np.flatnonzero(tailles >= 40) + 1)
    Es = R.ech(L.lo, L.la, sigma_m)
    yt = T.blocs(np.maximum(Es, 0)) + (np.maximum(E, 0) - np.maximum(Es, 0)) * v
    dIn = ndimage.distance_transform_edt(mer_r)
    fond_r = 61.6 - np.minimum(1.0 + 2.2 * dIn, 22.0) + 0.8 * bruit(L.X, L.Z, 7, 940)
    y_r = np.where(mer_r, fond_r, np.maximum(yt, 64.0))
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
    mer = np.isin(lab, np.unique(dehors[dehors > 0]))
    rive = lisse(np.clip(ndimage.distance_transform_edt(~mer) / 3, 0, 1))
    y = np.where(mer, np.minimum(y, 61.9), np.maximum(y, 63.6 + 1.2 * rive))
    eau = np.where(mer & (L.bord() > 0.02), 63.0, np.nan)
    print(f"  fjord : {int(mer_r.sum())} colonnes de mer du relief, {int(mer.sum())} en eau, ancrage {L.c.round(1)}")
    return L, E * (a > 0.05), y, eau, mer


def geiranger():
    """Geirangerfjord sur le relief réel (agrandi 3 fois, comme la carte du mod), parois exagérées ; les Sept Sœurs
    (sept filets d'eau côte à côte) tombent de la paroi nord, le Prétendant de la paroi sud, à leur vraie place."""
    R = Relief("geiranger")
    L, E, y, eau, F = fjord_reel(R, 62.112, 6.950, 3.0, -30, 380, -120, 110, v=0.042, sigma_m=1500.0)
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
    L, E, y, eau, F = fjord_reel(R, 58.907, 6.089, 3.0, -30, 270, -250, 40, v=0.05, sigma_m=1500.0)
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


LIEUX = {"gavarnie": gavarnie, "cervin": cervin, "tre_cime": tre_cime, "plitvice": plitvice, "geiranger": geiranger, "preikestolen": preikestolen}

if __name__ == "__main__":
    noms = [a for a in sys.argv[1:] if not a.startswith("--")]
    for n in (noms or LIEUX):
        LIEUX[n]()

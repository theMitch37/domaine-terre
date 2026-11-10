"""Copie Python du terrain du mod Terre (trait de côte et hauteur de base), pour placer et contrôler les lieux.

Reproduit au bloc près : Random de Java (LegacyRandomSource), ImprovedNoise de Minecraft, la carte des côtes
(côtes fines GSHHG au bloc près, sinon cotes.png bilinéaire) et la hauteur de base (relief.png bicubique + détail). Les fleuves ne sont pas copiés.
"""
import os
import numpy as np
from PIL import Image

RACINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
CARTE = os.path.join(RACINE, "src/main/resources/domaine_terre/carte/")
BPD = 445.28          # blocs par degré en 1:250
NIVEAU_MER = 63


class RandomJava:
    """java.util.Random / LegacyRandomSource."""
    M = (1 << 48) - 1

    def __init__(self, graine):
        self.s = (graine ^ 0x5DEECE66D) & self.M

    def next(self, bits):
        self.s = (self.s * 0x5DEECE66D + 0xB) & self.M
        r = self.s >> (48 - bits)
        return r - (1 << bits) if r >= 1 << (bits - 1) else r      # int signé 32 bits

    def next_int(self, borne):
        if borne & -borne == borne:
            return (borne * (self.next(31) & 0x7FFFFFFF)) >> 31
        while True:
            bits = self.next(31) & 0x7FFFFFFF
            val = bits % borne
            if bits - val + (borne - 1) < (1 << 31):
                return val

    def next_double(self):
        return (((self.next(26) & 0x3FFFFFF) << 27) + (self.next(27) & 0x7FFFFFF)) * 2.0 ** -53


GRAD = np.array([[1, 1, 0], [-1, 1, 0], [1, -1, 0], [-1, -1, 0], [1, 0, 1], [-1, 0, 1], [1, 0, -1], [-1, 0, -1],
                 [0, 1, 1], [0, -1, 1], [0, 1, -1], [0, -1, -1], [1, 1, 0], [0, -1, 1], [-1, 1, 0], [0, -1, -1]], float)


class ImprovedNoise:
    """net.minecraft.world.level.levelgen.synth.ImprovedNoise (vectorisé)."""

    def __init__(self, rnd):
        self.xo, self.yo, self.zo = rnd.next_double() * 256, rnd.next_double() * 256, rnd.next_double() * 256
        p = list(range(256))
        for i in range(256):
            j = rnd.next_int(256 - i)
            p[i], p[i + j] = p[i + j], p[i]
        self.p = np.array(p, np.int64)

    def _p(self, i):
        return self.p[i & 255]

    def noise(self, x, y, z):
        x = np.asarray(x, float) + self.xo; y = np.asarray(y, float) + self.yo; z = np.asarray(z, float) + self.zo
        ix, iy, iz = np.floor(x).astype(np.int64), np.floor(y).astype(np.int64), np.floor(z).astype(np.int64)
        fx, fy, fz = x - ix, y - iy, z - iz
        a, b = self._p(ix), self._p(ix + 1)
        aa, ab, ba, bb = self._p(a + iy), self._p(a + iy + 1), self._p(b + iy), self._p(b + iy + 1)
        def g(h, dx, dy, dz):
            gg = GRAD[h & 15]
            return gg[..., 0] * dx + gg[..., 1] * dy + gg[..., 2] * dz
        d000 = g(self._p(aa + iz), fx, fy, fz); d100 = g(self._p(ba + iz), fx - 1, fy, fz)
        d010 = g(self._p(ab + iz), fx, fy - 1, fz); d110 = g(self._p(bb + iz), fx - 1, fy - 1, fz)
        d001 = g(self._p(aa + iz + 1), fx, fy, fz - 1); d101 = g(self._p(ba + iz + 1), fx - 1, fy, fz - 1)
        d011 = g(self._p(ab + iz + 1), fx, fy - 1, fz - 1); d111 = g(self._p(bb + iz + 1), fx - 1, fy - 1, fz - 1)
        s = lambda t: t * t * t * (t * (t * 6 - 15) + 10)
        u, v, w = s(fx), s(fy), s(fz)
        l = lambda t, a_, b_: a_ + t * (b_ - a_)
        return l(w, l(v, l(u, d000, d100), l(u, d010, d110)), l(v, l(u, d001, d101), l(u, d011, d111)))


_r = RandomJava(20261014)
BRUIT_COTE = ImprovedNoise(_r)
BRUIT_DETAIL = ImprovedNoise(_r)
_cotes = _relief = None


def _cartes():
    global _cotes, _relief
    if _cotes is None:
        _cotes = (np.array(Image.open(CARTE + "cotes.png")).astype(float) - 128) / 4.0
        _relief = np.array(Image.open(CARTE + "relief.png"), dtype=np.float64) - 11000
    return _cotes, _relief


def _idx(g, ix, iy):
    H, W = g.shape
    return g[np.clip(iy, 0, H - 1), np.mod(ix, W)]


def _distance_grossiere(x, z):
    cotes, _ = _cartes()
    lon, lat = x / BPD, -z / BPD
    fx = (lon + 180) / 360 * 7200 - 0.5; fy = (90 - lat) / 180 * 3600 - 0.5
    ix, iy = np.floor(fx).astype(int), np.floor(fy).astype(int); tx, ty = fx - ix, fy - iy
    a, b, c, d = _idx(cotes, ix, iy), _idx(cotes, ix + 1, iy), _idx(cotes, ix, iy + 1), _idx(cotes, ix + 1, iy + 1)
    return (a + (b - a) * tx) * (1 - ty) + (c + (d - c) * tx) * ty


# ---------------------------------------------------------------- côtes fines (CotesFines.java, outils/cotes_fines.py)
RAYON_FIN = 48
_fines = None


def _cotes_fines():
    global _fines
    if _fines is None:
        import struct, zlib
        chemin = CARTE + "cotes_fines.bin"
        if not os.path.exists(chemin):
            _fines = False
            return _fines
        b = open(chemin, "rb").read()
        assert b[:4] == b"COTE"
        _, _, T, TX, TY = struct.unpack_from("<idiii", b, 4)
        o = 4 + struct.calcsize("<idiii")
        etat = np.frombuffer(b, np.uint8, TX * TY, o).reshape(TY, TX); o += TX * TY
        n, = struct.unpack_from("<i", b, o); o += 4
        tab = np.frombuffer(b, "<i4", 2 * n, o).reshape(n, 2); o += 8 * n
        pos = {}
        for k, L in tab:
            pos[int(k)] = (o, int(L)); o += int(L)
        _fines = dict(b=b, T=T, TX=TX, TY=TY, etat=etat, pos=pos, zlib=zlib)
    return _fines


def _masque_fin(gx0, gy0, W, H):
    """Terre (True) des cases [gx0, gx0+W) x [gy0, gy0+H)."""
    F = _cotes_fines(); T, TX, TY = F["T"], F["TX"], F["TY"]
    m = np.zeros((H, W), bool)
    for ty in range(gy0 // T, (gy0 + H - 1) // T + 1):
        for tx in range(gx0 // T, (gx0 + W - 1) // T + 1):
            ya, yb = max(ty * T, gy0), min((ty + 1) * T, gy0 + H)
            xa, xb = max(tx * T, gx0), min((tx + 1) * T, gx0 + W)
            if ty < 0 or ty >= TY:
                t = np.full((T, T), ty >= TY)
            else:
                e = F["etat"][ty, tx % TX]
                if e != 2:
                    t = np.full((T, T), bool(e))
                else:
                    o, L = F["pos"][int(ty * TX + tx % TX)]
                    t = np.unpackbits(np.frombuffer(F["zlib"].decompress(F["b"][o:o + L]), np.uint8)).reshape(T, T).astype(bool)
            m[ya - gy0:yb - gy0, xa - gx0:xb - gx0] = t[ya - ty * T:yb - ty * T, xa - tx * T:xb - tx * T]
    return m


def distance_fine(x, z):
    """CotesFines.distance en cases (≈ blocs à 1:250), bornée à ±48, au 1/16 près comme en Java."""
    from scipy import ndimage
    x = np.asarray(x, float); z = np.asarray(z, float)
    gx = np.floor(x + 0.5 + 180 * BPD).astype(np.int64); gy = np.floor(z + 0.5 + 90 * BPD).astype(np.int64)
    M = RAYON_FIN
    gx0, gy0 = int(gx.min()) - M, int(gy.min()) - M
    W, H = int(gx.max()) - gx0 + M + 1, int(gy.max()) - gy0 + M + 1
    m = _masque_fin(gx0, gy0, W, H)
    d = np.where(m, ndimage.distance_transform_edt(m) - 0.5, -(ndimage.distance_transform_edt(~m) - 0.5))
    d = np.clip(d, -M, M)
    return np.round(d[gy - gy0, gx - gx0] * 16) / 16


def distance_cote(x, z):
    """Terrain.distanceCote : distance signée à la côte en minutes d'arc (positive dans les terres)."""
    x = np.asarray(x, float); z = np.asarray(z, float)
    sd = _distance_grossiere(x, z)
    if not _cotes_fines():
        n = BRUIT_COTE.noise(x / 37.0, 0, z / 37.0) * 0.8 + BRUIT_COTE.noise(x / 11.0, 10, z / 11.0) * 0.35
        return sd + n
    f = distance_fine(x, z)
    mpc = 60 / 445.28; bord = RAYON_FIN * mpc
    return np.where(np.abs(f) < RAYON_FIN, f * mpc, np.where(f > 0, np.maximum(sd, bord), np.minimum(sd, -bord)))


def _cub(p0, p1, p2, p3, t):
    return p1 + 0.5 * t * (p2 - p0 + t * (2 * p0 - 5 * p1 + 4 * p2 - p3 + t * (3 * (p1 - p2) + p3 - p0)))


def relief(lon, lat):
    _, rel = _cartes()
    fx = (lon + 180) / 360 * 7200 - 0.5; fy = (90 - lat) / 180 * 3600 - 0.5
    ix, iy = np.floor(fx).astype(int), np.floor(fy).astype(int); tx, ty = fx - ix, fy - iy
    l = [_cub(*(_idx(rel, ix + k, iy - 1 + j) for k in (-1, 0, 1, 2)), tx) for j in range(4)]
    return _cub(*l, ty)


def blocs(a):
    """Copie de Terrain.blocsDepuisAltitude (monde de y -512 à 1024 depuis le 10/11/2026)."""
    a = np.asarray(a, float)
    mer = np.select([a > -200, a > -6000], [62 + a / 200 * 20, 42 + (a + 200) / 5800 * 292],
                    -250 - 170 * np.minimum((-a - 6000) / 3800, 1) - 80 * (1 - (1 - np.clip((-a - 9800) / 500, 0, 1)) ** 2.5))
    terre = np.select([a <= 500, a <= 2000, a <= 4000],
                      [64 + a / 500 * 16, 80 + (a - 500) / 1500 * 60, 140 + (a - 2000) / 2000 * 100],
                      240 + np.minimum((a - 4000) / 4849, 1) * 380)
    return np.where(a < 0, mer, terre)


def lisse(t):
    t = np.clip(t, 0, 1); return t * t * (3 - 2 * t)


def pente(x, z):
    lo, la, d = x / BPD, -z / BPD, 0.05
    gx = relief(lo + d, la) - relief(lo - d, la); gz = relief(lo, la + d) - relief(lo, la - d)
    return np.sqrt(gx * gx + gz * gz) / (2 * d * 111.32)


def hauteur_base(x, z, eaux=True):
    """Terrain.colonne sans les lieux : hauteur visée du sol en y, fleuves et lacs compris."""
    X, Z = np.asarray(x, float), np.asarray(z, float)
    sd = distance_cote(x, z); lon, lat = x / BPD, -z / BPD
    alt = relief(lon, lat)
    p = np.clip(pente(x, z) / 80, 0, 1)
    detail = BRUIT_DETAIL.noise(x / 48.0, 0, z / 48.0) * (1.2 + 6.0 * p) + BRUIT_DETAIL.noise(x / 13.0, 5, z / 13.0) * 0.6
    h_terre = blocs(np.maximum(alt, 1)) + detail
    terre = NIVEAU_MER + 0.6 + (np.maximum(h_terre, NIVEAU_MER + 0.6) - NIVEAU_MER - 0.6) * lisse(sd / 2)
    h_mer = blocs(np.minimum(alt, -1))
    mer = NIVEAU_MER - 1 + (np.minimum(h_mer, NIVEAU_MER - 1) - NIVEAU_MER + 1) * lisse(-sd / 2)
    h = np.where(sd >= 0, terre, mer)
    if not eaux:                                    # sans fleuves ni lacs (pour le plafond des lacs)
        return h, sd
    Xa = X if np.ndim(x) else np.array(x); Za = Z if np.ndim(z) else np.array(z)
    _, _, nivl, pres = niveaux_lacs(Xa, Za, sd)
    h, _, _, _ = appliquer_rivieres(h, Xa, Za, sd, np.where(pres, nivl, np.iinfo(np.int64).min))
    lb = _RIV_CACHE["present"] & (_RIV_CACHE["d"] <= _RIV_CACHE["hw"] + BERGE_RIVIERE)
    h, _, _ = appliquer_lacs(h, X if np.ndim(x) else np.array(x), Z if np.ndim(z) else np.array(z), sd, lb)
    return h, sd


def facteur(h, sd):
    """Terrain.facteur hors fleuves et hors lieux (un lieu met aussi 30)."""
    return np.where(sd >= 0, 30.0, 8.0 + 10.0 * np.clip((h - 40.0) / 18.0, 0, 1))


def sol_exact(x0, z0, W, D):
    """Dessus du sol réel (y du bloc plein le plus haut) sur la grille [x0, x0+W) x [z0, z0+D), hors fleuves et lieux.

    Depuis 0.3.2 la densité est linéaire en y : 4 * facteur * (H - y) / 128 (sloped_cheese sans coude ni bruit 3D),
    interpolée par le jeu sur des cellules de 4 x 8 x 4 blocs. Le sol passe donc à y* = moyenne des H aux 4 coins de la
    cellule, pondérée par l'interpolation et le facteur ; le bloc le plus haut est ceil(y*) - 1.
    """
    cx0, cz0 = (x0 // 4) * 4, (z0 // 4) * 4
    nx, nz = (x0 + W - cx0) // 4 + 2, (z0 + D - cz0) // 4 + 2
    GX, GZ = np.meshgrid(cx0 + 4.0 * np.arange(nx), cz0 + 4.0 * np.arange(nz))
    HC, SDC = hauteur_base(GX, GZ); FC = facteur(HC, SDC)
    X, Z = np.meshgrid(np.arange(x0, x0 + W), np.arange(z0, z0 + D))
    i, j = (X - cx0) // 4, (Z - cz0) // 4
    tx, tz = (X - cx0 - 4 * i) / 4.0, (Z - cz0 - 4 * j) / 4.0
    w = [((1 - tx) * (1 - tz), j, i), (tx * (1 - tz), j, i + 1), ((1 - tx) * tz, j + 1, i), (tx * tz, j + 1, i + 1)]
    num = sum(a * FC[jj, ii] * HC[jj, ii] for a, jj, ii in w)
    den = sum(a * FC[jj, ii] for a, jj, ii in w)
    sol = np.ceil(num / den).astype(int) - 1
    # berges des lacs : plancher de densité (Terrain.plancher), rien sous l'eau du lac voisin sur 4 cases
    Xf, Zf = X.astype(float), Z.astype(float)
    sdf = distance_cote(Xf, Zf)
    sans = np.iinfo(np.int64).min
    _, _, nivl, pres = niveaux_lacs(Xf, Zf, sdf)
    _, _, _, berge_riv = appliquer_rivieres(np.zeros(X.shape), Xf, Zf, sdf, np.where(pres, nivl, sans))
    lb = _RIV_CACHE["present"] & (_RIV_CACHE["d"] <= _RIV_CACHE["hw"] + BERGE_RIVIERE)
    _, eau_lac, berge = appliquer_lacs(np.zeros(X.shape), Xf, Zf, sdf, lb)
    lac_eau = _eau_lac_large(Xf, Zf, sdf)
    sol = np.where(berge != sans, np.maximum(sol, berge), sol)
    return np.where((berge_riv != sans) & ~lac_eau, np.maximum(sol, berge_riv), sol)


DEMI_LARGEUR = {1: 30.0, 2: 12.0, 3: 4.5}     # Terrain.demiLargeur
VALLEE_MAX = 64.0                              # Terrain.VALLEE_MAX
_fleuves = None


def _segments_fleuves():
    """Segments des cours d'eau (Fleuves.charger) : ax, az, bx, bz, classe, niveau d'eau en a, niveau en b.
    Niveau d'un sommet (étape C2) : deux blocs sous le fond de vallée réel lissé, jamais sous la mer ; puis il ne fait que
    descendre de l'amont (le bout le plus haut) vers l'aval."""
    global _fleuves
    if _fleuves is None:
        import json
        tab = json.load(open(os.path.join(CARTE, "fleuves.json")))
        polys = [np.array(r["p"], float).reshape(-1, 2) for r in tab]
        tout = np.vstack([q for q in polys if len(q)])
        xs, zs = tout[:, 0] * BPD, -tout[:, 1] * BPD
        niv_tout = np.maximum(NIVEAU_MER, np.floor(_niveau_vallee(np.floor(xs), np.floor(zs))).astype(np.int64) - 2)
        # près d'un lac (48 cases), jamais sous le niveau du lac (ETOPO met une valeur vide sous les lacs)
        lac_pts = _lacs_points(np.floor(xs), np.floor(zs))
        c = _carte_lacs()
        if c:
            nl = np.minimum(niveau_lac(c["alt"][lac_pts]), c["plafond"][lac_pts]).astype(np.int64)
            niv_tout = np.where(lac_pts > 0, np.maximum(niv_tout, nl), niv_tout)
        seg, k = [], 0
        for r, q in zip(tab, polys):
            n = len(q)
            nv = niv_tout[k:k + n].copy(); k += n
            if n < 2:
                continue
            amont_debut = nv[0] >= nv[-1]
            if amont_debut:
                nv = np.minimum.accumulate(nv)
            else:
                nv = np.minimum.accumulate(nv[::-1])[::-1]
            src = np.zeros(n - 1)
            if amont_debut:
                src[0] += 1
            else:
                src[-1] += 2
            x, z = q[:, 0] * BPD, -q[:, 1] * BPD
            seg.append(np.c_[x[:-1], z[:-1], x[1:], z[1:], np.full(n - 1, r["c"]), nv[:-1], nv[1:], src])
        _fleuves = np.vstack(seg)
    return _fleuves


PROFONDEUR = {1: 6, 2: 4, 3: 2}                # Terrain.profondeur
VALLEE_EAU, VALLEE_SECHE = 80.0, 86.0


def _niveau_vallee(fx, fz):
    """Terrain.niveauVallee : minimum du relief en 5 points espacés de 0,055°, en y."""
    lo, la, dd = fx / BPD, -fz / BPD, 0.055
    mini = np.minimum.reduce([relief(lo + a, la + b) for a, b in ((0, 0), (dd, 0), (-dd, 0), (0, dd), (0, -dd))])
    return blocs(np.maximum(mini, 1))


def rivieres(X, Z):
    """Fleuves.proche + Terrain.riviereBrute : pour chaque colonne, le cours d'eau retenu (plus petit d - demi-largeur)
    s'il influence la colonne. Rend (présent, distance, demi-largeur, profondeur, niveau du fond de vallée)."""
    s = _segments_fleuves()
    X = np.asarray(X, float); Z = np.asarray(Z, float)
    x0, x1, z0, z1 = X.min(), X.max(), Z.min(), Z.max()
    m = 30 + VALLEE_MAX + 2
    k = (np.maximum(s[:, 0], s[:, 2]) > x0 - m) & (np.minimum(s[:, 0], s[:, 2]) < x1 + m) & \
        (np.maximum(s[:, 1], s[:, 3]) > z0 - m) & (np.minimum(s[:, 1], s[:, 3]) < z1 + m)
    score = np.full(X.shape, np.inf); dmin = np.zeros(X.shape); cx = np.zeros(X.shape); cz = np.zeros(X.shape)
    cl = np.zeros(X.shape, np.int64); eau = np.zeros(X.shape, np.int64)
    for ax, az, bx, bz, c, na, nb, src in s[k]:
        ax, az, bx, bz = (float(np.float32(v)) for v in (ax, az, bx, bz))     # Java : segments en float
        dx, dz = bx - ax, bz - az
        l2 = dx * dx + dz * dz
        t0 = ((X - ax) * dx + (Z - az) * dz) / l2 if l2 > 0 else np.zeros(X.shape)
        au_dela = ((t0 < 0) & ((int(src) & 1) > 0)) | ((t0 > 1) & ((int(src) & 2) > 0))
        t = np.clip(t0, 0, 1)
        px, pz = ax + t * dx, az + t * dz
        d = np.hypot(X - px, Z - pz) + np.where(au_dela, DEMI_LARGEUR[int(c)], 0.0)
        sc = d - DEMI_LARGEUR[int(c)]
        mieux = sc < score
        score = np.where(mieux, sc, score); dmin = np.where(mieux, d, dmin)
        cx = np.where(mieux, px, cx); cz = np.where(mieux, pz, cz); cl = np.where(mieux, int(c), cl)
        eau = np.where(mieux, np.floor(na + (nb - na) * t).astype(np.int64), eau)
    hw = np.where(cl > 0, np.vectorize(lambda c: DEMI_LARGEUR.get(int(c), 4.5))(np.maximum(cl, 1)), 0.0)
    present = np.isfinite(score) & (dmin <= hw + VALLEE_MAX)
    niveau = np.zeros(X.shape)
    if present.any():
        niveau[present] = _niveau_vallee(np.floor(cx[present]), np.floor(cz[present]))
    prof = np.vectorize(lambda c: PROFONDEUR.get(int(c), 2))(np.maximum(cl, 1))
    return present, dmin, hw, prof, niveau, eau


BERGE_RIVIERE, EAU_RIVIERE = 4.0, 20.0             # Terrain
_RIV_CACHE = {}


def appliquer_rivieres(h, X, Z, sd, w_min=None):
    """Terrain.calculerHauteur (étape C2) : lit sous le niveau du cours d'eau, rive un demi-bloc au-dessus, pente douce
    jusqu'au terrain ; berge jamais sous l'eau près du lit. w_min : niveau minimal (près d'un lac, celui du lac).
    Rend (h, présent, niveau de l'eau, berge pour le plancher)."""
    present, d, hw, prof, niveau, w = rivieres(X, Z)
    present &= np.asarray(sd) >= 0
    if w_min is not None:
        w = np.maximum(w, w_min)
    _RIV_CACHE["d"], _RIV_CACHE["hw"], _RIV_CACHE["present"] = d, hw, present
    u = d / np.maximum(hw, 1e-9)
    lit = (w - 1) - np.maximum(1.0, prof * (1 - u * u)) + 0.5
    larg = np.clip((h - w) * 2.0, 2.0 * hw, VALLEE_MAX)
    t = lisse(np.clip((d - hw) / np.maximum(larg, 1e-9), 0, 1))
    rive = np.minimum(h, (w + 0.5) + (h - (w + 0.5)) * t)
    rive = np.where(d <= hw + BERGE_RIVIERE, np.maximum(rive, w + 0.6), rive)
    hr = np.where(d <= hw, np.minimum(h, lit), rive)
    sans = np.iinfo(np.int64).min
    berge = np.where(present & (d > hw) & (d <= hw + BERGE_RIVIERE), w, sans)
    return np.where(present, hr, h), present, w, berge


def influence_fleuves(X, Z):
    """Marge (blocs) au-delà de la zone où un fleuve du mod creuse sa vallée : < 0 dans la vallée (comme Terrain :
    demi-largeur + largeurVallee selon le fond lissé, rien si vallée sèche). Un lieu en tuiles n'y sculpte rien."""
    present, d, hw, prof, niveau, w = rivieres(X, Z)
    # la vallée réelle (Terrain.largeurVallee depuis le terrain sans les eaux) : près d'une embouchure, sur un plateau
    # bas, elle est bien plus étroite que VALLEE_MAX (sinon les falaises d'Étretat s'abaissaient jusqu'à 100 blocs de
    # la Seine)
    h0, _ = hauteur_base(np.asarray(X, float), np.asarray(Z, float), eaux=False)
    larg = np.clip((h0 - w) * 2, 2 * hw, VALLEE_MAX)
    return np.where(present, d - hw - larg, np.inf)


# ---------------------------------------------------------------- lacs (étape C1), comme Lacs.java et Terrain
RAYON_LAC = 48
BERGE = 20.0                                   # Terrain.BERGE
_lacs = None


def _carte_lacs():
    """lacs.bin (outils/lacs_fins.py) : table des lacs et index des tuiles."""
    global _lacs
    if _lacs is None:
        import struct
        chemin = os.path.join(CARTE, "lacs.bin")
        if not os.path.exists(chemin):
            _lacs = False
            return _lacs
        b = open(chemin, "rb").read()
        assert b[:4] == b"LACS"
        version, _, t, tx, ty = struct.unpack_from("<idiii", b, 4)
        p = 4 + struct.calcsize("<idiii")
        (L,) = struct.unpack_from("<i", b, p); p += 4
        nv = 2 if version == 1 else 3
        tab = np.frombuffer(b, "<f4", nv * L, p).reshape(L, nv); p += 4 * nv * L
        (n,) = struct.unpack_from("<i", b, p); p += 4
        idx = np.frombuffer(b, "<i4", 2 * n, p).reshape(n, 2); p += 8 * n
        debut = {}
        for k, lg in idx:
            debut[int(k)] = (p, int(lg)); p += int(lg)
        pla = tab[:, 2] if nv == 3 else np.full(L, 3.4e38, np.float32)
        _lacs = {"b": b, "T": t, "TX": tx, "TY": ty, "alt": np.r_[0, tab[:, 0]], "sup": np.r_[0, tab[:, 1]],
                 "plafond": np.r_[3.4e38, pla].astype(float),
                 "debut": debut, "cache": {}}
    return _lacs


def _ids_tuile(c, txi, tyi):
    import zlib
    k = tyi * c["TX"] + (txi % c["TX"])
    if k not in c["debut"] or tyi < 0 or tyi >= c["TY"]:
        return None
    if k not in c["cache"]:
        p, lg = c["debut"][k]
        c["cache"][k] = np.frombuffer(zlib.decompress(c["b"][p:p + lg]), "<u2").reshape(c["T"], c["T"])
    return c["cache"][k]


def lacs_proches(X, Z):
    """(numéro du lac le plus proche, distance signée à son rivage en cases, + dans le lac) comme Lacs.proche :
    0 et 0 au-delà de RAYON_LAC. X, Z : grille régulière de colonnes (pas 1)."""
    from scipy import ndimage
    c = _carte_lacs()
    lac = np.zeros(X.shape, np.int64); dist = np.zeros(X.shape)
    if not c:
        return lac, dist
    T_ = c["T"]
    gx0, gy0 = int(np.floor(X.min() + 0.5 + 180 * BPD)), int(np.floor(Z.min() + 0.5 + 90 * BPD))
    gx1, gy1 = int(np.floor(X.max() + 0.5 + 180 * BPD)), int(np.floor(Z.max() + 0.5 + 90 * BPD))
    M = RAYON_LAC + 2
    a0, a1, b0, b1 = gx0 - M, gx1 + M + 1, gy0 - M, gy1 + M + 1
    ids = np.zeros((b1 - b0, a1 - a0), np.int64)
    for tyi in range(b0 // T_, (b1 - 1) // T_ + 1):
        for txi in range(a0 // T_, (a1 - 1) // T_ + 1):
            m = _ids_tuile(c, txi, tyi)
            if m is None:
                continue
            j0, i0 = max(tyi * T_, b0), max(txi * T_, a0)
            j1, i1 = min((tyi + 1) * T_, b1), min((txi + 1) * T_, a1)
            ids[j0 - b0:j1 - b0, i0 - a0:i1 - a0] = m[j0 - tyi * T_:j1 - tyi * T_, i0 - txi * T_:i1 - txi * T_]
    if not ids.any():
        return lac, dist
    eau = ids > 0
    d_hors, (ji, ii) = ndimage.distance_transform_edt(~eau, return_indices=True)
    d_dans = ndimage.distance_transform_edt(eau)
    gx = np.floor(X + 0.5 + 180 * BPD).astype(np.int64) - a0
    gy = np.floor(Z + 0.5 + 90 * BPD).astype(np.int64) - b0
    dans = eau[gy, gx]
    v = np.where(dans, d_dans[gy, gx] - 0.5, -(d_hors[gy, gx] - 0.5))
    num = np.where(dans, ids[gy, gx], ids[ji[gy, gx], ii[gy, gx]])
    v = np.round(np.clip(v, -RAYON_LAC, RAYON_LAC) * 16) / 16
    loin = v < -RAYON_LAC + 1e-9
    lac = np.where(loin, 0, num); dist = np.where(loin, 0.0, v)
    return lac, dist


def niveau_lac(alt):
    alt = np.asarray(alt, float)
    y = np.where(alt < 0, 64 + alt / 500 * 16, blocs(np.maximum(alt, 0)))
    return np.floor(y).astype(np.int64)


def niveaux_lacs(X, Z, sd):
    """(numéro du lac, distance signée, niveau d'eau du lac, près du lac (dedans ou à moins de BERGE cases))."""
    c = _carte_lacs()
    if not c:
        z = np.zeros(np.shape(X), np.int64)
        return z, np.zeros(np.shape(X)), z, np.zeros(np.shape(X), bool)
    lac, d = lacs_proches(X, Z)
    lac = np.where(np.asarray(sd) >= 0, lac, 0)
    niv = np.minimum(niveau_lac(c["alt"][lac]), c["plafond"][lac]).astype(np.int64)
    pres = (lac > 0) & ((d > 0) | (-d <= BERGE))
    return lac, d, niv, pres


def appliquer_lacs(h, X, Z, sd, lit_berge=None):
    """Terrain.colonne : cuvette dans les lacs, berges autour. Rend (h, niveau d'eau du lac ou None, niveau de berge)."""
    c = _carte_lacs()
    sans = np.full(h.shape, np.iinfo(np.int64).min)
    if not c:
        return h, sans, sans
    lac, d = lacs_proches(X, Z)
    lac = np.where(sd >= 0, lac, 0)
    niv = np.minimum(niveau_lac(c["alt"][lac]), c["plafond"][lac]).astype(np.int64)
    sup = c["sup"][lac]
    pmax = np.clip(2.0 + 2.2 * np.log10(sup + 1.0), 2.0, 14.0)
    larg = np.clip(pmax * 3.0, 4.0, 40.0)
    fond = niv - 2.9 - (pmax - 1.0) * lisse(np.clip(d / larg, 0, 1))
    dh = -d
    berge = np.maximum(h, niv + 0.6 - 0.3 * np.maximum(dh - BERGE, 0.0))
    xx = np.maximum(dh - 2.0, 0.0)
    berge = np.minimum(berge, niv + 0.6 + 0.6 * xx + 0.02 * xx * xx)
    berge = np.where(dh < 3.0, np.maximum(berge, niv + 0.6), berge)
    t = lisse(np.clip((dh - 36.0) / 12.0, 0, 1))
    berge = berge + (h - berge) * t
    dedans = (lac > 0) & (d > 0); autour = (lac > 0) & (d <= 0)
    if lit_berge is not None:                     # lit et berge d'un cours d'eau : la berge du lac ne les comble pas
        autour_forme = autour & ~lit_berge
    else:
        autour_forme = autour
    h = np.where(dedans, fond, np.where(autour_forme, berge, h))
    return h, np.where(dedans, niv, sans), np.where(autour_forme & (dh < BERGE), niv, sans)


def _eau_lac_large(X, Z, sd):
    """Colonnes où l'aquifère prend le niveau d'un lac (dans le lac et à moins de BERGE cases) : Terrain.eauLac."""
    c = _carte_lacs()
    if not c:
        return np.zeros(X.shape, bool)
    lac, d = lacs_proches(X, Z)
    return (lac > 0) & (np.asarray(sd) >= 0) & ((d > 0) | (-d <= BERGE))


def _lacs_points(X, Z):
    """Lac le plus proche (dans RAYON_LAC cases) de points épars, comme Lacs.proche : regroupés par tuile de lacs."""
    from scipy import ndimage
    c = _carte_lacs()
    X = np.asarray(X, float); Z = np.asarray(Z, float)
    res = np.zeros(X.shape, np.int64)
    if not c:
        return res
    T_ = c["T"]; M = RAYON_LAC + 2
    gx = np.floor(X + 0.5 + 180 * BPD).astype(np.int64); gy = np.floor(Z + 0.5 + 90 * BPD).astype(np.int64)
    tx, ty = gx // T_, gy // T_
    cles = {}
    for k in np.unique(ty * 100000 + tx):
        tyi, txi = divmod(int(k), 100000)
        if not any(_ids_tuile(c, txi + a, tyi + b) is not None for a in (-1, 0, 1) for b in (-1, 0, 1)):
            continue
        sel = (tx == txi) & (ty == tyi)
        a0, b0 = txi * T_ - M, tyi * T_ - M
        ids = np.zeros((T_ + 2 * M, T_ + 2 * M), np.int64)
        for tyy in range((b0) // T_, (b0 + T_ + 2 * M - 1) // T_ + 1):
            for txx in range((a0) // T_, (a0 + T_ + 2 * M - 1) // T_ + 1):
                m = _ids_tuile(c, txx, tyy)
                if m is None:
                    continue
                j0, i0 = max(tyy * T_, b0), max(txx * T_, a0)
                j1, i1 = min((tyy + 1) * T_, b0 + T_ + 2 * M), min((txx + 1) * T_, a0 + T_ + 2 * M)
                ids[j0 - b0:j1 - b0, i0 - a0:i1 - a0] = m[j0 - tyy * T_:j1 - tyy * T_, i0 - txx * T_:i1 - txx * T_]
        if not ids.any():
            continue
        eau = ids > 0
        d_hors, (ji, ii) = ndimage.distance_transform_edt(~eau, return_indices=True)
        lj, li = gy[sel] - b0, gx[sel] - a0
        dans = eau[lj, li]
        v = np.where(dans, 1.0, -(d_hors[lj, li] - 0.5))
        num = np.where(dans, ids[lj, li], ids[ji[lj, li], ii[lj, li]])
        res[sel] = np.where(np.round(v * 16) / 16 < -RAYON_LAC + 1e-9, 0, num)
    return res

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
    a = np.asarray(a, float)
    mer = np.select([a > -200, a > -6000], [62 + a / 200 * 20, 42 + (a + 200) / 5800 * 42],
                    -np.minimum((-a - 6000) / 4300, 1) * 61)
    return np.where(a < 0, mer,
                    np.where(a <= 500, 64 + a / 500 * 16, np.where(a <= 2000, 80 + (a - 500) / 1500 * 60,
                                                                    140 + np.minimum((a - 2000) / 6800, 1) * 160)))


def lisse(t):
    t = np.clip(t, 0, 1); return t * t * (3 - 2 * t)


def pente(x, z):
    lo, la, d = x / BPD, -z / BPD, 0.05
    gx = relief(lo + d, la) - relief(lo - d, la); gz = relief(lo, la + d) - relief(lo, la - d)
    return np.sqrt(gx * gx + gz * gz) / (2 * d * 111.32)


def hauteur_base(x, z):
    """Terrain.hauteurBase (sans les fleuves) : hauteur visée du sol en y."""
    sd = distance_cote(x, z); lon, lat = x / BPD, -z / BPD
    alt = relief(lon, lat)
    p = np.clip(pente(x, z) / 80, 0, 1)
    detail = BRUIT_DETAIL.noise(x / 48.0, 0, z / 48.0) * (1.2 + 6.0 * p) + BRUIT_DETAIL.noise(x / 13.0, 5, z / 13.0) * 0.6
    h_terre = blocs(np.maximum(alt, 1)) + detail
    terre = NIVEAU_MER + 0.6 + (np.maximum(h_terre, NIVEAU_MER + 0.6) - NIVEAU_MER - 0.6) * lisse(sd / 2)
    h_mer = blocs(np.minimum(alt, -1))
    mer = NIVEAU_MER - 1 + (np.minimum(h_mer, NIVEAU_MER - 1) - NIVEAU_MER + 1) * lisse(-sd / 2)
    return np.where(sd >= 0, terre, mer), sd

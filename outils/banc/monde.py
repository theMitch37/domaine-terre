"""Lecture des fichiers de région Minecraft 1.18+ (.mca) : NBT, sections, palettes de blocs.

extraire(dossier_region, x0, x1, z0, z1, y0, y1) -> (noms, blocs[z, y, x] en uint16, statuts)
"""
import gzip, os, struct, zlib
import numpy as np


class _Lecteur:
    def __init__(self, b):
        self.b, self.p = b, 0

    def lire(self, fmt, n):
        v = struct.unpack_from(fmt, self.b, self.p); self.p += n
        return v[0]

    def chaine(self):
        n = self.lire(">H", 2); s = self.b[self.p:self.p + n].decode("utf-8", "replace"); self.p += n
        return s

    def charge(self, t):
        if t == 1: return self.lire(">b", 1)
        if t == 2: return self.lire(">h", 2)
        if t == 3: return self.lire(">i", 4)
        if t == 4: return self.lire(">q", 8)
        if t == 5: return self.lire(">f", 4)
        if t == 6: return self.lire(">d", 8)
        if t == 7:
            n = self.lire(">i", 4); v = self.b[self.p:self.p + n]; self.p += n; return v
        if t == 8: return self.chaine()
        if t == 9:
            st = self.lire(">b", 1); n = self.lire(">i", 4)
            return [self.charge(st) for _ in range(n)]
        if t == 10:
            d = {}
            while True:
                st = self.lire(">b", 1)
                if st == 0: return d
                k = self.chaine(); d[k] = self.charge(st)
        if t == 11:
            n = self.lire(">i", 4); v = np.frombuffer(self.b, ">i4", n, self.p); self.p += 4 * n; return v
        if t == 12:
            n = self.lire(">i", 4); v = np.frombuffer(self.b, ">i8", n, self.p); self.p += 8 * n; return v
        raise ValueError(f"tag NBT inconnu {t}")


def nbt(b):
    r = _Lecteur(b)
    t = r.lire(">b", 1); r.chaine()
    return r.charge(t)


def chunks_region(chemin):
    """Itère (cx, cz, nbt) sur les chunks d'un fichier .mca."""
    data = open(chemin, "rb").read()
    if len(data) < 8192: return
    for i in range(1024):
        off = int.from_bytes(data[i * 4:i * 4 + 3], "big"); cnt = data[i * 4 + 3]
        if off == 0 or cnt == 0: continue
        p = off * 4096
        n = struct.unpack_from(">i", data, p)[0]; comp = data[p + 4]
        brut = data[p + 5:p + 4 + n]
        if comp == 2: brut = zlib.decompress(brut)
        elif comp == 1: brut = gzip.decompress(brut)
        elif comp != 3: continue
        c = nbt(brut)
        yield c.get("xPos"), c.get("zPos"), c


def _indices(section):
    bs = section.get("block_states")
    if bs is None: return None, None
    pal = bs["palette"]
    if "data" not in bs or len(pal) == 1:
        return np.zeros(4096, np.int64), pal
    bits = max(4, int(np.ceil(np.log2(len(pal)))))
    vpl = 64 // bits
    longs = np.asarray(bs["data"]).view(np.uint64)
    sh = (np.arange(vpl, dtype=np.uint64) * np.uint64(bits))
    vals = (longs[:, None] >> sh[None, :]) & np.uint64((1 << bits) - 1)
    return vals.reshape(-1)[:4096].astype(np.int64), pal


def extraire(dossier, x0, x1, z0, z1, y0, y1):
    """Blocs de la boîte [x0, x1) x [y0, y1) x [z0, z1). Les chunks absents sont de l'air (statut 'absent')."""
    noms = ["minecraft:air"]; index = {"minecraft:air": 0}
    W, H, D = x1 - x0, y1 - y0, z1 - z0
    blocs = np.zeros((D, H, W), np.uint16)
    statuts = {}
    regions = {(cx >> 5, cz >> 5) for cx in range(x0 >> 4, ((x1 - 1) >> 4) + 1) for cz in range(z0 >> 4, ((z1 - 1) >> 4) + 1)}
    for (rx, rz) in regions:
        f = os.path.join(dossier, f"r.{rx}.{rz}.mca")
        if not os.path.exists(f): continue
        for cx, cz, c in chunks_region(f):
            bx, bz = cx * 16, cz * 16
            if bx + 16 <= x0 or bx >= x1 or bz + 16 <= z0 or bz >= z1: continue
            statuts[(cx, cz)] = c.get("Status", "?")
            for s in c.get("sections", []):
                sy = s["Y"] * 16
                if sy + 16 <= y0 or sy >= y1: continue
                idx, pal = _indices(s)
                if idx is None: continue
                g = []
                for e in pal:
                    n = e["Name"]
                    if n not in index: index[n] = len(noms); noms.append(n)
                    g.append(index[n])
                vol = np.asarray(g, np.uint16)[idx].reshape(16, 16, 16)        # [y, z, x]
                ya, yb = max(sy, y0), min(sy + 16, y1)
                xa, xb = max(bx, x0), min(bx + 16, x1)
                za, zb = max(bz, z0), min(bz + 16, z1)
                part = vol[ya - sy:yb - sy, za - bz:zb - bz, xa - bx:xb - bx]  # [y, z, x]
                blocs[za - z0:zb - z0, ya - y0:yb - y0, xa - x0:xb - x0] = part.transpose(1, 0, 2)
    return noms, blocs, statuts

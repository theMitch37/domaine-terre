"""Lieux uniques « par la méthode » (10/11/2026) : ce que le relief fin (GLO-90, 1 point par bloc) donne tout seul.

Pour chaque lieu de la feuille de route marqué « relief », découpe le terrain que le mod génère (carte 3' + 50 % du
détail fin, comme Terrain.colonne), et le dessine en ombrage + altitude. Sert à trier : reconnaissable tel quel
(le lieu se fait par des règles : biome, couleurs, surfaces) ou trop petit pour 250 m par bloc (addon Lieux).

Usage : python3 outils/lieux_methode.py <cache des paquets> <sortie.png> [detail]
(paquets relief_<bx>_<bz>.bin des versions v1-z<bz> de domaine-terre-relief, téléchargés à part)
"""
import os, sys, struct, zlib
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import terre_py as T

BPD = 445.28
# nom, latitude, longitude, demi-côté en km
LIEUX = [
    ("Kilimandjaro", -3.07, 37.35, 35), ("Ngorongoro", -3.18, 35.55, 25), ("Lac Natron", -2.35, 36.0, 35),
    ("Montagne de la Table", -33.96, 18.42, 12), ("Œil du Sahara", 21.12, -11.40, 30), ("Dallol", 14.24, 40.30, 15),
    ("Sossusvlei", -24.73, 15.35, 25), ("Erg Chebbi", 31.15, -3.98, 20), ("Delta de l'Okavango", -19.3, 22.9, 120),
    ("Mer Morte", 31.5, 35.5, 50), ("Wadi Rum", 29.57, 35.42, 25), ("Everest", 27.99, 86.93, 30),
    ("Mont Fuji", 35.36, 138.73, 30), ("Kamtchatka (Klioutchevskoï)", 56.06, 160.64, 40),
    ("Bromo-Tengger", -7.94, 112.95, 15), ("Yosemite", 37.74, -119.57, 20), ("Crater Lake", 42.94, -122.10, 15),
    ("Vallée de la Mort", 36.4, -117.0, 60), ("Rocheuses (lac Louise)", 51.42, -116.2, 30),
    ("Yellowstone", 44.5, -110.6, 60), ("Monument Valley", 36.98, -110.1, 20), ("Mont Roraima", 5.14, -60.76, 20),
    ("Auyantepui (Salto Ángel)", 5.85, -62.5, 30), ("Salar d'Uyuni", -20.13, -67.49, 80),
    ("Torres del Paine", -50.98, -73.0, 25), ("Fitz Roy", -49.27, -73.04, 20), ("Galápagos (Isabela)", -0.6, -91.1, 60),
    ("Pain de Sucre", -22.95, -43.16, 8), ("Uluru et Kata Tjuta", -25.32, 130.9, 25), ("Milford Sound", -44.62, 167.9, 25),
    ("Aoraki / Mont Cook", -43.6, 170.14, 25), ("Tongariro", -39.2, 175.6, 25), ("Bora Bora", -16.5, -151.74, 10),
    ("Kīlauea", 19.4, -155.28, 25), ("Mont Erebus", -77.53, 167.15, 30), ("Vallées sèches McMurdo", -77.5, 162.0, 50),
    ("Ilulissat", 69.2, -50.5, 40), ("Svalbard (Isfjorden)", 78.2, 15.6, 50), ("Vinicunca", -13.87, -71.30, 15),
    ("Mont Kenya", -0.15, 37.31, 30), ("Atacama (vallée de la Lune)", -22.92, -68.27, 15),
]


def paquet(cache, bx, bz):
    f = os.path.join(cache, f"relief_{bx}_{bz}.bin")
    if not os.path.exists(f):
        return {}
    b = open(f, "rb").read()
    assert b[:4] == b"RELB"
    out = {}
    for i in range(16):
        off, ln = struct.unpack_from("<ii", b, 16 + 8 * i)
        if ln:
            d = np.frombuffer(zlib.decompress(b[off:off + ln]), "<i2").reshape(512, 512).astype(np.int32)
            vide = d == -32768
            v = np.cumsum(np.where(vide, 0, d), axis=1)     # écarts avec le voisin de gauche
            out[i] = (v * 5.0, vide)
    return out


def fin(cache, x0, z0, W, H):
    a = np.full((H, W), np.nan)
    for tz in range(z0 >> 9, ((z0 + H - 1) >> 9) + 1):
        for tx in range(x0 >> 9, ((x0 + W - 1) >> 9) + 1):
            p = paquet(cache, tx >> 2, tz >> 2)
            i = (tx & 3) + 4 * (tz & 3)
            if i not in p:
                continue
            v, vide = p[i]
            v = np.where(vide, np.nan, v)
            gx0, gz0 = tx * 512, tz * 512
            xa, xb = max(x0, gx0), min(x0 + W, gx0 + 512); za, zb = max(z0, gz0), min(z0 + H, gz0 + 512)
            a[za - z0:zb - z0, xa - x0:xb - x0] = v[za - gz0:zb - gz0, xa - gx0:xb - gx0]
    return a


def terrain(cache, lat, lon, km, detail):
    r = int(km * BPD / 111.32); x0 = int(lon * BPD) - r; z0 = int(-lat * BPD) - r; W = H = 2 * r
    X, Z = np.meshgrid(np.arange(x0, x0 + W) + 0.5, np.arange(z0, z0 + H) + 0.5)
    alt = T.relief(X / BPD, -Z / BPD)
    af = fin(cache, x0, z0, W, H)
    base = T.blocs(np.maximum(alt, 1))
    h = np.where(np.isnan(af), T.blocs(alt), base + (T.blocs(np.maximum(np.nan_to_num(af, nan=1), 1)) - base) * detail)
    h = np.where(alt < 0, T.blocs(alt), h)
    return h, af, x0, z0


def paquets_utiles():
    s = set()
    for _, lat, lon, km in LIEUX:
        r = int(km * BPD / 111.32); x0 = int(lon * BPD) - r; z0 = int(-lat * BPD) - r
        for z in (z0, z0 + 2 * r):
            for x in (x0, x0 + 2 * r):
                s.add((x >> 11, z >> 11))
    return sorted(s)


if __name__ == "__main__":
    if sys.argv[1] == "--paquets":
        for bx, bz in paquets_utiles():
            print(bx, bz)
        sys.exit()
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LightSource
    cache, sortie = sys.argv[1], sys.argv[2]; detail = float(sys.argv[3]) if len(sys.argv) > 3 else 0.5
    n = len(LIEUX); c = 6; l = (n + c - 1) // c
    fig, ax = plt.subplots(l, c, figsize=(c * 4, l * 4.3))
    ls = LightSource(315, 35)
    for k, (nom, lat, lon, km) in enumerate(LIEUX):
        a = ax.flat[k]
        h, af, x0, z0 = terrain(cache, lat, lon, km, detail)
        rgb = ls.shade(h, plt.cm.terrain, vert_exag=1, blend_mode="soft", vmin=40, vmax=max(160, np.nanmax(h)))
        a.imshow(rgb); a.set_xticks([]); a.set_yticks([])
        manque = np.isnan(af).mean()
        a.set_title(f"{nom}\ny {np.nanmin(h):.0f}–{np.nanmax(h):.0f}, {h.shape[1]} blocs"
                    + (f", fin absent {manque:.0%}" if manque > 0.05 else ""), fontsize=9)
    for a in ax.flat[n:]:
        a.axis("off")
    plt.tight_layout(); plt.savefig(sortie, dpi=70)

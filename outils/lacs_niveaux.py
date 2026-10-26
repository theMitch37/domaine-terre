"""Plafond des lacs (étape C1) : un lac ne doit pas être perché au-dessus du relief généré autour de lui.

L'altitude réelle d'un lac de montagne (Copernicus) dépasse souvent le relief du mod, lissé par la carte à 3' :
le lac était alors perché et sa berge relevée tout autour (« cratères » dans les Alpes et les Pyrénées).
Pour chaque lac : médiane de la hauteur du terrain généré (terre_py, sans fleuves ni lacs) sur un anneau de 15 à 30
blocs autour du rivage, hors lacs et hors mer ; le niveau du lac ne dépasse pas cette médiane - 1.

Usage : python3 outils/lacs_niveaux.py   (réécrit src/main/resources/domaine_terre/carte/lacs.bin en version 2 :
la table des lacs a 3 valeurs par lac, altitude réelle, superficie, plafond du niveau en y ; le reste ne change pas)
"""
import os, struct, time, zlib
import numpy as np
import terre_py as T

CHEMIN = os.path.join(T.CARTE, "lacs.bin")


def main():
    t0 = time.time()
    b = open(CHEMIN, "rb").read()
    assert b[:4] == b"LACS"
    version, bpd, TT, TX, TY = struct.unpack_from("<idiii", b, 4)
    p = 4 + struct.calcsize("<idiii")
    (L,) = struct.unpack_from("<i", b, p); p += 4
    nval = 2 if version == 1 else 3
    tab = np.frombuffer(b, "<f4", nval * L, p).reshape(L, nval).copy(); p += 4 * nval * L
    reste = b[p:]
    (n,) = struct.unpack_from("<i", reste, 0)
    idx = np.frombuffer(reste, "<i4", 2 * n, 4).reshape(n, 2)
    q = 4 + 8 * n
    # rives : cases d'un lac dont une voisine n'est pas de ce lac ; jusqu'à 40 par lac, au hasard
    rng = np.random.default_rng(1)
    rives = {}
    for k, lg in idx:
        m = np.frombuffer(zlib.decompress(reste[q:q + lg]), "<u2").reshape(TT, TT); q += lg
        ty, tx = divmod(int(k), TX)
        bord = np.zeros(m.shape, bool)
        bord[1:-1, 1:-1] = (m[1:-1, 1:-1] > 0) & ((m[1:-1, 1:-1] != m[:-2, 1:-1]) | (m[1:-1, 1:-1] != m[2:, 1:-1]) |
                                                   (m[1:-1, 1:-1] != m[1:-1, :-2]) | (m[1:-1, 1:-1] != m[1:-1, 2:]))
        jj, ii = np.nonzero(bord)
        if not len(jj):
            continue
        ids = m[jj, ii]
        for lac in np.unique(ids):
            s = np.flatnonzero(ids == lac)
            if len(s) > 40:
                s = rng.choice(s, 40, replace=False)
            gx = tx * TT + ii[s]; gy = ty * TT + jj[s]
            rives.setdefault(int(lac), []).append(np.c_[gx, gy])
    print(f"rives de {len(rives)} lacs ({time.time() - t0:.0f} s)", flush=True)
    plafond = np.full(L, 32767.0, np.float32)
    ang = np.linspace(0, 2 * np.pi, 8, endpoint=False)
    lacs = sorted(rives)
    for n0 in range(0, len(lacs), 1):
        lot = lacs[n0:n0 + 1]
        pts, qui = [], []
        for lac in lot:
            g = np.vstack(rives[lac])
            if len(g) > 40:
                g = g[rng.choice(len(g), 40, replace=False)]
            x = g[:, 0] - 180 * T.BPD; z = g[:, 1] - 90 * T.BPD
            for r in (15.0, 22.0, 30.0):
                px = (x[:, None] + r * np.cos(ang)).ravel(); pz = (z[:, None] + r * np.sin(ang)).ravel()
                pts.append(np.c_[px, pz]); qui.append(np.full(len(px), lac))
        P = np.vstack(pts); Q = np.concatenate(qui)
        X, Z = P[:, 0], P[:, 1]
        h, sd = T.hauteur_base(X, Z, eaux=False)
        # hors des lacs : case de lac à la position ?
        lac_ici = np.zeros(len(X), np.int64)
        gx = np.floor(X + 0.5 + 180 * T.BPD).astype(np.int64); gy = np.floor(Z + 0.5 + 90 * T.BPD).astype(np.int64)
        c = T._carte_lacs()
        for (txi, tyi) in set(zip((gx // TT).tolist(), (gy // TT).tolist())):
            sel = (gx // TT == txi) & (gy // TT == tyi)
            m = T._ids_tuile(c, txi, tyi)
            if m is not None:
                lac_ici[sel] = m[gy[sel] - tyi * TT, gx[sel] - txi * TT]
        ok = (sd >= 0) & (lac_ici == 0)
        for lac in lot:
            v = h[(Q == lac) & ok]
            if len(v) >= 8:
                plafond[lac - 1] = np.floor(np.median(v) - 1.0)
        if n0 % 500 == 0:
            print(f"  {n0 + len(lot)}/{len(lacs)} ({time.time() - t0:.0f} s)", flush=True)
    niv = np.floor(np.where(tab[:, 0] < 0, 64 + tab[:, 0] / 500 * 16, T.blocs(np.maximum(tab[:, 0], 0))))
    baisse = niv > plafond
    print(f"lacs abaissés : {int(baisse.sum())} sur {L} ; baisse médiane {np.median((niv - plafond)[baisse]):.1f} blocs",
          flush=True)
    for nom, k in [("Léman", 361), ("Annecy", 3799), ("Baïkal", 6), ("Titicaca", 34), ("Constance", 415)]:
        print(f"  {nom:10s} : niveau réel y {niv[k - 1]:.0f}, plafond {plafond[k - 1]:.0f}", flush=True)
    out = b"LACS" + struct.pack("<idiii", 2, bpd, TT, TX, TY) + struct.pack("<i", L)
    out += np.c_[tab[:, 0], tab[:, 1], plafond].astype("<f4").tobytes() + reste
    open(CHEMIN, "wb").write(out)
    print(f"écrit {CHEMIN} (version 2), {len(out) / 1e6:.1f} Mo ({time.time() - t0:.0f} s)")


if __name__ == "__main__":
    main()

"""Murs fins au banc (10/11/2026) : colonnes plus hautes d'au moins SEUIL blocs que leurs deux voisines opposées
(est-ouest, nord-sud ou en diagonale), à 2 blocs de distance. Une paroi de gorge n'en est pas une (un côté est le
plateau à la même hauteur) ; une crête d'un ou deux blocs dressée au-dessus du terrain des deux côtés, si.

Usage : python3 outils/banc/murs.py <zone.npz> ...
"""
import sys
import numpy as np

SEUIL = 6
for f in sys.argv[1:]:
    d = np.load(f)
    noms = [str(n) for n in d["noms"]]
    b = d["blocs"]
    ignore = np.array([n.split(":")[-1] in ("air", "cave_air", "snow", "grass", "tall_grass", "fern", "large_fern",
                                             "water") or "flower" in n or "tulip" in n or "leaves" in n or "log" in n or "kelp" in n or "seagrass" in n or "coral" in n or "pickle" in n or "roots" in n or "propagule" in n or "vine" in n or "carpet" in n
                       for n in noms])
    H = b.shape[1]
    ok = ~ignore[b]
    Y = (H - 1 - np.argmax(ok[:, ::-1, :], axis=1)).astype(int)
    m = np.zeros(Y.shape, bool)
    c = Y[2:-2, 2:-2]
    for dj, di in ((0, 2), (2, 0), (2, 2), (2, -2)):
        a = Y[2 + dj:Y.shape[0] - 2 + dj, 2 + di:Y.shape[1] - 2 + di]
        bb = Y[2 - dj:Y.shape[0] - 2 - dj, 2 - di:Y.shape[1] - 2 - di]
        m[2:-2, 2:-2] |= (c - a >= SEUIL) & (c - bb >= SEUIL)
    print(f"{f.split('/')[-1]:28s} murs fins : {int(m.sum()):5d} colonnes")

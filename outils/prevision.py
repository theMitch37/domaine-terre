"""Prévision d'un lieu en grille, en blocs : même format que le banc d'essai, pour le même rendu (outils/banc/rendu.py).

Usage : python3 outils/prevision.py <lieu> <sortie.npz>   (après outils/lieux_cotiers.py <lieu>)
Exact pour la forme et les blocs du lieu ; sans le hasard vanilla (grottes, arbres, herbes), que seul le banc montre.
"""
import sys
import numpy as np
from rendu_grille import bloc, PALETTE

Y0 = 36


def prevoir(nom, sortie):
    d = np.load(f"/tmp/lieu_{nom}.npz")
    X, Z, y, typ, sommet, vox = d["X"], d["Z"], d["y"], d["typ"], d["sommet"], d["vox"]
    pal = PALETTE[nom]
    Y = np.floor(y).astype(int)
    D, W = Y.shape
    H = int(max(Y.max(), 63)) + 4 - Y0
    noms = ["minecraft:air", "minecraft:water"]; index = {n: i for i, n in enumerate(noms)}
    B = np.zeros((D, H, W), np.uint16)
    cl = typ & 15
    taillee = (typ & 16) > 0
    for j in range(D):
        for i in range(W):
            x, z, top = int(X[j, i]), int(Z[j, i]), int(Y[j, i])
            c = int(cl[j, i]); ref = float(sommet[j, i])
            for yy in range(Y0, top + 1):
                if c == 0 or not taillee[j, i]:
                    n = "grass_block" if yy == top and top > 62 else ("dirt" if yy >= top - 3 and top > 62 else "stone")
                    if top <= 62 and yy == top: n = "sand"
                else:
                    n = bloc(pal, c, x, yy, z, ref, yy == top)
                    n = {"grass": "grass_block"}.get(n, n)
                n = "minecraft:" + n
                if n not in index: index[n] = len(noms); noms.append(n)
                B[j, yy - Y0, i] = index[n]
            for yy in range(top + 1, 63):
                B[j, yy - Y0, i] = 1
    x0, z0 = int(X[0, 0]), int(Z[0, 0])
    for (vx, vy, vz, c) in vox:
        i, j = vx - x0, vz - z0
        if 0 <= i < W and 0 <= j < D and Y0 <= vy < Y0 + H and c == 0:
            B[j, vy - Y0, i] = 1 if vy <= 62 else 0
    np.savez_compressed(sortie, noms=np.array(noms), blocs=B, x0=x0, y0=Y0, z0=z0)
    print("écrit", sortie, B.shape)


if __name__ == "__main__":
    prevoir(sys.argv[1], sys.argv[2])

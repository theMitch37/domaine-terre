"""Contrôle « mer fidèle » d'un passage du banc : îles inventées et mares inventées hors des lieux.

Usage : python3 outils/banc/mer.py <dossier des .npz du banc>
Île inventée : colonne en mer d'après la carte (distance à la côte < 0), hors lieu, dont le sol dépasse y 61.
Fond à sec : colonne en mer d'après la carte, sol sous la mer (y ≤ 61) et pas d'eau au-dessus (lieux compris).
Mare inventée : colonne de terre ferme (> 0,5' de la côte), hors lieu et hors fleuve, dont l'eau monte au-dessus du sol.
Le poids des lieux en grille vient de /tmp/lieu_<nom>.npz (outils/lieux_cotiers.py) ; sans lui, toute la zone compte.
"""
import os, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
import terre_py as T
from rendu import classes


def controle(chemin):
    d = np.load(chemin); noms = [str(n) for n in d["noms"]]; b = d["blocs"]; kl = classes(noms)[b]
    # les arbres du rivage qui penchent sur l'eau ne sont pas du terrain
    arbre = np.array([n.endswith(("_leaves", "_log", "_wood")) or "mushroom_block" in n for n in noms])
    kl = np.where(arbre[b], 0, kl)
    ny = b.shape[1]; y0, x0, z0 = int(d["y0"]), int(d["x0"]), int(d["z0"])
    top = lambda m: np.where(m.any(1), ny - 1 - np.argmax(m[:, ::-1, :], axis=1), -999) + y0
    sol, eau = top(kl == 2), top(kl == 1)
    D, W = sol.shape
    X, Z = np.meshgrid(np.arange(x0, x0 + W, dtype=float), np.arange(z0, z0 + D, dtype=float))
    sd = T.distance_cote(X, Z)
    nom = os.path.basename(chemin)[:-4]
    hors = np.ones(sol.shape, bool)
    if os.path.exists(f"/tmp/lieu_{nom}.npz"):
        g = np.load(f"/tmp/lieu_{nom}.npz")
        gx0, gz0 = int(g["X"][0, 0]), int(g["Z"][0, 0]); P = g["poids"]
        j0, i0 = gz0 - z0, gx0 - x0
        hors[max(j0, 0):j0 + P.shape[0], max(i0, 0):i0 + P.shape[1]] = \
            P[max(-j0, 0):D - j0, max(-i0, 0):W - i0] < 0.01
    iles = (sd < 0) & hors & (sol > 61)
    mares = (sd > 0.5) & hors & (eau > sol) & (eau <= 62)
    sec = (sd < 0) & (sol >= -64) & (sol <= 61) & (eau <= sol)
    print(f"{nom:20s} mer {int(((sd < 0) & hors).sum()):6d} col. -> îles inventées {int(iles.sum()):5d} "
          f"| terre {int(((sd > 0.5) & hors).sum()):6d} col. -> mares au niveau de la mer {int(mares.sum()):5d} "
          f"| fond à sec {int(sec.sum()):5d}")
    return int(iles.sum())


if __name__ == "__main__":
    dos = sys.argv[1]
    for f in sorted(os.listdir(dos)):
        if f.endswith(".npz"):
            controle(os.path.join(dos, f))

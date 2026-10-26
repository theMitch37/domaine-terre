"""Contrôle « relief 100 % Terre » d'un passage du banc : le sol réel suit-il au bloc près terre_py.sol_exact ?

Usage : python3 outils/banc/relief.py <dossier des .npz du banc> [zone ...]
Compte les colonnes de terre ferme (> 4 blocs de la côte), hors lieux en grille (poids < 0,01, d'après
/tmp/lieu_<nom>.npz produit par outils/lieux_cotiers.py) ; les fleuves ne sont pas copiés en Python, leurs
vallées sortent donc en écart. Rapporte aussi le saut de hauteur au bord des lieux (marche).
"""
import os, sys
import numpy as np
from scipy import ndimage
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
import terre_py as T
from rendu import classes


def controle(chemin):
    d = np.load(chemin); noms = [str(n) for n in d["noms"]]; b = d["blocs"]; kl = classes(noms)[b]
    arbre = np.array([n.endswith(("_leaves", "_log", "_wood")) or "mushroom" in n for n in noms])
    kl = np.where(arbre[b], 0, kl)
    ny = b.shape[1]; y0, x0, z0 = int(d["y0"]), int(d["x0"]), int(d["z0"])
    sol = np.where((kl == 2).any(1), ny - 1 - np.argmax((kl == 2)[:, ::-1, :], axis=1), -999) + y0
    D, W = sol.shape
    X, Z = np.meshgrid(np.arange(x0, x0 + W, dtype=float), np.arange(z0, z0 + D, dtype=float))
    _, sd = T.hauteur_base(X, Z)
    prevu = T.sol_exact(x0, z0, W, D)
    nom = os.path.basename(chemin)[:-4]
    hors = np.ones(sol.shape, bool); P = np.zeros(sol.shape)
    if os.path.exists(f"/tmp/lieu_{nom}.npz"):
        g = np.load(f"/tmp/lieu_{nom}.npz"); G = g["poids"]
        gx0, gz0 = int(g["X"][0, 0]), int(g["Z"][0, 0]); j0, i0 = gz0 - z0, gx0 - x0
        P[max(j0, 0):j0 + G.shape[0], max(i0, 0):i0 + G.shape[1]] = G[max(-j0, 0):D - j0, max(-i0, 0):W - i0]
        hors = P < 0.01
    m = hors & (sd > 4) & (sol > 63)
    e = sol - prevu
    txt = f"{nom:20s} {int(m.sum()):6d} col. : exact {np.mean(e[m] == 0) * 100:5.1f} %, ±1 {np.mean(abs(e[m]) <= 1) * 100:5.1f} %, " \
          f"écart moyen {e[m].mean():+.2f}"
    if (~hors).any():
        # marche au bord du lieu : écart réel - prévu juste dehors (1 à 3 blocs du lieu)
        dist = ndimage.distance_transform_edt(hors)
        k = hors & (dist >= 1) & (dist <= 3) & (sd > 4) & (sol > 63)
        if k.sum(): txt += f" | bord du lieu ({int(k.sum())} col.) écart {e[k].mean():+.2f}"
    print(txt)


if __name__ == "__main__":
    dos = sys.argv[1]; zones = sys.argv[2:]
    for f in sorted(os.listdir(dos)):
        if f.endswith(".npz") and (not zones or f[:-4] in zones) and not f.startswith("mer_"):
            controle(os.path.join(dos, f))

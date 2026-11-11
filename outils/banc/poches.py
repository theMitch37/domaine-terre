"""Poches d'air sous l'eau au banc (12/11/2026, test en jeu : « des zones sans eau dans la mer ») : air (ou air de
grotte) avec de l'eau plus haut dans la même colonne. Usage : python3 outils/banc/poches.py <zone.npz> ..."""
import os, sys
import numpy as np
from scipy import ndimage
for f in sys.argv[1:]:
    d = np.load(f)
    noms = [str(n).split(":")[-1] for n in d["noms"]]
    b = d["blocs"]; y0 = int(d["y0"]); x0 = int(d["x0"]); z0 = int(d["z0"])
    A = np.array([n in ("air", "cave_air") for n in noms])[b]
    W = np.array([n == "water" for n in noms])[b]
    S = ~A & ~W
    # air sous de l'eau, sans bloc solide entre les deux (sinon c'est une grotte fermée sous le fond, normale)
    haut = np.zeros_like(W)
    etat = np.zeros((b.shape[0], b.shape[2]), bool)
    for y in range(b.shape[1] - 1, -1, -1):
        etat = np.where(W[:, y, :], True, np.where(S[:, y, :], False, etat))
        haut[:, y, :] = etat
    poche = A & haut
    lab, n = ndimage.label(poche)
    print(f"{os.path.basename(f):28s} poches d'air sous l'eau : {int(poche.sum()):6d} blocs, {n} groupes")
    if n:
        t = ndimage.sum(poche, lab, range(1, n + 1))
        for i in np.argsort(-t)[:4]:
            p = np.argwhere(lab == i + 1)
            print(f"   {int(t[i]):5d} blocs vers x={x0 + int(p[:, 2].mean())} z={z0 + int(p[:, 0].mean())} y {y0 + p[:, 1].min()}..{y0 + p[:, 1].max()}")

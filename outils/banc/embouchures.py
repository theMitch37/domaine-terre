"""Eau des cours d'eau reliée à la mer au banc (10/11/2026) : part de l'eau posée sur terre (d'après la carte des
côtes) qui touche la mer par de l'eau. Un fleuve qui finit en cul-de-sac dans les terres fait baisser la part.

Usage : python3 outils/banc/embouchures.py <zone.npz> ...
"""
import os, sys
import numpy as np
from scipy import ndimage
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import terre_py as T

for f in sys.argv[1:]:
    d = np.load(f)
    noms = [str(n) for n in d["noms"]]
    b = d["blocs"]
    ign = np.array([n.split(":")[-1] in ("air", "cave_air", "grass", "tall_grass", "fern", "large_fern") or "flower" in n
                    or "leaves" in n or "log" in n or "kelp" in n or "seagrass" in n for n in noms])
    eau = np.array([n.endswith(":water") for n in noms])
    H = b.shape[1]
    top = H - 1 - np.argmax((~ign[b])[:, ::-1, :], axis=1)
    we = eau[np.take_along_axis(b, top[:, None, :], 1)[:, 0, :]]
    x0, z0 = int(d["x0"]), int(d["z0"])
    X, Z = np.meshgrid(np.arange(x0, x0 + we.shape[1]) + 0.5, np.arange(z0, z0 + we.shape[0]) + 0.5)
    mer = T.distance_cote(X, Z) < 0
    lab, _ = ndimage.label(we)
    touche = np.unique(lab[we & mer])
    terre = we & ~mer
    relie = terre & np.isin(lab, touche[touche > 0])
    print(f"{os.path.basename(f):28s} eau sur terre {int(terre.sum()):6d}, reliée à la mer {relie.sum() / max(terre.sum(), 1):4.0%}")

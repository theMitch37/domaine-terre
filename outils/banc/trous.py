"""Trous d'eau et herbe sous l'eau au banc (11/11/2026, Maxime : « cherche les trous d'eau, l'herbe dans les
rivières »).

- trou : colonne sans eau en surface dont le sol est plus bas que la surface d'une eau voisine (4 voisins) : l'eau
  devrait y être (creux à sec au bord d'un lit, d'un lac ou de la mer, marche d'eau suspendue) ;
- herbe sous l'eau : herbe, fleurs, plantes terrestres ou bloc d'herbe/podzol/mycélium sous de l'eau.

Usage : python3 outils/banc/trous.py <zone.npz> ...   (-v : liste des groupes de trous)
"""
import os, sys
import numpy as np
from scipy import ndimage

verbeux = "-v" in sys.argv
for f in [a for a in sys.argv[1:] if a != "-v"]:
    d = np.load(f)
    noms = [str(n).split(":")[-1] for n in d["noms"]]
    b = d["blocs"]
    y0 = int(d["y0"])
    vide = np.array([n in ("air", "cave_air") for n in noms])
    eau = np.array([n == "water" for n in noms])
    plante = np.array([n in ("grass", "tall_grass", "fern", "large_fern", "dandelion", "poppy", "dead_bush", "sweet_berry_bush")
                       or n.endswith("_tulip") or n in ("oxeye_daisy", "cornflower", "azure_bluet", "allium", "lily_of_the_valley")
                       for n in noms])
    sol_herbe = np.array([n in ("grass_block", "podzol", "mycelium", "dirt_path") for n in noms])
    # plantes de bord d'eau tolérées (roseaux, nénuphars, algues, racines…) : ignorées pour la surface
    ign = vide | plante | np.array([n in ("sugar_cane", "lily_pad", "kelp", "kelp_plant", "seagrass", "tall_seagrass",
                                          "snow", "bamboo", "vine") or "leaves" in n or "log" in n or "root" in n
                                    or "propagule" in n or "carpet" in n for n in noms])
    H = b.shape[1]
    top = H - 1 - np.argmax((~ign[b])[:, ::-1, :], axis=1)
    tb = np.take_along_axis(b, top[:, None, :], 1)[:, 0, :]
    w = eau[tb]
    surf = np.where(w, top, -10**6)
    voisin = np.full(top.shape, -10**6)
    voisin[1:, :] = np.maximum(voisin[1:, :], surf[:-1, :]); voisin[:-1, :] = np.maximum(voisin[:-1, :], surf[1:, :])
    voisin[:, 1:] = np.maximum(voisin[:, 1:], surf[:, :-1]); voisin[:, :-1] = np.maximum(voisin[:, :-1], surf[:, 1:])
    trou = ~w & (top < voisin)
    trou[[0, -1], :] = trou[:, [0, -1]] = False
    profond = trou & (top < voisin - 1)
    E = eau[b]
    sous = (plante[b][:, :-1, :] | sol_herbe[b][:, :-1, :]) & E[:, 1:, :]
    lab, n = ndimage.label(trou, np.ones((3, 3)))
    print(f"{os.path.basename(f):28s} trous {int(trou.sum()):5d} (dont {int(profond.sum()):4d} de 2 blocs et plus, "
          f"{n} groupes) ; herbe sous l'eau {int(sous.sum()):5d}")
    if verbeux and n:
        tailles = ndimage.sum(trou, lab, range(1, n + 1))
        for i in np.argsort(-tailles)[:8]:
            pts = np.argwhere(lab == i + 1)
            a, c = pts[0]
            print(f"   {int(tailles[i]):4d} col. vers z={int(d['z0']) + int(pts[:, 0].mean())} x={int(d['x0']) + int(pts[:, 1].mean())} "
                  f"sol {top[a, c] + y0} eau voisine {voisin[a, c] + y0} bloc {noms[tb[a, c]]}")

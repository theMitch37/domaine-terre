"""Contrôle d'un lieu en tuiles au banc : sculpture exacte et eau du lieu (lot 2).

Usage : python3 outils/banc/lieux_eau.py <dossier des .npz du banc> [lieu ...]
Il faut d'abord /tmp/lieu_<nom>.npz (outils/lieux_cotiers.py ou outils/lieux_montagne.py).
- sculpture : sol généré = floor(round(y x 16) / 16) sur les colonnes taillées du lieu ;
- eau : colonnes d'eau du lieu en eau jusqu'à eau - 1 ; colonnes d'eau à sec ; eau ailleurs dans le lieu (hors mer).
"""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from rendu import classes


def controle(dos, nom):
    f = os.path.join(dos, nom + ".npz")
    g = f"/tmp/lieu_{nom}.npz"
    if not (os.path.exists(f) and os.path.exists(g)):
        print(f"{nom:14s} : pas de données ({f} ou {g})")
        return
    d = np.load(f); noms = [str(n) for n in d["noms"]]; b = d["blocs"]; kl = classes(noms)[b]
    arbre = np.array([n.endswith(("_leaves", "_log", "_wood")) or "mushroom_block" in n for n in noms])
    kl = np.where(arbre[b], 0, kl)
    ny = b.shape[1]; y0, x0, z0 = int(d["y0"]), int(d["x0"]), int(d["z0"])
    top = lambda m: np.where(m.any(1), ny - 1 - np.argmax(m[:, ::-1, :], axis=1), -999) + y0
    sol, eau_g = top(kl == 2), top(kl == 1)
    L = np.load(g)
    X, Z, y, typ = L["X"], L["Z"], L["y"], L["typ"]
    eau = L["eau"] if "eau" in L.files else np.full(X.shape, np.nan)
    actif = L["poids"] > 0.5
    # recouvrement zone du banc / grille du lieu
    gx0, gz0 = int(X[0, 0]), int(Z[0, 0])
    D, W = sol.shape
    jb0, ib0 = max(gz0 - z0, 0), max(gx0 - x0, 0)
    jg0, ig0 = max(z0 - gz0, 0), max(x0 - gx0, 0)
    H = min(D - jb0, X.shape[0] - jg0); Wd = min(W - ib0, X.shape[1] - ig0)
    s_b = sol[jb0:jb0 + H, ib0:ib0 + Wd]; e_b = eau_g[jb0:jb0 + H, ib0:ib0 + Wd]
    y_l = y[jg0:jg0 + H, ig0:ig0 + Wd]; t_l = typ[jg0:jg0 + H, ig0:ig0 + Wd]
    e_l = eau[jg0:jg0 + H, ig0:ig0 + Wd]; a_l = actif[jg0:jg0 + H, ig0:ig0 + Wd]
    taillee = a_l & ((t_l & 16) > 0) & ~np.isfinite(e_l)
    attendu = np.floor(np.round(y_l * 16) / 16)
    ok = s_b[taillee] == attendu[taillee]
    ecart = (s_b - attendu)[taillee]
    w = a_l & np.isfinite(e_l)
    en_eau = w & (e_b >= e_l - 1)
    sec = w & (e_b < s_b)
    inonde = (t_l & 128) > 0
    ailleurs = a_l & ~w & ~inonde & (e_b > s_b) & (e_b > 62)
    print(f"{nom:14s} : sculpture {ok.mean() * 100:5.1f} % exacte ({taillee.sum()} col., écart moyen {ecart.mean():+.2f}, "
          f"|écart|>2 : {int((np.abs(ecart) > 2).sum())}) | eau du lieu : {w.sum()} col., au niveau {en_eau.sum()} "
          f"({en_eau.sum() / max(w.sum(), 1) * 100:.0f} %), à sec {sec.sum()} | eau hors des bassins : {ailleurs.sum()}")


if __name__ == "__main__":
    dos = sys.argv[1]
    lieux = sys.argv[2:] or ["mer_de_glace", "jokulsarlon", "gavarnie", "gullfoss", "skogafoss", "plitvice", "geiranger", "preikestolen", "cervin",
                             "tre_cime"]
    for n in lieux:
        controle(dos, n)

"""Embouchures (26/10) : le tracé Natural Earth d'un fleuve s'arrête souvent un peu avant le trait de côte fin (GSHHG) —
la Seine finit à Tancarville, 20 à 40 blocs avant le bout de l'estuaire : le lit s'arrêtait dans les terres.
Pour chaque cours d'eau dont le bout aval est dans les terres, au niveau de la mer, et ne rejoint pas un autre cours
d'eau, on ajoute un dernier sommet sur la case de vraie mer la plus proche (au plus MAX blocs), à au moins LARGE cases de
la terre.

Usage : python3 outils/embouchures.py            (réécrit src/main/resources/domaine_terre/carte/fleuves.json)
Idempotent : un cours d'eau prolongé porte "emb": 1 (ignoré par le jeu) et n'est plus touché.
"""
import json, os, sys
import numpy as np
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import terre_py as T

MAX = 96          # blocs (cases à 1:250)
LARGE = 3         # le nouveau sommet est dans une mer à au moins 3 cases de la terre
CHEMIN = os.path.join(T.CARTE, "fleuves.json")
B = T.BPD


def niveau(x, z):
    return max(T.NIVEAU_MER, int(np.floor(T._niveau_vallee(np.floor(np.array([x])), np.floor(np.array([z])))[0])) - 2)


def mer_proche(x, z):
    """Case de vraie mer la plus proche (x, z en blocs, distance) dans un carré de ±MAX ; "mer" si on y est déjà ; None."""
    gx = int(np.floor(x + 0.5 + 180 * B)); gy = int(np.floor(z + 0.5 + 90 * B))
    gx0, gy0, W = gx - MAX, gy - MAX, 2 * MAX + 1
    m = T._masque_fin(gx0, gy0, W, W)                  # True = terre
    if m.all():
        return None
    # seulement la vraie mer : un morceau de mer qui touche le bord du carré (les flaques isolées du trait de côte
    # fin, comme au bout de l'estuaire de la Seine, ne comptent pas)
    lab, _ = ndimage.label(~m)
    bord = np.unique(np.r_[lab[0], lab[-1], lab[:, 0], lab[:, -1]])
    vraie = np.isin(lab, bord[bord > 0])
    if not vraie.any():
        return None
    # et une mer assez large pour être de l'eau visible (à au moins LARGE cases de la terre) : un chenal d'estuaire
    # du trait de côte fin, fin comme un fil, a son fond au ras de l'eau et se voit comme de la terre
    large = vraie & (ndimage.distance_transform_edt(vraie) >= LARGE)
    if not large.any():
        return None
    j, i = MAX, MAX
    if large[j, i]:
        return "mer"
    d, (iy, ix) = ndimage.distance_transform_edt(~large, return_indices=True)
    if d[j, i] > MAX:
        return None
    sy, sx = iy[j, i], ix[j, i]
    return (gx0 + sx - 180 * B, gy0 + sy - 90 * B, float(d[j, i]))


def main():
    tab = json.load(open(CHEMIN))
    seg = []
    for f, r in enumerate(tab):
        q = np.array(r["p"], float).reshape(-1, 2)
        for a, b in zip(q[:-1], q[1:]):
            seg.append((a[0] * B, -a[1] * B, b[0] * B, -b[1] * B, T.DEMI_LARGEUR[r["c"]], f))
    seg = np.array(seg)
    n_ok = 0
    for f, r in enumerate(tab):
        if r.get("emb") or len(r["p"]) < 4:
            continue
        q = np.array(r["p"], float).reshape(-1, 2)
        bouts = [(0, q[0]), (len(q) - 1, q[-1])]
        nv = [niveau(p[0] * B, -p[1] * B) for _, p in bouts]
        # le bout aval : le plus bas (comme Fleuves.charger : amont au début si niv[0] >= niv[fin])
        aval = bouts[1] if nv[0] >= nv[1] else bouts[0]
        k, p = aval
        if niveau(p[0] * B, -p[1] * B) != T.NIVEAU_MER:
            continue
        x, z = p[0] * B, -p[1] * B
        # rejoint un autre cours d'eau ? (bout dans le lit, ou tout près, d'un autre)
        s = seg[seg[:, 5] != f]
        dx, dz = s[:, 2] - s[:, 0], s[:, 3] - s[:, 1]
        l2 = np.maximum(dx * dx + dz * dz, 1e-9)
        t = np.clip(((x - s[:, 0]) * dx + (z - s[:, 1]) * dz) / l2, 0, 1)
        dd = np.hypot(x - (s[:, 0] + t * dx), z - (s[:, 1] + t * dz)) - s[:, 4] - T.DEMI_LARGEUR[r["c"]]
        if (dd < 4).any():
            continue
        m = mer_proche(x, z)
        if m is None or m == "mer":
            continue
        sx, sz, dist = m
        if dist <= T.DEMI_LARGEUR[r["c"]] * 0.5:
            continue                                    # le lit touche déjà la mer
        nouveau = [round(sx / B, 5), round(-sz / B, 5)]
        r["p"] = (r["p"] + nouveau) if k > 0 else (nouveau + r["p"])
        r["emb"] = 1
        n_ok += 1
        print(f"  {r.get('n') or '(sans nom)':28s} classe {r['c']} : bout à {p[1]:.3f} N {p[0]:.3f} E, "
              f"mer à {dist:.0f} blocs", flush=True)
    with open(CHEMIN, "w") as fo:
        json.dump(tab, fo, separators=(",", ":"), ensure_ascii=False)
    print(f"{n_ok} embouchures prolongées jusqu'à la mer")


if __name__ == "__main__":
    main()

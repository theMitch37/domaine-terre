"""Embouchures jusqu'à la mer (10/11/2026, test de Maxime : « les fleuves ne rejoignent pas toujours la mer »).

Le tracé Natural Earth s'arrête souvent quelques dizaines de blocs avant le trait de côte du mod (deltas du Gange,
de l'Indus, du Niger…) : le lit finissait en cul-de-sac dans les terres. Une embouchure (le bout le plus bas) restée
à terre, avec la mer franche (3 blocs au large) à 64 blocs au plus, reçoit un dernier point dans la mer franche (6 blocs au large).
Pas dans les tuiles des lieux (leurs colonnes non sculptées garderaient un lit sans eau).

Corrige les données une fois pour toutes (rien à calculer au chargement du monde ; les outils Python le voient aussi).
Usage : python3 outils/fleuves_mer.py   (idempotent : un bout déjà en mer n'est pas prolongé)
"""
import json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import terre_py as T

ICI = os.path.dirname(os.path.abspath(__file__))
F = os.path.join(ICI, "../src/main/resources/domaine_terre/carte/fleuves.json")
INDEX = os.path.join(ICI, "../lieux/src/main/resources/domaine_terre_lieux/tuiles/index.txt")
B = T.BPD
MPB = 60.0 / B                                     # minutes d'arc par bloc
MER_MAX, LARGE, FRANCHE = 64, -3 * MPB, -6 * MPB

lieux = {tuple(map(int, l.split())) for l in open(INDEX) if l.strip()}
t = json.load(open(F, encoding="utf-8"))
ang = np.arange(32) * np.pi / 16
rs = np.arange(2, MER_MAX + 7, 2)
prolonges = 0
for o in t:
    p = o["p"]
    if len(p) < 4:
        continue
    a = T.relief(np.array([p[0], p[-2]]), np.array([p[1], p[-1]]))
    fin = a[1] <= a[0]
    lo, la = (p[-2], p[-1]) if fin else (p[0], p[1])
    x, z = lo * B, -la * B
    d0 = float(T.distance_cote(np.array([x]), np.array([z]))[0])
    if d0 <= LARGE or d0 > MER_MAX * MPB:
        continue
    XX = x + np.cos(ang)[:, None] * rs[None, :]
    ZZ = z + np.sin(ang)[:, None] * rs[None, :]
    # mer franche : 6 blocs au large (une mare de la côte fine ou un chenal de 2 blocs ne compte pas) ; le nouveau
    # bout y est posé directement
    mer = T.distance_cote(XX, ZZ) < FRANCHE
    if not mer.any():
        continue
    premier = np.where(mer.any(1), rs[np.argmax(mer, axis=1)], 10 ** 9)
    k = int(np.argmin(premier))
    r = premier[k]
    mx, mz = x + np.cos(ang[k]) * r, z + np.sin(ang[k]) * r
    if any((int(np.floor((x + (mx - x) * s) / 512)), int(np.floor((z + (mz - z) * s) / 512))) in lieux
           for s in np.linspace(0, 1, 9)):
        continue
    q = [round(mx / B, 4), round(-mz / B, 4)]
    o["p"] = p + q if fin else q + p
    prolonges += 1
json.dump(t, open(F, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print(prolonges, "embouchures prolongées jusqu'à la mer")

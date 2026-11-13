"""Emplacements fixes des villages de Domaine Village (13/11/2026).

Tirés des vraies villes (GeoNames cities1000, CC BY 4.0) : la carte est découpée en cases de 512 blocs (32 chunks,
le « maillage vaste » validé par Maxime) ; dans chaque case, la ville la plus peuplée donne le village. Le point est
ensuite poussé au plus près sur un sol constructible du mod Terre (copie Python du terrain, outils/terre_py.py) :
terre ferme à plus de ~15 blocs de la mer, hors fleuve et lac, pente douce, et toujours dans sa case. Deux villages
sont à au moins 300 blocs l'un de l'autre (le plus peuplé l'emporte).

Usage : python3 outils/villages.py <cities1000.txt> <sortie.csv> [processus]
Sortie : x;z;population;nom;pays (blocs à l'échelle 1:250), triée par case.
"""
import csv, math, multiprocessing as mp, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import terre_py as T

CASE = 512
MARGE = 24            # le village (≈ 100 blocs de large) reste dans sa case
ECART_MIN = 300
RAYON = 160           # recherche d'un sol constructible autour de la ville
PAS = 16


def valides(X, Z):
    sd = T.distance_cote(X, Z)
    pres, dmin, hw, _, _, _ = T.rivieres(X, Z)
    riv = pres & (dmin <= hw + 6)
    lac, dl = T.lacs_proches(X, Z)
    dans_lac = (lac > 0) & (dl > -8)
    alt = T.relief(X / T.BPD, -Z / T.BPD)
    return (sd > 2) & ~riv & ~dans_lac & (T.pente(X, Z) < 40) & (alt < 2500)


def placer(args):
    """(cx, cz, candidats) -> (x, z, ville) ou None ; candidats = villes de la case, plus peuplée d'abord."""
    cx, cz, villes = args
    x0, x1 = cx * CASE + MARGE, (cx + 1) * CASE - MARGE
    z0, z1 = cz * CASE + MARGE, (cz + 1) * CASE - MARGE
    for v in villes[:3]:
        x, z = min(max(v["x"], x0), x1), min(max(v["z"], z0), z1)
        if valides(np.array([[x]]), np.array([[z]]))[0, 0]:
            return round(x), round(z), v
        g = np.arange(-RAYON, RAYON + 1, PAS, dtype=float)
        X, Z = np.meshgrid(x + g, z + g)
        dedans = (X >= x0) & (X <= x1) & (Z >= z0) & (Z <= z1)
        ok = valides(X, Z) & dedans
        if ok.any():
            d = np.where(ok, np.hypot(X - x, Z - z), np.inf)
            i = np.unravel_index(np.argmin(d), d.shape)
            return round(float(X[i])), round(float(Z[i])), v
    return None


def main():
    src, sortie = sys.argv[1], sys.argv[2]
    n_proc = int(sys.argv[3]) if len(sys.argv) > 3 else os.cpu_count()
    cases = {}
    with open(src, encoding="utf-8") as f:
        for l in f:
            c = l.rstrip("\n").split("\t")
            if len(c) < 15 or c[6] != "P":
                continue
            lat, lon, pop = float(c[4]), float(c[5]), int(c[14] or 0)
            if abs(lat) > 72:
                continue
            x, z = lon * T.BPD, -lat * T.BPD
            cases.setdefault((math.floor(x / CASE), math.floor(z / CASE)), []).append(
                {"x": x, "z": z, "pop": pop, "nom": c[1], "pays": c[8]})
    taches = [(cx, cz, sorted(v, key=lambda r: -r["pop"])) for (cx, cz), v in cases.items()]
    taches.sort(key=lambda t: -t[2][0]["pop"])
    print(f"{len(taches)} cases avec au moins une ville", flush=True)
    with mp.Pool(n_proc) as pool:
        places = []
        for i, r in enumerate(pool.imap(placer, taches, chunksize=16)):
            if r:
                places.append(r)
            if i % 2000 == 0:
                print(f"  {i} / {len(taches)}", flush=True)
    # écart minimal : le plus peuplé d'abord
    places.sort(key=lambda r: -r[2]["pop"])
    gardes, grille = [], {}
    for x, z, v in places:
        k = (x // ECART_MIN, z // ECART_MIN)
        voisins = [p for dx in (-1, 0, 1) for dz in (-1, 0, 1) for p in grille.get((k[0] + dx, k[1] + dz), [])]
        if any((x - a) ** 2 + (z - b) ** 2 < ECART_MIN ** 2 for a, b in voisins):
            continue
        grille.setdefault(k, []).append((x, z))
        gardes.append((x, z, v))
    gardes.sort(key=lambda r: (math.floor(r[1] / CASE), math.floor(r[0] / CASE)))
    os.makedirs(os.path.dirname(os.path.abspath(sortie)), exist_ok=True)
    with open(sortie, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["x", "z", "population", "nom", "pays"])
        for x, z, v in gardes:
            w.writerow([x, z, v["pop"], v["nom"], v["pays"]])
    print(f"{len(gardes)} villages ({len(places) - len(gardes)} écartés, trop proches)")


if __name__ == "__main__":
    main()

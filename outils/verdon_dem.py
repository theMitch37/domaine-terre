"""Prépare le relief réel des gorges du Verdon pour l'addon Lieux (Copernicus DEM GLO-30).

Entrée : outils/donnees/relief_verdon.npz (outils/relief_lieu.py, via GitHub Actions).
Sortie : lieux/src/main/resources/domaine_terre_lieux/verdon.bin (format ReliefLieu, gzip), 6 grilles int16 :
  0 E = altitude réelle (m)
  1 P = niveau du plateau autour de la gorge (m), pris hors de la gorge et prolongé vers le fleuve
  2 D = distance au talweg du Verdon (1e-5 degré, en « espace blocs » : sans cos(lat), comme la carte du mod)
  3 S = abscisse du point du talweg le plus proche (1e-4 degré le long du fleuve, 0 = pont du Galetas)
  4 A = distance au talweg de l'Artuby (1e-5 degré)
  5 L = distance signée au rivage du lac de Sainte-Croix (1e-5 degré, négative dans le lac)
Usage : python3 outils/verdon_dem.py [apercu.png]
"""
import gzip, os, struct, sys
import numpy as np
from scipy import ndimage
from skimage.graph import route_through_array

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
d = np.load("outils/donnees/relief_verdon.npz")
E1 = d["E"].astype(np.float32)
LON_T, LAT_T, PAS_T = float(d["lon0"]), float(d["lat0"]), float(d["pas_lon"])

# zone du lieu et pas de la grille du mod (4", ~0,5 bloc en 1:250)
LON0, LON1, LAT0, LAT1 = 6.07, 6.56, 43.88, 43.69
PAS = 1 / 900

def px1(lat, lon):
    return int(round((LAT_T - lat) / PAS_T - 0.5)), int(round((lon - LON_T) / PAS_T - 0.5))

# ---------------------------------------------------------------- talwegs (sur la grille fine, 1")
loc = E1 - ndimage.minimum_filter(E1, size=7)
cout = 1.0 + (loc / 10.0) ** 2 + np.maximum(E1 - ndimage.minimum_filter(E1, size=31), 0) / 30.0

def talweg(passages):
    chemin = []
    for (la0, lo0), (la1, lo1) in zip(passages, passages[1:]):
        pts, _ = route_through_array(cout, px1(la0, lo0), px1(la1, lo1), fully_connected=True, geometric=True)
        chemin += pts if not chemin else pts[1:]
    return np.array(chemin)

VERDON = [(43.8008, 6.2555),   # pont du Galetas (sortie de la gorge dans le lac)
          (43.7650, 6.3000),
          (43.7470, 6.3300),
          (43.7420, 6.3800),   # la Mescla (confluence de l'Artuby)
          (43.7856, 6.3940),
          (43.7967, 6.4106),   # Point Sublime
          (43.8460, 6.5120)]   # Castellane
ARTUBY = [(43.7420, 6.3800), (43.7020, 6.4020)]
cv, ca = talweg(VERDON), talweg(ARTUBY)

# abscisse le long du Verdon (degrés, espace blocs)
seg = np.hypot(np.diff(cv[:, 0]), np.diff(cv[:, 1])) * PAS_T
absc = np.concatenate([[0.0], np.cumsum(seg)])
for nom, (la, lo) in [("Mescla", VERDON[3]), ("Point Sublime", VERDON[5]), ("Castellane", VERDON[6])]:
    i = np.argmin(np.hypot(cv[:, 0] - px1(la, lo)[0], cv[:, 1] - px1(la, lo)[1]))
    print(f"abscisse {nom} : {absc[i]:.4f} deg = {absc[i] * 445.28:.0f} blocs en 1:250")

def distance(chemin, valeurs=None):
    m = np.zeros_like(E1, bool); m[chemin[:, 0], chemin[:, 1]] = True
    dist, (iy, ix) = ndimage.distance_transform_edt(~m, return_indices=True)
    dist = dist * PAS_T
    if valeurs is None:
        return dist, None
    V = np.zeros_like(E1); V[chemin[:, 0], chemin[:, 1]] = valeurs
    return dist, V[iy, ix]

DV, SV = distance(cv, absc)
DA, _ = distance(ca)
print(f"Verdon : {len(cv)} points, {absc[-1]:.3f} deg ; Artuby : {len(ca)} points")
print("altitude du talweg : Galetas", E1[tuple(cv[0])], "Mescla", E1[tuple(cv[len(cv) // 3])], "Castellane", E1[tuple(cv[-1])])

# ---------------------------------------------------------------- lac de Sainte-Croix
NIV_LAC = 473
eau = np.abs(E1 - NIV_LAC) <= 1
lab, n = ndimage.label(eau)
tailles = ndimage.sum(eau, lab, range(1, n + 1))
lac = lab == (1 + int(np.argmax(tailles)))
lac = ndimage.binary_closing(lac, iterations=3)
lac = ndimage.binary_fill_holes(lac)
L = (ndimage.distance_transform_edt(~lac) - ndimage.distance_transform_edt(lac)) * PAS_T
print(f"lac : {lac.sum() * (PAS_T * 111.32) ** 2 * np.cos(np.radians(43.77)):.1f} km2")

# ---------------------------------------------------------------- plateau
# niveau du rebord : le relief réel pris à plus de ~1,2 km des talwegs, prolongé vers le fleuve par diffusion
hors = ((DV > 0.012) & (DA > 0.012) & ~lac).astype(np.float32)
num = ndimage.gaussian_filter(E1 * hors, 40); den = ndimage.gaussian_filter(hors, 40)
for _ in range(6):
    plein = den > 0.05
    num = np.where(plein, num, ndimage.gaussian_filter(num, 40)); den = np.where(plein, den, ndimage.gaussian_filter(den, 40))
P = np.where(den > 1e-4, num / np.maximum(den, 1e-4), E1)
P = ndimage.gaussian_filter(P, 8)

# ---------------------------------------------------------------- ré-échantillonnage à 4" sur la zone du lieu
W = round((LON1 - LON0) / PAS); H = round((LAT0 - LAT1) / PAS)
gy, gx = np.mgrid[0:H, 0:W].astype(np.float32)
fy = (LAT_T - (LAT0 - (gy + 0.5) * PAS)) / PAS_T - 0.5
fx = (LON0 + (gx + 0.5) * PAS - LON_T) / PAS_T - 0.5
def rech(G, order=1):
    return ndimage.map_coordinates(G.astype(np.float32), [fy, fx], order=order, mode="nearest")
Es = rech(ndimage.gaussian_filter(E1, 2))
grilles = [Es, rech(P), np.minimum(rech(DV) * 1e5, 32000), np.minimum(rech(SV) * 1e4, 32000),
           np.minimum(rech(DA) * 1e5, 32000), np.clip(rech(L) * 1e5, -32000, 32000)]

blob = struct.pack("<4d2i", LON0, LAT0, PAS, PAS, W, H)
for g in grilles:
    blob += np.round(g).astype("<i2").tobytes()
sortie = "lieux/src/main/resources/domaine_terre_lieux/verdon.bin"
with gzip.open(sortie, "wb", 9) as f:
    f.write(blob)
print(f"écrit {sortie} : {W} x {H}, {os.path.getsize(sortie)} octets")
print(f"plateau près de la gorge : {np.percentile(grilles[1][grilles[2] < 1500], [5, 50, 95]).round()} m")
np.savez_compressed(sys.argv[1] if len(sys.argv) > 1 else "/tmp/verdon.npz", *grilles)

"""Prépare le relief réel du Grand Canyon pour l'addon Lieux (ETOPO 2022, 15 secondes d'arc).

Entrée : ETOPO_2022_v1_15s_N45W120_surface.tif (tuile NOAA, « ice surface », GeoTIFF).
Sortie : lieux/src/main/resources/domaine_terre_lieux/grand_canyon.bin (gzip) contenant, pour la zone
         LON0..LON1 x LAT1..LAT0, quatre grilles int16 :
         E = altitude réelle, P = niveau du plateau (rebord), R = niveau du Colorado le plus proche (m),
         D = distance au talweg du Colorado (hectomètres).
Usage : python3 outils/grand_canyon_dem.py <tuile.tif> [apercu.png]
"""
import gzip, json, struct, sys, zlib
import numpy as np
from scipy import ndimage

LON0, LON1, LAT0, LAT1 = -114.95, -111.30, 37.15, 35.55     # zone (ouest, est, nord, sud)
PAS = 1 / 240                                               # 15"

def lire_etopo(f):
    import tifffile
    p = tifffile.TiffFile(f).pages[0]
    TW, TH, W, H = p.tilewidth, p.tilelength, p.imagewidth, p.imagelength
    ntx, nty = (W + TW - 1) // TW, (H + TH - 1) // TH
    raw = open(f, "rb").read()
    out = np.zeros((nty * TH, ntx * TW), np.float32)
    for i, (o, l) in enumerate(zip(p.dataoffsets, p.databytecounts)):
        ty, tx = divmod(i, ntx)
        b = np.frombuffer(zlib.decompress(raw[o:o + l]), np.uint8).reshape(TH, TW * 4)
        b = np.cumsum(b, axis=1, dtype=np.uint64).astype(np.uint8)   # prédicteur flottant
        out[ty * TH:(ty + 1) * TH, tx * TW:(tx + 1) * TW] = \
            b.reshape(TH, 4, TW).transpose(0, 2, 1).copy().view(">f4").reshape(TH, TW)
    tie = p.tags["ModelTiepointTag"].value
    return out[:H, :W], tie[3], tie[4]

src = sys.argv[1]
a, lon_t, lat_t = lire_etopo(src)
x0 = round((LON0 - lon_t) / PAS); x1 = round((LON1 - lon_t) / PAS)
y0 = round((lat_t - LAT0) / PAS); y1 = round((lat_t - LAT1) / PAS)
E = a[y0:y1, x0:x1].astype(np.float32)
H, W = E.shape
print(f"zone {W} x {H} points, altitude {E.min():.0f} à {E.max():.0f} m")

# Talweg réel du Colorado : chemin le plus bas à travers le relief, entre des points de passage connus
from skimage.graph import route_through_array
PASSAGES = [(36.937, -111.484),   # barrage de Glen Canyon
            (36.865, -111.588),   # Lees Ferry
            (36.193, -111.800),   # confluence du Petit Colorado
            (36.100, -112.093),   # Phantom Ranch
            (36.200, -112.700),   # Havasu
            (36.070, -114.020),   # Grand Wash Cliffs (entrée du lac Mead)
            (36.016, -114.737),   # barrage Hoover
            (35.560, -114.665)]   # lac Mohave (sortie de la zone)
def px(lat, lon):
    return int(round((LAT0 - lat) / PAS - 0.5)), int(round((lon - LON0) / PAS - 0.5))
loc = E - ndimage.minimum_filter(E, size=9)
cout = 1.0 + (loc / 15.0) ** 2 + np.maximum(E - ndimage.minimum_filter(E, size=41), 0) / 40.0
chemin = []
for (la0, lo0), (la1, lo1) in zip(PASSAGES, PASSAGES[1:]):
    pts, _ = route_through_array(cout, px(la0, lo0), px(la1, lo1), fully_connected=True, geometric=True)
    chemin += pts if not chemin else pts[1:]
chemin = np.array(chemin)
# niveau du fleuve : altitude le long du talweg, jamais en montée vers l'aval
niv = np.minimum.accumulate(E[chemin[:, 0], chemin[:, 1]])
niv = ndimage.uniform_filter1d(niv, 9, mode="nearest")
riv = np.zeros_like(E, bool); riv[chemin[:, 0], chemin[:, 1]] = True
NIV = np.zeros_like(E); NIV[chemin[:, 0], chemin[:, 1]] = niv
mx = PAS * 111320 * np.cos(np.radians(36.3)); my = PAS * 111320
dist, (iy, ix) = ndimage.distance_transform_edt(~riv, sampling=(my, mx), return_indices=True)
R = NIV[iy, ix]
D = np.minimum(dist / 100.0, 30000)          # hectomètres
print(f"talweg : {len(chemin)} points, du niveau {niv[0]:.0f} m au niveau {niv[-1]:.0f} m")
# plateau (niveau du rebord) : fermeture morphologique, qui comble les vallées plus étroites que le disque
# (le canyon) sans remonter les grands plateaux au pied des escarpements (Marble Platform, Vermilion Cliffs)
r = 20
yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
P = ndimage.grey_closing(E, footprint=(xx * xx + yy * yy) <= r * r)
P = ndimage.gaussian_filter(P, 3)
P = np.maximum(P, E)
P = np.maximum(P, R + 1)

# ---------------------------------------------------------------- élargissement du canyon
# La hauteur du monde est fixe : 1 350 m de profondeur tiennent dans ~85 blocs, alors qu'en 1:250 un bloc
# fait 250 m de large. Sans rien faire, le canyon serait ~15 fois plus raide qu'en vrai (aiguilles, fentes).
# On l'élargit donc ELARG fois autour du talweg : un point à la distance d du fleuve lit le relief réel à la
# distance s(d) = d / ELARG, puis s rattrape d entre A et B (le plateau autour est un peu tassé). Le fleuve
# et tout ce qui est loin restent à leur vraie place.
ELARG, A_KM = 1.0, 24.0
pente = 2.0                                  # rattrapage : s grandit 2 fois plus vite que d
B_KM = A_KM * (2.0 - 1.0 / ELARG)            # s(B) = B
# point du fleuve le plus proche, lissé : évite les éventails dans les virages et les coutures entre méandres
qy = ndimage.gaussian_filter(iy.astype(np.float32), 8)
qx = ndimage.gaussian_filter(ix.astype(np.float32), 8)
gy, gx = np.mgrid[0:H, 0:W].astype(np.float32)
dkm = np.hypot((gy - qy) * my, (gx - qx) * mx) / 1000.0
skm = np.where(dkm <= A_KM, dkm / ELARG, np.where(dkm <= B_KM, A_KM / ELARG + (dkm - A_KM) * pente, dkm))
ratio = np.where(dkm > 1e-6, skm / np.maximum(dkm, 1e-6), 1.0)
sy = qy + (gy - qy) * ratio
sx = qx + (gx - qx) * ratio
def deformer(G):
    return ndimage.map_coordinates(G.astype(np.float32), [sy, sx], order=1, mode="nearest")
if ELARG > 1.0:
    E, P, R = deformer(E), deformer(P), deformer(R)
print(f"élargissement x{ELARG} jusqu'à {A_KM:.0f} km du fleuve, raccord jusqu'à {B_KM:.0f} km")

blob = struct.pack("<4d2i", LON0, LAT0, PAS, PAS, W, H)
for g in (E, P, R, D):
    blob += np.round(g).astype("<i2").tobytes()
sortie = "lieux/src/main/resources/domaine_terre_lieux/grand_canyon.bin"
import os; os.makedirs(os.path.dirname(sortie), exist_ok=True)
with gzip.open(sortie, "wb", 9) as f:
    f.write(blob)
print("écrit", sortie, os.path.getsize(sortie), "octets")
np.savez_compressed(sys.argv[2] if len(sys.argv) > 2 else "/tmp/gc.npz", E=E, P=P, R=R, D=D)

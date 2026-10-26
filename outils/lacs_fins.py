"""Carte des lacs de Terre 0.3.2 (étape C1, lacs en altitude) : chaque case (un bloc à 1:250) sait à quel lac elle
appartient ; chaque lac a l'altitude réelle de sa surface.

Lancé par .github/workflows/lacs-fins.yml (GSHHG et Copernicus ne se téléchargent pas depuis le poste de travail).
Usage : python outils/lacs_fins.py <GSHHS_shp> <sortie lacs.bin>

Sources :
- contours : GSHHG 2.3.7 « full » (Wessel & Smith, LGPL), niveau 2 (lacs) moins le niveau 3 (îles des lacs), sans la
  mer Caspienne (comptée comme mer dans les côtes fines) ; lacs d'au moins 0,5 km² (8 blocs) ;
- altitude de la surface : Copernicus DEM GLO-90 (© DLR e.V. 2010-2014 et © Airbus Defence and Space GmbH 2014-2018,
  fourni dans le cadre de COPERNICUS par l'Union européenne et l'ESA), lu sur AWS Open Data : médiane de 9 points
  à l'intérieur du lac (un modèle de surface met l'eau d'un lac à l'altitude de sa surface ; vérifié à quelques
  mètres près sur 16 lacs connus, outils/mesure_lacs_dem.py). Sans le modèle : relief ETOPO du mod.

Grille et tuiles : celles des côtes fines (outils/cotes_fines.py), 256 x 256 cases, BPD = 445,28.

Format (petit-boutiste) :
  "LACS" | int32 version=1 | float64 BPD | int32 taille=256 | int32 TX | int32 TY
  int32 L (lacs) puis L x (float32 altitude de surface en m, float32 superficie en km²) ; le lac k (1..L) est le k-ième
  int32 N (tuiles qui contiennent de l'eau de lac) puis N x (int32 index = ty·TX + tx, int32 longueur) puis les N blocs
  zlib, chacun = 256·256 uint16 (ligne par ligne) : numéro du lac, 0 hors lac.
"""
import glob, math, os, struct, sys, time, zlib
from concurrent.futures import ProcessPoolExecutor
import numpy as np
import pyogrio
import shapely
from rasterio import features
from rasterio.transform import from_origin
from PIL import Image

BPD = 445.28
T = 256
TX = math.ceil(360 * BPD / T)
TY = math.ceil(180 * BPD / T)
PAS = T / BPD
AIRE_MIN = 0.5                                  # km²
RACINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
RELIEF = os.path.join(RACINE, "src/main/resources/domaine_terre/carte/relief.png")
URL = "/vsicurl/https://copernicus-dem-90m.s3.amazonaws.com/{n}/{n}.tif"

_LACS = _ILES = _A_LACS = _A_ILES = None


def charger(chemin):
    _, _, wkb, _ = pyogrio.raw.read(chemin)
    return [q for g in shapely.from_wkb(wkb) if g is not None for q in getattr(g, "geoms", [g])]


def aire_km2(p):
    return p.area * 111.32 ** 2 * math.cos(math.radians(p.centroid.y))


# ---------------------------------------------------------------- altitude de surface

def nom_tuile(lat, lon):
    la, lo = math.floor(lat), math.floor(lon)
    return (f"Copernicus_DSM_COG_30_{'N' if la >= 0 else 'S'}{abs(la):02d}_00_"
            f"{'E' if lo >= 0 else 'W'}{abs(lo):03d}_00_DEM")


_ouvertes = {}


def lire_dem(lat, lon):
    import rasterio
    n = nom_tuile(lat, lon)
    if n not in _ouvertes:
        try:
            _ouvertes[n] = rasterio.open(URL.format(n=n))
        except Exception:
            _ouvertes[n] = None
    ds = _ouvertes[n]
    if ds is None:
        return np.nan
    try:
        r, c = ds.index(lon, lat)
        v = ds.read(1, window=((r, r + 1), (c, c + 1)))
        return float(v[0, 0]) if v.size else np.nan
    except Exception:
        return np.nan


def points_dedans(p, n=9, graine=1):
    rng = np.random.default_rng(graine)
    x0, y0, x1, y1 = p.bounds
    marge = 0.25 * min(x1 - x0, y1 - y0) * 0.25
    try:
        cible = p.buffer(-marge)
        if cible.is_empty:
            cible = p
    except Exception:
        cible = p
    pts = []
    for _ in range(3000):
        x, y = rng.uniform(x0, x1), rng.uniform(y0, y1)
        if shapely.contains_xy(cible, x, y):
            pts.append((y, x))
            if len(pts) >= n:
                break
    if not pts:
        c = p.representative_point(); pts = [(c.y, c.x)]
    return pts


def altitude_lac(args):
    k, wkb = args
    p = shapely.from_wkb(wkb)
    v = np.array([lire_dem(y, x) for y, x in points_dedans(p)])
    v = v[np.isfinite(v) & (v > -500) & (v < 9000)]
    return k, (float(np.median(v)) if len(v) else np.nan), len(v)


def altitude_etopo(p, rel):
    H, W = rel.shape
    c = p.representative_point()
    i, j = int((c.x + 180) / 360 * W), int((90 - c.y) / 180 * H)
    return float(rel[min(max(j, 0), H - 1), i % W])


# ---------------------------------------------------------------- carte

def _init(lacs, iles):
    global _LACS, _ILES, _A_LACS, _A_ILES
    _LACS, _ILES = lacs, iles
    _A_LACS, _A_ILES = shapely.STRtree(lacs), shapely.STRtree(iles)


def decouper(g, x0, y0, x1, y1):
    try:
        return shapely.clip_by_rect(g, x0, y0, x1, y1)
    except shapely.errors.GEOSException:
        return g


def raster(idx):
    ty, tx = divmod(idx, TX)
    lon0, lat0 = -180 + tx * PAS, 90 - ty * PAS
    boite = shapely.box(lon0, lat0 - PAS, lon0 + PAS, lat0)
    tr = from_origin(lon0, lat0, 1 / BPD, 1 / BPD)
    m = np.zeros((T, T), np.uint16)
    formes = []
    for i in _A_LACS.query(boite):
        g = decouper(_LACS[i], lon0, lat0 - PAS, lon0 + PAS, lat0)
        if not g.is_empty:
            formes.append((g, i + 1))
    if not formes:
        return idx, None
    features.rasterize(formes, out=m, transform=tr, all_touched=False, dtype=np.uint16)
    iles = [decouper(_ILES[i], lon0, lat0 - PAS, lon0 + PAS, lat0) for i in _A_ILES.query(boite)]
    iles = [g for g in iles if not g.is_empty]
    if iles:
        features.rasterize(iles, out=m, transform=tr, default_value=0, all_touched=False, dtype=np.uint16)
    return idx, (m if m.any() else None)


def tuiles_candidates(lacs):
    t = set()
    for p in lacs:
        x0, y0, x1, y1 = p.bounds
        for ty in range(max(int((90 - y1) // PAS), 0), min(int((90 - y0) // PAS), TY - 1) + 1):
            for tx in range(int((x0 + 180) // PAS), int((x1 + 180) // PAS) + 1):
                t.add(ty * TX + tx % TX)
    return sorted(t)


def main():
    dos, sortie = sys.argv[1:3]
    t0 = time.time()
    tous = charger(sorted(glob.glob(os.path.join(dos, "f", "GSHHS_f_L2.shp")))[0])
    caspienne = max(tous, key=lambda p: p.area)
    c = caspienne.centroid
    assert 46 < c.x < 54 and 36 < c.y < 47, "le plus grand lac devrait être la Caspienne"
    lacs = [p for p in tous if p is not caspienne and aire_km2(p) >= AIRE_MIN]
    lacs.sort(key=lambda p: -p.area)
    assert len(lacs) < 65535
    iles = charger(sorted(glob.glob(os.path.join(dos, "f", "GSHHS_f_L3.shp")))[0])
    print(f"{len(lacs)} lacs ≥ {AIRE_MIN} km² (sur {len(tous)}), {len(iles)} îles de lacs ({time.time() - t0:.0f} s)",
          flush=True)

    # altitude de surface (Copernicus GLO-90, lecture partielle des tuiles COG)
    os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
    os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif")
    os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "4")
    alt = np.full(len(lacs), np.nan); npts = np.zeros(len(lacs), int)
    with ProcessPoolExecutor(16) as ex:
        for n, (k, a, m) in enumerate(ex.map(altitude_lac, [(k, shapely.to_wkb(p)) for k, p in enumerate(lacs)],
                                             chunksize=8)):
            alt[k], npts[k] = a, m
            if n % 500 == 0:
                print(f"  altitudes {n}/{len(lacs)} ({time.time() - t0:.0f} s)", flush=True)
    rel = np.array(Image.open(RELIEF), dtype=np.float64) - 11000
    sans = np.flatnonzero(~np.isfinite(alt))
    for k in sans:
        alt[k] = altitude_etopo(lacs[k], rel)
    aires = np.array([aire_km2(p) for p in lacs])
    print(f"altitudes : {len(lacs) - len(sans)} lues dans Copernicus, {len(sans)} dans ETOPO ({time.time() - t0:.0f} s)",
          flush=True)
    for nom, la, lo in [("Léman", 46.45, 6.55), ("Annecy", 45.86, 6.17), ("Baïkal", 53.5, 108.0),
                        ("Titicaca", -15.9, -69.4), ("Supérieur", 47.7, -87.5), ("Constance", 47.6, 9.4)]:
        k = [i for i, p in enumerate(lacs) if shapely.contains_xy(p, lo, la)]
        if k:
            print(f"  {nom:10s} : lac {k[0] + 1}, {alt[k[0]]:.1f} m, {aires[k[0]]:.0f} km²", flush=True)

    # carte au bloc près
    cand = tuiles_candidates(lacs)
    print(f"{len(cand)} tuiles candidates ({time.time() - t0:.0f} s)", flush=True)
    blocs = {}
    with ProcessPoolExecutor(os.cpu_count(), initializer=_init, initargs=(lacs, iles)) as ex:
        for n, (idx, m) in enumerate(ex.map(raster, cand, chunksize=16)):
            if m is not None:
                blocs[idx] = zlib.compress(m.astype("<u2").tobytes(), 9)
            if n % 2000 == 0:
                print(f"  tuiles {n}/{len(cand)} ({time.time() - t0:.0f} s)", flush=True)
    cles = sorted(blocs)
    with open(sortie, "wb") as f:
        f.write(b"LACS" + struct.pack("<idiii", 1, BPD, T, TX, TY))
        f.write(struct.pack("<i", len(lacs)))
        f.write(np.c_[alt, aires].astype("<f4").tobytes())
        f.write(struct.pack("<i", len(cles)))
        for k in cles:
            f.write(struct.pack("<ii", k, len(blocs[k])))
        for k in cles:
            f.write(blocs[k])
    print(f"écrit {sortie} : {os.path.getsize(sortie) / 1e6:.1f} Mo, {len(lacs)} lacs, {len(cles)} tuiles, "
          f"{time.time() - t0:.0f} s", flush=True)


if __name__ == "__main__":
    main()

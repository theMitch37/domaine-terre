"""Carte des côtes fines de Terre 0.3.2 (étape B de la « mer fidèle ») : le vrai trait de côte au bloc près.

Lancé par .github/workflows/cotes-fines.yml (GSHHG ne se télécharge pas depuis le poste de travail).
Usage : python outils/cotes_fines.py <GSHHS_shp> <ne_10m_lakes.shp> <sortie cotes_fines.bin>

Source : GSHHG 2.3.7 « full » (Wessel & Smith, LGPL), niveau 1 (terres / océan) et niveau 5 (Antarctique, front
des glaces). Comme la carte actuelle, les grands lacs de Natural Earth (scalerank <= 4) sont comptés comme de l'eau.

Grille : une case par bloc à l'échelle 1:250 (BPD = 445,28 blocs par degré). La case gx couvre les longitudes
[-180 + gx/BPD, -180 + (gx+1)/BPD[ et la case gy les latitudes ]90 - (gy+1)/BPD, 90 - gy/BPD].
Un bloc (x, z) tombe dans gx = floor(x + 0,5 + 180·BPD), gy = floor(z + 0,5 + 90·BPD).
Tuiles de 256 x 256 cases : TX = ceil(360·BPD/256) colonnes, TY = ceil(180·BPD/256) lignes.

Format (petit-boutiste) :
  "COTE" | int32 version=1 | float64 BPD | int32 taille=256 | int32 TX | int32 TY
  octet[TX·TY] état des tuiles, ligne par ligne : 0 mer, 1 terre, 2 mixte
  int32 N (tuiles mixtes) puis N x (int32 index = ty·TX + tx, int32 longueur) puis les N blocs zlib,
  chacun = 256·256 bits (np.packbits, ligne par ligne, 1 = terre).
"""
import glob, math, os, struct, sys, time, zlib
from concurrent.futures import ProcessPoolExecutor
import numpy as np
import pyogrio
import shapely
from rasterio import features
from rasterio.transform import from_origin

BPD = 445.28
T = 256
TX = math.ceil(360 * BPD / T)
TY = math.ceil(180 * BPD / T)
PAS = T / BPD                                   # degrés par tuile

_POLYS = _LACS = _ARBRE = _ARBRE_LACS = None


def charger(chemins, filtre=None):
    out = []
    for c in chemins:
        meta, _, wkb, champs = pyogrio.raw.read(c)
        geoms = shapely.from_wkb(wkb)
        for i, g in enumerate(geoms):
            if g is None or (filtre and not filtre(meta, champs, i)):
                continue
            out.extend(getattr(g, "geoms", [g]))
    return out


def grand_lac(meta, champs, i):
    noms = list(meta["fields"])
    if "scalerank" not in noms:
        return True
    v = champs[noms.index("scalerank")][i]
    return v is not None and v <= 4


def tuiles_traversees(polys):
    """Tuiles touchées par une côte (points denses le long de chaque anneau, 16 par tuile au moins)."""
    t = set()
    for p in polys:
        for a in [np.asarray(p.exterior.coords)] + [np.asarray(h.coords) for h in p.interiors]:
            d = np.diff(a, axis=0)
            n = np.maximum(1, np.ceil(np.hypot(d[:, 0], d[:, 1]) / (PAS / 16))).astype(int)
            i = np.repeat(np.arange(len(d)), n)
            k = np.arange(len(i)) - np.repeat(np.cumsum(n) - n, n)
            xy = a[:-1][i] + d[i] * (k / n[i])[:, None]
            tx = np.floor((xy[:, 0] + 180) / PAS).astype(np.int64)
            ty = np.floor((90 - xy[:, 1]) / PAS).astype(np.int64)
            ok = (tx >= 0) & (tx < TX) & (ty >= 0) & (ty < TY)
            t.update(np.unique(ty[ok] * TX + tx[ok]).tolist())
    return t


def _init(polys, lacs):
    global _POLYS, _LACS, _ARBRE, _ARBRE_LACS
    _POLYS, _LACS = polys, lacs
    _ARBRE, _ARBRE_LACS = shapely.STRtree(polys), shapely.STRtree(lacs)


def raster(idx):
    ty, tx = divmod(idx, TX)
    lon0, lat0 = -180 + tx * PAS, 90 - ty * PAS
    boite = shapely.box(lon0, lat0 - PAS, lon0 + PAS, lat0)
    tr = from_origin(lon0, lat0, 1 / BPD, 1 / BPD)
    m = np.zeros((T, T), np.uint8)
    # clip_by_rect : rapide et tolérant aux géométries invalides (GSHHG en a quelques-unes)
    terres = [shapely.clip_by_rect(_POLYS[i], lon0, lat0 - PAS, lon0 + PAS, lat0) for i in _ARBRE.query(boite)]
    terres = [g for g in terres if not g.is_empty]
    if terres:
        features.rasterize(terres, out=m, transform=tr, default_value=1, all_touched=False)
    lacs = [shapely.clip_by_rect(_LACS[i], lon0, lat0 - PAS, lon0 + PAS, lat0) for i in _ARBRE_LACS.query(boite)]
    lacs = [g for g in lacs if not g.is_empty]
    if lacs:
        features.rasterize(lacs, out=m, transform=tr, default_value=0, all_touched=False)
    return idx, m


def etat_centres(polys, lacs, idx):
    """Terre (1) ou mer (0) au centre des tuiles non traversées."""
    ty, tx = np.divmod(np.asarray(idx), TX)
    lon = -180 + (tx + 0.5) * PAS; lat = 90 - (ty + 0.5) * PAS
    pts = shapely.points(lon, lat)
    terre = np.zeros(len(idx), bool)
    a, b = shapely.STRtree(polys).query(pts, predicate="within")
    terre[np.unique(a)] = True
    a, b = shapely.STRtree(lacs).query(pts, predicate="within")
    terre[np.unique(a)] = False
    return terre


def main():
    dos, lacs_shp, sortie = sys.argv[1:4]
    t0 = time.time()
    polys = charger(sorted(glob.glob(os.path.join(dos, "f", "GSHHS_f_L1.shp"))) +
                    sorted(glob.glob(os.path.join(dos, "f", "GSHHS_f_L5.shp"))))
    lacs = charger([lacs_shp], grand_lac)
    print(f"{len(polys)} terres, {len(lacs)} grands lacs ({time.time() - t0:.0f} s)", flush=True)
    mixtes = sorted(tuiles_traversees(polys + lacs))
    print(f"{len(mixtes)} tuiles traversées par une côte ({time.time() - t0:.0f} s)", flush=True)
    etat = np.zeros(TX * TY, np.uint8)
    reste = np.setdiff1d(np.arange(TX * TY), np.asarray(mixtes))
    etat[reste] = etat_centres(polys, lacs, reste).astype(np.uint8)
    print(f"tuiles pleines : {int(etat[reste].sum())} terre, {len(reste) - int(etat[reste].sum())} mer "
          f"({time.time() - t0:.0f} s)", flush=True)
    blocs = {}
    with ProcessPoolExecutor(os.cpu_count(), initializer=_init, initargs=(polys, lacs)) as ex:
        for n, (idx, m) in enumerate(ex.map(raster, mixtes, chunksize=16)):
            s = int(m.sum())
            if s == 0 or s == T * T:                                    # traversée par un point, mais uniforme
                etat[idx] = 1 if s else 0
            else:
                etat[idx] = 2
                blocs[idx] = zlib.compress(np.packbits(m).tobytes(), 9)
            if n % 1000 == 0:
                print(f"  {n}/{len(mixtes)} ({time.time() - t0:.0f} s)", flush=True)
    cles = sorted(blocs)
    with open(sortie, "wb") as f:
        f.write(b"COTE" + struct.pack("<idiii", 1, BPD, T, TX, TY))
        f.write(etat.tobytes())
        f.write(struct.pack("<i", len(cles)))
        for k in cles:
            f.write(struct.pack("<ii", k, len(blocs[k])))
        for k in cles:
            f.write(blocs[k])
    print(f"écrit {sortie} : {os.path.getsize(sortie) / 1e6:.1f} Mo, {len(cles)} tuiles mixtes, "
          f"{time.time() - t0:.0f} s", flush=True)


if __name__ == "__main__":
    main()

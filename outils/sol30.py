"""Sol du monde 1:30 (09/11/2026) : couverture du sol et roche, un octet chacun par bloc.

Croise :
- ESA WorldCover 10 m (2021, v200, CC BY 4.0) : classe la plus fréquente sur la case de 30 m du bloc ;
- Macrostrat (CC BY 4.0, cartes géologiques du monde, au plus détaillé disponible) : famille de roche (ROCHES) de
  l'unité géologique qui affleure au bloc, tirée des tuiles vectorielles « carto » (zoom 12) et des définitions.

Même projection que le mod : centre du bloc x : lon = (x + 0.5) / BPD, lat = -(z + 0.5) / BPD, BPD = 111320 / 30.
Paquets : format v2 du relief (outils relief30.py : « RELB » v2, 16 x 16 régions de 512 blocs, zlib int16 en écarts
avec le voisin de gauche) ; valeur = roche * 256 + couverture ; -32768 = pas de donnée. Fichiers sol30_<bx>_<bz>.bin.

Usage : python outils/sol30.py <zones.json> <noms,séparés,virgules> <sortie>   (régions de 512 couvrant les zones)
"""
import io, json, math, os, struct, sys, time, urllib.request, zlib
from collections import Counter
import numpy as np

ECHELLE = 30
BPD = 111320 / ECHELLE
T, N = 512, 16
VIDE = -32768
WC = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_{}_Map.tif"
MS = "https://macrostrat.org/api/v2"
TUILES = "https://tiles.macrostrat.org/carto/{z}/{x}/{y}.mvt"
Z = 12

# familles de roche (le mod lit ces numéros : monde/SolFeature.java)
ROCHES = ["inconnue", "gres", "argile", "calcaire", "dolomie", "craie", "conglomerat", "evaporite", "basalte",
          "andesite", "tuf", "granite", "gabbro", "gneiss", "quartzite", "marbre", "meuble", "glaciaire", "dune"]
MOTS = [  # (mot dans le nom de la lithologie, famille) : le premier qui correspond gagne
    ("dune", "dune"), ("eolian", "dune"), ("loess", "meuble"), ("till", "glaciaire"), ("moraine", "glaciaire"),
    ("glacial", "glaciaire"), ("alluvi", "meuble"), ("gravel", "meuble"), ("unconsolidated", "meuble"),
    ("colluvi", "meuble"), ("sand", "gres"), ("arkose", "gres"), ("wacke", "gres"), ("arenite", "gres"),
    ("conglomerate", "conglomerat"), ("breccia", "conglomerat"), ("chalk", "craie"), ("dolo", "dolomie"),
    ("limestone", "calcaire"), ("carbonate", "calcaire"), ("travertine", "calcaire"), ("marble", "marbre"),
    ("quartzite", "quartzite"), ("gypsum", "evaporite"), ("evaporite", "evaporite"), ("salt", "evaporite"),
    ("anhydrite", "evaporite"), ("shale", "argile"), ("mud", "argile"), ("silt", "argile"), ("clay", "argile"),
    ("argillite", "argile"), ("marl", "argile"), ("slate", "gneiss"), ("phyllite", "gneiss"), ("schist", "gneiss"),
    ("gneiss", "gneiss"), ("migmatite", "gneiss"), ("amphibolite", "gneiss"), ("metavolcanic", "gneiss"),
    ("metasediment", "gneiss"), ("metamorphic", "gneiss"), ("basalt", "basalte"), ("mafic volcanic", "basalte"),
    ("lava", "basalte"), ("rhyolite", "tuf"), ("tuff", "tuf"), ("ignimbrite", "tuf"), ("pyroclastic", "tuf"),
    ("volcaniclastic", "tuf"), ("andesite", "andesite"), ("dacite", "andesite"), ("volcanic", "andesite"),
    ("gabbro", "gabbro"), ("diorite", "gabbro"), ("ultramafic", "gabbro"), ("peridotite", "gabbro"),
    ("mafic", "gabbro"), ("granit", "granite"), ("tonalite", "granite"), ("monzonite", "granite"),
    ("syenite", "granite"), ("pegmatite", "granite"), ("plutonic", "granite"), ("felsic", "granite"),
    ("intrusive", "granite"), ("igneous", "granite"), ("sedimentary", "argile"), ("siliciclastic", "gres")]


def famille(texte):
    t = (texte or "").lower()
    for m, f in MOTS:
        if m in t:
            return ROCHES.index(f)
    return 0


def get(url, essais=5, binaire=False):
    for k in range(essais):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "DomaineTerre-sol30"})
            with urllib.request.urlopen(req, timeout=60) as r:
                b = r.read()
            return b if binaire else json.loads(b)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(2 * (k + 1))
        except Exception:
            time.sleep(2 * (k + 1))
    return None


# ---------------------------------------------------------------- WorldCover

def couverture(tx, tz, dossier):
    import rasterio
    from rasterio.merge import merge
    from rasterio.warp import reproject
    from rasterio.enums import Resampling
    from rasterio.transform import from_origin
    o, e = tx * T / BPD, (tx + 1) * T / BPD
    n, s = -tz * T / BPD, -(tz + 1) * T / BPD
    srcs = []
    for la in range(math.floor(s / 3) * 3, math.floor(n / 3) * 3 + 1, 3):
        for lo in range(math.floor(o / 3) * 3, math.floor(e / 3) * 3 + 1, 3):
            nom = (f"N{la:02d}" if la >= 0 else f"S{-la:02d}") + (f"E{lo:03d}" if lo >= 0 else f"W{-lo:03d}")
            p = os.path.join(dossier, nom + ".tif")
            if not os.path.exists(p):
                b = get(WC.format(nom), binaire=True)
                if b is None:
                    continue
                open(p, "wb").write(b)
            srcs.append(rasterio.open(p))
    out = np.zeros((T, T), np.uint8)
    if not srcs:
        return out
    m = 2 / BPD
    mos, tr = merge(srcs, bounds=(o - m, s - m, e + m, n + m), nodata=0)
    reproject(mos[0], out, src_transform=tr, src_crs="EPSG:4326", src_nodata=0,
              dst_transform=from_origin(o, n, 1 / BPD, 1 / BPD), dst_crs="EPSG:4326", dst_nodata=0,
              resampling=Resampling.mode)
    return out


# ---------------------------------------------------------------- Macrostrat

def tuile_xy(lon, lat, z):
    n = 2 ** z
    x = (np.asarray(lon) + 180) / 360 * n
    y = (1 - np.arcsinh(np.tan(np.radians(lat))) / np.pi) / 2 * n
    return x, y


_unites = {}


def unite(map_id):
    """Famille de roche d'une unité de carte Macrostrat (lithologie principale)."""
    if map_id in _unites:
        return _unites[map_id]
    j = get(f"{MS}/geologic_units/map?map_id={map_id}")
    f = 0
    try:
        d = j["success"]["data"][0]
        txt = d.get("lith") or ""
        maj = txt.split("Major:{")[1].split("}")[0] if "Major:{" in txt else txt
        f = famille(maj) or famille(txt) or famille(d.get("name")) or famille(d.get("descrip"))
    except Exception:
        pass
    _unites[map_id] = f
    return f


def roche(tx, tz, journal):
    """Famille de roche par bloc d'une région, depuis les tuiles vectorielles carto de Macrostrat (zoom Z)."""
    import mapbox_vector_tile
    from PIL import Image, ImageDraw
    xs = (tx * T + np.arange(T) + 0.5) / BPD
    zs = -(tz * T + np.arange(T) + 0.5) / BPD
    LON, LAT = np.meshgrid(xs, zs)
    fx, fy = tuile_xy(LON, LAT, Z)
    out = np.zeros((T, T), np.uint8)
    R = 1024                                             # trame d'une tuile
    for ty in range(int(fy.min()), int(fy.max()) + 1):
        for txx in range(int(fx.min()), int(fx.max()) + 1):
            b = get(TUILES.format(z=Z, x=txx, y=ty), binaire=True)
            if not b:
                continue
            try:
                d = mapbox_vector_tile.decode(b)
            except Exception as ex:
                journal.append(f"tuile {txx} {ty} illisible : {ex}")
                continue
            img = Image.new("I", (R, R), 0)
            dr = ImageDraw.Draw(img)
            ids = {}
            for nom_couche, c in d.items():
                ext = c.get("extent", 4096)
                for f in c["features"]:
                    p = f.get("properties", {})
                    mid = p.get("map_id")
                    if mid is None:
                        continue
                    if not journal or len(journal) < 3:
                        journal.append(f"couche {nom_couche} : {sorted(p.keys())}")
                    k = ids.setdefault(mid, len(ids) + 1)
                    g = f["geometry"]
                    polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"] if g["type"] == "MultiPolygon" else []
                    for poly in polys:
                        for i, anneau in enumerate(poly):
                            pts = [(px * R / ext, R - py * R / ext) for px, py in anneau]   # y vers le haut dans la tuile
                            if len(pts) >= 3:
                                dr.polygon(pts, fill=k if i == 0 else 0)
            a = np.array(img)
            sel = (fx >= txx) & (fx < txx + 1) & (fy >= ty) & (fy < ty + 1)
            px = np.clip(((fx[sel] - txx) * R).astype(int), 0, R - 1)
            py = np.clip(((fy[sel] - ty) * R).astype(int), 0, R - 1)
            v = a[py, px]
            inv = {k: unite(m) for m, k in ids.items()}
            out[sel] = np.array([inv.get(int(k), 0) for k in v], np.uint8)
    return out


# ---------------------------------------------------------------- paquets

def encoder(v):
    q = v.astype(np.int32)
    d = q.copy()
    d[:, 1:] = q[:, 1:] - q[:, :-1]
    d[q == VIDE] = VIDE
    d[:, 1:][(q[:, :-1] == VIDE) & (q[:, 1:] != VIDE)] = q[:, 1:][(q[:, :-1] == VIDE) & (q[:, 1:] != VIDE)]
    return zlib.compress(np.clip(d, -32768, 32767).astype("<i2").tobytes(), 9)


def paquet(bx, bz, rs):
    tete = bytearray(b"RELB" + struct.pack("<iiiii", 2, bx, bz, N, ECHELLE))
    dec = len(tete) + N * N * 8
    corps = bytearray()
    table = []
    for k in range(N * N):
        b = rs.get(k, b"")
        table.append((dec + len(corps) if b else 0, len(b)))
        corps += b
    for t in table:
        tete += struct.pack("<ii", *t)
    return bytes(tete + corps)


def main():
    zones = json.load(open(sys.argv[1]))
    noms = sys.argv[2].split(",")
    sortie = sys.argv[3]
    os.makedirs(sortie, exist_ok=True)
    wc = "/tmp/worldcover"
    os.makedirs(wc, exist_ok=True)
    regions = set()
    for nom in noms:
        x0, x1, z0, z1 = zones[nom]
        for tz in range(z0 >> 9, (z1 >> 9) + 1):
            for tx in range(x0 >> 9, (x1 >> 9) + 1):
                regions.add((tx, tz))
    paquets, bilan = {}, {}
    journal = []
    for tx, tz in sorted(regions):
        t0 = time.time()
        c = couverture(tx, tz, wc)
        r = roche(tx, tz, journal)
        v = np.where(c > 0, r.astype(np.int32) * 256 + c, VIDE)
        paquets.setdefault((tx >> 4, tz >> 4), {})[(tx & 15) + 16 * (tz & 15)] = encoder(v)
        cc = Counter(c.ravel().tolist())
        rr = Counter(r.ravel().tolist())
        bilan[f"{tx},{tz}"] = {"couverture": {str(k): n for k, n in cc.most_common()},
                               "roche": {ROCHES[k]: n for k, n in rr.most_common()}}
        print(f"région {tx} {tz} : {time.time() - t0:.0f} s, couverture {cc.most_common(4)}, "
              f"roche {[(ROCHES[k], n) for k, n in rr.most_common(4)]}", flush=True)
    for (bx, bz), rs in paquets.items():
        open(os.path.join(sortie, f"sol30_{bx}_{bz}.bin"), "wb").write(paquet(bx, bz, rs))
    json.dump({"bilan": bilan, "journal": journal, "unites": {str(k): ROCHES[v] for k, v in _unites.items()}},
              open(os.path.join(sortie, "bilan.json"), "w"), indent=1)
    print("\n".join(journal[:10]))


if __name__ == "__main__":
    main()

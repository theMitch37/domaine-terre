"""Construit les cartes embarquées dans le mod domaine_terre à partir de Natural Earth et ETOPO.

Grille de sortie : 3 minutes d'arc (7200 x 3600), longitude -180 -> 180, latitude 90 -> -90.
Dans le monde Minecraft (projection équirectangulaire), 1 minute d'arc = 1,853 bloc en 1:1000.

Sorties (dossier SORTIE) :
  relief.png     16 bits : altitude en mètres + 11000
  cotes.png      8 bits  : distance signée à la côte (128 = côte, +4 par minute d'arc vers l'intérieur)
  lacs.png       8 bits  : idem pour les grands lacs (128 = rive, > 128 dans le lac)
  terroirs.png   8 bits  : 0 = mer, 1..29 = terroir (voir terroirs.json)
  terroirs.json  : index -> clé, nom, continent, couleur
  fleuves.json   : tracés simplifiés, avec leur classe (1 grand fleuve, 2 fleuve moyen, 3 rivière)
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

from shp import lire_zip

SORTIE = sys.argv[1] if len(sys.argv) > 1 else "sortie"
os.makedirs(SORTIE, exist_ok=True)
W3, H3 = 7200, 3600            # grille 3'
W1, H1 = 21600, 10800          # grille 1' (rastérisation)


def px(lon, lat, w, h):
    return ((lon + 180.0) / 360.0 * w, (90.0 - lat) / 180.0 * h)


def aire_signee(anneau):
    s = 0.0
    for (x1, y1), (x2, y2) in zip(anneau, anneau[1:] + anneau[:1]):
        s += x1 * y2 - x2 * y1
    return s / 2


def rasteriser(formes, w, h, filtre=None):
    """Polygones -> masque. Anneaux horaires = extérieurs, anti-horaires = trous (convention shapefile)."""
    img = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(img)
    trous = []
    for i, parts in enumerate(formes):
        if filtre and not filtre(i):
            continue
        for anneau in parts:
            if len(anneau) < 3:
                continue
            pts = [px(lo, la, w, h) for lo, la in anneau]
            if aire_signee(anneau) < 0:      # horaire en lon/lat -> extérieur
                d.polygon(pts, fill=1)
            else:
                trous.append(pts)
    for pts in trous:
        d.polygon(pts, fill=0)
    return np.array(img, dtype=bool)


def distance_signee(masque, fac, plafond=32, tuile=1080):
    """Distance signée à la limite du masque (minutes d'arc, grille 1'), plafonnée à ±plafond,
    calculée par tuiles avec marge (exacte sous le plafond), puis moyennée par blocs fac x fac.
    La longitude boucle (le monde fait le tour de la Terre)."""
    marge = plafond + 8
    out = np.zeros((H1 // fac, W1 // fac), np.float32)
    for y0 in range(0, H1, tuile):
        for x0 in range(0, W1, tuile):
            ys = np.clip(np.arange(y0 - marge, y0 + tuile + marge), 0, H1 - 1)
            xs = np.arange(x0 - marge, x0 + tuile + marge) % W1
            m = masque[np.ix_(ys, xs)]
            if m.all():
                sd = np.full(m.shape, plafond, np.float32)
            elif not m.any():
                sd = np.full(m.shape, -plafond, np.float32)
            else:
                dedans = ndimage.distance_transform_edt(m)
                dehors = ndimage.distance_transform_edt(~m)
                sd = np.where(m, dedans - 0.5, -(dehors - 0.5)).astype(np.float32)
            sd = np.clip(sd[marge:marge + tuile, marge:marge + tuile], -plafond, plafond)
            h, w = sd.shape
            out[y0 // fac:(y0 + h) // fac, x0 // fac:(x0 + w) // fac] = \
                sd.reshape(h // fac, fac, w // fac, fac).mean(axis=(1, 3))
    return out


def vers_png8(sd, echelle=4.0):
    return np.clip(np.round(128 + sd * echelle), 0, 255).astype(np.uint8)


print("1/6 terres et lacs", flush=True)
terres_f, _ = lire_zip("ne_10m_land.zip")
lacs_f, lacs_d = lire_zip("ne_10m_lakes.zip")
terre1 = rasteriser(terres_f, W1, H1)
# grands lacs seulement (les petits disparaissent de toute façon à cette échelle)
lacs1 = rasteriser(lacs_f, W1, H1, filtre=lambda i: (lacs_d[i]["scalerank"] or 99) <= 4)
terre1 &= ~lacs1

print("2/6 distances aux côtes", flush=True)
if os.path.exists("cache_cotes.npy"):
    sd_cotes = np.load("cache_cotes.npy")
else:
    sd_cotes = distance_signee(terre1, 3); np.save("cache_cotes.npy", sd_cotes)
Image.fromarray(vers_png8(sd_cotes)).save(f"{SORTIE}/cotes.png", optimize=True)
if os.path.exists("cache_lacs.npy"):
    sd_lacs = np.load("cache_lacs.npy")
else:
    sd_lacs = distance_signee(lacs1, 3); np.save("cache_lacs.npy", sd_lacs)
Image.fromarray(vers_png8(sd_lacs)).save(f"{SORTIE}/lacs.png", optimize=True)
terre = sd_cotes > 0
del terre1, lacs1

print("3/6 relief", flush=True)
alt = np.load("altitude_3min.npy").astype(np.int32)
# Natural Earth fait foi pour le trait de côte : terres >= 1 m, mer <= -1 m
alt = np.where(terre, np.maximum(alt, 1), np.minimum(alt, -1))
Image.fromarray(np.clip(alt + 11000, 0, 65535).astype(np.uint16)).save(f"{SORTIE}/relief.png", optimize=True)

print("4/6 continents", flush=True)
LON = (np.arange(W3) + 0.5) / W3 * 360 - 180
LAT = 90 - (np.arange(H3) + 0.5) / H3 * 180
LON, LAT = np.meshgrid(LON, LAT)
rng = np.random.default_rng(1729)


def bruit(echelle, octaves=4):
    tot = np.zeros((H3, W3)); amp = 1; norm = 0
    for o in range(octaves):
        cell = max(echelle / 2 ** o, 2)
        gh, gw = int(H3 / cell) + 3, int(W3 / cell) + 3
        g = rng.standard_normal((gh, gw)).astype(np.float32)
        tot += amp * ndimage.zoom(g, (H3 / (gh - 2), W3 / (gw - 2)), order=3)[:H3, :W3]
        norm += amp; amp *= .5
    return tot / norm


Lo = LON + bruit(80) * 7.0
La = LAT + bruit(80) * 4.5
rel = ndimage.gaussian_filter(np.clip((alt - 1500) / 3000.0, 0, 1).astype(np.float32), 8)

comp, ncomp = ndimage.label(terre)
idx = np.arange(1, ncomp + 1)
taille = ndimage.sum(np.ones_like(comp), comp, idx)
c_lon = ndimage.mean(LON, comp, idx)
c_lat = ndimage.mean(LAT, comp, idx)


def dans_polygone(lon, lat, poly):
    """Test vectorisé point-dans-polygone (règle pair-impair)."""
    res = np.zeros(lon.shape, bool)
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]; x2, y2 = poly[(i + 1) % n]
        cond = ((y1 > lat) != (y2 > lat)) & (lon < (x2 - x1) * (lat - y1) / (y2 - y1 + 1e-12) + x1)
        res ^= cond
    return res


# Afrique : tout ce qui est au sud de la Méditerranée et à l'ouest de Suez / mer Rouge / golfe d'Aden
AFRIQUE = [(-20, 38), (-5.6, 35.95), (-1, 36.6), (3, 37.9), (9, 38.1), (11.5, 37.6), (13, 36.0), (20, 34.0),
           (25, 33.0), (32.3, 31.6), (32.55, 29.95), (33.7, 27.8), (35.9, 24.0), (38.5, 19.5), (41, 15.5),
           (43.4, 12.6), (51.5, 12.2), (60, 10), (60, -45), (-20, -45)]
REG = {"mer": 0, "europe": 1, "afrique": 2, "asie": 3, "ameriques": 4, "oceanie": 5, "gelees": 6}
reg = np.zeros((H3, W3), np.uint8)
def comp_en(lon, lat):
    x, y = px(lon, lat, W3, H3); return comp[int(y), int(x)]
CONTINENTS_PRINCIPAUX = {comp_en(-100, 40), comp_en(20, 10), comp_en(135, -25)}
grand = taille > 20000
fenetres = ndimage.find_objects(comp)
japon_comp = []
for k in range(ncomp):
    lo, la = c_lon[k], c_lat[k]
    sl = fenetres[k]
    msl = comp[sl] == (k + 1)
    principal = (k + 1) in CONTINENTS_PRINCIPAUX
    if -25 < lo < -12 and 62 < la < 67:                    # Islande
        r = "europe"
    elif la < -58:
        r = "gelees"
    elif -55 < lo < -10 and la > 59:                       # Groenland
        r = "gelees"
    elif not principal and la > 64 and -125 < lo < -60:    # archipel arctique canadien
        r = "gelees"
    elif not principal and la > 70.3 and (lo > 9 or lo < -168):   # Svalbard, Zemble, Sibérie arctique…
        r = "gelees"
    elif lo < -168 and la > 60:                            # bout est de la Tchoukotka
        r = "asie"
    elif (lo > 155 or lo < -130) and la < 30 and not grand[k]:   # îles du Pacifique
        r = "oceanie"
    elif lo > 112 and la < -10.5:                          # Australie, Tasmanie, Nouvelle-Zélande
        r = "oceanie"
    elif lo > 130.9 and -12 < la < 0:                      # Nouvelle-Guinée et voisines
        r = "oceanie"
    elif -170 < lo < -25 or (lo > 170 and la > 48):        # Amériques (+ Aléoutiennes)
        r = "ameriques"
    elif not principal and lo > 128.5 and 30 < la < 46:    # archipel japonais
        r = "japon"
    else:
        r = "eurasie_afrique"
    if r == "japon":
        japon_comp.append(k + 1); r = "asie"
    if r != "eurasie_afrique":
        reg[sl][msl] = REG[r]
        continue
    lo_, la_ = LON[sl][msl], LAT[sl][msl]
    af = dans_polygone(lo_, la_, AFRIQUE)
    wl, wa = Lo[sl][msl], La[sl][msl]
    eu = ((lo_ < 28) & (la_ > 34)) | ((wl < 58) & (la_ > 46.5)) | ((lo_ >= 28) & (lo_ < 48) & (la_ > 42.3))
    anatolie = ((lo_ > 29.1) & (la_ < 42)) | ((lo_ > 26.1) & (la_ < 40.4) & (lo_ < 45))
    eu &= ~anatolie
    sub = np.where(af, REG["afrique"], np.where(eu, REG["europe"], REG["asie"])).astype(np.uint8)
    reg[sl][msl] = sub

print("5/6 terroirs", flush=True)
TERROIRS = [  # (clé, nom, continent, couleur)
    ("atlantique", "Atlantique", "europe", (92, 150, 200)),
    ("mediterranee", "Méditerranée", "europe", (232, 160, 70)),
    ("continentale", "Continentale", "europe", (120, 175, 95)),
    ("nordique", "Nordique", "europe", (70, 115, 140)),
    ("alpine", "Alpine", "europe", (175, 180, 200)),
    ("maghreb", "Maghreb", "afrique", (205, 120, 75)),
    ("sahara_sahel", "Sahara-Sahel", "afrique", (240, 205, 130)),
    ("afrique_tropicale", "Afrique tropicale", "afrique", (60, 135, 55)),
    ("afrique_est", "Afrique de l'Est", "afrique", (165, 110, 60)),
    ("afrique_australe", "Australe et Madagascar", "afrique", (200, 170, 90)),
    ("moyen_orient", "Moyen-Orient", "asie", (215, 180, 120)),
    ("steppes_tibet", "Steppes et Tibet", "asie", (185, 190, 130)),
    ("siberie", "Sibérie", "asie", (110, 140, 125)),
    ("inde", "Inde", "asie", (230, 120, 60)),
    ("chine", "Chine", "asie", (200, 70, 70)),
    ("japon_coree", "Japon-Corée", "asie", (235, 150, 185)),
    ("asie_sud_est", "Asie du Sud-Est", "asie", (80, 165, 90)),
    ("boreale", "Boréale", "ameriques", (90, 125, 105)),
    ("grandes_plaines", "Grandes plaines et Est", "ameriques", (175, 195, 95)),
    ("ouest_mexique", "Ouest aride et Mexique", "ameriques", (210, 125, 70)),
    ("amerique_centrale", "Amérique centrale et Caraïbes", "ameriques", (60, 175, 150)),
    ("amazonie", "Amazonie", "ameriques", (40, 115, 45)),
    ("andes", "Andes", "ameriques", (150, 130, 160)),
    ("cone_sud", "Cône sud", "ameriques", (150, 185, 205)),
    ("australie", "Australie", "oceanie", (215, 110, 55)),
    ("nouvelle_zelande", "Nouvelle-Zélande", "oceanie", (95, 170, 120)),
    ("melanesie", "Mélanésie", "oceanie", (50, 150, 120)),
    ("arctique", "Arctique", "gelees", (225, 235, 245)),
    ("antarctique", "Antarctique", "gelees", (205, 215, 230)),
]
ID = {t[0]: i + 1 for i, t in enumerate(TERROIRS)}
ter = np.zeros((H3, W3), np.uint8)


def poser(cle, m):
    libre = (ter == 0) & m & terre
    ter[libre] = ID[cle]


eu, af, asi, am, oc, ge = (reg == REG[k] for k in ("europe", "afrique", "asie", "ameriques", "oceanie", "gelees"))
poser("nordique", eu & ((La > 58.3) | (LON < -12) | ((La > 55.3) & (Lo > 11.5) & (Lo < 31))))
poser("alpine", eu & (rel > .12) & (LAT < 50))
poser("mediterranee", eu & (La < 44.2) & ~((Lo < -5.5) & (La > 41.8)))
poser("atlantique", eu & ((Lo < 3) | ((Lo < 9.5) & (La > 50.3) & (La < 56))))
poser("continentale", eu)
poser("maghreb", af & (La > 28.5))
poser("afrique_australe", af & ((La < -12.5) | ((LON > 42.5) & (LAT < -11))))
poser("afrique_est", af & (((Lo > 33) & (La < 15.5) & (La > -12.5)) | ((Lo > 29) & (La < 1.5) & (La > -12.5))))
poser("sahara_sahel", af & (La > 11.5))
poser("afrique_tropicale", af)
japon = np.isin(comp, japon_comp)
coree = (LON > 124.3) & (LON < 131) & (LAT > 33) & (LAT < 39.8 + (LON - 124.3) * 0.42)
poser("japon_coree", asi & (japon | coree))
plateau = ndimage.gaussian_filter(alt.astype(np.float32), 4) > 2500
poser("steppes_tibet", asi & plateau & (LAT > 27.5) & (LON > 73) & (LON < 104))
poser("inde", asi & (LON > 66) & (LON < 77.5) & (LAT < 34.5) & (LAT > 23))
poser("moyen_orient", asi & (((Lo < 61.5) & (La < 42.5)) | ((LON < 71.5) & (LAT < 37.5))))
poser("siberie", asi & ((La > 53) | ((Lo > 127) & (La > 47.5) & ~((LON > 139) & (LAT < 45.6))) | (LON < -168)))
poser("inde", asi & (Lo > 61) & (Lo < 92.3) & (La < 29.5) & (LAT > 5))
poser("asie_sud_est", asi & (La < 22.5) & (Lo > 92.3))
poser("steppes_tibet", asi & (((La > 36) & (Lo < 100)) | ((La > 41.5) & (Lo < 121))))
poser("chine", asi)
poser("boreale", am & (La > 52))
sud = am & ((LAT < 8.5) | ((LON > -77.3) & (LAT < 12.6)))
poser("andes", sud & (rel > .25) & (LON < -62) & (LAT > -42))
poser("cone_sud", sud & (La < -24))
poser("amazonie", sud)
poser("amerique_centrale", am & (LAT < 23.6) & (LON > -92.6))
poser("ouest_mexique", am & ((Lo < -101) | (La < 26)))
poser("grandes_plaines", am)
poser("nouvelle_zelande", oc & (LON > 165) & (LAT < -33))
poser("melanesie", oc & ((LAT > -11) | (LON > 160) | (LON < 0)))
poser("australie", oc)
poser("arctique", ge & (LAT > 0))
poser("antarctique", ge)

# Nettoyage des enclaves : une petite tache d'un terroir entourée d'un autre (sur la même terre) est absorbée
for passe in range(2):
    for t in range(1, len(TERROIRS) + 1):
        lab, n = ndimage.label(ter == t)
        if n == 0:
            continue
        tailles = ndimage.sum(np.ones_like(lab), lab, np.arange(1, n + 1))
        fen = ndimage.find_objects(lab)
        for k in np.where(tailles < 600)[0]:
            sl = fen[k]
            y0, y1 = max(sl[0].start - 3, 0), min(sl[0].stop + 3, H3)
            x0, x1 = max(sl[1].start - 3, 0), min(sl[1].stop + 3, W3)
            m = lab[y0:y1, x0:x1] == (k + 1)
            bord = ndimage.binary_dilation(m, iterations=2) & ~m & terre[y0:y1, x0:x1]
            if not bord.any():
                continue                       # île entière : on garde son terroir
            voisins = ter[y0:y1, x0:x1][bord]
            ter[y0:y1, x0:x1][m] = np.bincount(voisins, minlength=len(TERROIRS) + 1).argmax()

Image.fromarray(ter).save(f"{SORTIE}/terroirs.png", optimize=True)
json.dump([{"index": i + 1, "cle": t[0], "nom": t[1], "continent": t[2], "couleur": "#%02x%02x%02x" % t[3]}
           for i, t in enumerate(TERROIRS)], open(f"{SORTIE}/terroirs.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

print("6/6 fleuves", flush=True)
fl_f, fl_d = lire_zip("ne_10m_rivers_lake_centerlines.zip")


def simplifier(pts, tol):
    """Douglas-Peucker (tolérance en degrés)."""
    if len(pts) < 3:
        return pts
    a, b = np.array(pts[0]), np.array(pts[-1])
    ab = b - a; L = np.hypot(*ab) or 1e-12
    dmax, imax = 0, 0
    for i in range(1, len(pts) - 1):
        p = np.array(pts[i])
        d = abs(ab[0] * (a[1] - p[1]) - ab[1] * (a[0] - p[0])) / L
        if d > dmax:
            dmax, imax = d, i
    if dmax <= tol:
        return [pts[0], pts[-1]]
    return simplifier(pts[:imax + 1], tol)[:-1] + simplifier(pts[imax:], tol)


fleuves = []
for parts, d in zip(fl_f, fl_d):
    sr = d["scalerank"]
    if sr is None or sr > 9 or d["featurecla"] == "Canal":
        continue
    classe = 1 if sr <= 3 else (2 if sr <= 6 else 3)
    for p in parts:
        s = simplifier(p, 0.01)
        fleuves.append({"c": classe, "n": d["name_fr"] or d["name"] or "",
                        "p": [round(v, 4) for xy in s for v in xy]})
json.dump(fleuves, open(f"{SORTIE}/fleuves.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))

print("terminé :", {k: int((reg == v).sum()) for k, v in REG.items()}, "| tracés de fleuves :", len(fleuves))

"""Carte des biomes fixe : chaque pixel de la grille 3' (7200 x 3600) reçoit UN biome, décidé d'après la réalité.

Plus aucun tirage Minecraft pour la surface des terres : le biome vient de
  - la couverture du sol réelle (MODIS MCD12C1, classes IGBP), si fournie ;
  - le climat Köppen-Geiger (climat.png) ;
  - l'altitude et la pente réelles (relief.png) ;
  - le terroir (terroirs.png), pour quelques biomes régionaux (cerisiers, bambous, tournesols).

Sans couverture du sol, l'outil marche quand même (climat + relief seuls) : utile pour tester.

Usage :
  python outils/carte_biomes.py [--couverture fichier_igbp.tif] [--controle dossier_images]
Sorties (src/main/resources/domaine_terre/carte/) :
  biomes.png   8 bits : 0 = pas de biome fixe (mer), sinon index dans biomes.json
  biomes.json  liste des biomes vanilla (index 1..n)
  neige.json   température à donner à chaque copie terroir/biome (limite des neiges réelle)
"""
import argparse
import json
import os

import numpy as np
from PIL import Image
from scipy import ndimage

Image.MAX_IMAGE_PIXELS = None
CARTE = "src/main/resources/domaine_terre/carte"
W, H = 7200, 3600

# ------------------------------------------------------------------ lecture
p = argparse.ArgumentParser()
p.add_argument("--couverture", help="GeoTIFF IGBP (MCD12C1 LC_Type1 ou équivalent), grille mondiale lon -180..180, lat 90..-90")
p.add_argument("--controle", help="dossier où écrire les cartes de contrôle (PNG)")
a = p.parse_args()

k = np.array(Image.open(f"{CARTE}/climat.png")).astype(np.int16)              # 0 mer, 1..30 Köppen
ter_brut = np.array(Image.open(f"{CARTE}/terroirs.png"))
ter = (ter_brut & 0x7F).astype(np.int16)
lac = (ter_brut & 0x80) != 0
alt = np.array(Image.open(f"{CARTE}/relief.png")).astype(np.int32) - 11000     # mètres
terroirs = {t["index"]: t["cle"] for t in json.load(open(f"{CARTE}/terroirs.json", encoding="utf-8"))}
terre = ter > 0

lat = 90.0 - (np.arange(H) + 0.5) / H * 180.0
lon = -180.0 + (np.arange(W) + 0.5) / W * 360.0
LAT = np.repeat(lat[:, None], W, axis=1)
LON = np.repeat(lon[None, :], H, axis=0)

# pente réelle en m/km (pixel de 3' = 5,56 km en latitude)
gy, gx = np.gradient(alt.astype(np.float32))
dx = 5.56 * np.maximum(np.cos(np.radians(LAT)), 0.05)
pente = np.sqrt((gx / dx) ** 2 + (gy / 5.56) ** 2)

# couverture du sol IGBP (0 = inconnue)
lc = np.zeros((H, W), np.int16)
if a.couverture:
    import tifffile
    src = tifffile.imread(a.couverture)
    if src.ndim > 2:
        src = src[..., 0] if src.shape[-1] < 8 else src[0]
    hs, ws = src.shape
    if (hs, ws) == (H, W):
        lc = src.astype(np.int16)
    elif hs % H == 0 and ws % W == 0:
        # plus fin que 3' : classe majoritaire par bloc
        f = hs // H
        b = src.reshape(H, f, W, f)
        best = np.zeros((H, W), np.int32)
        for c in range(1, 18):
            n = (b == c).sum(axis=(1, 3))
            m = n > best
            lc[m] = c
            best[m] = n[m]
    else:
        # autre grille : plus proche voisin
        yi = np.minimum((np.arange(H) + 0.5) / H * hs, hs - 1).astype(int)
        xi = np.minimum((np.arange(W) + 0.5) / W * ws, ws - 1).astype(int)
        lc = src[yi][:, xi].astype(np.int16)
    lc[(lc < 1) | (lc > 17)] = 0
    print("couverture du sol :", a.couverture, src.shape, "classes", np.bincount(lc[terre].ravel(), minlength=18).tolist())
else:
    print("pas de couverture du sol : climat et relief seuls")

# eau (17), villes (13), inconnu (0) et lacs : on prend la couverture de la terre naturelle la plus proche
a_remplir = terre & ((lc == 0) | (lc == 13) | (lc == 17) | lac)
if a.couverture and a_remplir.any() and (terre & ~a_remplir).any():
    _, (iy, ix) = ndimage.distance_transform_edt(a_remplir | ~terre, return_indices=True)
    # on veut le plus proche pixel de terre valide : on refait le calcul sur ce masque
    _, (iy, ix) = ndimage.distance_transform_edt(~(terre & ~a_remplir), return_indices=True)
    lc[a_remplir] = lc[iy[a_remplir], ix[a_remplir]]
# idem pour le climat des terres hors carte Köppen (bord de côte)
sans_k = terre & (k == 0)
if sans_k.any():
    _, (iy, ix) = ndimage.distance_transform_edt(~(terre & (k > 0)), return_indices=True)
    k[sans_k] = k[iy[sans_k], ix[sans_k]]

# ------------------------------------------------------------------ groupes de climat
def dans(*classes):
    return np.isin(k, classes)

TROP_HUMIDE = dans(1, 2)          # Af, Am
TROP_SEC = dans(3)                # Aw
TROP = TROP_HUMIDE | TROP_SEC
DESERT = dans(4, 5)               # BWh, BWk
STEPPE_CH = dans(6)               # BSh
STEPPE_FR = dans(7)               # BSk
ARIDE = DESERT | STEPPE_CH | STEPPE_FR
MEDIT = dans(8, 9)                # Csa, Csb
TEMPERE = dans(11, 12, 14, 15)    # Cwa, Cwb, Cfa, Cfb
OCEAN_FROID = dans(10, 13, 16)    # Csc, Cwc, Cfc
CONT = dans(17, 18, 21, 22, 25, 26)   # D*a, D*b
SUBARC = dans(19, 23, 27)             # D*c
EXTREME = dans(20, 24, 28)            # D*d
TUNDRA = dans(29)
GLACE = dans(30)
CHAUD = TROP | dans(4, 6)

def couv(*classes):
    return np.isin(lc, classes)

RESINEUX = couv(1, 3)             # forêt de conifères (sempervirents ou mélèzes)
FEUILLUS_PERS = couv(2)           # forêt sempervirente de feuillus
FEUILLUS = couv(4)
MIXTE = couv(5)
FORET = RESINEUX | FEUILLUS_PERS | FEUILLUS | MIXTE
FOURRES = couv(6)
FOURRES_OUV = couv(7)
SAV_BOISEE = couv(8)
SAVANE = couv(9)
PRAIRIE = couv(10)
HUMIDE = couv(11)
CULTURES = couv(12, 14)
NEIGE = couv(15)
NU = couv(16)
CONNU = lc > 0

# ------------------------------------------------------------------ choix du biome
BIOMES = ["plains", "sunflower_plains", "forest", "birch_forest", "flower_forest", "dark_forest",
          "taiga", "old_growth_pine_taiga", "old_growth_spruce_taiga", "snowy_taiga", "snowy_plains",
          "grove", "meadow", "cherry_grove", "windswept_hills", "windswept_forest",
          "snowy_slopes", "frozen_peaks", "jagged_peaks", "stony_peaks",
          "desert", "badlands", "wooded_badlands", "eroded_badlands",
          "savanna", "savanna_plateau", "windswept_savanna",
          "jungle", "sparse_jungle", "bamboo_jungle", "swamp", "mangrove_swamp"]
IDX = {b: i + 1 for i, b in enumerate(BIOMES)}
bio = np.zeros((H, W), np.uint8)

def poser(masque, biome):
    bio[masque & terre] = IDX[biome]

def terroir_est(*cles):
    ids = [i for i, c in terroirs.items() if c in cles]
    return np.isin(ter, ids)

# 1) base climatique (vaut seule sans couverture du sol, et sert de secours)
poser(TROP_HUMIDE, "jungle")
poser(TROP_SEC | STEPPE_CH, "savanna")
poser(DESERT, "desert")
poser(STEPPE_FR, "plains")
poser(dans(8), "plains")
poser(dans(9), "forest")
poser(TEMPERE, "forest")
poser(OCEAN_FROID, "taiga")
poser(dans(17, 18), "plains")
poser(dans(21, 22, 25, 26), "forest")
poser(SUBARC, "taiga")
poser(EXTREME, "snowy_taiga")
poser(TUNDRA | GLACE, "snowy_plains")

# 2) couverture du sol réelle
if a.couverture:
    # forêts de conifères
    poser(RESINEUX & (TEMPERE | CONT | SUBARC), "taiga")
    poser(RESINEUX & (ARIDE | MEDIT | TROP), "old_growth_pine_taiga")      # pins ponderosa, pins méditerranéens
    poser(RESINEUX & (OCEAN_FROID | dans(15)) & (np.abs(LAT) > 40), "old_growth_spruce_taiga")  # forêts pluviales tempérées
    poser(RESINEUX & (EXTREME | TUNDRA), "snowy_taiga")
    # forêts de feuillus et mixtes
    poser((FEUILLUS_PERS | FEUILLUS | MIXTE) & TROP_HUMIDE, "jungle")
    poser((FEUILLUS_PERS | FEUILLUS | MIXTE) & (TROP_SEC | STEPPE_CH), "sparse_jungle")
    poser((FEUILLUS_PERS | FEUILLUS | MIXTE) & (TEMPERE | MEDIT | OCEAN_FROID | dans(17, 18, 21, 25)), "forest")
    poser((FEUILLUS | MIXTE) & dans(22, 26), "forest")
    poser(FEUILLUS & SUBARC, "birch_forest")
    poser(MIXTE & SUBARC, "taiga")
    poser(FEUILLUS_PERS & (ARIDE), "savanna")                              # eucalyptus clairs d'Australie, etc.
    # fourrés, savanes, prairies
    poser((FOURRES | FOURRES_OUV) & (DESERT | (STEPPE_CH & (lc == 7))), "desert")
    poser((FOURRES | FOURRES_OUV) & (TROP | (STEPPE_CH & (lc == 6))), "savanna")
    poser((FOURRES | FOURRES_OUV) & (STEPPE_FR | MEDIT | TEMPERE | CONT), "plains")
    poser((FOURRES | FOURRES_OUV) & (SUBARC | OCEAN_FROID), "taiga")
    poser((FOURRES | FOURRES_OUV) & (EXTREME | TUNDRA), "snowy_plains")
    poser(SAV_BOISEE & (TROP | STEPPE_CH), "savanna")
    poser(SAV_BOISEE & (TEMPERE | MEDIT | CONT | STEPPE_FR), "forest")
    poser(SAV_BOISEE & (SUBARC | OCEAN_FROID), "taiga")
    poser(SAV_BOISEE & (EXTREME | TUNDRA), "snowy_taiga")
    poser(SAVANE & (TROP | STEPPE_CH | DESERT), "savanna")
    poser(SAVANE & ~(TROP | STEPPE_CH | DESERT), "plains")
    poser(PRAIRIE & (TROP | STEPPE_CH), "savanna")
    poser(PRAIRIE & DESERT, "desert")
    poser(PRAIRIE & (STEPPE_FR | MEDIT | TEMPERE | OCEAN_FROID | CONT | SUBARC), "plains")
    poser(PRAIRIE & (EXTREME | TUNDRA), "snowy_plains")
    # cultures : plaines (tournesols dans la ceinture de la mer Noire et de la Volga)
    poser(CULTURES & (TROP | STEPPE_CH), "savanna")
    poser(CULTURES & DESERT, "desert")
    poser(CULTURES & ~(TROP | STEPPE_CH | DESERT), "plains")
    poser(CULTURES & (CONT | STEPPE_FR) & (LAT > 44) & (LAT < 55) & (LON > 22) & (LON < 60), "sunflower_plains")
    # zones humides
    poser(HUMIDE & (TROP | TEMPERE | MEDIT | dans(21, 25, 17)), "swamp")
    poser(HUMIDE & (dans(22, 26, 18) | SUBARC), "taiga")
    poser(HUMIDE & (EXTREME | TUNDRA), "snowy_plains")
    # sol nu, neige et glace
    poser(NU & (CHAUD | ARIDE), "desert")
    poser(NU & ~(CHAUD | ARIDE), "snowy_plains")
    poser(NEIGE, "snowy_plains")

# mangroves : zones humides tropicales en bord de mer
cote = (np.array(Image.open(f"{CARTE}/cotes.png")).astype(np.int16) - 128) / 4.0   # minutes d'arc, + vers l'intérieur
if a.couverture:
    poser(HUMIDE & (TROP | STEPPE_CH | dans(11, 14)) & (cote < 6) & (np.abs(LAT) < 30), "mangrove_swamp")
    poser(FEUILLUS_PERS & dans(11, 14) & terroir_est("chine", "asie_sud_est", "japon_coree") & (alt < 1500)
          & ((LAT * 7 + LON * 3).astype(int) % 5 == 0), "bamboo_jungle")
    poser((FEUILLUS | MIXTE) & terroir_est("japon_coree") & (alt > 300) & (alt < 1500), "cherry_grove")
    poser(FEUILLUS & TEMPERE & (np.abs(LAT) > 45) & (alt < 800) & terroir_est("atlantique", "continentale"), "forest")

# 3) relief : montagnes, plateaux, collines (d'après l'altitude et la pente réelles)
haut = alt >= 1500
froid_haut = TUNDRA | GLACE | (NEIGE if a.couverture else np.zeros_like(terre))
# hautes montagnes froides (climat de toundra ou glaciers d'altitude)
poser(froid_haut & haut & (pente < 25) & ~(NEIGE | GLACE), "meadow")             # alpages, plateau tibétain
poser(froid_haut & haut & (pente >= 25), "snowy_slopes")
poser(froid_haut & haut & (pente >= 60), "jagged_peaks")
poser((GLACE | NEIGE) & haut & (pente >= 40), "frozen_peaks")
# montagnes sèches et rocheuses (Atlas, Hoggar, Zagros, Andes sèches)
if a.couverture:
    poser(NU & ARIDE & (alt >= 1200) & (pente >= 45), "stony_peaks")
    poser(NU & (TUNDRA) & (alt >= 2500) & (pente >= 25), "stony_peaks")
# badlands : sols nus ou fourrés ouverts en climat sec, sur relief disséqué (plateau du Colorado, Australie)
ravine = (pente >= 18) & (pente < 60)
if a.couverture:
    poser((NU | FOURRES_OUV) & (DESERT | STEPPE_FR) & ravine & (alt >= 600)
          & terroir_est("ouest_mexique", "australie", "afrique_australe", "sahara_sahel", "moyen_orient"), "badlands")
    poser((SAV_BOISEE | SAVANE) & (DESERT | STEPPE_FR) & ravine & (alt >= 600)
          & terroir_est("ouest_mexique", "australie"), "wooded_badlands")
    poser((NU | FOURRES_OUV) & DESERT & (pente >= 45) & terroir_est("ouest_mexique", "australie"), "eroded_badlands")
# forêts de montagne : épicéas au-dessus de 1 200 m en climat tempéré ou continental (Alpes, Carpates)
foret_monts = (FORET if a.couverture else (TEMPERE | CONT | MEDIT)) & (alt >= 1200) & (pente >= 25) & (TEMPERE | CONT | MEDIT | OCEAN_FROID)
poser(foret_monts & np.isin(bio, [IDX["forest"], IDX["birch_forest"], IDX["dark_forest"], IDX["flower_forest"]]), "taiga")
# limite des arbres : bosquets enneigés juste sous la toundra d'altitude
poser(np.isin(bio, [IDX["taiga"], IDX["snowy_taiga"]]) & (alt >= 1800) & (pente >= 25) & (SUBARC | EXTREME | OCEAN_FROID), "grove")
# collines venteuses : landes et prairies sur pentes fortes (Écosse, Pyrénées, Massif central)
poser(np.isin(bio, [IDX["plains"]]) & (pente >= 35) & (alt >= 300) & (alt < 2000) & (TEMPERE | OCEAN_FROID | CONT | MEDIT), "windswept_hills")
poser(np.isin(bio, [IDX["plains"]]) & (pente < 35) & (alt >= 1500) & (TEMPERE | CONT | MEDIT), "meadow")
# savanes d'altitude et escarpées
poser(np.isin(bio, [IDX["savanna"]]) & (alt >= 1000) & (pente < 30), "savanna_plateau")
poser(np.isin(bio, [IDX["savanna"]]) & (pente >= 45), "windswept_savanna")
# montagnes sèches sans couverture : rochers nus
if not a.couverture:
    poser(ARIDE & (alt >= 1800) & (pente >= 45), "stony_peaks")

# ------------------------------------------------------------------ sorties
bio[~terre] = 0
Image.fromarray(bio).save(f"{CARTE}/biomes.png", optimize=True)
json.dump(BIOMES, open(f"{CARTE}/biomes.json", "w", encoding="utf-8"), indent=1)

# limite des neiges : température minimale de chaque copie terroir/biome pour ne pas avoir de neige
# là où il n'y en a pas en vrai (Minecraft : neige si temp - (y - 80) x 0,00125 < 0,15)
def y_depuis_alt(m):
    m = np.maximum(m, 1)
    return np.where(m <= 500, 64 + m / 500 * 16,
                    np.where(m <= 2000, 80 + (m - 500) / 1500 * 60, 140 + np.minimum((m - 2000) / 6800, 1) * 160))

NEIGEUX = {"snowy_taiga", "snowy_plains", "grove", "snowy_slopes", "frozen_peaks", "jagged_peaks"}
y = y_depuis_alt(alt)
neige_reelle = TUNDRA | GLACE | (NEIGE if a.couverture else np.zeros_like(terre))
utilisation = {}
temp_min = {}
for ti, cle in terroirs.items():
    dans_t = ter == ti
    present = np.bincount(bio[dans_t].ravel(), minlength=len(BIOMES) + 1)
    for bi, n in enumerate(present):
        if bi == 0 or n == 0:
            continue
        b = BIOMES[bi - 1]
        utilisation.setdefault(cle, {})[b] = int(n)
        if b in NEIGEUX:
            continue
        m = dans_t & (bio == bi) & ~neige_reelle
        if m.any():
            y99 = float(np.percentile(y[m], 99.5))
            temp_min[f"{cle}/{b}"] = round(0.15 + (y99 + 12 - 80) * 0.00125, 3)
json.dump({"utilisation": utilisation, "temperature_min": temp_min},
          open(f"{CARTE}/neige.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)

tot = np.bincount(bio[terre].ravel(), minlength=len(BIOMES) + 1)
print("répartition des terres :")
for i, b in enumerate(BIOMES):
    if tot[i + 1]:
        print(f"  {b:26s} {100 * tot[i + 1] / terre.sum():5.1f} %")

# ------------------------------------------------------------------ cartes de contrôle
COULEURS = {
    "plains": (141, 179, 96), "sunflower_plains": (181, 219, 136), "forest": (5, 102, 33), "birch_forest": (48, 116, 68),
    "flower_forest": (45, 142, 73), "dark_forest": (64, 81, 26), "taiga": (11, 102, 89), "old_growth_pine_taiga": (89, 102, 81),
    "old_growth_spruce_taiga": (69, 79, 62), "snowy_taiga": (49, 85, 74), "snowy_plains": (240, 240, 245), "grove": (190, 210, 200),
    "meadow": (150, 205, 120), "cherry_grove": (240, 170, 200), "windswept_hills": (96, 112, 96), "windswept_forest": (80, 112, 80),
    "snowy_slopes": (200, 210, 225), "frozen_peaks": (160, 180, 255), "jagged_peaks": (220, 220, 240), "stony_peaks": (130, 125, 120),
    "desert": (250, 148, 24), "badlands": (217, 69, 21), "wooded_badlands": (176, 151, 101), "eroded_badlands": (255, 109, 61),
    "savanna": (189, 178, 95), "savanna_plateau": (167, 157, 100), "windswept_savanna": (229, 218, 135),
    "jungle": (83, 123, 9), "sparse_jungle": (98, 139, 23), "bamboo_jungle": (118, 142, 20), "swamp": (7, 249, 178),
    "mangrove_swamp": (44, 204, 142),
}
if a.controle:
    os.makedirs(a.controle, exist_ok=True)
    pal = np.zeros((256, 3), np.uint8)
    pal[0] = (40, 70, 120)
    for b, c in COULEURS.items():
        pal[IDX[b]] = c
    rgb = pal[bio]
    rgb[lac] = (70, 110, 170)
    ZONES = {"monde": (-180, 180, -60, 85), "europe": (-12, 35, 35, 72), "alpes": (4, 17, 43, 48.5),
             "france": (-5.5, 9.5, 41, 51.5), "scandinavie": (4, 32, 54, 71.5), "sahara": (-18, 35, 10, 36),
             "arizona": (-116, -108, 33, 38), "amazonie": (-80, -34, -20, 6), "himalaya": (70, 100, 25, 40)}
    for nom, (lo0, lo1, la0, la1) in ZONES.items():
        x0, x1 = int((lo0 + 180) * 20), int((lo1 + 180) * 20)
        y0, y1 = int((90 - la1) * 20), int((90 - la0) * 20)
        im = Image.fromarray(rgb[y0:y1, x0:x1])
        if nom == "monde":
            im = im.resize((im.width // 3, im.height // 3), Image.NEAREST)
        elif im.width < 1200:
            f = max(1, 1200 // im.width)
            im = im.resize((im.width * f, im.height * f), Image.NEAREST)
        im.save(f"{a.controle}/biomes_{nom}.png")
    # légende
    from PIL import ImageDraw
    leg = Image.new("RGB", (330, 22 * len(BIOMES) + 10), (255, 255, 255))
    d = ImageDraw.Draw(leg)
    for i, b in enumerate(BIOMES):
        d.rectangle([8, 6 + 22 * i, 26, 22 + 22 * i], fill=COULEURS[b], outline=(0, 0, 0))
        d.text((34, 8 + 22 * i), b, fill=(0, 0, 0))
    leg.save(f"{a.controle}/legende.png")
    print("cartes de contrôle :", a.controle)

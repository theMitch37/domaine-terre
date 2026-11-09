"""Données de faune embarquées dans le mod Terre (lancer après zones.py).

Sorties dans src/main/resources/domaine_terre/faune/ :
  zones.png     8 bits, grille 3' (7200 x 3600) :
                  terre  : 1..14 = grand biome RESOLVE de l'écorégion, 16+k = écorégion précise n° k (precises.json),
                           0 = sans écorégion (roche et glace) ;
                  mer    : 128 + terroir de la terre la plus proche (0 au-delà de 8°, haute mer sans terroir).
  especes.json  {"precises": [{nom, biome}], "especes": [...]} ; une entrée par ligne gardée de especes.csv :
                  entite, cat (sauvage, ferme, poisson, insecte, fantastique, monstre), terroirs (index), biomes,
                  precis {terroir: [k]}, eau, cote, mer {temperatures, bandes} ou null, min, max, poids, nuit, etage.
Untamed Wilds n'est pas dans la table : il fait naître ses animaux par ses propres features (par terroir).
"""
import csv
import json
import os
import re

import numpy as np
from PIL import Image
from scipy import ndimage

ICI = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(ICI, "../../src/main/resources/domaine_terre")
OUT = os.path.join(RES, "faune")
os.makedirs(OUT, exist_ok=True)

terroirs = json.load(open(os.path.join(RES, "carte/terroirs.json"), encoding="utf-8"))
INDEX = {t["cle"]: t["index"] for t in terroirs}
VRAIS = list(INDEX)
MILIEUX = json.load(open(os.path.join(ICI, "milieux.json"), encoding="utf-8"))
PRECIS = json.load(open(os.path.join(ICI, "ecoregions_precises.json"), encoding="utf-8"))
table = {int(k): v for k, v in json.load(open(os.path.join(ICI, "ecoregions.json"), encoding="utf-8")).items()}
par_nom = {v["nom"]: k for k, v in table.items()}

# ---------------------------------------------------------------- carte des zones
eco = np.array(Image.open(os.path.join(ICI, "ecoregions_3min.png"))).astype(np.int32)
ter_brut = np.array(Image.open(os.path.join(RES, "carte/terroirs.png")))
ter = ter_brut & 0x7F
noms_precis = sorted({n for d in PRECIS.values() for l in d.values() for n in l})
precises = [{"nom": n, "biome": table[par_nom[n]]["biome"]} for n in noms_precis]
assert len(precises) < 112
lut = np.zeros(eco.max() + 1, np.uint8)
for k, v in table.items():
    lut[k] = v["biome"]
for i, n in enumerate(noms_precis):
    lut[par_nom[n]] = 16 + i
zones = lut[eco]
terre = ter > 0
zones[~terre] = 0
# mer : terroir de la terre la plus proche (distance en pixels ; 8° = 160 pixels)
dist, (iy, ix) = ndimage.distance_transform_edt(~terre, return_indices=True)
proche = ter[iy, ix]
proche[dist > 160] = 0
zones = np.where(terre, zones, 128 + proche).astype(np.uint8)
Image.fromarray(zones).save(os.path.join(OUT, "zones.png"), optimize=True)
print("zones.png :", len(precises), "écorégions précises")

# ---------------------------------------------------------------- espèces
TEMPS = ["chaude", "tiede", "temperee", "froide", "gelee"]
BANDES = ["cote", "plateau", "large", "abysse"]
MERS = {
    "mers_tropicales": (["chaude", "tiede"], BANDES), "mers_chaudes_tempérées": (["chaude", "tiede", "temperee"], BANDES),
    "mers_froides": (["froide", "gelee"], BANDES), "toutes_les_mers_froides": (["froide", "gelee"], BANDES),
    "toutes_les_mers": (TEMPS, BANDES), "tous_les_océans": (TEMPS, ["plateau", "large", "abysse"]),
    "mers_profondes": (TEMPS, ["large", "abysse"]), "tous_les_océans_profonds": (TEMPS, ["large", "abysse"]),
    "abysses": (TEMPS, ["abysse"]),
}
EAU = {"eau_douce", "marais", "près de l'eau"}
COTE = {"cote", "plage", "plage tropicale"}
ETAGES = {"couches hautes": "couches_hautes", "profondeurs": "profondeurs", "abîmes": "abimes",
          "grottes inondées": "grottes_inondees"}
POIDS = {"ferme": 10, "sauvage": 8, "poisson": 10, "insecte": 4, "fantastique": 1, "monstre": 6}


def jetons(milieu):
    m = milieu.strip()
    if m in MILIEUX:
        return [m]
    m = re.sub(r"^ciel\s*", "", m)
    return [x.strip() for x in re.split(r"[,()]", m) if x.strip()]


def aire(ts):
    if ts.startswith("partout_sauf:"):
        return [t for t in VRAIS if t not in ts[13:].split(",")]
    if ts.startswith("partout"):
        return list(VRAIS)
    return [t for t in ts.split(",") if t in INDEX]


def groupe(g):
    m = re.fullmatch(r"(\d+)(?:-(\d+))?", g.strip())
    if not m:
        return 1, 1
    a = int(m[1])
    return a, int(m[2] or a)


# abondance réelle (outils/faune/abondance.py) : très commun, commun, peu commun, rare
ABONDANCE = {"TC": 16, "C": 8, "PC": 3, "R": 1}
UW_TERRE = {"bear", "big_cat", "hyena", "large_snake", "monitor", "boar", "bison", "camel", "hippo", "rhino",
            "wildebeest", "aardvark", "newt", "snake", "softshell_turtle", "tortoise", "tarantula", "opossum", "butterfly"}

# Conditions en plus de la règle générale (09/11/2026, décisions de Maxime), lues par FauneTerre.filtrer :
#   biome_jeu      : seulement dans ce biome du jeu (grottes luxuriantes) ;
#   altitude_min   : seulement au-dessus de cette altitude réelle, en mètres ;
#   tirage         : garde l'espèce une fois sur N tentatives (rareté sans toucher aux poids des autres) ;
#   monstre_surface: monstre de la table autorisé en surface (sinon : sorcières des marais seulement).
CONDITIONS = {
    "alexsmobs:guster": {"tirage": 40, "monstre_surface": True},      # grands ergs, rare ; sable et pluie : règle du mod
    "alexsmobs:flutter": {"biome_jeu": "lush_caves"},
    "alexsmobs:sunbird": {"altitude_min": 2500, "tirage": 10},
}

rows = list(csv.DictReader(open(os.path.join(ICI, "especes.csv"), encoding="utf-8"), delimiter=";"))
especes, vus = [], set()
for r in rows:
    st = r["statut"]
    if st not in ("garder", "souterrain"):
        continue
    ent = r["id"].split("/")[0]
    # Untamed Wilds (07/11/2026) : ses bêtes de terre naissent par cette table (abondance cohérente avec le reste) ;
    # ses bêtes de mer et ses poissons d'eau douce gardent son propre système (le jeu ne fait naître à la génération
    # que la catégorie des animaux de terre)
    if ent.startswith("untamedwilds:") and ent.split(":")[1] not in UW_TERRE:
        continue
    if ent in ("guardvillagers:guard", "alexsmobs:mimicube"):
        continue
    toks = [j for m in r["milieu"].split(",") for j in jetons(m)] if r["milieu"] not in MILIEUX else [r["milieu"]]
    biomes = sorted({b for t in toks if t in MILIEUX for b in MILIEUX[t]})
    eau = any(t in EAU or t.startswith("eau_douce") or t == "eau" for t in toks)
    cote = any(t in COTE for t in toks)
    mer = None
    zone = r["terroirs"].strip()
    if zone in MERS:
        mer = {"temperatures": MERS[zone][0], "bandes": MERS[zone][1]}
    elif zone.startswith("toutes_les_côtes"):
        cote = True
    ts = aire(r["terroirs"])
    if not ts and zone in MERS:
        # espèces de mer sans terroir (« mers_tropicales », « toutes_les_mers »…) : toutes les mers de leur température.
        # Avant (08/11/2026), liste de terroirs vide -> jamais nées : dauphins, calmars, poissons tropicaux, thons…
        ts = list(VRAIS)
    # récifs (08/11/2026 : vers de Bobbit partout en mer) : eaux chaudes et tièdes, près des côtes et sur le plateau
    if "récifs" in toks and ts and (mer is None or zone in MERS):
        mer = {"temperatures": ["chaude", "tiede"], "bandes": ["cote", "plateau"]}
    if mer is None and ts and ("abysses" in toks or "mer profonde" in toks):
        mer = {"temperatures": TEMPS, "bandes": ["large", "abysse"]}
    if "mer" in toks or "large" in toks:
        if mer is None and ts:          # poisson de mer d'un terroir (morue de l'Atlantique…) : mers bordant ce terroir
            mer = {"temperatures": TEMPS, "bandes": BANDES}
    if st == "garder" and "souterrain" in toks and not biomes:
        biomes = list(range(1, 15))     # chauve-souris : partout dans son aire, le jeu la met dans les grottes
    if not ts and zone.startswith(("toutes_les_côtes", "partout")):
        ts = list(VRAIS)
    etage = None
    if st == "souterrain":
        n = r["note"]
        etage = "fosses" if "fosses" in n else next((v for k, v in ETAGES.items() if k in n), "couches_hautes")
        if "grottes inondées seulement" in n:
            continue                    # calmar luisant : laissé au jeu de base
    precis = {str(INDEX[t]): [noms_precis.index(n) for n in l] for t, l in PRECIS.get(r["id"], {}).items() if t in INDEX}
    mn, mx = groupe(r["groupe"])
    especes.append({
        "id": r["id"], "entite": ent, "cat": r["categorie"], "terroirs": [INDEX[t] for t in ts], "biomes": biomes,
        "precis": precis, "eau": eau, "cote": cote, "mer": mer, "min": mn, "max": mx,
        "poids": ABONDANCE.get(r.get("abondance", ""), 1 if "RARE" in r["note"] else POIDS.get(r["categorie"], 6)),
        "nuit": "nuit" in r["milieu"], "etage": etage, **CONDITIONS.get(r["id"], {})})
json.dump({"precises": precises, "especes": especes}, open(os.path.join(OUT, "especes.json"), "w", encoding="utf-8"),
          ensure_ascii=False, separators=(",", ":"))
print("especes.json :", len(especes), "entrées")

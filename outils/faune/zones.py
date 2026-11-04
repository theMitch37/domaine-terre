"""Croise les espèces (outils/faune/especes.csv) avec les écorégions RESOLVE 2017 et les terroirs du mod.

Règle (décision de Maxime, 04/11/2026 : « des endroits logiques, pas tout le continent ») :
un animal terrestre peut apparaître sur un pixel 3' si
  - le terroir du pixel fait partie de ses terroirs, ET
  - le grand biome RESOLVE de l'écorégion du pixel correspond à l'un de ses milieux (milieux.json).
Les milieux d'eau (eau_douce, marais) et de côte (cote, plage) ne regardent que le terroir : le jeu les place sur
les blocs d'eau douce ou de rivage. Exemple : le crocodile du Nil ne sort que dans l'eau du Nil au Sahara.

Usage : python3 outils/faune/zones.py
Sorties : outils/faune/milieux.json (milieu -> grands biomes RESOLVE), outils/faune/zones_bilan.csv
"""
import csv
import json
import os
import re

import numpy as np
from PIL import Image

ICI = os.path.dirname(os.path.abspath(__file__))
CARTE = os.path.join(ICI, "../../src/main/resources/domaine_terre/carte")

# grands biomes RESOLVE : 1 forêts tropicales humides, 2 forêts tropicales sèches, 3 forêts tropicales de conifères,
# 4 forêts tempérées feuillues et mixtes, 5 forêts tempérées de conifères, 6 forêt boréale / taïga,
# 7 savanes et prairies tropicales, 8 prairies et steppes tempérées, 9 prairies inondables, 10 prairies de montagne,
# 11 toundra, 12 forêts et maquis méditerranéens, 13 déserts et broussailles xériques, 14 mangroves
MILIEUX = {
    "foret_tropicale": [1, 3, 14], "foret": [1, 2, 3, 4, 5, 6, 12], "prairie": [4, 7, 8, 9, 10, 12],
    "culture": [1, 2, 4, 5, 7, 8, 9, 12], "steppe": [8, 10, 13], "montagne": [3, 4, 5, 6, 10, 12],
    "desert": [13], "toundra": [6, 11], "banquise": [11], "savane": [2, 7, 9], "mediterraneen": [12],
    "foret (humide)": [1, 4, 5], "foret (nuit)": [1, 2, 3, 4, 5, 6, 12], "foret (bambou)": [4, 5, 10],
    "foret (montagne)": [3, 4, 5, 10], "foret_tropicale (nuit)": [1, 3], "prairie (pluie)": [4, 7, 8, 12],
    "prairie, foret (nuit)": [1, 2, 4, 5, 7, 8, 12], "desert (côtier)": [13], "culture (rizières)": [1, 2, 9],
    "marais (lagunes salées)": [9, 14], "toundra,foret": [6, 11], "mangrove": [14],
    "partout": list(range(1, 15)), "sol": list(range(1, 15)),
}
# Espèces emblématiques à aire réduite : dans les terroirs nommés, seulement ces écorégions (noms RESOLVE exacts).
# Les autres terroirs de l'espèce gardent la règle générale. Vaut aussi pour l'eau (ornithorynque).
PRECIS = {
    "untamedwilds:big_cat/tiger": {"siberie": ["Ussuri broadleaf and mixed forests", "Manchurian mixed forests",
                                               "Okhotsk-Manchurian taiga", "Amur meadow steppe"]},
    "alexsmobs:tiger": {"chine": ["Manchurian mixed forests", "Changbai Mountains mixed forests"]},
    "minecraft:panda": {"chine": ["Qionglai-Minshan conifer forests", "Qin Ling Mountains deciduous forests",
                                  "Hengduan Mountains subalpine conifer forests"]},
    "untamedwilds:bear/panda": {"chine": ["Qionglai-Minshan conifer forests", "Qin Ling Mountains deciduous forests",
                                          "Hengduan Mountains subalpine conifer forests"]},
    "alexsmobs:komodo_dragon": {"asie_sud_est": ["Lesser Sundas deciduous forests"]},
    "naturalist:lion": {"inde": ["Khathiar-Gir dry deciduous forests"]},
    "alexsmobs:tasmanian_devil": {"australie": ["Tasmanian Central Highland forests", "Tasmanian temperate forests",
                                                "Tasmanian temperate rain forests"]},
    "naturalist:canary": {"mediterranee": ["Canary Islands dry woodlands and forests", "Madeira evergreen forests",
                                           "Azores temperate mixed forests"],
                          "maghreb": ["Canary Islands dry woodlands and forests"]},
    "alexsmobs:gelada_monkey": {"afrique_est": ["Ethiopian montane grasslands and woodlands", "Ethiopian montane moorlands"]},
    "untamedwilds:rhino/javan": {"asie_sud_est": ["Western Java rain forests", "Western Java montane rain forests"]},
    "untamedwilds:rhino/sumatran": {"asie_sud_est": ["Sumatran lowland rain forests", "Sumatran montane rain forests",
                                                     "Borneo lowland rain forests"]},
    "untamedwilds:rhino/indian": {"inde": ["Terai-Duar savanna and grasslands", "Brahmaputra Valley semi-evergreen forests"]},
    "untamedwilds:bison/wisent": {"continentale": ["Central European mixed forests", "Carpathian montane forests"]},
    "alexsmobs:platypus": {"australie": ["Eastern Australian temperate forests", "Southeast Australia temperate forests",
                                         "Queensland tropical rain forests", "Tasmanian temperate forests",
                                         "Tasmanian temperate rain forests", "Tasmanian Central Highland forests"]},
}
EAU = {"eau_douce", "marais", "près de l'eau"}
COTE = {"cote", "plage", "plage tropicale"}


def jetons(milieu):
    """'ciel (savane, montagne)' -> ['savane', 'montagne'] ; 'cote (plage)' -> ['cote', 'plage']."""
    m = milieu.strip()
    if m in MILIEUX:
        return [m]
    m = re.sub(r"^ciel\s*", "", m)
    out = []
    for x in re.split(r"[,()]", m):
        x = x.strip()
        if x in ("mer", "large", "abysses", "mer profonde", "souterrain", "récifs", "fond froid", "eau", "—", ""):
            continue
        out.append(x)
    return out


terroirs = json.load(open(os.path.join(CARTE, "terroirs.json"), encoding="utf-8"))
INDEX = {t["cle"]: t["index"] for t in terroirs}
VRAIS = list(INDEX)
ter = np.array(Image.open(os.path.join(CARTE, "terroirs.png"))) & 0x7F
eco = np.array(Image.open(os.path.join(ICI, "ecoregions_3min.png"))).astype(np.int32)
table = {int(k): v for k, v in json.load(open(os.path.join(ICI, "ecoregions.json"), encoding="utf-8")).items()}
lut = np.zeros(eco.max() + 1, np.uint8)
for k, v in table.items():
    lut[k] = v["biome"]
grand = lut[eco]                                   # grand biome RESOLVE par pixel (0 = mer / glace)

# pondération par la surface réelle d'un pixel 3' (cos de la latitude)
lat = 90.0 - (np.arange(ter.shape[0]) + 0.5) * 0.05
poids = np.cos(np.radians(lat))[:, None] * np.ones((1, ter.shape[1]))


def aire_terroirs(ts):
    if ts.startswith("partout_sauf:"):
        return [t for t in VRAIS if t not in ts[13:].split(",")]
    if ts.startswith("partout"):
        return list(VRAIS)
    return [t for t in ts.split(",") if t in INDEX]


rows = list(csv.DictReader(open(os.path.join(ICI, "especes.csv"), encoding="utf-8"), delimiter=";"))
inconnus, bilan = set(), []
for r in rows:
    if r["statut"] not in ("garder", "a_confirmer"):
        continue
    ts = aire_terroirs(r["terroirs"])
    if not ts:
        continue                                   # espèces marines (zones à part)
    toks = [j for m in r["milieu"].split(",") for j in jetons(m)] if r["milieu"] not in MILIEUX else [r["milieu"]]
    eau = any(t in EAU or t.startswith("eau_douce") for t in toks)
    cote = any(t in COTE for t in toks)
    biomes = set()
    for t in toks:
        if t in EAU or t in COTE or t.startswith("eau_douce"):
            continue
        if t in MILIEUX:
            biomes |= set(MILIEUX[t])
        else:
            inconnus.add(t)
    masque_t = np.isin(ter, [INDEX[t] for t in ts])
    for t_, noms_ in PRECIS.get(r["id"], {}).items():
        if t_ in INDEX:
            ok = [k for k, v in table.items() if v["nom"] in noms_]
            masque_t &= ~((ter == INDEX[t_]) & ~np.isin(eco, ok))
    total = float(poids[masque_t].sum())
    if biomes:
        m = masque_t & np.isin(grand, list(biomes))
        part = float(poids[m].sum()) / total if total else 0.0
        ids, n = np.unique(eco[m], return_counts=True)
        top = [table[int(i)]["nom"] for i, _ in sorted(zip(ids, n), key=lambda x: -x[1])[:3] if int(i) in table]
    else:
        part, top = (None, [])
    bilan.append({"id": r["id"], "nom": r["nom"], "milieu": r["milieu"], "biomes": " ".join(map(str, sorted(biomes))),
                  "eau": "oui" if eau else "", "cote": "oui" if cote else "",
                  "part_terroirs": "" if part is None else f"{part:.0%}", "ecoregions_principales": " / ".join(top)})

json.dump(MILIEUX, open(os.path.join(ICI, "milieux.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump(PRECIS, open(os.path.join(ICI, "ecoregions_precises.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
with open(os.path.join(ICI, "zones_bilan.csv"), "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(bilan[0]), delimiter=";")
    w.writeheader()
    w.writerows(bilan)
print(len(bilan), "espèces terrestres ; milieux inconnus :", sorted(inconnus))

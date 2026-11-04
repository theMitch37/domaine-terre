"""Réduit les écorégions terrestres RESOLVE Ecoregions 2017 à la grille du mod (3', 7200 x 3600).

Source : Dinerstein, E. et al. An Ecoregion-Based Approach to Protecting Half the Terrestrial Realm.
BioScience 67(6), 534-545 (2017). Licence CC BY 4.0. Fichier Ecoregions2017.zip (storage.googleapis.com/teow2016).

Usage : python outils/faune/ecoregions.py <Ecoregions2017.shp> <dossier de sortie>
Sorties :
  ecoregions_3min.png   PNG 16 bits, 0 = mer / hors écorégion, sinon ECO_ID
  ecoregions.json       ECO_ID -> {nom, biome (1..14), nom du biome, royaume, pixels}
Chaque pixel 3' prend l'écorégion qui couvre son centre (all_touched=False) ; les îles plus petites qu'un pixel
sont rattrapées par un second passage all_touched=True sur les pixels restés vides.
"""
import json
import os
import sys

import fiona
import numpy as np
from PIL import Image
from rasterio import features
from rasterio.transform import from_origin

W, H = 7200, 3600
SHP, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
transform = from_origin(-180.0, 90.0, 0.05, 0.05)

table, formes = {}, []
with fiona.open(SHP) as src:
    for f in src:
        p = f["properties"]
        eid = int(p["ECO_ID"])
        if eid <= 0:                      # « Rock and Ice » et polygones sans écorégion
            continue
        table[eid] = {"nom": p["ECO_NAME"], "biome": int(p["BIOME_NUM"] or 0), "biome_nom": p["BIOME_NAME"],
                      "royaume": p["REALM"]}
        formes.append((f["geometry"], eid))
print(len(table), "écorégions,", len(formes), "polygones")

carte = features.rasterize(formes, out_shape=(H, W), transform=transform, fill=0, dtype="uint16", all_touched=False)
petits = features.rasterize(formes, out_shape=(H, W), transform=transform, fill=0, dtype="uint16", all_touched=True)
carte = np.where(carte == 0, petits, carte).astype(np.uint16)

ids, n = np.unique(carte, return_counts=True)
for i, c in zip(ids, n):
    if int(i) in table:
        table[int(i)]["pixels"] = int(c)
Image.fromarray(carte, mode="I;16").save(os.path.join(OUT, "ecoregions_3min.png"))
json.dump({str(k): v for k, v in sorted(table.items())}, open(os.path.join(OUT, "ecoregions.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("pixels terrestres :", int((carte > 0).sum()))

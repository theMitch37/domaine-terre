"""Structures vanilla de Domaine Village 0.1 (13/11/2026) : listes des sites fixes et fichiers de données.

Placements validés par Maxime le 12/11 (doc domaine-village-idees) :
- sites fixes (une liste par structure, au plus un site par case de 512 blocs) : pyramides, temples de la jungle,
  igloos, manoirs, temples de la mer, ruines sous-marines autour des temples, épaves (cimetières de navires), ruines
  de piste, forteresses de l'End (une par continent) ;
- au hasard, mais à leur façon : avant-postes de pillards (loin des villages), portails en ruine (seulement sous
  terre), cités antiques (très profond).

Écrit, dans village/src/main/resources :
- domaine_terre_village/<liste>.csv (x;z;nom, blocs à l'échelle 1:250) ;
- data/minecraft/worldgen/structure_set/*.json (placement « fixe » de l'addon) ;
- data/minecraft/worldgen/structure/*.json (biomes permissifs pour les sites fixes : c'est le site qui décide ;
  portails sous terre ; cités antiques à 40 blocs du fond du monde) ;
- data/domaine_terre_village/tags/worldgen/biome/sites/*.json.

Usage : python3 outils/structures_village.py <dossier data vanilla 1.20.1 (misode/mcmeta, branche 1.20.1-data)>
"""
import json, math, os, sys

VANILLA = sys.argv[1]                         # .../data/minecraft
RACINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
RES = os.path.join(RACINE, "village/src/main/resources")
BIOMES = os.path.join(RACINE, "src/main/resources/data/domaine_terre/worldgen/biome")
BPD = 445.28
CASE = 512

# ------------------------------------------------------------------ sites (lat, lon) ; décalés en mer ou dans le
# désert quand le vrai site tombe sur un fleuve ou une côte
SITES = {
    "pyramides": [("Gizeh", 29.979, 31.10), ("Meroe", 16.94, 33.75)],          # Saqqarah, Dahchour : même case que Gizeh
    "temples_jungle": [("Tikal", 17.222, -89.623), ("Chichen Itza", 20.684, -88.568), ("Palenque", 17.484, -92.046),
                       ("Calakmul", 18.105, -89.810), ("Copan", 14.840, -89.142), ("Angkor", 13.412, 103.867)],
    "igloos": [("Ilulissat", 69.45, -51.10), ("Qaanaaq", 77.70, -69.23), ("Tasiilaq", 65.85, -37.64),
               ("Iqaluit", 64.00, -68.52), ("Igloolik", 69.62, -81.80), ("Cambridge Bay", 69.36, -105.06),
               ("Rankin Inlet", 63.05, -92.09), ("Utqiagvik", 71.10, -156.50), ("Kotzebue", 67.10, -162.30)],
    "manoirs": [("Foret de Hoia-Baciu (Transylvanie)", 46.78, 23.48), ("Bran (Transylvanie)", 45.40, 25.30),
                ("Foret-Noire", 48.30, 8.15)],
    "temples_mer": [("Atlantide (Acores)", 37.40, -27.50), ("Yonaguni", 24.40, 122.90), ("Dwarka", 22.10, 68.60),
                    ("Pavlopetri", 36.40, 22.90), ("Route de Bimini", 25.70, -79.40)],
    "epaves": [("Cap Hatteras", 35.10, -75.20), ("Bermudes", 32.10, -64.90), ("Florida Keys", 24.40, -81.20),
               ("Silver Bank (route des galions)", 20.30, -69.80), ("Cap Horn", -56.10, -67.30),
               ("Cap de Bonne-Esperance", -34.45, 18.30)],
    "ruines_piste": [("Pompei", 40.749, 14.485), ("Troie", 39.957, 26.239), ("Petra", 30.329, 35.444),
                     ("Mohenjo-daro", 27.324, 68.136), ("Carthage", 36.853, 10.323)],
}
# ruines sous-marines : à ~70 blocs des temples de la mer (vieille cité submergée autour du temple)
SITES["ruines_mer"] = [(n + " (ruines)", la - 0.16, lo + 0.16) for n, la, lo in SITES["temples_mer"]]
# forteresses de l'End : une par continent, en profondeur (positions des anneaux remplacées par l'addon)
FORTERESSES = [("Europe : Stonehenge", 51.179, -1.826), ("Afrique : Grand Zimbabwe", -20.27, 30.93),
               ("Asie : mont Kailash", 31.07, 81.31), ("Amerique du Nord : Chaco Canyon", 36.06, -107.96),
               ("Amerique du Sud : Tiwanaku", -16.55, -68.67), ("Oceanie : Uluru", -25.34, 131.04)]

# structure_set vanilla -> (liste, structures rallumées) ; None = placement vanilla gardé (au hasard)
ENSEMBLES = {
    "desert_pyramids": "pyramides", "jungle_temples": "temples_jungle", "igloos": "igloos",
    "woodland_mansions": "manoirs", "ocean_monuments": "temples_mer", "ocean_ruins": "ruines_mer",
    "shipwrecks": "epaves", "trail_ruins": "ruines_piste",
}
# structure -> étiquette vanilla (pour garder le comportement hors monde Terre)
STRUCTURES_SITES = {
    "desert_pyramid": "terre", "jungle_pyramid": "terre", "igloo": "terre", "mansion": "terre",
    "trail_ruins": "terre", "monument": "mer", "ocean_ruin_cold": "mer_froide", "ocean_ruin_warm": "mer_chaude",
    "shipwreck": "mer", "shipwreck_beached": "terre",
}


def ecrire(chemin, obj):
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)
        f.write("\n")


def liste_csv(nom, sites):
    cases, lignes = set(), []
    for n, la, lo in sites:
        x, z = round(lo * BPD), round(-la * BPD)
        c = (math.floor(x / CASE), math.floor(z / CASE))
        if c in cases:
            print(f"! {nom} : {n} tombe dans une case déjà prise, ignoré")
            continue
        cases.add(c)
        lignes.append(f"{x};{z};{n}")
    chemin = os.path.join(RES, "domaine_terre_village", nom + ".csv")
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as f:
        f.write("x;z;nom\n" + "\n".join(lignes) + "\n")
    print(f"{nom} : {len(lignes)} sites")


def biomes_terre():
    terre, mer = [], []
    for ter in sorted(os.listdir(BIOMES)):
        d = os.path.join(BIOMES, ter)
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            b = f"domaine_terre:{ter}/{f[:-5]}"
            if ter == "mer":
                mer.append(b)
            elif f[:-5] not in ("lac", "fleuve"):
                terre.append(b)
    return terre, mer


def main():
    for nom, sites in SITES.items():
        liste_csv(nom, sites)
    liste_csv("forteresses", FORTERESSES)

    for ens, liste in ENSEMBLES.items():
        v = json.load(open(os.path.join(VANILLA, "worldgen/structure_set", ens + ".json")))
        p = v["placement"]
        p["type"] = "domaine_terre_village:fixe"
        p.pop("spread_type", None)
        p["liste"] = liste
        ecrire(os.path.join(RES, "data/minecraft/worldgen/structure_set", ens + ".json"), v)

    terre, mer = biomes_terre()
    for s, genre in STRUCTURES_SITES.items():
        v = json.load(open(os.path.join(VANILLA, "worldgen/structure", s + ".json")))
        etiquette = v["biomes"]
        ecrire(os.path.join(RES, "data/domaine_terre_village/tags/worldgen/biome/sites", s + ".json"),
               {"replace": False, "values": [etiquette] + {
                   "terre": terre, "mer": mer,
                   "mer_chaude": [b for b in mer if "/chaude" in b or "/tiede" in b],
                   "mer_froide": [b for b in mer if not ("/chaude" in b or "/tiede" in b)]}[genre]})
        v["biomes"] = f"#domaine_terre_village:sites/{s}"
        ecrire(os.path.join(RES, "data/minecraft/worldgen/structure", s + ".json"), v)

    # portails en ruine : seulement sous terre, dans une poche d'air (comme une grotte)
    for s in ("ruined_portal", "ruined_portal_desert", "ruined_portal_jungle", "ruined_portal_swamp",
              "ruined_portal_mountain"):
        v = json.load(open(os.path.join(VANILLA, "worldgen/structure", s + ".json")))
        base = dict(v["setups"][0])
        base.update({"placement": "underground", "air_pocket_probability": 1.0, "weight": 1.0})
        v["setups"] = [base]
        ecrire(os.path.join(RES, "data/minecraft/worldgen/structure", s + ".json"), v)

    # cités antiques : à 40 blocs du fond du monde (y −472 dans un monde Terre, −24 en vanilla comme avant),
    # sous n'importe quel biome du mod (pas de deep dark au fond du monde Terre)
    v = json.load(open(os.path.join(VANILLA, "worldgen/structure", "ancient_city.json")))
    ecrire(os.path.join(RES, "data/domaine_terre_village/tags/worldgen/biome/sites/ancient_city.json"),
           {"replace": False, "values": [v["biomes"], "minecraft:lush_caves", "minecraft:dripstone_caves"] + terre})
    v["biomes"] = "#domaine_terre_village:sites/ancient_city"
    v["start_height"] = {"above_bottom": 40}
    ecrire(os.path.join(RES, "data/minecraft/worldgen/structure/ancient_city.json"), v)
    # tout le fond du monde convient : moins serrées que les 24 chunks vanilla (une tous les ~800 blocs)
    v = json.load(open(os.path.join(VANILLA, "worldgen/structure_set", "ancient_cities.json")))
    v["placement"].update({"spacing": 48, "separation": 16})
    ecrire(os.path.join(RES, "data/minecraft/worldgen/structure_set/ancient_cities.json"), v)
    print("fichiers de données écrits")


main()

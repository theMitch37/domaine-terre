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
    "pyramides": [("Gizeh", 29.979, 31.10), ("Meroe", 16.94, 33.90)],          # Saqqarah, Dahchour : même case que Gizeh
    "temples_jungle": [("Tikal", 17.222, -89.623), ("Chichen Itza", 20.684, -88.568), ("Palenque", 17.484, -92.046),
                       ("Calakmul", 18.105, -89.810), ("Copan", 14.840, -89.142), ("Angkor", 13.412, 103.867)],
    "igloos": [("Qaanaaq", 77.70, -69.23), ("Tasiilaq", 65.85, -37.64), ("Kangerlussuaq", 67.01, -50.69),
               ("Iqaluit", 64.00, -68.52), ("Cambridge Bay", 69.36, -105.06), ("Baker Lake", 64.32, -96.03),
               ("Rankin Inlet", 62.81, -92.09),
               ("Kotzebue", 67.10, -162.30), ("Anaktuvuk Pass", 68.14, -151.74)],
    "manoirs": [("Foret de Hoia-Baciu (Transylvanie)", 46.78, 23.48), ("Bran (Transylvanie)", 45.40, 25.30),
                ("Foret-Noire", 48.30, 8.15)],
    "temples_mer": [("Atlantide (Acores)", 37.40, -27.50), ("Yonaguni", 24.10, 122.60), ("Dwarka", 22.10, 68.60),
                    ("Pavlopetri", 36.15, 22.60), ("Route de Bimini", 25.55, -79.60)],
    "epaves": [("Cap Hatteras", 35.10, -75.20), ("Bermudes", 32.10, -64.90), ("Florida Keys", 24.40, -81.20),
               ("Silver Bank (route des galions)", 20.30, -69.80), ("Cap Horn", -56.10, -67.30),
               ("Cap de Bonne-Esperance", -34.45, 18.30)],
    "ruines_piste": [("Pompei", 40.749, 14.485), ("Troie", 39.957, 26.239), ("Petra", 30.329, 35.444),
                     ("Mohenjo-daro", 27.324, 68.00), ("Carthage", 36.85, 10.20)],
}
# ruines sous-marines : à ~70 blocs des temples de la mer (vieille cité submergée autour du temple)
SITES["ruines_mer"] = [("Atlantide (ruines)", 37.24, -27.34), ("Yonaguni (ruines)", 24.04, 122.42),
                       ("Dwarka (ruines)", 22.26, 68.76), ("Pavlopetri (ruines)", 36.05, 22.45),
                       ("Bimini (ruines)", 25.40, -79.70)]
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


# sites à terre : poussés au plus près sur un sol sec (même règle que les villages : hors mer, fleuve et lac),
# 13/11 : les igloos de Baker Lake et Rankin Inlet tombaient sur un lac
A_TERRE = {"pyramides", "temples_jungle", "igloos", "manoirs", "ruines_piste"}


def au_sec(x, z):
    """Centre de chunk sec le plus proche (la structure naît au centre de son chunk : c'est lui qui doit être sec,
    ainsi que ses abords à 6 blocs)."""
    import numpy as np
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from villages import valides
    c0x, c0z = (x // 16) * 16 + 8, (z // 16) * 16 + 8
    g = np.arange(-160, 161, 16, dtype=float)
    X, Z = np.meshgrid(c0x + g, c0z + g)
    ok = np.ones(X.shape, bool)
    for dx, dz in ((0, 0), (6, 6), (-6, 6), (6, -6), (-6, -6)):
        ok &= valides(X + dx, Z + dz)
    if not ok.any():
        print(f"! aucun sol sec à moins de 160 blocs de ({x}, {z})")
        return x, z
    d = np.where(ok, np.hypot(X - x, Z - z), np.inf)
    i = np.unravel_index(np.argmin(d), d.shape)
    return int(X[i]), int(Z[i])


def liste_csv(nom, sites):
    cases, lignes = set(), []
    for n, la, lo in sites:
        x, z = round(lo * BPD), round(-la * BPD)
        if nom in A_TERRE:
            x2, z2 = au_sec(x, z)
            if math.hypot(x2 - x, z2 - z) > 12:
                print(f"  {nom} : {n} poussé de {math.hypot(x2 - x, z2 - z):.0f} blocs sur un sol sec")
            x, z = x2, z2
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
    # quelques épaves au hasard le long des côtes (décision de Maxime, 13/11), seulement dans un monde Terre :
    # en mer près des côtes (bandes « côte » et « plateau »), ou échouées sur les plages
    plages = [b for b in terre if b.endswith("/beach") or b.endswith("/snowy_beach")] + [
        "minecraft:beach", "minecraft:snowy_beach"]
    cote = [b for b in mer if b.endswith("_cote") or b.endswith("_plateau")]
    for nom, src, bio in (("epave_cote", "shipwreck", cote), ("epave_echouee", "shipwreck_beached", plages)):
        v = json.load(open(os.path.join(VANILLA, "worldgen/structure", src + ".json")))
        v["biomes"] = f"#domaine_terre_village:{nom}"
        ecrire(os.path.join(RES, f"data/domaine_terre_village/tags/worldgen/biome/{nom}.json"),
               {"replace": False, "values": bio})
        ecrire(os.path.join(RES, f"data/domaine_terre_village/worldgen/structure/{nom}.json"), v)
    ecrire(os.path.join(RES, "data/domaine_terre_village/worldgen/structure_set/epaves_cotes.json"), {
        "placement": {"type": "domaine_terre_village:fixe", "salt": 165745297, "spacing": 64, "separation": 16,
                      "liste": "*hasard"},
        "structures": [{"structure": "domaine_terre_village:epave_cote", "weight": 3},
                       {"structure": "domaine_terre_village:epave_echouee", "weight": 1}]})
    print("fichiers de données écrits")


main()

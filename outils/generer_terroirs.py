"""Génère les biomes de terroir (copies des biomes vanilla), leurs tags, leurs noms et le type de monde.
Entrée : run/export_biomes (commande /domaine exporter) + src/main/resources/domaine_terre/carte/*.json
"""
import json, os, shutil

RES = "src/main/resources"
EXP = "run/export_biomes"
terroirs = json.load(open(f"{RES}/domaine_terre/carte/terroirs.json", encoding="utf-8"))
listes = json.load(open(f"{RES}/domaine_terre/carte/terroirs_biomes.json", encoding="utf-8"))
tags = json.load(open(f"{EXP}/tags.json", encoding="utf-8"))
noms = json.load(open(f"{EXP}/noms.json", encoding="utf-8"))

TROPIQUES = ["amazonie", "amerique_centrale", "asie_sud_est", "afrique_tropicale", "inde", "melanesie"]
VANILLA_REGIONAUX = {"minecraft:panda": ["chine"], "minecraft:llama": ["andes", "steppes_tibet"],
                     "minecraft:parrot": TROPIQUES, "minecraft:ocelot": TROPIQUES, "minecraft:polar_bear": ["arctique"]}
dossier_biomes = f"{RES}/data/domaine_terre/worldgen/biome"
shutil.rmtree(dossier_biomes, ignore_errors=True)
copies = {}            # biome vanilla -> liste des copies
nb = 0
for t in terroirs:
    cle = t["cle"]
    os.makedirs(f"{dossier_biomes}/{cle}", exist_ok=True)
    for b in listes[cle]:
        j = json.load(open(f"{EXP}/biome/{b}.json", encoding="utf-8"))
        # on retire nos propres ajouts (déjà appliqués par le biome modifier)
        j["features"] = [[f for f in etape if not f.startswith("domaine_terre:")] for etape in j["features"]]
        # animaux vanilla régionalisés : chaque espèce typée seulement dans ses terroirs
        for groupe, liste in j.get("spawners", {}).items():
            j["spawners"][groupe] = [sp for sp in liste
                                     if cle in VANILLA_REGIONAUX.get(sp["type"], [cle])]
        json.dump(j, open(f"{dossier_biomes}/{cle}/{b}.json", "w", encoding="utf-8"), indent=1)
        copies.setdefault(f"minecraft:{b}", []).append(f"domaine_terre:{cle}/{b}")
        nb += 1

def ecrire_tag(id_tag, valeurs):
    ns, chemin = id_tag.split(":", 1)
    p = f"{RES}/data/{ns}/tags/worldgen/biome/{chemin}.json"
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump({"replace": False, "values": sorted(valeurs)}, open(p, "w", encoding="utf-8"), indent=1)

# 1) tags vanilla / Forge / c : chaque copie rejoint les tags de son biome d'origine
nt = 0
for id_tag, membres in tags.items():
    if id_tag.split(":")[0] not in ("minecraft", "forge", "c"):
        continue
    v = [c for m in membres for c in copies.get(m, [])]
    if v:
        ecrire_tag(id_tag, v); nt += 1

# 2) tags du mod : terroir, continent, tous
par_continent = {}
for t in terroirs:
    v = [f"domaine_terre:{t['cle']}/{b}" for b in listes[t["cle"]]]
    ecrire_tag(f"domaine_terre:terroir/{t['cle']}", v)
    par_continent.setdefault(t["continent"], []).append(f"#domaine_terre:terroir/{t['cle']}")
for c, v in par_continent.items():
    ecrire_tag(f"domaine_terre:continent/{c}", v)
ecrire_tag("domaine_terre:terroirs", [f"#domaine_terre:terroir/{t['cle']}" for t in terroirs])
# régions : découpage plus fin que les continents (les 25 aires culturelles viendront plus tard)
REGIONS = {
    "amerique_nord": ["boreale", "grandes_plaines", "ouest_mexique"],
    "amerique_centrale": ["amerique_centrale"],
    "amerique_sud": ["amazonie", "andes", "cone_sud"],
    "europe_nord": ["nordique"],
    "europe_ouest": ["atlantique", "continentale", "alpine"],
    "europe_sud": ["mediterranee"],
    "afrique_nord": ["maghreb", "sahara_sahel"],
    "afrique_subsaharienne": ["afrique_tropicale", "afrique_est", "afrique_australe"],
    "moyen_orient": ["moyen_orient"],
    "asie_centrale": ["steppes_tibet"],
    "asie_nord": ["siberie"],
    "asie_sud": ["inde"],
    "asie_est": ["chine", "japon_coree"],
    "asie_sud_est": ["asie_sud_est"],
    "oceanie": ["australie", "nouvelle_zelande", "melanesie"],
    "arctique": ["arctique"],
    "antarctique": ["antarctique"],
}
assert sorted(c for v in REGIONS.values() for c in v) == sorted(t["cle"] for t in terroirs), "terroir sans région"
for r, v in REGIONS.items():
    ecrire_tag(f"domaine_terre:region/{r}", [f"#domaine_terre:terroir/{c}" for c in v])

# 3) noms affichés (F3, cartes) : « Plaines (Méditerranée) »
lang = {}
for t in terroirs:
    for b in listes[t["cle"]]:
        lang[f"biome.domaine_terre.{t['cle']}.{b}"] = f"{noms.get(b, b)} ({t['nom']})"
os.makedirs(f"{RES}/assets/domaine_terre/lang", exist_ok=True)
for l in ("fr_fr", "en_us"):
    json.dump(lang, open(f"{RES}/assets/domaine_terre/lang/{l}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# 4) types de monde : « Par défaut » = Terre 1:250 (échelle des lieux uniques) ; en plus Terre 1:500 et Terre 1:1000
def preset(echelle):
    return {"dimensions": {
        "minecraft:overworld": {"type": "minecraft:overworld", "generator": {"type": "minecraft:noise",
            "settings": "minecraft:overworld", "biome_source": {"type": "domaine_terre:terre", "echelle": echelle}}},
        "minecraft:the_nether": {"type": "minecraft:the_nether", "generator": {"type": "minecraft:noise",
            "settings": "minecraft:nether", "biome_source": {"type": "minecraft:multi_noise", "preset": "minecraft:nether"}}},
        "minecraft:the_end": {"type": "minecraft:the_end", "generator": {"type": "minecraft:noise",
            "settings": "minecraft:end", "biome_source": {"type": "minecraft:the_end"}}}}}
def ecrire(p, d):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(d, open(p, "w", encoding="utf-8"), indent=1)
ecrire(f"{RES}/data/minecraft/worldgen/world_preset/normal.json", preset(250))
ecrire(f"{RES}/data/domaine_terre/worldgen/world_preset/terre_1000.json", preset(1000))
ecrire(f"{RES}/data/domaine_terre/worldgen/world_preset/terre_500.json", preset(500))
ecrire(f"{RES}/data/minecraft/tags/worldgen/world_preset/normal.json",
       {"replace": False, "values": ["domaine_terre:terre_500", "domaine_terre:terre_1000"]})
lang["generator.domaine_terre.terre_1000"] = "Terre 1:1000 (petite)"
lang["generator.domaine_terre.terre_500"] = "Terre 1:500 (moyenne)"
for l in ("fr_fr", "en_us"):
    json.dump(lang, open(f"{RES}/assets/domaine_terre/lang/{l}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# 5) règles de surface : chaque copie reçoit le sol de son biome d'origine
ns_p = f"{EXP}/noise_settings_overworld.json"
if os.path.exists(ns_p):
    ns = json.load(open(ns_p, encoding="utf-8"))
    nr = [0]
    def parcourir(o):
        if isinstance(o, dict):
            if o.get("type") == "minecraft:biome" and isinstance(o.get("biome_is"), list):
                o["biome_is"] = o["biome_is"] + [c for b in o["biome_is"] for c in copies.get(b, [])]
                nr[0] += 1
            for v in o.values(): parcourir(v)
        elif isinstance(o, list):
            for v in o: parcourir(v)
    parcourir(ns["surface_rule"])
    p2 = f"{RES}/data/minecraft/worldgen/noise_settings/overworld.json"
    os.makedirs(os.path.dirname(p2), exist_ok=True)
    json.dump(ns, open(p2, "w", encoding="utf-8"), indent=1)
    print("règles de surface complétées :", nr[0])
print(f"{nb} biomes de terroir, {nt} tags vanilla/Forge complétés, {len(lang)} noms, type de monde activé")

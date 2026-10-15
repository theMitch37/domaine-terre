"""Génère le datapack « domaine_terroirs » (plantes et animaux dans leur terroir) + les réglages Alex's Mobs.
Usage : python3 outils/generer_placement.py "<dossier instance>" """
import glob, io, json, os, re, shutil, sys, zipfile

INST = sys.argv[1]
MODS = os.path.join(INST, "mods")
LISTES = json.load(open("src/main/resources/domaine_terre/carte/terroirs_biomes.json", encoding="utf-8"))
T = lambda *ts: [f"#domaine_terre:terroir/{t}" for t in ts]          # tags de terroir
fichiers = {}                                                       # chemin dans le datapack -> contenu


def jar(motif):
    l = glob.glob(os.path.join(MODS, motif))
    return zipfile.ZipFile(l[0]) if l else None


def tag(chemin, *terroirs):
    fichiers[chemin] = {"replace": True, "values": [{"id": v, "required": False} for v in T(*terroirs)]}


def modifier(motif_jar, chemin, champ, *terroirs, retirer=()):
    """Recopie un biome modifier d'un mod en remplaçant ses biomes par des terroirs."""
    z = jar(motif_jar)
    if not z or chemin not in z.namelist():
        print("  absent :", chemin); return
    d = json.loads(z.read(chemin))
    valeur = T(*terroirs)
    if champ == "includeBiomes":
        # format propre à Aquaculture : liste de tags, ou valeur simple pour les « mob_spawn »
        d[champ] = valeur[0] if isinstance(d.get(champ), str) else valeur
    elif len(valeur) == 1:
        d[champ] = valeur[0]
    else:
        d[champ] = {"type": "forge:or", "values": valeur}   # plusieurs tags : ensemble « ou » de Forge
    for r in retirer:
        d.pop(r, None)
    fichiers[chemin] = d


# ---------------------------------------------------------------- PLANTES
F = "data/farm_and_charm/tags/worldgen/biome/"
tag(F + "spawns_wild_barley.json", "moyen_orient")
tag(F + "spawns_wild_emmer.json", "moyen_orient")
tag(F + "spawns_wild_oat.json", "continentale")
tag(F + "spawns_wild_potatoes.json", "andes")
tag(F + "spawns_wild_tomatoes_and_corn.json", "ouest_mexique", "andes")
tag(F + "spawns_wild_strawberries.json", "atlantique")
tag(F + "spawns_wild_crops.json", "mediterranee", "steppes_tibet")
tag(F + "spawns_wild_flowers.json", "continentale", "atlantique")
tag("data/bakery/tags/worldgen/biome/spawns_strawberries.json", "atlantique")
tag("data/brewery/tags/worldgen/biome/taiga.json", "continentale")
V = "data/vinery/tags/worldgen/biome/"
tag(V + "spawns_grape.json", "mediterranee")
tag(V + "spawns_savanna_grape.json", "afrique_australe")
tag(V + "spawns_taiga_grape.json", "boreale")
tag(V + "spawns_jungle_grape.json", "amerique_centrale")
tag(V + "spawns_cherry_tree.json", "moyen_orient", "steppes_tibet")
tag("data/supplementaries/tags/worldgen/biome/has_wild_flax.json", "moyen_orient")
H = "data/herbalbrews/forge/biome_modifier/"
modifier("letsdo-herbalbrews*.jar", H + "add_coffee_patch.json", "biomes", "afrique_est")
modifier("letsdo-herbalbrews*.jar", H + "add_hibiscus_patch.json", "biomes", "afrique_tropicale")
modifier("letsdo-herbalbrews*.jar", H + "add_lavender_patch.json", "biomes", "mediterranee")
modifier("letsdo-herbalbrews*.jar", H + "add_rooibos_patch.json", "biomes", "afrique_australe")
modifier("letsdo-herbalbrews*.jar", H + "add_yerba_mate_patch.json", "biomes", "cone_sud")
modifier("RamadanDelight*.jar", "data/ramadandelight/forge/biome_modifier/add_tree_palm.json", "biomes", "moyen_orient", "maghreb")
modifier("letsdo-wildernature*.jar", "data/bloomingnature/forge/biome_modifier/add_patch_hazelnut_bush.json", "biomes", "continentale")
C = "data/culturaldelights/forge/biome_modifier/"
modifier("culturaldelights*.jar", C + "trees_avocado.json", "biomes", "amerique_centrale")
modifier("culturaldelights*.jar", C + "wild_corn.json", "biomes", "ouest_mexique")
modifier("culturaldelights*.jar", C + "wild_cucumbers.json", "biomes", "inde")
modifier("culturaldelights*.jar", C + "wild_eggplants.json", "biomes", "inde")
FD = [("FarmersDelight*.jar", "farmersdelight", {"wild_cabbages": ["atlantique"], "wild_beetroots": ["mediterranee"],
       "wild_carrots": ["steppes_tibet"], "wild_onions": ["steppes_tibet"], "wild_potatoes": ["andes"],
       "wild_rice": ["chine"], "wild_tomatoes": ["andes"]}),
      ("rice-delight*.jar", "rice_delight", {"wild_basil": ["inde"], "wild_bell_peppers": ["ouest_mexique"]}),
      ("corn_delight*.jar", "corn_delight", {"wild_corn": ["ouest_mexique"]}),
      ("RamadanDelight*.jar", "ramadandelight", {"wild_chickpea": ["moyen_orient"], "wild_parsley": ["mediterranee"]})]
for mj, ns, m in FD:
    for nom, ts in m.items():
        modifier(mj, f"data/{ns}/forge/biome_modifier/{nom}.json", "allowed_biomes", *ts,
                 retirer=("denied_biomes", "min_temperature", "max_temperature"))
E = "data/ecologics/forge/biome_modifier/"
modifier("ecologics*.jar", E + "add_prickly_pear.json", "biomes", "ouest_mexique")
modifier("ecologics*.jar", E + "add_walnut_tree.json", "biomes", "steppes_tibet", "moyen_orient")
modifier("ecologics*.jar", E + "add_beach_features.json", "biomes", "asie_sud_est", "melanesie")

# ---------------------------------------------------------------- ANIMAUX
N = "data/naturalist/tags/worldgen/biome/has_"
for a, ts in {"bear": ["nordique", "siberie", "boreale"], "bluejay": ["grandes_plaines", "boreale"],
              "cardinal": ["grandes_plaines"], "boar": ["continentale", "mediterranee"],
              "deer": ["continentale", "atlantique", "grandes_plaines"], "lion": ["afrique_est", "sahara_sahel"],
              "vulture": ["afrique_est", "sahara_sahel"], "giraffe": ["afrique_est", "afrique_australe"],
              "zebra": ["afrique_est", "afrique_australe"], "rhino": ["afrique_est", "afrique_australe"],
              "elephant": ["afrique_est", "afrique_tropicale"], "hippo": ["afrique_est", "afrique_tropicale"],
              "alligator": ["grandes_plaines"], "bass": ["grandes_plaines"], "catfish": ["grandes_plaines"],
              "rattlesnake": ["ouest_mexique"], "coral_snake": ["amerique_centrale"],
              "canary": ["mediterranee", "maghreb"], "tortoise": ["mediterranee", "maghreb"],
              "robin": ["atlantique", "continentale"]}.items():
    tag(N + a + ".json", *ts)
W = "data/wildernature/tags/worldgen/biome/spawns_"
for a, ts in {"bison": ["grandes_plaines"], "raccoon": ["grandes_plaines"], "turkey": ["grandes_plaines"],
              "red_wolf": ["grandes_plaines"], "deer": ["continentale", "atlantique"],
              "hedgehog": ["atlantique", "continentale"], "squirrel": ["continentale", "atlantique"],
              "boar": ["continentale", "mediterranee"], "cassowary": ["melanesie", "australie"],
              "flamingo": ["afrique_est", "amerique_centrale"], "penguin": ["antarctique"], "minisheep": ["alpine"]}.items():
    tag(W + a + ".json", *ts)
M = "data/meadow/tags/worldgen/biome/"
tag(M + "spawns_meadow_sheeps.json", "alpine")
tag(M + "spawns_rocky_sheep.json", "alpine")
tag(M + "spawns_meadow_wooly_cows.json", "atlantique")
tag(M + "spawns_sunset_cow.json", "afrique_est")
modifier("letsdo-meadow*.jar", "data/meadow/forge/biome_modifier/spawn_buffalo.json", "biomes", "inde", "asie_sud_est")
A = "data/aquaculture/forge/biome_modifier/"
for f, ts in {"arapaima_spawn": ["amazonie"], "piranha_spawn": ["amazonie"], "tambaqui_spawn": ["amazonie"],
              "arrau_turtle_spawn": ["amazonie"], "bayad_spawn": ["sahara_sahel", "afrique_tropicale"],
              "boulti_spawn": ["sahara_sahel", "afrique_tropicale"], "capitaine_spawn": ["sahara_sahel", "afrique_tropicale"],
              "synodontis_spawn": ["sahara_sahel", "afrique_tropicale"], "box_turtle_spawn": ["grandes_plaines"]}.items():
    modifier("Aquaculture*.jar", A + f + ".json", "includeBiomes", *ts)
modifier("ecologics*.jar", E + "spawn_camel.json", "biomes", "moyen_orient", "sahara_sahel")
modifier("ecologics*.jar", E + "spawn_penguin.json", "biomes", "antarctique")
modifier("ecologics*.jar", E + "spawn_squirrel.json", "biomes", "continentale")

# Untamed Wilds : espèce -> terroirs ; None = espèce préhistorique désactivée
UW = {"bear": {"black": ["boreale", "grandes_plaines"], "brown": ["nordique", "siberie", "boreale"], "panda": ["chine"],
               "polar": ["arctique"], "spectacled": ["andes"], "sun": ["asie_sud_est"], "cave": None, "blind": None},
      "big_cat": {"lion": ["afrique_est"], "leopard": ["afrique_tropicale", "inde"], "tiger": ["inde", "chine", "siberie"],
                  "snow_leopard": ["steppes_tibet"], "jaguar": ["amazonie"], "puma": ["ouest_mexique", "andes"],
                  "cave_lion": None, "sabertooth": None, "marsupial_lion": None},
      "bison": {"plains": ["grandes_plaines"], "wisent": ["continentale"]},
      "boar": {"eurasian": ["continentale", "mediterranee"], "peccary": ["amazonie"], "red_river": ["afrique_tropicale"],
               "warthog": ["afrique_est"]},
      "camel": {"dromedary": ["moyen_orient", "sahara_sahel"], "bactrian": ["steppes_tibet"], "wild_bactrian": ["steppes_tibet"]},
      "rhino": {"black": ["afrique_est", "afrique_australe"], "white": ["afrique_est", "afrique_australe"], "indian": ["inde"],
                "javan": ["asie_sud_est"], "sumatran": ["asie_sud_est"], "wooly": None},
      "hyena": {"spotted": ["afrique_est"], "striped": ["moyen_orient", "sahara_sahel"], "brown": ["afrique_australe"],
                "aardwolf": ["afrique_australe"], "shortface": None},
      "wildebeest": {"*": ["afrique_est", "afrique_australe"]}, "aardvark": {"*": ["afrique_est", "afrique_australe"]},
      "hippo": {"*": ["afrique_est", "afrique_tropicale"]}, "opossum": {"*": ["grandes_plaines"]},
      "terror_bird": {"*": None},
      "large_snake": {"anaconda": ["amazonie"], "reticulated_python": ["asie_sud_est"]},
      "giant_salamander": {"chinese": ["chine"], "japanese": ["japon_coree"], "hellbender": ["grandes_plaines"]}}


def resources(terroirs):
    return [[f"resource|domaine_terre:{t}/{b}"] for t in terroirs for b in LISTES[t]]


z = jar("untamedwilds*.jar")
if z:
    for ent, especes in UW.items():
        chemin = f"data/untamedwilds/entities/{ent}.json"
        d = json.loads(z.read(chemin).decode("utf-8-sig"))
        for sp in d.get("species", []):
            ts = especes.get(sp["name"], especes.get("*", "garder"))
            if ts == "garder":
                continue
            sp["spawnBiomes"] = [["resource|minecraft:the_void"]] if ts is None else resources(ts)
        fichiers[chemin] = d

# ---------------------------------------------------------------- écriture du datapack
fichiers["pack.mcmeta"] = {"pack": {"pack_format": 15, "description": "Le Domaine d'Aubin : plantes et animaux par terroir"}}
dst = os.path.join(INST, "config/openloader/data/domaine_terroirs.zip")
with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
    for p, d in fichiers.items():
        zout.writestr(p, json.dumps(d, indent=1, ensure_ascii=False))
print("datapack :", len(fichiers), "fichiers ->", dst)

# ---------------------------------------------------------------- Alex's Mobs (fichiers de config)
AM = {"kangaroo": ["australie"], "emu": ["australie"], "platypus": ["australie"], "tasmanian_devil": ["australie"],
      "sugar_glider": ["australie", "melanesie"], "gorilla": ["afrique_tropicale"], "gelada_monkey": ["afrique_est"],
      "shoebill": ["afrique_est"], "gazelle": ["afrique_est", "sahara_sahel"], "jerboa": ["sahara_sahel", "moyen_orient"],
      "rain_frog": ["afrique_australe"], "crocodile": ["afrique_tropicale", "inde"], "komodo_dragon": ["asie_sud_est"],
      "mudskipper": ["asie_sud_est"], "moose": ["boreale"], "bald_eagle": ["boreale"], "grizzly_bear": ["boreale"],
      "banana_slug": ["boreale"], "skunk": ["grandes_plaines"], "alligator_snapping_turtle": ["grandes_plaines"],
      "raccoon": ["grandes_plaines"], "blue_jay": ["grandes_plaines"], "bison": ["grandes_plaines"], "terrapin": ["grandes_plaines"],
      "roadrunner": ["ouest_mexique"], "rattlesnake": ["ouest_mexique"], "devils_hole_pupfish": ["ouest_mexique"],
      "hummingbird": ["amerique_centrale", "amazonie"], "caiman": ["amazonie"], "anaconda": ["amazonie"],
      "capuchin_monkey": ["amazonie"], "toucan": ["amazonie"], "potoo": ["amazonie"], "anteater": ["amazonie"],
      "leafcutter_anthill": ["amazonie"], "maned_wolf": ["cone_sud"], "elephant": ["afrique_est"],
      "rhinoceros": ["afrique_est"], "tiger": ["inde", "chine", "siberie"], "snow_leopard": ["steppes_tibet"]}
cfg = os.path.join(INST, "config/alexsmobs")
sauv = os.path.join(INST, "config/alexsmobs_avant_domaine")
if not os.path.exists(sauv):
    shutil.copytree(cfg, sauv)
n = 0
for a, ts in AM.items():
    p = os.path.join(cfg, f"{a}_spawns.json")
    if not os.path.exists(p):
        print("  config absente :", a); continue
    d = json.load(open(p, encoding="utf-8"))
    d["biomes"] = [[{"type": "BIOME_TAG", "negate": False, "value": f"domaine_terre:terroir/{t}"}] for t in ts]
    json.dump(d, open(p, "w", encoding="utf-8"), indent=2)
    n += 1
print("Alex's Mobs :", n, "animaux placés")

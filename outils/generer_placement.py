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

# Untamed Wilds : espèce -> terroirs, repris de outils/faune/especes.csv (04/11/2026 : races régionales et milieux).
# Untamed Wilds fait naître ses animaux par ses propres features : on règle les biomes de chaque espèce.
# None = espèce retirée (préhistorique ou inventée). Les biomes gardés suivent le milieu de l'espèce.
import csv as _csv
TYPES_MILIEU = {
    "foret_tropicale": {"jungle", "sparse_jungle", "bamboo_jungle", "mangrove_swamp"},
    "foret": {"forest", "birch_forest", "old_growth_birch_forest", "dark_forest", "flower_forest", "taiga",
              "old_growth_pine_taiga", "old_growth_spruce_taiga", "snowy_taiga", "windswept_forest", "jungle",
              "sparse_jungle", "bamboo_jungle", "cherry_grove", "grove"},
    "savane": {"savanna", "savanna_plateau", "windswept_savanna", "sparse_jungle"},
    "prairie": {"plains", "sunflower_plains", "meadow", "savanna", "cherry_grove"},
    "culture": {"plains", "sunflower_plains", "meadow"},
    "steppe": {"plains", "savanna", "savanna_plateau", "desert", "windswept_hills", "snowy_plains"},
    "desert": {"desert", "badlands", "wooded_badlands", "eroded_badlands", "savanna_plateau"},
    "montagne": {"windswept_hills", "windswept_gravelly_hills", "windswept_forest", "stony_peaks", "jagged_peaks",
                 "frozen_peaks", "snowy_slopes", "meadow", "grove"},
    "haute_montagne": {"stony_peaks", "jagged_peaks", "frozen_peaks"},
    "toundra": {"snowy_plains", "snowy_taiga", "ice_spikes", "grove", "snowy_slopes"},
    "banquise": {"snowy_plains", "ice_spikes", "snowy_beach"},
    "marais": {"swamp", "mangrove_swamp"},
    "mediterraneen": {"plains", "forest", "flower_forest", "savanna", "sunflower_plains"},
    "cote": {"beach", "stony_shore", "snowy_beach", "mangrove_swamp"},
}
EAU_UW = {"eau_douce", "marais"}
VRAIS_T = list(LISTES)


def _aire(ts):
    if ts.startswith("partout_sauf:"):
        return [t for t in VRAIS_T if t not in ts[13:].split(",")]
    if ts.startswith("partout"):
        return list(VRAIS_T)
    return [t for t in ts.split(",") if t in LISTES]


UW = {}
RARETE = {}            # (entité, espèce) -> poids de l'abondance réelle (07/11/2026), « rarity » d'Untamed Wilds
_ABONDANCE = {"TC": 16, "C": 8, "PC": 3, "R": 1}
for _r in _csv.DictReader(open("outils/faune/especes.csv", encoding="utf-8"), delimiter=";"):
    if not _r["id"].startswith("untamedwilds:") or "/" not in _r["id"]:
        continue
    _ent, _sp = _r["id"][13:].split("/", 1)
    if _r.get("abondance") in _ABONDANCE:
        RARETE[(_ent, _sp)] = _ABONDANCE[_r["abondance"]]
    if _r["statut"] in ("retirer", "souterrain"):
        UW.setdefault(_ent, {})[_sp] = None
        continue
    if not _aire(_r["terroirs"]) or re.search(r"\b(mer|large|abysses)\b", _r["milieu"]):
        continue                                 # espèces marines : biomes d'origine (tags d'océan, mers du mod)
    _toks = {x.strip() for x in _r["milieu"].replace("(", ",").replace(")", ",").split(",") if x.strip()}
    _types = set().union(*[TYPES_MILIEU.get(t, set()) for t in _toks]) if _toks else set()
    UW.setdefault(_ent, {})[_sp] = (_aire(_r["terroirs"]), _types, bool(_toks & EAU_UW))


def resources_milieu(terroirs, types, eau):
    out = []
    for t in terroirs:
        bs = [b for b in LISTES[t] if not types or b in types]
        if not bs:
            bs = LISTES[t]                       # aucun biome du milieu dans ce terroir : tout le terroir
        out += [[f"resource|domaine_terre:{t}/{b}"] for b in bs]
        if eau:
            out.append([f"resource|domaine_terre:{t}/lac"])
            out.append([f"resource|domaine_terre:{t}/fleuve"])
    return out


def resources(terroirs):
    return [[f"resource|domaine_terre:{t}/{b}"] for t in terroirs for b in LISTES[t]]


# Untamed Wilds : « scale » de certaines espèces, pour leur taille réelle (1 bloc = 1 m)
# 08/11/2026 : taille réelle (1 bloc = 1 m) ; base du modèle = boîte de collision (largeur pour les poissons, serpents et
# varans, hauteur pour les autres), calibrée sur le grand requin blanc mesuré en jeu ; petits animaux un peu agrandis
# (0,3 bloc minimum), insectes entre 0,12 et 0,35 bloc. Espèces disparues ou inventées : inchangées (retirées).
ECHELLE = {("aardvark", "common"): 0.72,
           ("arowana", "black"): 1.38,
           ("arowana", "green"): 1.54,
           ("arowana", "jardini"): 1.38,
           ("arowana", "silver"): 1.54,
           ("baleen_whale", "blue"): 8.93,
           ("baleen_whale", "fin"): 7.86,
           ("baleen_whale", "gray"): 5.0,
           ("baleen_whale", "humpback"): 5.36,
           ("baleen_whale", "minke"): 2.86,
           ("baleen_whale", "sei"): 6.07,
           ("bear", "black"): 0.77,
           ("bear", "brown"): 1.0,
           ("bear", "panda"): 0.69,
           ("bear", "polar"): 1.08,
           ("bear", "spectacled"): 0.62,
           ("bear", "sun"): 0.54,
           ("big_cat", "jaguar"): 0.75,
           ("big_cat", "leopard"): 0.7,
           ("big_cat", "lion"): 1.2,
           ("big_cat", "puma"): 0.75,
           ("big_cat", "snow_leopard"): 0.65,
           ("big_cat", "tiger"): 1.1,
           ("bison", "plains"): 1.19,
           ("bison", "wisent"): 1.19,
           ("boar", "eurasian"): 0.75,
           ("boar", "peccary"): 0.46,
           ("boar", "red_river"): 0.67,
           ("boar", "warthog"): 0.62,
           ("butterfly", "birdwing"): 0.58,
           ("butterfly", "blue_swallowtail"): 0.58,
           ("butterfly", "brimstone"): 0.58,
           ("butterfly", "cabbage"): 0.5,
           ("butterfly", "comma"): 0.5,
           ("butterfly", "emperor"): 0.58,
           ("butterfly", "glasswing"): 0.58,
           ("butterfly", "kite"): 0.58,
           ("butterfly", "leaf"): 0.58,
           ("butterfly", "malachite"): 0.58,
           ("butterfly", "monarch"): 0.58,
           ("butterfly", "morpho"): 0.58,
           ("butterfly", "mourning_cloak"): 0.58,
           ("butterfly", "narcissus"): 0.5,
           ("butterfly", "orange_tip"): 0.45,
           ("butterfly", "peacock"): 0.58,
           ("butterfly", "red_admiral"): 0.58,
           ("butterfly", "speckled_wood"): 0.45,
           ("butterfly", "tiger_swallowtail"): 0.58,
           ("butterfly", "triangle"): 0.58,
           ("camel", "bactrian"): 1.1,
           ("camel", "dromedary"): 1.05,
           ("camel", "wild_bactrian"): 1.0,
           ("catfish", "blue"): 1.51,
           ("catfish", "channel"): 0.81,
           ("catfish", "redtail"): 1.51,
           ("football_fish", "atlantic"): 0.7,
           ("giant_clam", "derasa"): 0.55,
           ("giant_clam", "gigas"): 1.2,
           ("giant_clam", "maxima"): 0.44,
           ("giant_clam", "squamosa"): 0.47,
           ("giant_salamander", "chinese"): 1.15,
           ("giant_salamander", "hellbender"): 0.44,
           ("giant_salamander", "japanese"): 0.92,
           ("hippo", "common"): 0.89,
           ("hyena", "aardwolf"): 0.5,
           ("hyena", "brown"): 0.73,
           ("hyena", "spotted"): 0.82,
           ("hyena", "striped"): 0.68,
           ("king_crab", "centolla"): 1.67,
           ("king_crab", "red"): 2.0,
           ("king_crab", "spiny"): 1.33,
           ("large_snake", "anaconda"): 2.56,
           ("large_snake", "reticulated_python"): 3.08,
           ("manatee", "african"): 1.55,
           ("manatee", "amazon"): 1.29,
           ("manatee", "dugong"): 1.55,
           ("manatee", "west"): 1.65,
           ("monitor", "bengal"): 0.89,
           ("monitor", "desert"): 0.71,
           ("monitor", "nile"): 1.07,
           ("monitor", "rock"): 0.95,
           ("monitor", "water"): 1.18,
           ("newt", "coastal"): 0.47,
           ("newt", "crested"): 0.41,
           ("newt", "eastern"): 0.38,
           ("newt", "fire_salamander"): 0.47,
           ("newt", "ribbed"): 0.52,
           ("newt", "tiger"): 0.52,
           ("opossum", "virginia"): 0.56,
           ("rhino", "black"): 0.89,
           ("rhino", "indian"): 1.06,
           ("rhino", "javan"): 0.89,
           ("rhino", "sumatran"): 0.72,
           ("rhino", "white"): 1.0,
           ("sawfish", "dwarf"): 0.72,
           ("sawfish", "green"): 3.09,
           ("sawfish", "large_tooth"): 3.09,
           ("sawfish", "narrow"): 1.55,
           ("sawfish", "small_tooth"): 2.58,
           ("shark", "bigeye"): 2.06,
           ("shark", "bluntnose"): 2.58,
           ("shark", "bull"): 1.55,
           ("shark", "goblin"): 2.06,
           ("shark", "great_white"): 3.6,
           ("shark", "greenland"): 2.58,
           ("shark", "hammerhead"): 2.32,
           ("shark", "lemon"): 1.55,
           ("shark", "mako"): 1.8,
           ("shark", "tiger"): 2.32,
           ("snake", "adder"): 0.48,
           ("snake", "ball_python"): 0.97,
           ("snake", "black_mamba"): 2.02,
           ("snake", "carpet_python"): 2.02,
           ("snake", "cave_racer"): 1.21,
           ("snake", "coral"): 0.56,
           ("snake", "coral_blue"): 1.21,
           ("snake", "corn"): 1.05,
           ("snake", "emerald"): 1.45,
           ("snake", "grass_snake"): 0.81,
           ("snake", "gray_kingsnake"): 0.81,
           ("snake", "green_mamba"): 1.61,
           ("snake", "rattlesnake"): 0.97,
           ("snake", "rice_paddy"): 0.48,
           ("snake", "swamp_moccasin"): 0.81,
           ("snake", "taipan"): 1.61,
           ("snake", "western_rattlesnake"): 0.81,
           ("softshell_turtle", "black"): 0.77,
           ("softshell_turtle", "chinese"): 0.68,
           ("softshell_turtle", "flapshell"): 0.72,
           ("softshell_turtle", "nile"): 1.38,
           ("softshell_turtle", "peacock"): 0.92,
           ("softshell_turtle", "pig_nose"): 0.85,
           ("softshell_turtle", "spiny"): 0.81,
           ("spadefish", "atlantic"): 0.64,
           ("spadefish", "dusky"): 0.51,
           ("spadefish", "orbicular"): 0.55,
           ("spadefish", "teira"): 0.7,
           ("sunfish", "southern"): 1.73,
           ("sunfish", "sunfish"): 1.45,
           ("tarantula", "black"): 1.25,
           ("tarantula", "black_and_white"): 1.25,
           ("tarantula", "cobalt"): 1.25,
           ("tarantula", "king"): 1.3,
           ("tarantula", "red_knee"): 1.25,
           ("tarantula", "regalis"): 1.25,
           ("tarantula", "rose"): 1.25,
           ("tarantula", "tiger"): 1.25,
           ("tortoise", "asian_box"): 0.61,
           ("tortoise", "gopher"): 0.78,
           ("tortoise", "leopard"): 0.92,
           ("tortoise", "marginated"): 0.73,
           ("tortoise", "star"): 0.67,
           ("tortoise", "sulcata"): 1.33,
           ("trevally", "bigeye"): 0.81,
           ("trevally", "bluespotted"): 0.7,
           ("trevally", "giant"): 1.74,
           ("trevally", "golden"): 1.05,
           ("trevally", "jack"): 0.81,
           ("triggerfish", "clown"): 0.58,
           ("triggerfish", "grey"): 0.64,
           ("triggerfish", "orangelined"): 0.51,
           ("triggerfish", "picasso"): 0.47,
           ("triggerfish", "redtooth"): 0.55,
           ("triggerfish", "reef"): 0.51,
           ("triggerfish", "titan"): 0.87,
           ("whale_shark", "whale_shark"): 4.29,
           ("wildebeest", "black"): 1.0,
           ("wildebeest", "blue"): 1.17}

z = jar("untamedwilds*.jar")
# océans vanilla (plus générés : remplacés par les mers du mod, 04/11/2026) -> biomes domaine_terre:mer/…
_TEMP = {"warm_ocean": "chaude", "deep_warm_ocean": "chaude", "lukewarm_ocean": "tiede", "deep_lukewarm_ocean": "tiede",
         "ocean": "temperee", "deep_ocean": "temperee", "cold_ocean": "froide", "deep_cold_ocean": "froide",
         "frozen_ocean": "gelee", "deep_frozen_ocean": "gelee"}


def mers(liste):
    out = []
    for groupe in liste:
        g = []
        for v in groupe:
            n = v.split("|minecraft:", 1)[1] if v.startswith("resource|minecraft:") else None
            if n in _TEMP:
                bandes = ["large", "abysse"] if n.startswith("deep_") else ["cote", "plateau"]
                if n == "warm_ocean":
                    bandes = ["cote", "plateau", "large", "abysse"]
                g += [f"resource|domaine_terre:mer/{_TEMP[n]}_{b}" for b in bandes]
            else:
                g.append(v)
        out += [[x] for x in g] if len(g) > len(groupe) else [g]
    return out


if z:
    for chemin in sorted(n for n in z.namelist() if n.startswith("data/untamedwilds/entities/") and n.endswith(".json")):
        ent = chemin.rsplit("/", 1)[1][:-5]
        especes = UW.get(ent, {})
        d = json.loads(z.read(chemin).decode("utf-8-sig"))
        change = False
        for sp in d.get("species", []):
            # rareté entre les espèces d'une même créature (Untamed Wilds tire l'espèce au sort, pondérée par « rarity »)
            # taille réelle (08/11/2026 : grand requin blanc deux fois trop petit, 3,5 blocs au lieu de 6-7)
            ech = ECHELLE.get((ent, sp["name"]))
            if ech is not None and sp.get("scale") != ech:
                sp["scale"], change = ech, True
            rar = RARETE.get((ent, sp["name"]), RARETE.get((ent, "*")))
            if rar is not None and sp.get("rarity") != rar:
                sp["rarity"], change = rar, True
            ts = especes.get(sp["name"], especes.get("*", "garder"))
            if ts == "garder":
                nv = mers(sp.get("spawnBiomes", []))
                if nv != sp.get("spawnBiomes", []):
                    sp["spawnBiomes"], change = nv, True
                continue
            sp["spawnBiomes"] = [["resource|minecraft:the_void"]] if ts is None else resources_milieu(*ts)
            change = True
        if change:
            fichiers[chemin] = d

# ---------------------------------------------------------------- écriture du datapack
fichiers["pack.mcmeta"] = {"pack": {"pack_format": 15, "description": "Le Domaine d'Aubin : plantes et animaux par terroir"}}
dst = os.path.join(INST, "config/openloader/data/domaine_terroirs.zip")
with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
    for p, d in fichiers.items():
        zout.writestr(p, json.dumps(d, indent=1, ensure_ascii=False))
print("datapack :", len(fichiers), "fichiers ->", dst)

# ---------------------------------------------------------------- Untamed Wilds (fichier de config)
# 07/11/2026 : ses bêtes de terre naissent par la table du mod Terre (abondance réelle, comme les autres mods) ; son
# propre système ne garde que la mer, les poissons d'eau douce et les fonds (sinon elles naîtraient deux fois).
UW_CFG = os.path.join(INST, "config/untamedwilds-common.toml")
if os.path.exists(UW_CFG):
    t = open(UW_CFG, encoding="utf-8").read()
    for cle in ("freqapex", "freqherbivore", "freqcritter"):
        t = re.sub(r"(?m)^(\s*" + cle + r"\s*=\s*)\d+", r"\g<1>0", t)
    # 08/11/2026 : bancs de poissons et baleines trop nombreux ; la table du mod Terre peuple déjà les mers
    t = re.sub(r"(?m)^(\s*freqocean\s*=\s*)\d+", r"\g<1>96", t)
    open(UW_CFG, "w", encoding="utf-8").write(t)
    print("Untamed Wilds : prédateurs, herbivores et petites bêtes confiés au mod Terre")
else:
    print("Untamed Wilds : config absente (lancer le jeu une fois), à relancer ensuite")

# ---------------------------------------------------------------- Alex's Mobs (fichiers de config)
AM = {"kangaroo": ["australie"], "emu": ["australie"], "platypus": ["australie"], "tasmanian_devil": ["australie"],
      "sugar_glider": ["australie", "melanesie"], "gorilla": ["afrique_tropicale"], "gelada_monkey": ["afrique_est"],
      "shoebill": ["afrique_est"], "gazelle": ["afrique_est", "sahara_sahel"], "jerboa": ["sahara_sahel", "moyen_orient"],
      "rain_frog": ["afrique_australe"], "crocodile": ["afrique_tropicale", "inde"], "komodo_dragon": ["asie_sud_est"],
      "mudskipper": ["asie_sud_est"], "moose": ["boreale"], "bald_eagle": ["boreale"], "grizzly_bear": ["boreale", "grandes_plaines"],
      "banana_slug": ["boreale"], "skunk": ["grandes_plaines"], "alligator_snapping_turtle": ["grandes_plaines"],
      "raccoon": ["grandes_plaines"], "blue_jay": ["grandes_plaines"], "bison": ["grandes_plaines"], "terrapin": ["grandes_plaines"],
      "roadrunner": ["ouest_mexique"], "rattlesnake": ["ouest_mexique"], "devils_hole_pupfish": ["ouest_mexique"],
      "hummingbird": ["amerique_centrale", "amazonie"], "caiman": ["amazonie"], "anaconda": ["asie_sud_est"],
      "capuchin_monkey": ["amazonie"], "toucan": ["amazonie"], "potoo": ["amazonie"], "anteater": ["amazonie"],
      "leafcutter_anthill": ["amazonie"], "maned_wolf": ["cone_sud"], "elephant": ["afrique_est"],
      "rhinoceros": ["afrique_est", "inde"], "tiger": ["inde"], "snow_leopard": ["steppes_tibet"]}
cfg = os.path.join(INST, "config/alexsmobs")
sauv = os.path.join(INST, "config/alexsmobs_avant_domaine")
if not os.path.isdir(cfg):
    print("Alex's Mobs absent : configs non touchées (la faune du mod Terre place ses animaux)")
    sys.exit(0)
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

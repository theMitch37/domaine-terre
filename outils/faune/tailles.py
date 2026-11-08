"""Facteurs de taille des créatures (08/11/2026) -> src/main/resources/domaine_terre/faune/tailles.json.

Principe (Maxime) : taille réelle pour tous (1 bloc = 1 m) ; insectes et petits invertébrés plus petits qu'avant mais
visibles (entre 0,12 et 0,35 bloc). Base : boîte de collision d'origine relevée en jeu (domaine_tailles.csv, export du
mod) comparée à la vraie taille (hauteur au sommet de la tête pour les quadrupèdes et les oiseaux, longueur pour les
poissons, reptiles et animaux allongés, dont le modèle dépasse souvent la boîte). Approché : à retoucher à l'œil en jeu.
Pas touchés : Untamed Wilds (« scale » de ses espèces, outils/generer_placement.py), créatures inventées et monstres,
créatures en plusieurs morceaux (anaconda, cachalot d'Alex's Mobs), calmar géant d'Alex's Mobs (modèle à vérifier).
Usage : python3 outils/faune/tailles.py
"""
import json, os

# id : (taille réelle en m, mesure, facteur)   mesure : h = hauteur, l = longueur, i = insecte (taille affichée)
T = {
    # Alex's Mobs
    "alexsmobs:alligator_snapping_turtle": (0.7, "l", 0.6), "alexsmobs:anteater": (0.9, "h", 0.85),
    "alexsmobs:bald_eagle": (0.85, "h", 0.9), "alexsmobs:banana_slug": (0.2, "i", 0.45), "alexsmobs:bison": (1.9, "h", 0.9),
    "alexsmobs:blobfish": (0.3, "l", 0.45), "alexsmobs:blue_jay": (0.28, "l", 0.5), "alexsmobs:caiman": (2.0, "l", 1.2),
    "alexsmobs:capuchin_monkey": (0.45, "h", 0.65), "alexsmobs:catfish": (1.5, "l", 1.6), "alexsmobs:cockroach": (0.03, "i", 0.25),
    "alexsmobs:comb_jelly": (0.1, "l", 0.2), "alexsmobs:crocodile": (4.5, "l", 1.4), "alexsmobs:crow": (0.45, "l", 1.0),
    "alexsmobs:devils_hole_pupfish": (0.025, "l", 0.2), "alexsmobs:elephant": (3.3, "h", 0.95), "alexsmobs:emu": (1.75, "h", 1.0),
    "alexsmobs:fly": (0.007, "i", 0.35), "alexsmobs:flying_fish": (0.3, "l", 0.5), "alexsmobs:frilled_shark": (1.6, "l", 1.0),
    "alexsmobs:gazelle": (1.0, "h", 0.8), "alexsmobs:gelada_monkey": (0.7, "h", 0.6), "alexsmobs:gorilla": (1.5, "h", 1.1),
    "alexsmobs:grizzly_bear": (1.4, "h", 0.78), "alexsmobs:hammerhead_shark": (4.0, "l", 1.5), "alexsmobs:hummingbird": (0.1, "l", 0.25),
    "alexsmobs:jerboa": (0.12, "l", 0.3), "alexsmobs:kangaroo": (1.6, "h", 1.05), "alexsmobs:komodo_dragon": (2.6, "l", 1.0),
    "alexsmobs:leafcutter_ant": (0.015, "i", 0.15), "alexsmobs:lobster": (0.4, "l", 0.6), "alexsmobs:maned_wolf": (1.1, "h", 0.9),
    "alexsmobs:mantis_shrimp": (0.15, "l", 0.15), "alexsmobs:mimic_octopus": (0.6, "l", 0.65), "alexsmobs:moose": (2.1, "h", 0.95),
    "alexsmobs:mudskipper": (0.15, "l", 0.25), "alexsmobs:orca": (7.0, "l", 1.4), "alexsmobs:platypus": (0.5, "l", 0.65),
    "alexsmobs:potoo": (0.4, "h", 0.5), "alexsmobs:raccoon": (0.45, "h", 0.55), "alexsmobs:rain_frog": (0.05, "l", 0.22),
    "alexsmobs:rattlesnake": (1.2, "l", 1.0), "alexsmobs:rhinoceros": (1.8, "h", 0.75), "alexsmobs:roadrunner": (0.55, "l", 0.75),
    "alexsmobs:seagull": (0.45, "l", 1.0), "alexsmobs:seal": (1.8, "l", 1.2), "alexsmobs:shoebill": (1.3, "h", 0.87),
    "alexsmobs:skunk": (0.6, "l", 0.7), "alexsmobs:snow_leopard": (0.75, "h", 0.65), "alexsmobs:sugar_glider": (0.17, "l", 0.22),
    "alexsmobs:tarantula_hawk": (0.05, "i", 0.25), "alexsmobs:tasmanian_devil": (0.65, "l", 0.8), "alexsmobs:terrapin": (0.2, "l", 0.3),
    "alexsmobs:tiger": (1.1, "h", 1.0), "alexsmobs:toucan": (0.55, "l", 1.0), "alexsmobs:triops": (0.05, "l", 0.17),
    # Aquaculture
    "aquaculture:arapaima": (2.5, "l", 2.8), "aquaculture:arrau_turtle": (0.8, "l", 1.6), "aquaculture:atlantic_cod": (0.8, "l", 1.6),
    "aquaculture:atlantic_halibut": (1.5, "l", 2.0), "aquaculture:atlantic_herring": (0.3, "l", 1.0), "aquaculture:bayad": (0.7, "l", 1.3),
    "aquaculture:blackfish": (0.5, "l", 1.0), "aquaculture:bluegill": (0.2, "l", 0.67), "aquaculture:boulti": (0.35, "l", 1.15),
    "aquaculture:box_turtle": (0.15, "l", 0.3), "aquaculture:brown_trout": (0.5, "l", 1.0), "aquaculture:capitaine": (1.2, "l", 2.4),
    "aquaculture:carp": (0.6, "l", 1.0), "aquaculture:catfish": (1.5, "l", 2.0), "aquaculture:gar": (1.2, "l", 1.5),
    "aquaculture:jellyfish": (0.4, "l", 0.6), "aquaculture:minnow": (0.07, "l", 0.25), "aquaculture:muskellunge": (1.1, "l", 1.4),
    "aquaculture:pacific_halibut": (1.5, "l", 2.0), "aquaculture:perch": (0.25, "l", 0.85), "aquaculture:pink_salmon": (0.55, "l", 1.1),
    "aquaculture:piranha": (0.25, "l", 0.85), "aquaculture:pollock": (0.7, "l", 1.4), "aquaculture:rainbow_trout": (0.5, "l", 1.0),
    "aquaculture:red_grouper": (0.6, "l", 1.2), "aquaculture:smallmouth_bass": (0.4, "l", 0.8), "aquaculture:starshell_turtle": (0.25, "l", 0.5),
    "aquaculture:synodontis": (0.2, "l", 0.67), "aquaculture:tambaqui": (0.8, "l", 1.35), "aquaculture:tuna": (1.5, "l", 2.5),
    # Best Revived Animals (betteranimalsplus)
    "betteranimalsplus:badger": (0.75, "l", 0.9), "betteranimalsplus:barracuda": (1.4, "l", 0.95), "betteranimalsplus:blackbear": (1.0, "h", 0.75),
    "betteranimalsplus:boar": (0.9, "h", 1.0), "betteranimalsplus:brownbear": (1.3, "h", 0.7), "betteranimalsplus:butterfly": (0.06, "i", 1.0),
    "betteranimalsplus:coyote": (0.75, "h", 0.85), "betteranimalsplus:crab": (0.2, "l", 0.25), "betteranimalsplus:deer": (1.6, "h", 1.0),
    "betteranimalsplus:dragonfly": (0.08, "i", 1.0), "betteranimalsplus:eel_freshwater": (0.8, "l", 0.8), "betteranimalsplus:eel_saltwater": (1.5, "l", 1.5),
    "betteranimalsplus:flying_fish": (0.3, "l", 0.3), "betteranimalsplus:goose": (0.8, "h", 0.8), "betteranimalsplus:jellyfish": (0.4, "l", 0.5),
    "betteranimalsplus:lammergeier": (1.1, "l", 1.2), "betteranimalsplus:lamprey": (0.8, "l", 0.8), "betteranimalsplus:moose": (2.3, "h", 0.78),
    "betteranimalsplus:nautilus": (0.2, "l", 0.27), "betteranimalsplus:octopus": (0.9, "l", 0.9), "betteranimalsplus:pheasant": (0.8, "l", 0.8),
    "betteranimalsplus:piranha": (0.25, "l", 0.5), "betteranimalsplus:reindeer": (1.5, "h", 0.85), "betteranimalsplus:shark": (3.0, "l", 1.2),
    "betteranimalsplus:songbird": (0.15, "l", 0.3), "betteranimalsplus:squid_colossal": (10.0, "l", 1.5), "betteranimalsplus:squid_giant": (10.0, "l", 1.5),
    "betteranimalsplus:squirrel": (0.4, "l", 0.8), "betteranimalsplus:tarantula": (0.25, "i", 0.25), "betteranimalsplus:turkey": (1.0, "h", 1.0),
    "betteranimalsplus:walrus": (3.2, "l", 1.05), "betteranimalsplus:whale": (15.0, "l", 1.8),
    # Critters and Companions
    "crittersandcompanions:dragonfly": (0.08, "i", 0.4), "crittersandcompanions:dumbo_octopus": (0.3, "l", 0.75),
    "crittersandcompanions:ferret": (0.5, "l", 0.65), "crittersandcompanions:jumping_spider": (0.012, "i", 0.25),
    "crittersandcompanions:koi_fish": (0.6, "l", 1.0), "crittersandcompanions:ladybug": (0.008, "i", 0.25),
    "crittersandcompanions:leaf_insect": (0.08, "i", 0.9), "crittersandcompanions:otter": (1.1, "l", 1.3),
    "crittersandcompanions:red_panda": (0.6, "l", 0.8), "crittersandcompanions:roly_poly": (0.015, "i", 0.25),
    "crittersandcompanions:sea_bunny": (0.025, "l", 0.27), "crittersandcompanions:shima_enaga": (0.14, "l", 0.25),
    "crittersandcompanions:stag_beetle": (0.07, "i", 0.7),
    # Ecologics, Meadow
    "ecologics:coconut_crab": (0.4, "l", 0.6), "ecologics:penguin": (0.8, "h", 0.85), "ecologics:squirrel": (0.4, "l", 0.45),
    "meadow:water_buffalo": (1.7, "h", 1.2), "meadow:wooly_cow": (1.3, "h", 0.95), "meadow:wooly_sheep": (1.0, "h", 0.9),
    # Minecraft
    "minecraft:axolotl": (0.25, "l", 0.35), "minecraft:bat": (0.1, "l", 0.3), "minecraft:bee": (0.015, "i", 0.17),
    "minecraft:chicken": (0.6, "h", 0.85), "minecraft:cod": (0.8, "l", 1.6), "minecraft:cow": (1.5, "h", 1.05),
    "minecraft:dolphin": (2.5, "l", 1.7), "minecraft:donkey": (1.3, "h", 0.9), "minecraft:fox": (0.5, "h", 0.75),
    "minecraft:frog": (0.08, "l", 0.2), "minecraft:goat": (1.0, "h", 0.8), "minecraft:horse": (1.8, "h", 1.1),
    "minecraft:llama": (1.8, "h", 1.0), "minecraft:ocelot": (0.45, "h", 0.7), "minecraft:panda": (0.9, "h", 0.75),
    "minecraft:parrot": (0.4, "l", 0.6), "minecraft:pig": (0.9, "h", 1.0), "minecraft:polar_bear": (1.4, "h", 1.0),
    "minecraft:pufferfish": (0.3, "l", 0.45), "minecraft:rabbit": (0.4, "l", 0.8), "minecraft:salmon": (0.8, "l", 1.1),
    "minecraft:sheep": (1.0, "h", 0.8), "minecraft:squid": (0.6, "l", 0.75), "minecraft:tropical_fish": (0.1, "l", 0.25),
    "minecraft:turtle": (1.0, "l", 0.85), "minecraft:wolf": (0.85, "h", 1.0),
    # Naturalist
    "naturalist:alligator": (3.5, "l", 1.4), "naturalist:bass": (0.4, "l", 0.6), "naturalist:bear": (1.3, "h", 0.76),
    "naturalist:bluejay": (0.28, "l", 0.45), "naturalist:boar": (0.9, "h", 1.0), "naturalist:butterfly": (0.06, "i", 0.5),
    "naturalist:canary": (0.12, "l", 0.25), "naturalist:cardinal": (0.22, "l", 0.37), "naturalist:caterpillar": (0.04, "i", 0.6),
    "naturalist:catfish": (1.0, "l", 1.4), "naturalist:coral_snake": (0.8, "l", 1.0), "naturalist:deer": (1.2, "h", 0.75),
    "naturalist:dragonfly": (0.08, "i", 0.4), "naturalist:duck": (0.6, "h", 0.6), "naturalist:elephant": (3.3, "h", 0.95),
    "naturalist:finch": (0.15, "l", 0.25), "naturalist:firefly": (0.015, "i", 0.17), "naturalist:giraffe": (5.0, "h", 0.93),
    "naturalist:hippo": (1.6, "h", 1.1), "naturalist:lion": (1.3, "h", 0.75), "naturalist:lizard": (0.3, "l", 0.4),
    "naturalist:rattlesnake": (1.2, "l", 1.0), "naturalist:rhino": (1.8, "h", 0.65), "naturalist:robin": (0.14, "l", 0.25),
    "naturalist:snail": (0.04, "i", 0.35), "naturalist:snake": (1.0, "l", 1.0), "naturalist:sparrow": (0.15, "l", 0.25),
    "naturalist:tortoise": (0.2, "l", 0.25), "naturalist:vulture": (1.0, "l", 1.1), "naturalist:zebra": (1.4, "h", 0.95),
    # Let's Do WilderNature
    "wildernature:bison": (1.9, "h", 0.86), "wildernature:boar": (0.9, "h", 0.82), "wildernature:cassowary": (1.7, "h", 1.2),
    "wildernature:deer": (2.0, "h", 1.15), "wildernature:flamingo": (1.3, "h", 1.1), "wildernature:hedgehog": (0.25, "l", 0.85),
    "wildernature:owl": (0.4, "h", 0.45), "wildernature:pelican": (1.5, "h", 1.4), "wildernature:penguin": (0.8, "h", 0.9),
    "wildernature:raccoon": (0.4, "h", 0.7), "wildernature:red_wolf": (0.8, "h", 0.9), "wildernature:squirrel": (0.4, "l", 0.45),
    "wildernature:turkey": (1.0, "h", 1.0),
}

# 08/11/2026 (Maxime) : les petits animaux un peu agrandis, pour ne pas avoir la taille d'un insecte
def affichee(reelle):
    """Taille affichée d'un animal (hors insectes) : réelle à partir de 0,6 m, un peu agrandie en dessous, 0,3 minimum."""
    return reelle if reelle >= 0.6 else max(0.3, 0.6 * (reelle / 0.6) ** 0.45)


def facteur(reelle, mesure, f):
    return f if mesure == "i" else f * affichee(reelle) / reelle


# créatures en plusieurs morceaux ou à modèle propre, réglées à l'œil (le rendu suit, pas la collision des morceaux)
T.update({
    "alexsmobs:cachalot_whale": (16.0, "l", 1.6),
    "alexsmobs:giant_squid": (10.0, "l", 2.0),
})

if __name__ == "__main__":
    sortie = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../src/main/resources/domaine_terre/faune/tailles.json")
    d = {"_": "facteur de taille par créature (1 = inchangé), outils/faune/tailles.py ; remplaçable par config/domaine_terre_tailles.json",
         "facteurs": {k: round(facteur(*v), 3) for k, v in sorted(T.items()) if abs(facteur(*v) - 1.0) > 0.01}}
    json.dump(d, open(sortie, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(len(d["facteurs"]), "facteurs ->", os.path.normpath(sortie))

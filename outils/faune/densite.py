"""Densité de vie des biomes du mod Terre (07/11/2026, décision de Maxime : la nature comme si l'homme n'existait pas,
plus ou moins riche selon le milieu réel). Règle « creature_spawn_probability » de chaque biome de terroir : à la
génération d'un chunk, le jeu fait naître un groupe d'animaux tant qu'un tirage reste sous cette probabilité
(0,1 dans le jeu de base). Lancer après copies_biomes.py (qui recrée les biomes). Usage : python3 outils/faune/densite.py
"""
import glob, json, os

ICI = os.path.dirname(os.path.abspath(__file__))
BIOMES = os.path.join(ICI, "../../src/main/resources/data/domaine_terre/worldgen/biome")

# richesse du milieu (biome du jeu) : grands troupeaux des savanes et prairies, vie des rives et des marais,
# forêts moyennes (les bêtes s'y cachent), déserts, glaces et sommets presque vides
MILIEU = {
    "savanna": 0.20, "savanna_plateau": 0.18, "windswept_savanna": 0.15,
    "plains": 0.13, "sunflower_plains": 0.13, "meadow": 0.12,
    "swamp": 0.15, "mangrove_swamp": 0.15, "fleuve": 0.16, "lac": 0.14,
    "forest": 0.10, "birch_forest": 0.10, "old_growth_birch_forest": 0.10, "flower_forest": 0.11, "dark_forest": 0.09,
    "cherry_grove": 0.10,
    "jungle": 0.12, "sparse_jungle": 0.12, "bamboo_jungle": 0.11,
    "taiga": 0.08, "old_growth_pine_taiga": 0.08, "old_growth_spruce_taiga": 0.08, "windswept_forest": 0.07,
    "snowy_taiga": 0.05, "grove": 0.05,
    "beach": 0.08, "stony_shore": 0.07, "snowy_beach": 0.06,
    "windswept_hills": 0.06, "windswept_gravelly_hills": 0.05,
    "snowy_plains": 0.04, "ice_spikes": 0.01,
    "desert": 0.03, "badlands": 0.03, "wooded_badlands": 0.04, "eroded_badlands": 0.02,
    "snowy_slopes": 0.03, "stony_peaks": 0.02, "jagged_peaks": 0.02, "frozen_peaks": 0.01,
}
# terroirs plus riches ou plus pauvres que la moyenne de leur milieu
TERROIR = {
    "afrique_est": 1.5, "afrique_australe": 1.3, "grandes_plaines": 1.3, "amazonie": 1.1, "afrique_tropicale": 1.1,
    "asie_sud_est": 1.1, "inde": 1.1, "australie": 1.1, "boreale": 1.0, "siberie": 0.9, "steppes_tibet": 0.8,
    "sahara_sahel": 0.8, "moyen_orient": 0.8, "arctique": 0.8, "antarctique": 0.3,
}

if __name__ == "__main__":
    n = 0
    for f in sorted(glob.glob(os.path.join(BIOMES, "*", "*.json"))):
        terroir, nom = os.path.basename(os.path.dirname(f)), os.path.basename(f)[:-5]
        if terroir == "mer" or nom not in MILIEU:
            continue
        p = round(min(0.35, MILIEU[nom] * TERROIR.get(terroir, 1.0)), 3)
        texte = open(f, encoding="utf-8").read()
        d = json.loads(texte)
        if d.get("creature_spawn_probability") == p:
            continue
        d["creature_spawn_probability"] = p
        sortie = json.dumps(d, ensure_ascii=False, indent=1) + ("\n" if texte.endswith("\n") else "")
        open(f, "w", encoding="utf-8").write(sortie)
        n += 1
    print("densité réglée dans", n, "biomes")

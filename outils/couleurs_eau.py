"""Couleurs des eaux du mod Terre (décision de Maxime, 04/11/2026).

1. Eaux douces et côtes des terres : une couleur par terroir (fleuves boueux d'Amazonie, du Huang He, du Mékong,
   lacs glaciaires turquoise des Alpes, eaux sombres et tanniques de la forêt boréale…). Marais et mangroves gardent
   leur eau trouble. Les terroirs aux grands fleuves boueux passent dans #minecraft:has_closer_water_fog
   (on y voit moins loin sous l'eau).
2. Océans : 20 biomes domaine_terre:mer/<température>_<profondeur>, copiés des océans vanilla 1.20.1, du lagon
   turquoise à l'abysse presque noir. Le mod choisit la bande selon la vraie profondeur du fond (TerroirBiomeSource).

Usage : python3 outils/couleurs_eau.py <dossier data/minecraft vanilla 1.20.1 (misode/mcmeta, tag 1.20.1-data)>
Relancer l'outil est sans danger (il réécrit les mêmes valeurs).
"""
import glob
import json
import os
import sys

VAN = sys.argv[1]
RES = "src/main/resources"
BIO = f"{RES}/data/domaine_terre/worldgen/biome"
TROUBLES = {"swamp", "mangrove_swamp"}
RETIRES = {"minecraft:lake_lava_surface", "minecraft:lake_lava_underground", "minecraft:spring_water",
           "minecraft:spring_lava", "minecraft:spring_lava_frozen", "minecraft:monster_room", "minecraft:monster_room_deep"}


def rgb(h):
    return int(h, 16)


def charger(p):
    return json.load(open(p, encoding="utf-8"))


def ecrire(p, d):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(d, open(p, "w", encoding="utf-8"), indent=1, ensure_ascii=False)


# ---------------------------------------------------------------- 1. eaux des terroirs (surface, brouillard sous l'eau)
TERROIRS = {
    "atlantique": ("3F76E4", "050533"), "mediterranee": ("3A9FE0", "06304A"), "continentale": ("4A7FB4", "0B2633"),
    "nordique": ("2F5370", "0A1A26"), "alpine": ("3FCFC4", "0C4A50"), "maghreb": ("4A9AC4", "0A3040"),
    "sahara_sahel": ("9C8656", "3A2F1C"), "afrique_tropicale": ("7A5A38", "2A1E10"), "afrique_est": ("5E8A6A", "1E3022"),
    "afrique_australe": ("6E7E58", "24281A"), "moyen_orient": ("4AA2B4", "0C3540"), "steppes_tibet": ("3FBCD4", "0D4452"),
    "siberie": ("2F4A60", "0B1822"), "inde": ("8A8858", "2E2C1A"), "chine": ("B09852", "463818"),
    "japon_coree": ("3F86C4", "072A40"), "asie_sud_est": ("98784A", "342616"), "boreale": ("3C4C40", "10170F"),
    "grandes_plaines": ("6E7A58", "24281A"), "ouest_mexique": ("3F8CC4", "0A2C40"), "amerique_centrale": ("42A4AC", "0C383C"),
    "amazonie": ("A27A46", "3A2812"), "andes": ("3FAEBE", "0E3C46"), "cone_sud": ("4A8CAE", "0E2E3C"),
    "australie": ("7A8866", "262C1E"), "nouvelle_zelande": ("3FB8C6", "0E4048"), "melanesie": ("42A6AE", "0C3A3E"),
    "arctique": ("3D57D6", "050533"), "antarctique": ("3938C9", "050533"),
}
BOUEUX = ["amazonie", "afrique_tropicale", "asie_sud_est", "chine", "inde", "sahara_sahel"]

n = 0
for t, (eau, brume) in TERROIRS.items():
    for p in glob.glob(f"{BIO}/{t}/*.json"):
        if os.path.basename(p)[:-5] in TROUBLES or p.endswith("/lac.json"):
            continue
        d = charger(p)
        d["effects"]["water_color"], d["effects"]["water_fog_color"] = rgb(eau), rgb(brume)
        ecrire(p, d)
        n += 1
print("biomes de terre recolorés :", n)

# ---------------------------------------------------------------- 2. océans par température et profondeur
# bandes : cote (fond à moins de 6 blocs), plateau (6-20), large (jusqu'à y 0), abysse (fosses, fond sous y 0)
BANDES = ["cote", "plateau", "large", "abysse"]
MERS = {  # température : (biome vanilla peu profond, biome vanilla profond, [(eau, brume) par bande])
    "chaude": ("warm_ocean", "warm_ocean",
               [("4FE3D6", "0E5560"), ("33C2E0", "07384A"), ("1F86C7", "042436"), ("0F3E8A", "010A1A")]),
    "tiede": ("lukewarm_ocean", "deep_lukewarm_ocean",
              [("52D4D0", "0F4C5A"), ("3FA6E8", "063049"), ("2D72C9", "041C33"), ("173A80", "010818")]),
    "temperee": ("ocean", "deep_ocean",
                 [("4A9FD0", "0B3A4D"), ("3F76E4", "062A45"), ("2A4FB8", "03132E"), ("14266E", "010614")]),
    "froide": ("cold_ocean", "deep_cold_ocean",
               [("4D86B8", "0A2D40"), ("3D57D6", "051E3A"), ("2D3FA6", "030F2A"), ("182264", "010411")]),
    "gelee": ("frozen_ocean", "deep_frozen_ocean",
              [("5C7FB0", "0C2238"), ("3938C9", "051633"), ("2B2C93", "030B26"), ("17185E", "01030F")]),
}
NOMS = {"chaude": ("mer chaude", "warm sea"), "tiede": ("mer tiède", "lukewarm sea"),
        "temperee": ("mer tempérée", "temperate sea"), "froide": ("mer froide", "cold sea"),
        "gelee": ("mer gelée", "frozen sea")}
NOMS_B = {"cote": ("côtière", "shallows"), "plateau": ("du plateau", "shelf"), "large": ("du large", "open"),
          "abysse": ("abyssale", "abyss")}

# appartenance des océans vanilla aux tags (références #tag résolues), hors structures (retirées par le mod)
tags_van = {}
for p in glob.glob(f"{VAN}/tags/worldgen/biome/**/*.json", recursive=True):
    nom = os.path.relpath(p, f"{VAN}/tags/worldgen/biome")[:-5]
    if nom.startswith("has_structure"):
        continue
    tags_van[nom] = charger(p)["values"]


def membres(tag, vus=()):
    out = set()
    for v in tags_van.get(tag, []):
        v = v["id"] if isinstance(v, dict) else v
        if v.startswith("#minecraft:"):
            if v[11:] not in vus:
                out |= membres(v[11:], vus + (tag,))
        else:
            out.add(v)
    return out


appartient = {t: membres(t) for t in tags_van}
ajouts = {}  # chemin du fichier de tag -> biomes à ajouter
langs = {l: charger(f"{RES}/assets/domaine_terre/lang/{l}.json") for l in ("fr_fr", "en_us")}
for temp, (peu, prof, couleurs) in MERS.items():
    for i, b in enumerate(BANDES):
        src = peu if i < 2 else prof
        d = charger(f"{VAN}/worldgen/biome/{src}.json")
        d["effects"]["water_color"], d["effects"]["water_fog_color"] = rgb(couleurs[i][0]), rgb(couleurs[i][1])
        # hasard vanilla retiré comme dans les copies de terroir (Terre 0.3.2) : sources, salles à monstres, grottes
        d["features"] = [[f for f in etape if f not in RETIRES] for etape in d["features"]]
        d["carvers"] = {}
        cle = f"mer/{temp}_{b}"
        ecrire(f"{BIO}/{cle}.json", d)
        rl = f"domaine_terre:{cle}"
        for tag, m in appartient.items():
            if f"minecraft:{src}" in m:
                ajouts.setdefault(f"{RES}/data/minecraft/tags/worldgen/biome/{tag}.json", []).append(rl)
        ajouts.setdefault(f"{RES}/data/forge/tags/worldgen/biome/is_water.json", []).append(rl)
        if temp in ("froide", "gelee"):
            ajouts.setdefault(f"{RES}/data/forge/tags/worldgen/biome/is_cold.json", []).append(rl)
        if temp == "chaude":
            ajouts.setdefault(f"{RES}/data/forge/tags/worldgen/biome/is_hot.json", []).append(rl)
        fr = f"{NOMS[temp][0].capitalize()} {NOMS_B[b][0]}"
        en = f"{NOMS[temp][1].capitalize()} {NOMS_B[b][1]}"
        langs["fr_fr"][f"biome.domaine_terre.mer.{temp}_{b}"] = fr
        langs["en_us"][f"biome.domaine_terre.mer.{temp}_{b}"] = en

# eaux boueuses : visibilité réduite sous l'eau (comme les marais)
for t in BOUEUX:
    for p in glob.glob(f"{BIO}/{t}/*.json"):
        if p.endswith("/lac.json"):
            continue
        ajouts.setdefault(f"{RES}/data/minecraft/tags/worldgen/biome/has_closer_water_fog.json", []).append(
            f"domaine_terre:{t}/{os.path.basename(p)[:-5]}")

for p, vals in ajouts.items():
    d = charger(p) if os.path.exists(p) else {"replace": False, "values": []}
    for v in vals:
        if v not in d["values"]:
            d["values"].append(v)
    ecrire(p, d)
for l, d in langs.items():
    ecrire(f"{RES}/assets/domaine_terre/lang/{l}.json", d)
print("biomes de mer :", len(MERS) * len(BANDES), "; fichiers de tags touchés :", len(ajouts))

# ---------------------------------------------------------------- 3. lacs : un biome « lac » par terroir, eau plus claire
# (décision du 04/11 : les lacs ne prennent plus l'eau boueuse des fleuves ; les cénotes et lacs célèbres auront
# leur propre biome de lieu). Le mod le pose sur les colonnes sous l'eau d'un lac (TerroirBiomeSource).
LACS = {"amazonie": ("6E8A5A", "22301C"), "afrique_tropicale": ("5A7A5A", "1C281C"), "asie_sud_est": ("5E8A6E", "1E2E22"),
        "chine": ("4A8AB0", "0E2C3A"), "inde": ("5A8A8A", "1C2E2E"), "sahara_sahel": ("4A9AAE", "0E3440"),
        "afrique_est": ("4E8A86", "102C2A"), "afrique_australe": ("4A8A9E", "0E2C34"), "grandes_plaines": ("4A7EA8", "0E2836"),
        "australie": ("4E8EA0", "102E36"), "siberie": ("2F6FB0", "082440"), "boreale": ("34505A", "0E181C")}
SOURCES_LAC = ["plains", "forest", "taiga", "savanna", "jungle", "desert", "snowy_plains", "meadow"]
NS_P = f"{RES}/data/minecraft/worldgen/noise_settings/overworld.json"
ns = charger(NS_P)
tags_mod = {p: charger(p) for p in glob.glob(f"{RES}/data/*/tags/worldgen/biome/**/*.json", recursive=True)}
noms_t = {t["cle"]: t["nom"] for t in charger(f"{RES}/domaine_terre/carte/terroirs.json")}


def completer_biome_is(o, ancien, nouveau):
    if isinstance(o, dict):
        if o.get("type") == "minecraft:biome" and isinstance(o.get("biome_is"), list) and ancien in o["biome_is"]:
            if nouveau not in o["biome_is"]:
                o["biome_is"].append(nouveau)
        for v in o.values():
            completer_biome_is(v, ancien, nouveau)
    elif isinstance(o, list):
        for v in o:
            completer_biome_is(v, ancien, nouveau)


for t in TERROIRS:
    src = next((b for b in SOURCES_LAC if os.path.exists(f"{BIO}/{t}/{b}.json")), None)
    if src is None:
        print("pas de lac pour", t)
        continue
    d = charger(f"{BIO}/{t}/{src}.json")
    eau, brume = LACS.get(t, TERROIRS[t])
    d["effects"]["water_color"], d["effects"]["water_fog_color"] = rgb(eau), rgb(brume)
    ecrire(f"{BIO}/{t}/lac.json", d)
    ancien, nouveau = f"domaine_terre:{t}/{src}", f"domaine_terre:{t}/lac"
    for p, tg in tags_mod.items():
        if p.endswith("has_closer_water_fog.json"):
            continue
        if ancien in tg["values"] and nouveau not in tg["values"]:
            tg["values"].append(nouveau)
            ecrire(p, tg)
    completer_biome_is(ns["surface_rule"], ancien, nouveau)
    langs["fr_fr"][f"biome.domaine_terre.{t}.lac"] = f"Lac ({noms_t[t]})"
    langs["en_us"][f"biome.domaine_terre.{t}.lac"] = f"Lake ({noms_t[t]})"
ecrire(NS_P, ns)
for l, d in langs.items():
    ecrire(f"{RES}/assets/domaine_terre/lang/{l}.json", d)
print("lacs : un biome par terroir")

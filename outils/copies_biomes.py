"""Complète les copies de biomes par terroir pour la carte des biomes fixe (à lancer après carte_biomes.py).

Pour chaque couple terroir/biome utilisé par biomes.png sans copie domaine_terre:<terroir>/<biome> :
  - crée la copie à partir d'une copie existante du même biome (faune régionale refiltrée) ;
  - l'ajoute à terroirs_biomes.json, aux tags (vanilla, Forge, c, terroir), aux règles de surface et aux noms.
Puis règle la température des copies (neige.json) : pas de neige là où il n'y en a pas en vrai.
Ne retire jamais rien : relancer l'outil est sans danger.
"""
import glob
import json
import os

RES = "src/main/resources"
CARTE = f"{RES}/domaine_terre/carte"
BIO = f"{RES}/data/domaine_terre/worldgen/biome"
TROPIQUES = ["amazonie", "amerique_centrale", "asie_sud_est", "afrique_tropicale", "inde", "melanesie"]
VANILLA_REGIONAUX = {"minecraft:panda": ["chine"], "minecraft:llama": ["andes", "steppes_tibet"],
                     "minecraft:parrot": TROPIQUES, "minecraft:ocelot": TROPIQUES, "minecraft:polar_bear": ["arctique"]}

terroirs = json.load(open(f"{CARTE}/terroirs.json", encoding="utf-8"))
noms_terroirs = {t["cle"]: t["nom"] for t in terroirs}
listes = json.load(open(f"{CARTE}/terroirs_biomes.json", encoding="utf-8"))
neige = json.load(open(f"{CARTE}/neige.json", encoding="utf-8"))

def charger(p):
    return json.load(open(p, encoding="utf-8"))

# hasard vanilla retiré (Terre 0.3.2) : on le réimplantera à notre façon
# (registre : notes/retire-vanilla.md)
RETIRES = {"minecraft:lake_lava_surface", "minecraft:lake_lava_underground", "minecraft:spring_water",
           "minecraft:spring_lava", "minecraft:spring_lava_frozen", "minecraft:monster_room", "minecraft:monster_room_deep"}


def ecrire(p, d):
    if isinstance(d, dict) and isinstance(d.get("features"), list):
        d["features"] = [[f for f in etape if f not in RETIRES] for etape in d["features"]]
        d["carvers"] = {}                                   # grottes et ravins retirés
    json.dump(d, open(p, "w", encoding="utf-8"), indent=1, ensure_ascii=False)

# fichiers à compléter
tags = {p: charger(p) for p in glob.glob(f"{RES}/data/*/tags/worldgen/biome/**/*.json", recursive=True)}
ns_p = f"{RES}/data/minecraft/worldgen/noise_settings/overworld.json"
ns = charger(ns_p)
langs = {l: charger(f"{RES}/assets/domaine_terre/lang/{l}.json") for l in ("fr_fr", "en_us")}

def modele(b):
    for cle in listes:
        if b in listes[cle] and os.path.exists(f"{BIO}/{cle}/{b}.json"):
            return cle
    return None

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

crees = []
for cle, utilises in neige["utilisation"].items():
    for b in utilises:
        if os.path.exists(f"{BIO}/{cle}/{b}.json"):
            if b not in listes[cle]:
                listes[cle].append(b)
            continue
        m = modele(b)
        if m is None:
            print("ATTENTION : aucune copie modèle pour", b)
            continue
        j = charger(f"{BIO}/{m}/{b}.json")
        for groupe, liste in j.get("spawners", {}).items():
            j["spawners"][groupe] = [sp for sp in liste if cle in VANILLA_REGIONAUX.get(sp["type"], [cle])]
        os.makedirs(f"{BIO}/{cle}", exist_ok=True)
        ecrire(f"{BIO}/{cle}/{b}.json", j)
        ancien, nouveau = f"domaine_terre:{m}/{b}", f"domaine_terre:{cle}/{b}"
        for p, t in tags.items():
            if p.endswith(f"terroir/{m}.json"):
                continue
            if ancien in t["values"] and nouveau not in t["values"]:
                t["values"].append(nouveau)
        tt = tags.get(f"{RES}/data/domaine_terre/tags/worldgen/biome/terroir/{cle}.json")
        if tt is not None and nouveau not in tt["values"]:
            tt["values"].append(nouveau)
        completer_biome_is(ns["surface_rule"], ancien, nouveau)
        for l, d in langs.items():
            nom = d.get(f"biome.domaine_terre.{m}.{b}", b).rsplit(" (", 1)[0]
            d[f"biome.domaine_terre.{cle}.{b}"] = f"{nom} ({noms_terroirs[cle]})"
        listes[cle].append(b)
        crees.append(f"{cle}/{b}")

for p, t in tags.items():
    t["values"] = sorted(set(t["values"]), key=t["values"].index)
    ecrire(p, t)
ecrire(ns_p, ns)
for l, d in langs.items():
    ecrire(f"{RES}/assets/domaine_terre/lang/{l}.json", d)
ecrire(f"{CARTE}/terroirs_biomes.json", listes)

# températures : limite des neiges réelle
reglees = []
for copie, tmin in neige["temperature_min"].items():
    p = f"{BIO}/{copie}.json"
    if not os.path.exists(p):
        continue
    j = charger(p)
    if j["temperature"] < tmin:
        reglees.append(f"{copie} {j['temperature']} -> {tmin}")
        j["temperature"] = tmin
        ecrire(p, j)

print(f"{len(crees)} copies créées :", ", ".join(crees))
print(f"{len(reglees)} températures relevées :")
for r in reglees:
    print("  ", r)

# grès sur les pentes raides des déserts : le sable seulement sur le plat (plus de murs de sable verticaux)
def est_regle_gres(r):
    try:
        return r["then_run"]["if_true"]["type"] == "minecraft:steep" and \
            r["then_run"]["then_run"]["then_run"]["result_state"]["Name"] == "minecraft:sandstone"
    except (KeyError, TypeError):
        return False
def biomes_desert():
    noms = ["minecraft:desert"]
    for cle in listes:
        if "desert" in listes[cle] and os.path.exists(f"{BIO}/{cle}/desert.json"):
            noms.append(f"domaine_terre:{cle}/desert")
    return noms
seq = ns["surface_rule"]["sequence"][1]["then_run"]["sequence"]
seq[:] = [r for r in seq if not est_regle_gres(r)]
seq.insert(0, {"type": "minecraft:condition",
               "if_true": {"type": "minecraft:biome", "biome_is": biomes_desert()},
               "then_run": {"type": "minecraft:condition", "if_true": {"type": "minecraft:steep"},
                            "then_run": {"type": "minecraft:condition",
                                         "if_true": {"type": "minecraft:stone_depth", "offset": 0, "add_surface_depth": True,
                                                     "secondary_depth_range": 0, "surface_type": "floor"},
                                         "then_run": {"type": "minecraft:block",
                                                      "result_state": {"Name": "minecraft:sandstone"}}}}})
ecrire(ns_p, ns)
print("règle grès :", len(biomes_desert()), "biomes désert")

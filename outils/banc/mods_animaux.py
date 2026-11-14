"""Mods d'animaux du pack pour le serveur du banc (10/11/2026).

Mêmes fichiers que l'instance « Refonte d'Aubin » (noms exacts), pris sur Modrinth, sinon sur le CDN de CurseForge
(Untamed Wilds n'est que sur CurseForge). Un mod dont une dépendance obligatoire manque est retiré (avertissement)
au lieu de faire planter le serveur. Sert au banc de la faune (vraies bêtes de tous les mods) et à l'export des
tailles d'origine de toutes les créatures (domaine_tailles.csv, écrit par le mod Terre au démarrage).

Usage : python3 outils/banc/mods_animaux.py <dossier mods>
"""
import json, os, re, sys, time, urllib.parse, urllib.request, zipfile

DEST = sys.argv[1]
UA = {"User-Agent": "theMitch37/domaine-terre banc (github.com/theMitch37/domaine-terre)"}

# fichier exact -> (projets Modrinth possibles, numéros de fichier CurseForge possibles)
MODS = {
    "alexsmobs-1.22.9.jar": (["alexs-mobs"], []),
    "citadel-2.6.3-1.20.1.jar": (["citadel"], []),
    "untamedwilds-1.20.1-4.0.4.jar": ([], [4790009, 4779746, 4767281, 4766547, 4723081, 4718771, 4709636]),
    "naturalist-2.0.9-forge-1.20.1.jar": (["naturalist"], []),          # 14/11 : baudroie abyssale
    "geckolib-forge-1.20.1-4.8.4.jar": (["geckolib"], []),
    "letsdo-wildernature-forge-1.0.6.jar": (["lets-do-wildernature", "wildernature"], []),
    "letsdo-meadow-forge-1.3.25.jar": (["lets-do-meadow", "meadow"], []),
    "letsdo-API-forge-1.2.15-forge.jar": (["lets-do-api", "letsdo-api"], []),
    "architectury-9.2.14-forge.jar": (["architectury-api"], []),
    "ecologics-forge-1.20.1-2.2.7.jar": (["ecologics"], []),
    "Aquaculture-1.20.1-2.5.7.jar": (["aquaculture", "aquaculture-2"], []),
    "savage_and_ravage-1.20.1-6.0.1.jar": (["savage-and-ravage"], []),
    "blueprint-1.20.1-7.1.5.jar": (["blueprint"], []),
    "betteranimalsplus-1.20.1-1.1-1.20.1-forge.jar": (["better-animals-plus", "betteranimalsplus", "best-revived-animals"], []),
    "crittersandcompanions-forge-1.20.1-2.7.1.jar": (["critters-and-companions"], []),
    "curios-forge-5.14.1+1.20.1.jar": (["curios"], []),
    "mysterious_mountain_lib-1.6.34-1.20.1.jar": (["mysterious-mountain-lib"], []),
    "FarmersDelight-1.20.1-1.3.4.jar": (["farmers-delight"], []),
    "OpenLoader-Forge-1.20.1-19.0.5.jar": (["open-loader", "openloader"], []),       # datapack domaine_terroirs
    "yet_another_config_lib_v3-3.6.6+1.20.1-forge.jar": (["yacl"], []),              # Critters and Companions
}


def lire(url, essais=3):
    for i in range(essais):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            if "404" in str(e):
                return None
            time.sleep(4 * (i + 1))
    return None


def modrinth(slugs, fichier):
    q = urllib.parse.urlencode({"loaders": '["forge"]', "game_versions": '["1.20.1"]'})
    for slug in slugs:
        v = lire(f"https://api.modrinth.com/v2/project/{slug}/version?{q}")
        if not v:
            continue
        for ver in json.loads(v):
            for f in ver["files"]:
                if f["filename"] == fichier:
                    return f["url"]
    return None


def curseforge(ids, fichier):
    for i in ids:
        url = f"https://mediafilez.forgecdn.net/files/{i // 1000}/{i % 1000}/{urllib.parse.quote(fichier)}"
        b = lire(url, 2)
        if b and b[:2] == b"PK":
            return url, b
    return None, None


def mod_ids(chemin):
    """modId et dépendances obligatoires (META-INF/mods.toml) d'un jar."""
    try:
        t = zipfile.ZipFile(chemin).read("META-INF/mods.toml").decode("utf-8", "ignore")
    except Exception:  # noqa: BLE001
        return set(), set()
    ids = set(re.findall(r'\[\[mods\]\][^\[]*?modId\s*=\s*"([^"]+)"', t, re.S))
    deps = set()
    for bloc in re.split(r"\[\[dependencies\.", t)[1:]:
        m = re.search(r'modId\s*=\s*"([^"]+)"', bloc)
        ob = re.search(r"mandatory\s*=\s*(true|false)", bloc)
        ty = re.search(r'type\s*=\s*"(\w+)"', bloc)
        obligatoire = (ob and ob.group(1) == "true") or (ty and ty.group(1).lower() == "required")
        if m and obligatoire:
            deps.add(m.group(1))
    return ids, deps


os.makedirs(DEST, exist_ok=True)
for fichier, (slugs, ids) in MODS.items():
    url = modrinth(slugs, fichier)
    b = lire(url) if url else None
    if not b:
        url, b = curseforge(ids, fichier)
    if not b:
        print(f"::warning::{fichier} introuvable (Modrinth et CurseForge)")
        continue
    open(os.path.join(DEST, fichier), "wb").write(b)
    print("téléchargé", fichier, "<-", url.split("/")[2])

# dépendances : retire ce qui ne peut pas démarrer (le jeu de base, Forge et notre mod sont toujours là)
presents = {"minecraft", "forge", "domaine_terre", "domaine_terre_lieux"}
jars = {j: mod_ids(os.path.join(DEST, j)) for j in os.listdir(DEST) if j.endswith(".jar")}
for ids, _ in jars.values():
    presents |= ids
retire = True
while retire:
    retire = False
    for j, (ids, deps) in list(jars.items()):
        manque = deps - presents
        if manque:
            print(f"::warning::{j} retiré : dépendance absente {sorted(manque)}")
            os.remove(os.path.join(DEST, j))
            del jars[j]
            presents -= ids
            retire = True
print(len(jars), "mods d'animaux et dépendances sur le serveur")

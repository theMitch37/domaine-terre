"""Mods de cultures du pack pour le banc des plantes (13/11/2026).

Prend sur Modrinth la version Forge 1.20.1 la plus récente de chaque mod (projet trouvé par son identifiant, sinon
par une recherche sur son nom) et ses dépendances obligatoires. Les versions peuvent différer de celles de
l'instance « Refonte d'Aubin » : le banc vérifie les règles de placement, pas une version précise.

Usage : python3 outils/banc/plantes_mods.py <dossier mods>
"""
import json, os, sys, urllib.parse, urllib.request, time

DEST = sys.argv[1]
UA = {"User-Agent": "theMitch37/domaine-terre banc (github.com/theMitch37/domaine-terre)"}
API = "https://api.modrinth.com/v2"
# nom lisible : identifiants Modrinth possibles (le premier qui existe)
MODS = {
    "Farmer's Delight": ["farmers-delight"],
    "Let's Do Farm & Charm": ["lets-do-farm-charm", "farm-and-charm"],
    "Let's Do Bakery": ["lets-do-bakery", "bakery"],
    "Let's Do Brewery": ["lets-do-brewery", "brewery"],
    "Let's Do Vinery": ["lets-do-vinery", "vinery"],
    "Let's Do HerbalBrews": ["lets-do-herbalbrews", "herbalbrews"],
    "Let's Do WilderNature": ["lets-do-wildernature", "wildernature"],
    "Let's Do Meadow": ["lets-do-meadow", "meadow"],
    "Cultural Delights": ["cultural-delights"],
    "Corn Delight": ["corn-delight"],
    "Rice Delight": ["rice-delight"],
    "Ramadan Delight": ["ramadan-delight"],
    "Supplementaries": ["supplementaries"],
    "Ecologics": ["ecologics"],
    "OpenLoader": ["open-loader", "openloader"],      # datapack domaine_terroirs (config/openloader/data)
}
Q = urllib.parse.urlencode({"loaders": '["forge"]', "game_versions": '["1.20.1"]'})


def lire(url):
    for i in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            if "404" in str(e):
                return None
            time.sleep(4 * (i + 1))
    return None


def versions(projet):
    v = lire(f"{API}/project/{projet}/version?{Q}")
    return json.loads(v) if v else []


def chercher(nom):
    f = urllib.parse.quote(json.dumps([["versions:1.20.1"], ["categories:forge"], ["project_type:mod"]]))
    r = lire(f"{API}/search?query={urllib.parse.quote(nom)}&facets={f}&limit=1")
    hits = json.loads(r)["hits"] if r else []
    return hits[0]["project_id"] if hits else None


pris = set()


def prendre(projet, nom, profondeur=0):
    if projet in pris or profondeur > 4:
        return
    vs = versions(projet)
    if not vs:
        print(f"::warning::{nom} ({projet}) : aucune version Forge 1.20.1")
        return
    v = vs[0]
    pris.add(projet)
    f = next((x for x in v["files"] if x.get("primary")), v["files"][0])
    b = lire(f["url"])
    if not b:
        print(f"::warning::{nom} : téléchargement raté")
        return
    open(os.path.join(DEST, f["filename"]), "wb").write(b)
    print(f"{'  ' * profondeur}{nom} -> {f['filename']}")
    for d in v.get("dependencies", []):
        if d.get("dependency_type") == "required" and d.get("project_id"):
            prendre(d["project_id"], "dépendance " + d["project_id"], profondeur + 1)


os.makedirs(DEST, exist_ok=True)
for nom, slugs in MODS.items():
    projet = next((s for s in slugs if versions(s)), None) or chercher(nom)
    if not projet:
        print(f"::warning::{nom} introuvable sur Modrinth")
        continue
    prendre(projet, nom)

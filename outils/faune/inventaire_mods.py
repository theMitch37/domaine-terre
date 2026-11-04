"""Inventaire des créatures des mods d'animaux du pack (Forge 1.20.1).

Lancé par le workflow « Inventaire faune » : télécharge chaque mod depuis Modrinth (ou CurseForge en secours),
puis lit dans le jar :
  - les noms des entités (fichiers de langue en_us / fr_fr, clés entity.<ns>.<nom>) ;
  - les œufs d'apparition (= créatures vivantes, pas projectiles ni objets) ;
  - les règles de spawn livrées dans le jar (biome modifiers forge:add_spawns : poids, taille de groupe, biomes) ;
  - les espèces d'Untamed Wilds (data/untamedwilds/entities/*.json).
Résultat : outils/faune/inventaire_mods.json (petit fichier commité sur la branche).
Usage : python3 outils/faune/inventaire_mods.py <dossier de travail>
"""
import io, json, os, re, sys, time, urllib.parse, urllib.request, zipfile

TRAVAIL = sys.argv[1]
os.makedirs(TRAVAIL, exist_ok=True)
SORTIE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "inventaire_mods.json")
UA = {"User-Agent": "domaine-terre-inventaire/1.0 (github.com/theMitch37/domaine-terre)"}

# nom lisible -> (requête Modrinth, slug CurseForge en secours)
MODS = {
    "Alex's Mobs": ("alexs-mobs", "alexs-mobs"),
    "Untamed Wilds": ("untamed-wilds", "untamed-wilds"),
    "Naturalist": ("naturalist", "naturalist"),
    "Let's Do WilderNature": ("lets-do-wildernature", "lets-do-wilder-nature"),
    "Let's Do Meadow": ("lets-do-meadow", "lets-do-meadow"),
    "Ecologics": ("ecologics", "ecologics"),
    "Aquaculture 2": ("aquaculture", "aquaculture"),
    "Critters and Companions": ("critters-and-companions", "critters-and-companions"),
}


def lire(url, essais=4):
    for i in range(essais):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            print("   échec", url, e)
            time.sleep(5 * (i + 1))
    return None


def modrinth(slug):
    """Dernier fichier Forge 1.20.1 du projet Modrinth `slug` -> (titre, version, url)."""
    p = lire(f"https://api.modrinth.com/v2/project/{slug}")
    if not p:
        return None
    titre = json.loads(p)["title"]
    q = urllib.parse.urlencode({"loaders": '["forge"]', "game_versions": '["1.20.1"]'})
    v = lire(f"https://api.modrinth.com/v2/project/{slug}/version?{q}")
    if not v:
        return None
    v = json.loads(v)
    if not v:
        return None
    f = next((f for f in v[0]["files"] if f.get("primary")), v[0]["files"][0])
    return titre, v[0]["version_number"], f["url"]


def curseforge(slug):
    """Secours sans clé : page de fichiers CurseForge -> lien de téléchargement direct du fichier Forge 1.20.1."""
    html = lire(f"https://www.curseforge.com/minecraft/mc-mods/{slug}/files/all?version=1.20.1&gameVersionTypeId=1")
    if not html:
        return None
    ids = re.findall(rf"/minecraft/mc-mods/{re.escape(slug)}/files/(\d{{6,}})", html.decode("utf-8", "ignore"))
    if not ids:
        return None
    fid = ids[0]
    return slug, fid, f"https://www.curseforge.com/api/v1/mods/{slug}/files/{fid}/download"


def json_jar(z, chemin):
    try:
        return json.loads(z.read(chemin).decode("utf-8-sig"))
    except Exception:  # noqa: BLE001
        return None


def analyser(z):
    noms = z.namelist()
    entites = {}
    for lang in ("en_us", "fr_fr"):
        for n in noms:
            if re.fullmatch(rf"assets/[^/]+/lang/{lang}\.json", n):
                d = json_jar(z, n) or {}
                for k, val in d.items():
                    m = re.fullmatch(r"entity\.([a-z0-9_]+)\.([a-z0-9_]+)", k)
                    if m:
                        entites.setdefault(f"{m[1]}:{m[2]}", {})[lang] = val
    oeufs = set()
    for n in noms:
        m = re.fullmatch(r"assets/([^/]+)/models/item/([a-z0-9_]+)_spawn_egg\.json", n)
        if m:
            oeufs.add(f"{m[1]}:{m[2]}")
    for e in entites:
        entites[e]["oeuf"] = e in oeufs
    for e in oeufs - set(entites):
        entites[e] = {"oeuf": True}

    spawns = []
    for n in noms:
        if not re.fullmatch(r"data/[^/]+/forge/biome_modifier/.+\.json", n):
            continue
        d = json_jar(z, n)
        if not isinstance(d, dict):
            continue
        sp = d.get("spawners")
        if sp is None:
            continue
        for s in sp if isinstance(sp, list) else [sp]:
            spawns.append({"fichier": n, "type": d.get("type"), "entite": s.get("type"), "poids": s.get("weight"),
                           "min": s.get("minCount"), "max": s.get("maxCount"), "biomes": d.get("biomes")})

    especes = {}
    for n in noms:
        m = re.fullmatch(r"data/untamedwilds/entities/([a-z0-9_]+)\.json", n)
        if m:
            d = json_jar(z, n) or {}
            especes[m[1]] = [{k: s.get(k) for k in ("name", "rarity", "groupCount", "spawnBiomes", "spawn_biomes")
                              if k in s} for s in d.get("species", [])]
    return {"entites": entites, "spawns": spawns, "especes_untamedwilds": especes}


resultat = {}
for nom, (mr, cf) in MODS.items():
    print("==", nom)
    src = modrinth(mr) or curseforge(cf)
    if not src:
        resultat[nom] = {"erreur": "introuvable"}
        continue
    titre, version, url = src
    data = lire(url)
    if not data:
        resultat[nom] = {"erreur": "téléchargement impossible", "url": url}
        continue
    with open(os.path.join(TRAVAIL, re.sub(r"[^A-Za-z0-9]+", "_", nom) + ".jar"), "wb") as f:
        f.write(data)
    r = analyser(zipfile.ZipFile(io.BytesIO(data)))
    r.update({"source": titre, "version": version, "url": url})
    resultat[nom] = r
    print("  ", titre, version, len(r["entites"]), "entités,", len(r["spawns"]), "règles de spawn")

json.dump(resultat, open(SORTIE, "w", encoding="utf-8"), indent=1, ensure_ascii=False, sort_keys=True)
print("->", SORTIE)

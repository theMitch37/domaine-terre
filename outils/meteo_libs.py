"""Bibliothèques de compilation de l'addon Domaine Weather (13/11/2026).

Télécharge depuis Modrinth les jars Forge 1.20.1 de Serene Seasons, GlitchCore, Weather2 et CoroUtil dans le
dossier donné (meteo/libs en CI). On vise les versions du pack (instance « Refonte d'Aubin ») ; si une version
exacte n'existe pas sur Modrinth, on prend la plus récente pour 1.20.1 / Forge et on le signale.

Usage : python3 outils/meteo_libs.py <dossier>
"""
import json, os, sys, urllib.parse, urllib.request

DEST = sys.argv[1]
UA = {"User-Agent": "theMitch37/domaine-terre meteo (github.com/theMitch37/domaine-terre)"}

# projet Modrinth -> numéro de version voulu (celui du pack), ou None pour le plus récent
MODS = {
    "serene-seasons": "9.1.0.3",
    "glitchcore": None,
    "weather-storms-tornadoes": "1.20.1-2.8.3",
    "coroutil": None,
}


def lire(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.read()


def main():
    os.makedirs(DEST, exist_ok=True)
    for projet, voulu in MODS.items():
        q = urllib.parse.urlencode({"game_versions": json.dumps(["1.20.1"]), "loaders": json.dumps(["forge"])})
        versions = json.loads(lire(f"https://api.modrinth.com/v2/project/{projet}/version?{q}"))
        if not versions:
            sys.exit(f"{projet} : aucune version 1.20.1 Forge sur Modrinth")
        choix = next((v for v in versions if voulu and v["version_number"] == voulu), None)
        if choix is None:
            choix = versions[0]
            if voulu:
                print(f"! {projet} : {voulu} introuvable, pris {choix['version_number']}")
        f = next((f for f in choix["files"] if f.get("primary")), choix["files"][0])
        chemin = os.path.join(DEST, f["filename"])
        with open(chemin, "wb") as o:
            o.write(lire(f["url"]))
        print(f"{projet} {choix['version_number']} -> {f['filename']}")


main()

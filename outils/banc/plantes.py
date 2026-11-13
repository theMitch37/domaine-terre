"""Banc des plantes (13/11/2026) : vrai serveur Forge avec Terre, les mods de cultures du pack et le datapack
« domaine_terroirs » (outils/generer_placement.py). Génère un carré de 320 blocs dans chaque terroir de test et
compte les blocs des plantes sauvages (et des arbres fruitiers des mods) : chaque plante doit pousser dans son
terroir d'origine et nulle part ailleurs (décision de Maxime : cultures endémiques).

Usage : python outils/banc/plantes.py <dossier_serveur> <sortie>
Sortie : plantes.txt (tableau plante x terroir), plantes.json, bilan.txt
"""
import collections, json, os, queue, re, subprocess, sys, threading, time
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import monde

SERVEUR, SORTIE = sys.argv[1], sys.argv[2]
FORGE = "1.20.1-47.4.10"
BPD = 445.28
COTE = 240                     # 15 × 15 chunks : /forceload en accepte 256 au plus
os.makedirs(SORTIE, exist_ok=True)
# terroir : (lat, lon) au cœur du terroir, loin des côtes
ZONES = {
    "moyen_orient": (35.0, 38.5), "andes": (-13.5, -72.0), "ouest_mexique": (20.5, -103.0), "chine": (29.5, 112.5),
    "mediterranee": (37.6, -4.2), "atlantique": (48.1, -2.5), "afrique_est": (-0.6, 36.6), "inde": (22.0, 78.0),
    "steppes_tibet": (48.5, 70.0), "continentale": (50.5, 10.5), "amerique_centrale": (15.6, -90.3),
    "afrique_australe": (-28.8, 26.5), "boreale": (58.0, -100.0), "cone_sud": (-31.5, -58.5),
    "afrique_tropicale": (6.0, 20.0), "maghreb": (33.9, -5.5), "grandes_plaines": (39.0, -97.5),
}
open(os.path.join(SERVEUR, "eula.txt"), "w").write("eula=true\n")
open(os.path.join(SERVEUR, "server.properties"), "w").write("\n".join([
    "online-mode=false", "level-seed=20261025", "level-name=plantes", "view-distance=3", "simulation-distance=3",
    "spawn-monsters=false", "spawn-animals=false", "max-tick-time=-1", "generate-structures=false",
    "sync-chunk-writes=false"]) + "\n")
journal = open(os.path.join(SORTIE, "serveur.log"), "w")
p = subprocess.Popen(["java", "-Xmx8G", f"@libraries/net/minecraftforge/forge/{FORGE}/unix_args.txt", "nogui"],
                     cwd=SERVEUR, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                     text=True, bufsize=1)
lignes = queue.Queue()


def lire():
    for l in p.stdout:
        journal.write(l); journal.flush(); lignes.put(l)
    lignes.put(None)


threading.Thread(target=lire, daemon=True).start()


def attendre(motif, delai):
    fin = time.time() + delai
    while time.time() < fin:
        try:
            l = lignes.get(timeout=5)
        except queue.Empty:
            continue
        if l is None:
            raise SystemExit("le serveur s'est arrêté")
        if motif in l:
            return l
    raise SystemExit(f"délai dépassé en attendant « {motif} »")


def cmd(c):
    journal.write(f">>> {c}\n"); p.stdin.write(c + "\n"); p.stdin.flush()


t0 = time.time()
attendre("Done (", 1500)
region = os.path.join(SERVEUR, "plantes", "region")
boites = {}
for nom, (la, lo) in ZONES.items():
    x, z = round(lo * BPD) // 16 * 16, round(-la * BPD) // 16 * 16   # calé sur les chunks
    boites[nom] = (x - COTE // 2 - 8, x + COTE // 2 - 8, z - COTE // 2 - 8, z + COTE // 2 - 8)
VANILLA = "minecraft:"
res = {}


def compter(nom, x0, x1, z0, z1):
    noms, blocs, _ = monde.extraire(region, x0, x1, z0, z1, 40, 330)
    n = np.bincount(blocs.ravel(), minlength=len(noms))
    res[nom] = {noms[i]: int(n[i]) for i in range(len(noms)) if n[i] and not noms[i].startswith(VANILLA)}
    json.dump(res, open(os.path.join(SORTIE, "plantes.json"), "w"), indent=1, ensure_ascii=False)


# 13/11 : chaque terroir est compté dès qu'il est généré (le premier passage n'avait rien écrit avant la fin)
for nom, (x0, x1, z0, z1) in boites.items():
    cmd(f"forceload add {x0} {z0} {x1 - 1} {z1 - 1}")
    voulus = ((x1 - 1) // 16 - x0 // 16 + 1) * ((z1 - 1) // 16 - z0 // 16 + 1)
    fin = time.time() + 600
    while True:
        time.sleep(15)
        cmd("save-all flush")
        attendre("Saved the game", 600)
        _, _, st = monde.extraire(region, x0, x1, z0, z1, 62, 63)
        faits = sum(1 for v in st.values() if v.endswith("full"))
        if faits >= voulus or time.time() > fin:
            break
    compter(nom, x0, x1, z0, z1)
    print(f"{nom} : {faits}/{voulus} chunks ({time.time() - t0:.0f} s) ; plantes des mods : "
          f"{sum(1 for b in res[nom] if not b.startswith('domaine_terre'))} sortes", flush=True)
    cmd("forceload remove all")
cmd("stop")
p.wait(timeout=600)

# plantes des mods trouvées : où ?
toutes = collections.defaultdict(dict)
for ter, d in res.items():
    for b, c in d.items():
        if b.startswith("domaine_terre"):
            continue
        toutes[b][ter] = c
with open(os.path.join(SORTIE, "plantes.txt"), "w") as f:
    for b in sorted(toutes):
        f.write(f"{b:55s} " + ", ".join(f"{t} {c}" for t, c in sorted(toutes[b].items(), key=lambda x: -x[1])) + "\n")
print(open(os.path.join(SORTIE, "plantes.txt")).read())
print(f"terminé en {time.time() - t0:.0f} s")

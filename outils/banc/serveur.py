"""Banc d'essai : lance un vrai serveur Forge avec les mods, génère les chunks des lieux, puis extrait leurs blocs.

Usage (GitHub Actions) : python outils/banc/serveur.py <dossier_serveur> <zones.json> <sortie>
Sortie : <sortie>/<lieu>.npz (noms, blocs[z, y, x], x0, y0, z0) + serveur.log
"""
import json, os, queue, subprocess, sys, threading, time
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import monde

SERVEUR, ZONES, SORTIE = sys.argv[1], sys.argv[2], sys.argv[3]
FORGE = "1.20.1-47.4.10"
Y0, Y1 = -64, 320                     # tout le monde en hauteur : fosses et sommets (y 300 pour l'Everest)
os.makedirs(SORTIE, exist_ok=True)
zones = {k: v for k, v in json.load(open(ZONES)).items() if not k.startswith("_")}
if len(sys.argv) > 4:
    zones = {k: zones[k] for k in sys.argv[4].split(",")}

with open(os.path.join(SERVEUR, "eula.txt"), "w") as f:
    f.write("eula=true\n")
with open(os.path.join(SERVEUR, "server.properties"), "w") as f:
    f.write("\n".join([
        "online-mode=false", "level-seed=20261025", "level-name=banc", "view-distance=3",
        "simulation-distance=3", "spawn-protection=0", "max-tick-time=-1", "spawn-monsters=false",
        "spawn-animals=false", "spawn-npcs=false", "generate-structures=true", "sync-chunk-writes=false"]) + "\n")

journal = open(os.path.join(SORTIE, "serveur.log"), "w")
p = subprocess.Popen(["java", "-Xmx12G", f"@libraries/net/minecraftforge/forge/{FORGE}/unix_args.txt", "nogui"],
                     cwd=SERVEUR, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                     text=True, bufsize=1)
lignes = queue.Queue()


def lire():
    for l in p.stdout:
        journal.write(l); journal.flush()
        lignes.put(l)
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
    journal.write(f">>> {c}\n")
    p.stdin.write(c + "\n"); p.stdin.flush()


t0 = time.time()
attendre("Done (", 900)
print(f"serveur prêt en {time.time() - t0:.0f} s", flush=True)

# chunks à générer, zone par zone, par lots de ~2 500 chunks au plus (au-delà, le serveur manque de mémoire) : on force
# un lot, on attend qu'il soit complet et enregistré, on libère ses chunks, puis le lot suivant
region = os.path.join(SERVEUR, "banc", "region")
lots, lot, taille = [], [], 0
for nom, (x0, x1, z0, z1) in zones.items():
    n = ((x1 - 1) // 16 - x0 // 16 + 1) * ((z1 - 1) // 16 - z0 // 16 + 1)
    if lot and taille + n > 2500:
        lots.append(lot); lot, taille = [], 0
    lot.append(nom); taille += n
if lot:
    lots.append(lot)
total = 0
for num, lot in enumerate(lots):
    voulus = set()
    for nom in lot:
        x0, x1, z0, z1 = zones[nom]
        cx0, cx1, cz0, cz1 = x0 >> 4, (x1 - 1) >> 4, z0 >> 4, (z1 - 1) >> 4
        for a in range(cx0, cx1 + 1, 16):
            for b in range(cz0, cz1 + 1, 16):
                e, s_ = min(a + 15, cx1), min(b + 15, cz1)
                cmd(f"forceload add {a * 16} {b * 16} {e * 16 + 15} {s_ * 16 + 15}")
                voulus |= {(i, j) for i in range(a, e + 1) for j in range(b, s_ + 1)}
    total += len(voulus)
    print(f"lot {num + 1}/{len(lots)} : {', '.join(lot)} — {len(voulus)} chunks", flush=True)
    fin = time.time() + 2400
    while True:
        time.sleep(20)
        cmd("save-all flush")
        attendre("Saved the game", 1200)
        faits = 0
        for nom in lot:
            x0, x1, z0, z1 = zones[nom]
            _, _, st = monde.extraire(region, x0, x1, z0, z1, 62, 63)
            faits += sum(1 for v in st.values() if v.endswith("full"))
        print(f"  {faits}/{len(voulus)} chunks complets ({time.time() - t0:.0f} s)", flush=True)
        if faits >= len(voulus) or time.time() > fin:
            break
    cmd("forceload remove all")
print(f"{total} chunks demandés en {len(lots)} lots", flush=True)

cmd("stop")
p.wait(timeout=600)
for nom, (x0, x1, z0, z1) in zones.items():
    noms, blocs, st = monde.extraire(region, x0, x1, z0, z1, Y0, Y1)
    np.savez_compressed(os.path.join(SORTIE, f"{nom}.npz"), noms=np.array(noms), blocs=blocs,
                        x0=x0, y0=Y0, z0=z0, statuts=np.array([f"{k[0]},{k[1]}={v}" for k, v in st.items()]))
    print(f"{nom} : {blocs.shape}, {len(noms)} sortes de blocs", flush=True)
print(f"terminé en {time.time() - t0:.0f} s", flush=True)

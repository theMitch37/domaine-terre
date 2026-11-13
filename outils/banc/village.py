"""Banc de Domaine Village (13/11/2026) : vrai serveur Forge avec Terre et Domaine Village.

Vérifie que le placement fixe se charge, puis demande /locate autour de villes de test : le village trouvé doit être
celui de villages.csv (même case, à quelques blocs près). Les pyramides (pas encore rallumées) ne doivent pas exister.

Usage : python outils/banc/village.py <dossier_serveur> <villages.csv> <sortie>
"""
import csv, math, os, queue, re, subprocess, sys, threading, time

SERVEUR, CSV, SORTIE = sys.argv[1], sys.argv[2], sys.argv[3]
FORGE = "1.20.1-47.4.10"
os.makedirs(SORTIE, exist_ok=True)
open(os.path.join(SERVEUR, "eula.txt"), "w").write("eula=true\n")
open(os.path.join(SERVEUR, "server.properties"), "w").write("\n".join([
    "online-mode=false", "level-seed=20261025", "level-name=village", "view-distance=3", "simulation-distance=3",
    "spawn-monsters=false", "max-tick-time=-1", "generate-structures=true"]) + "\n")
journal = open(os.path.join(SORTIE, "serveur.log"), "w")
p = subprocess.Popen(["java", "-Xmx6G", f"@libraries/net/minecraftforge/forge/{FORGE}/unix_args.txt", "nogui"],
                     cwd=SERVEUR, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                     text=True, bufsize=1)
tout, lignes = [], queue.Queue()


def lire():
    for l in p.stdout:
        journal.write(l); journal.flush(); tout.append(l); lignes.put(l)
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


def cmd(c, motif, delai=300):
    n0 = len(tout)
    journal.write(f">>> {c}\n")
    p.stdin.write(c + "\n"); p.stdin.flush()
    fin = time.time() + delai
    while time.time() < fin:
        for l in tout[n0:]:
            if re.search(motif, l):
                return l
        time.sleep(0.5)
    return ""


attendre("Done (", 1500)
villages = [(int(r["x"]), int(r["z"]), r["nom"]) for r in csv.DictReader(open(CSV, encoding="utf-8"), delimiter=";")]
BPD = 445.28
VILLES = {"Paris": (48.86, 2.35), "Lyon": (45.76, 4.84), "Le Caire": (30.04, 31.24), "Tokyo": (35.68, 139.69),
          "New York": (40.71, -74.01), "Sydney": (-33.87, 151.21), "Moscou": (55.76, 37.62), "Lima": (-12.05, -77.04)}
bilan, lignes_res = [], []
for nom, (la, lo) in VILLES.items():
    x, z = round(lo * BPD), round(-la * BPD)
    attendu = min(villages, key=lambda v: (v[0] - x) ** 2 + (v[1] - z) ** 2)
    l = cmd(f"execute positioned {x} 100 {z} run locate structure #minecraft:village",
            r"nearest #minecraft:village|Could not find|could not find")
    m = re.search(r"at \[(-?\d+), [^,]+, (-?\d+)\]", l)
    if m:
        tx, tz = int(m.group(1)), int(m.group(2))
        d = math.hypot(tx - attendu[0], tz - attendu[1])
        ok = d < 40
        lignes_res.append(f"{nom:10s} trouvé ({tx}, {tz}) ; attendu {attendu[2]} ({attendu[0]}, {attendu[1]}) ; écart {d:.0f}")
    else:
        ok = False
        lignes_res.append(f"{nom:10s} rien : {l.strip()}")
    bilan.append(f"{'OK    ' if ok else 'ÉCHEC '} village de {nom}")
    if not ok:                                      # pourquoi : biome au point attendu
        lignes_res.append("    " + cmd(f"village point {attendu[0]} {attendu[1]}", r"\[Village\]", 120).strip())
import random
random.seed(1)
sans = 0
echantillon = random.sample(villages, 60)
for vx, vz, vn in echantillon:
    l = cmd(f"village point {vx} {vz}", r"\[Village\]", 120)
    if "types : aucun" in l:
        sans += 1
        lignes_res.append("sans type : " + vn + " " + l.strip())
bilan.append(f"{'OK    ' if sans <= 3 else 'ÉCHEC '} biome compatible pour {60 - sans} villages sur 60 tirés au hasard")
l = cmd("execute positioned 13900 100 -13380 run locate structure minecraft:desert_pyramid",
        r"nearest|Could not find|could not find", 200)
bilan.append(f"{'OK    ' if 'nearest' not in l else 'ÉCHEC '} pas encore de pyramide (0.1)")
l = cmd("execute positioned 1064 60 -21769 run locate structure minecraft:mineshaft", r"nearest|Could not find|could not find", 200)
bilan.append(f"{'OK    ' if 'nearest' in l else 'ÉCHEC '} puits de mine rallumés")
cmd("stop", r"Stopping server", 60)
try:
    p.wait(timeout=180)
except subprocess.TimeoutExpired:
    p.kill()
log = "".join(tout)
bilan.insert(0, f"{'OK    ' if 'Domaine Village : monde Terre oui' in log else 'ÉCHEC '} Domaine Village chargé (monde Terre)")
bilan.insert(1, f"{'OK    ' if 'Exception in server tick loop' not in log and 'Minecraft Crash Report' not in log else 'ÉCHEC '} aucun plantage")
open(os.path.join(SORTIE, "bilan.txt"), "w").write("\n".join(bilan) + "\n")
open(os.path.join(SORTIE, "villages.txt"), "w").write("\n".join(lignes_res) + "\n")
print("\n".join(lignes_res)); print("\n".join(bilan))

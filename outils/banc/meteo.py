"""Banc de Domaine Weather (13/11/2026) : vrai serveur Forge avec Terre, Domaine Weather, Serene Seasons et Weather2.

Vérifie que les mixins s'appliquent (aucune erreur au démarrage), puis interroge /meteo point sur des lieux de test à
chaque saison (saison locale, climat, pluie, durée du jour, catastrophes possibles) et compare aux valeurs attendues.

Usage : python outils/banc/meteo.py <dossier_serveur> <sortie>
Sortie : <sortie>/meteo.txt (tableau), <sortie>/serveur.log, <sortie>/bilan.txt (OK / ÉCHEC par contrôle)
"""
import os, queue, re, subprocess, sys, threading, time

SERVEUR, SORTIE = sys.argv[1], sys.argv[2]
FORGE = "1.20.1-47.4.10"
os.makedirs(SORTIE, exist_ok=True)

with open(os.path.join(SERVEUR, "eula.txt"), "w") as f:
    f.write("eula=true\n")
with open(os.path.join(SERVEUR, "server.properties"), "w") as f:
    f.write("\n".join(["online-mode=false", "level-seed=20261025", "level-name=meteo", "view-distance=3",
                       "simulation-distance=3", "spawn-monsters=false", "max-tick-time=-1"]) + "\n")

journal = open(os.path.join(SORTIE, "serveur.log"), "w")
p = subprocess.Popen(["java", "-Xmx6G", f"@libraries/net/minecraftforge/forge/{FORGE}/unix_args.txt", "nogui"],
                     cwd=SERVEUR, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                     text=True, bufsize=1)
lignes = queue.Queue()
tout = []


def lire():
    for l in p.stdout:
        journal.write(l); journal.flush()
        tout.append(l)
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


attendre("Done (", 1500)

LIEUX = {  # nom : (lat, lon)
    "Paris": (48.86, 2.35), "Oslo": (59.91, 10.75), "Tromso": (69.65, 18.96), "Le Caire": (30.04, 31.24),
    "Sahara (Tamanrasset)": (22.79, 5.52), "Seville": (37.39, -5.98), "Bombay": (19.08, 72.88),
    "Manaus": (-3.12, -60.02), "Sydney": (-33.87, 151.21), "Ushuaia": (-54.80, -68.30),
    "Oklahoma City": (35.47, -97.52), "Dacca": (23.81, 90.41), "Iakoutsk": (62.03, 129.73),
}
SAISONS = ["mid_spring", "mid_summer", "mid_autumn", "mid_winter"]
res = {}
for s in SAISONS:
    cmd(f"season set {s}")
    time.sleep(2)
    for nom, (la, lo) in LIEUX.items():
        n0 = len(tout)
        cmd(f"meteo point {la} {lo}")
        fin = time.time() + 20
        while time.time() < fin and not any("Tornades :" in l for l in tout[n0:]):
            time.sleep(0.2)
        bloc = "".join(tout[n0:])
        res[(s, nom)] = bloc

cmd("stop")
try:
    p.wait(timeout=180)
except subprocess.TimeoutExpired:
    p.kill()


def champ(bloc, motif):
    m = re.search(motif, bloc)
    return m.group(1) if m else "?"


with open(os.path.join(SORTIE, "meteo.txt"), "w") as f:
    for s in SAISONS:
        f.write(f"== saison du nord : {s}\n")
        for nom in LIEUX:
            b = res[(s, nom)]
            v = [champ(b, m) for m in (r"Saison locale : (\S+)", r"Climat : (\S+)", r"pluie : (\d+) %",
                                       r"Jour : ([\d.]+) h", r"Tornades : (\S+)", r"sable : (\S+)", r"neige : (\S+)")]
            f.write("%-22s saison %-14s climat %-4s pluie %3s %%  jour %5s h  tornades %-4s sable %-4s neige %s\n"
                    % (nom, *v))

# contrôles
bilan = []


def ctrl(nom, ok):
    bilan.append(f"{'OK    ' if ok else 'ÉCHEC '} {nom}")


log = "".join(tout)
ctrl("aucune erreur de mixin", not re.search(r"Mixin.*(error|Error|failed|FAILED)|InvalidInjectionException|MixinApplyError", log))
ctrl("Domaine Weather chargé", "Domaine Weather : tornades sans dégâts" in log)
ctrl("aucun plantage", "Exception in server tick loop" not in log and "Minecraft Crash Report" not in log)
g = lambda s, n, m: champ(res[(s, n)], m)
ctrl("été à Paris quand c'est l'été au nord", g("mid_summer", "Paris", r"Saison locale : (\S+)") == "mid_summer")
ctrl("hiver à Sydney quand c'est l'été au nord", g("mid_summer", "Sydney", r"Saison locale : (\S+)") == "mid_winter")
def nb(t, d):
    try:
        return float(t)
    except ValueError:
        return d


ctrl("jours longs à Oslo l'été", nb(g("mid_summer", "Oslo", r"Jour : ([\d.]+) h"), 0) > 16)
ctrl("jours courts à Oslo l'hiver", nb(g("mid_winter", "Oslo", r"Jour : ([\d.]+) h"), 99) < 8)
ctrl("~12 h à Manaus toute l'année", all(abs(nb(g(s, "Manaus", r"Jour : ([\d.]+) h"), 0) - 12) < 0.6 for s in SAISONS))
ctrl("Séville sèche l'été", g("mid_summer", "Seville", r"pluie : (\d+) %") == "10")
ctrl("Sahara presque sec", g("mid_summer", "Sahara (Tamanrasset)", r"pluie : (\d+) %") == "5")
ctrl("tornades possibles à Oklahoma City", g("mid_spring", "Oklahoma City", r"Tornades : (\S+)") == "oui")
ctrl("pas de tornades à Paris", g("mid_spring", "Paris", r"Tornades : (\S+)") == "non")
ctrl("tempêtes de sable au Sahara", g("mid_spring", "Sahara (Tamanrasset)", r"sable : (\S+)") == "oui")
ctrl("pas de tempête de sable à Paris", g("mid_spring", "Paris", r"sable : (\S+)") == "non")
ctrl("tempêtes de neige à Iakoutsk", g("mid_winter", "Iakoutsk", r"neige : (\S+)") == "oui")
open(os.path.join(SORTIE, "bilan.txt"), "w").write("\n".join(bilan) + "\n")
print(open(os.path.join(SORTIE, "meteo.txt")).read())
print("\n".join(bilan))

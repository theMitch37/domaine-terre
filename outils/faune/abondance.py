"""Ajoute / met à jour la colonne « abondance » de especes.csv (07/11/2026, décision de Maxime : la nature comme si
l'homme n'existait pas ; animaux de ferme rares, comme des bêtes retournées à l'état sauvage, là où l'élevage existe).
Niveaux : TC (très commun), C (commun), PC (peu commun), R (rare). Poids de la table : TC 16, C 8, PC 3, R 1.
Usage : python3 outils/faune/abondance.py   (relancer après avoir ajouté des espèces ; les valeurs déjà saisies à la
main dans le CSV sont gardées)."""
import csv, io, os
ICI = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(ICI, "especes.csv")

NIVEAUX = {
 "TC": """rabbit sparrow songbird reindeer bison/plains wildebeest/blue zebra gazelle kangaroo penguin seagull minnow
  atlantic_herring tropical_fish betteranimalsplus:deer alexsmobs:kangaroo alexsmobs:bison""",
 "C": """frog bee bat finch robin crow duck goose naturalist:deer wildernature:deer squirrel crab jellyfish squid triops
  newt/ fox hedgehog raccoon coyote opossum turkey pheasant boar/eurasian naturalist:boar wildernature:boar
  betteranimalsplus:boar boar/warthog boar/peccary boar/red_river bear/black hyena/spotted hippo crocodile alligator caiman
  monitor/nile snake/adder snake/grass_snake snake/rattlesnake snake/western_rattlesnake snake/corn snake/swamp_moccasin
  snake/ball_python snake/rice_paddy snake/carpet_python snake/taipan naturalist:snake naturalist:rattlesnake
  alexsmobs:rattlesnake tarantula/rose tarantula/red_knee tarantula/black tarantula/black_and_white tarantula/tiger
  betteranimalsplus:tarantula butterfly naturalist:butterfly firefly fly cockroach caterpillar snail moth dragonfly
  baleen_whale/minke trevally triggerfish spadefish giant_clam king_crab capuchin gelada toucan hummingbird sugar_glider
  emu walrus lobster barracuda flying_fish jerboa pelican flamingo termite leafcutter banana_slug mudskipper horseshoe
  piranha tambaqui boulti bayad synodontis tuna pollock blackfish bluegill bass brown_trout rainbow_trout carp perch
  salmon atlantic_cod minecraft:cod catfish/channel catfish/blue bluejay blue_jay cardinal canary dolphin parrot goat
  wildebeest/black seal lizard naturalist:catfish alexsmobs:catfish aquaculture:catfish smallmouth_bass pink_salmon
  comb_jelly anteater""",
 "PC": """wolf feral_wolf red_wolf badger skunk owl bald_eagle vulture ostrich giraffe elephant rhino/black rhino/white
  rhino/indian naturalist:rhino alexsmobs:rhinoceros big_cat/lion naturalist:lion big_cat/leopard big_cat/jaguar
  big_cat/puma bear/brown naturalist:bear grizzly_bear brownbear blackbear bear/polar bear/sun hyena/striped hyena/brown
  hyena/aardwolf naturalist:hyena large_snake/anaconda large_snake/reticulated_python komodo monitor/desert monitor/bengal
  monitor/water monitor/rock snake/gray_kingsnake snake/coral snake/coral_blue snake/emerald snake/black_mamba
  snake/green_mamba naturalist:coral_snake tarantula/king tortoise softshell_turtle giant_salamander/japanese
  giant_salamander/hellbender manatee baleen_whale/humpback baleen_whale/fin baleen_whale/gray baleen_whale/sei orca
  cachalot shark/hammerhead shark/tiger shark/bull shark/lemon shark/mako shark/bigeye shark/bluntnose shark/greenland
  hammerhead_shark betteranimalsplus:shark gorilla potoo platypus tasmanian_devil cassowary moose roadrunner rain_frog
  mantis_shrimp octopus coconut_crab eel lamprey arapaima capitaine aquaculture:gar muskellunge halibut red_grouper arowana
  minecraft:turtle ocelot bison/wisent wildernature:bison water_buffalo catfish/redtail tarantula_hawk
  alligator_snapping_turtle terrapin arrau_turtle box_turtle starshell_turtle lammergeier""",
 "R": """big_cat/tiger alexsmobs:tiger big_cat/snow_leopard alexsmobs:snow_leopard bear/panda minecraft:panda
  bear/spectacled rhino/javan rhino/sumatran giant_salamander/chinese baleen_whale/blue shark/great_white shark/goblin
  whale_shark sawfish sunfish football_fish maned_wolf mimic_octopus nautilus bobbit giant_squid squid_colossal
  squid_giant frilled_shark blobfish shoebill devils_hole_pupfish axolotl camel/wild_bactrian tarantula/regalis
  tarantula/cobalt betteranimalsplus:whale polar_bear camel/dromedary ecologics:camel""",
}
POIDS = {"TC": 16, "C": 8, "PC": 3, "R": 1}
DEFAUT = {"ferme": "R", "fantastique": "R", "insecte": "C", "poisson": "C", "sauvage": "PC"}


def niveau(r):
    if r["categorie"] in ("ferme", "fantastique") or "RARE" in r["note"]:
        return "R"                       # option B : bêtes domestiques retournées à l'état sauvage, rares
    i = r["id"]
    for niv in ("R", "PC", "C", "TC"):   # du plus précis au plus large : un id exact gagne sur un motif
        for m in NIVEAUX[niv].split():
            if (":" in m and i == m) or (":" in m and m.endswith("/") is False and i.startswith(m + "/")):
                return niv
    for niv in ("R", "PC", "C", "TC"):
        for m in NIVEAUX[niv].split():
            if ":" not in m and m in i:
                return niv
    return DEFAUT.get(r["categorie"], "PC")


if __name__ == "__main__":
    lignes = open(P, encoding="utf-8", newline="").read().split("\r\n")
    tete = next(csv.reader([lignes[0]], delimiter=";"))
    if "abondance" not in tete:
        lignes[0] += ";abondance"
        tete.append("abondance")
    k = tete.index("abondance")
    stats = {}
    for n, l in enumerate(lignes[1:], 1):
        if not l:
            continue
        f = next(csv.reader([l], delimiter=";"))
        if len(f) > len(tete):
            raise SystemExit(f"ligne {n + 1} : trop de colonnes (un « ; » hors guillemets ?) : {l}")
        d = dict(zip(tete, f + [""] * (len(tete) - len(f))))
        if len(f) == k + 1 and f[k]:
            v = f[k]                                    # saisi à la main : gardé
        else:
            v = niveau(d) if d["statut"] in ("garder", "a_confirmer") else ""
            lignes[n] = l + ";" + v if len(f) == k else ";".join([l.rsplit(";", 1)[0], v])
        stats[v] = stats.get(v, 0) + 1
    open(P, "w", encoding="utf-8", newline="").write("\r\n".join(lignes))
    print(stats)

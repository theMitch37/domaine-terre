"""Résumé d'un profil Java Flight Recorder (jfr print --events jdk.ExecutionSample) : méthodes les plus vues en haut de
pile (temps propre) et dans la pile (temps total), pour savoir où part le temps de génération (10/11/2026)."""
import collections, re, sys

propre, total, n = collections.Counter(), collections.Counter(), 0
pile = []
for ligne in open(sys.argv[1], encoding="utf-8", errors="ignore"):
    ligne = ligne.strip()
    if ligne.startswith("jdk.ExecutionSample"):
        pile = []
        continue
    m = re.match(r"([\w.$/<>]+)\(", ligne)
    if m and "line:" in ligne:
        pile.append(m.group(1))
        continue
    if ligne == "]" and pile:
        n += 1
        propre[pile[0]] += 1
        for f in set(pile):
            total[f] += 1
        pile = []
print(f"{n} échantillons")
print("\n== temps propre (haut de pile)")
for f, c in propre.most_common(40):
    print(f"{100 * c / max(n, 1):5.1f} %  {f}")
print("\n== temps total (dans la pile)")
for f, c in total.most_common(60):
    print(f"{100 * c / max(n, 1):5.1f} %  {f}")

"""Bilan de la faune par terroir (07/11/2026) : part de chaque espèce parmi les naissances d'animaux de terre dans un
grand milieu (écorégion RESOLVE) du terroir, d'après especes.json (poids de l'abondance réelle) et la taille moyenne
des groupes. Usage : python3 outils/faune/bilan.py [terroir ...]   (sans argument : quelques terroirs témoins)"""
import json, os, sys, csv
ICI = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(ICI, "../../src/main/resources/domaine_terre")
E = json.load(open(os.path.join(RES, "faune/especes.json"), encoding="utf-8"))["especes"]
T = json.load(open(os.path.join(RES, "carte/terroirs.json"), encoding="utf-8"))
NOMS = {r["id"]: r["nom"] for r in csv.DictReader(open(os.path.join(ICI, "especes.csv"), encoding="utf-8"), delimiter=";")}
GRANDS = {1: "forêt tropicale humide", 2: "forêt tropicale sèche", 4: "forêt tempérée", 6: "taïga", 7: "savane",
          8: "prairie tempérée", 10: "montagne", 11: "toundra", 12: "méditerranéen", 13: "désert", 14: "mangrove"}
INDEX = {t["cle"]: t["index"] for t in T}


def bilan(nom, idx):
    print(f"\n=== {nom}")
    for g, gn in GRANDS.items():
        l = [e for e in E if e["cat"] not in ("poisson",) and not e["mer"] and not e.get("etage") and e["id"] != "minecraft:bat"
             and idx in e["terroirs"] and g in e["biomes"]]
        if not l:
            continue
        tot = sum(e["poids"] * (e["min"] + e["max"]) / 2 for e in l)
        parts = sorted(((e["poids"] * (e["min"] + e["max"]) / 2 / tot, NOMS.get(e["id"], e["id"])) for e in l), reverse=True)
        print(f"  {gn} ({len(l)} espèces) : " + ", ".join(f"{n} {p:.0%}" for p, n in parts[:10])
              + (f" … (+{len(parts) - 10})" if len(parts) > 10 else ""))


if __name__ == "__main__":
    for t in sys.argv[1:] or ["australie", "afrique_est", "atlantique", "sahara_sahel", "arctique", "amazonie"]:
        bilan(t, INDEX[t])

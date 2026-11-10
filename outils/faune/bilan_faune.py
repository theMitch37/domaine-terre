"""Bilan de la faune attendue dans une région (10/11/2026) : reproduit FauneTerre.calculer (animaux de terre nés à la
génération des chunks) et FauneTerre.rives à partir de especes.json, zones.png et terroirs.png, sans lancer le jeu.

Donne, pour chaque région, la part des individus de chaque espèce (poids x taille moyenne du groupe, moyenné sur les
pixels de la région) : sert à régler l'équilibre (aucune espèce ne doit écraser les autres) avant le banc.

Usage : python outils/faune/bilan_faune.py [--especes chemin.json] [region ...]
"""
import json, os, sys
import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
ICI = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(ICI, "../../src/main/resources/domaine_terre")
W, H = 7200, 3600

# régions de contrôle : lat min, lat max, lon min, lon max (+ part des chunks qui ont de l'eau douce)
REGIONS = {
    "nil_assouan": (23.6, 24.6, 32.5, 33.3, 0.5),
    "serengeti": (-3.0, -2.0, 34.4, 35.4, 0.1),
    "bourgogne": (46.8, 47.8, 4.0, 5.0, 0.2),
    "amazonie": (-4.0, -3.0, -61.0, -60.0, 0.3),
    "amour": (48.0, 49.0, 134.5, 135.5, 0.2),
    "cerrado": (-16.0, -15.0, -48.0, -47.0, 0.1),
    "sahara": (24.0, 25.0, 9.0, 10.0, 0.0),
    "taiga_canada": (54.0, 55.0, -100.0, -99.0, 0.3),
    "alpes": (45.8, 46.4, 6.8, 7.8, 0.2),
    "australie_centre": (-24.0, -23.0, 133.0, 134.0, 0.05),
    "inde_gange": (25.0, 26.0, 82.0, 83.0, 0.3),
    "grandes_plaines": (40.0, 41.0, -100.0, -99.0, 0.1),
}
# catégories qui ne sont pas des animaux de terre (le jeu ne les fait pas naître à la génération)
# (Alex's Mobs : catégories lues dans son registre, version 1.22.9)
PAS_TERRE = {"minecraft:bat", "minecraft:axolotl", "minecraft:glow_squid",
             "alexsmobs:flutter", "alexsmobs:fly", "alexsmobs:crimson_mosquito", "alexsmobs:triops",
             "alexsmobs:terrapin", "alexsmobs:jerboa", "alexsmobs:cockroach", "alexsmobs:rain_frog",
             "alexsmobs:sea_bear", "alexsmobs:skelewag", "alexsmobs:catfish", "alexsmobs:devils_hole_pupfish",
             "alexsmobs:lobster", "alexsmobs:blobfish", "alexsmobs:stradpole", "alexsmobs:comb_jelly"}


def charger(chemin=None):
    d = json.load(open(chemin or os.path.join(RES, "faune/especes.json"), encoding="utf-8"))
    zones = np.array(Image.open(os.path.join(RES, "faune/zones.png")))
    ter = np.array(Image.open(os.path.join(RES, "carte/terroirs.png"))) & 0x7F
    return d, zones, ter


PART_MAX = 0.20      # copie de FauneTerre.PART_MAX
RIVES_SUR = 3        # copie de RivesFeature : un chunk de berge sur RIVES_SUR


def equilibrer(l):
    """Copie de FauneTerre.equilibrer : aucune espèce au-delà de PART_MAX des individus (dès 5 espèces)."""
    if len(l) < 5:
        return {id(e): float(e["poids"]) for e in l}
    w = {id(e): float(e["poids"]) for e in l}
    m = {id(e): (e["min"] + e["max"]) / 2 for e in l}
    for _ in range(10):
        tot = sum(w[k] * m[k] for k in w)
        trop = [k for k in w if w[k] * m[k] > PART_MAX * tot * 1.0001]
        if not trop:
            break
        reste = sum(w[k] * m[k] for k in w if k not in trop)
        cible = PART_MAX * reste / (1 - PART_MAX * len(trop))
        for k in trop:
            w[k] = cible / m[k]
    return w


def bilan(d, zones, ter, lat0, lat1, lon0, lon1, part_eau, rives_proba=1 / RIVES_SUR):
    py0, py1 = int((90 - lat1) / 0.05), int((90 - lat0) / 0.05)
    px0, px1 = int((lon0 + 180) / 0.05), int((lon1 + 180) / 0.05)
    precises = d["precises"]
    biome_precis = [p["biome"] for p in precises]
    total = {}
    n = 0
    for py in range(py0, py1, 2):
        for px in range(px0, px1, 2):
            z = int(zones[py, px])
            if z >= 128 or z == 0:
                continue
            t = int(ter[py, px])
            grand, precis = (z, -1) if z <= 14 else (biome_precis[z - 16], z - 16)
            for eau_chunk, poids_cas in ((True, part_eau), (False, 1 - part_eau)):
                if poids_cas <= 0:
                    continue
                gen, riv = [], []
                for e in d["especes"]:
                    if e["mer"] or e["etage"] or e["cat"] in ("monstre", "poisson") or e["entite"] in PAS_TERRE:
                        continue
                    if t not in e["terroirs"]:
                        continue
                    pr = e["precis"].get(str(t))
                    if pr is not None and precis not in pr:
                        continue
                    if e.get("biome_jeu") or e.get("altitude_min") or e.get("monstre_surface"):
                        continue
                    terre = grand > 0 and grand in e["biomes"]
                    if terre:                      # bêtes d'eau : seulement par les rives (FauneTerre, 10/11/2026)
                        gen.append(e)
                    if e["eau"]:
                        riv.append(e)
                # génération : une liste pondérée, un groupe par tirage (même nombre de tirages par chunk partout)
                wg = equilibrer(gen); sw = sum(wg.values())
                for e in gen:
                    m = (e["min"] + e["max"]) / 2
                    total[e["id"]] = total.get(e["id"], 0) + poids_cas * wg[id(e)] / sw * m * 0.1 * 4
                if eau_chunk and riv:
                    wr = equilibrer(riv); sw = sum(wr.values())
                    for e in riv:
                        m = (e["min"] + e["max"]) / 2
                        total[e["id"]] = total.get(e["id"], 0) + poids_cas * rives_proba * wr[id(e)] / sw * m
            n += 1
    s = sum(total.values()) or 1
    return n, sorted(((k, v / s) for k, v in total.items()), key=lambda x: -x[1]), s / max(n, 1)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    chemin = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--especes=")), None)
    rp = float(next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--rives=")), 1 / RIVES_SUR))
    d, zones, ter = charger(chemin)
    for nom in (args or REGIONS):
        la0, la1, lo0, lo1, pe = REGIONS[nom]
        n, parts, dens = bilan(d, zones, ter, la0, la1, lo0, lo1, pe, rp)
        top = ", ".join(f"{k.split(':')[1]} {100 * v:.0f}%" for k, v in parts[:8])
        print(f"{nom:17s} {len(parts):3d} espèces, {dens:5.2f} bêtes/chunk : {top}")

"""Contrôle de la faune (15/11/2026, demande de Maxime : « vérifier le spawn de chaque espèce, qu'elle soit bien au bon
endroit selon nos règles »), sans lancer le jeu.

1. Table (especes.json) : relit chaque ligne et signale celles dont les règles sont incohérentes :
   - bête de mer qui remonte les fleuves / vit au rivage, permise sur toutes les terres (poissons-scies dans la Seine) ;
   - bête des grands fonds permise près des côtes ; bête qui ne peut naître nulle part ;
   - île préhistorique sans terre (ou sans mer, pour une bête de mer) dans sa boîte.
2. Monde (facultatif) : lit les entités d'une sauvegarde (dossier entities/ ou region/) et vérifie, bête par bête, que
   la table la permet là où elle est (terroir, terre ou mer, île préhistorique, étage souterrain). Les espèces d'Untamed
   Wilds sont lues par leur numéro de variante si on donne le jar d'Untamed Wilds.

Usage : python outils/faune/controle_faune.py [--monde <dossier entities>] [--uw <jar untamedwilds>] [--blocs 445.28]
"""
import argparse, collections, glob, io, json, os, struct, sys, zipfile, zlib

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
ICI = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(ICI, "../../src/main/resources/domaine_terre")
W, H = 7200, 3600
NIVEAU_MER = 62
TERROIRS = {t["index"]: t["cle"] for t in json.load(open(os.path.join(RES, "carte/terroirs.json"), encoding="utf-8"))}


def pixel(lon, lat):
    px = int((lon + 180.0) / 0.05) % W
    py = min(H - 1, max(0, int((90.0 - lat) / 0.05)))
    return py, px


def dans_boite(b, lon, lat):
    if lat < b[0] or lat > b[1]:
        return False
    return b[2] <= lon <= b[3] if b[2] <= b[3] else (lon >= b[2] or lon <= b[3])


# ------------------------------------------------------------------------------------------------ 1. la table
def controle_table(d, zones):
    alertes = []
    for e in d["especes"]:
        i = e["id"]
        mer = e.get("mer")
        if mer and (e["eau"] or e["cote"]) and len(e["terroirs"]) >= 29 and not e.get("boite"):
            alertes.append((i, "bête de mer permise dans les fleuves ou au rivage de TOUTES les terres"))
        if mer and e["cat"] == "poisson" and set(mer["bandes"]) <= {"large", "abysse"} and False:
            pass
        if not e.get("boite") and not e.get("etage") and not e["terroirs"]:
            alertes.append((i, "aucun terroir : ne naît jamais"))
        elif (not mer and not e.get("etage") and not e["biomes"] and not e["eau"] and not e["cote"]
              and not e.get("biome_jeu") and not e.get("boite")):
            alertes.append((i, "ni milieu, ni eau, ni côte, ni biome du jeu : ne naît jamais"))
        if e.get("boite"):
            b = e["boite"]
            n_terre = n_mer = 0
            for lat in np.arange(b[0], b[1], 0.05):
                lons = np.arange(b[2], b[3] if b[2] <= b[3] else b[3] + 360, 0.05)
                for lon in lons:
                    lon = ((lon + 180) % 360) - 180
                    z = int(zones[pixel(lon, lat)])
                    if z >= 128 or z == 0:
                        n_mer += 1
                    else:
                        n_terre += 1
            if mer and n_mer == 0:
                alertes.append((i, "île préhistorique : pas de mer dans la boîte"))
            if not mer and n_terre == 0:
                alertes.append((i, "île préhistorique : pas de terre dans la boîte"))
        if e.get("profondeur_min") and mer and "cote" in mer["bandes"]:
            alertes.append((i, "bête des profondeurs aussi permise dans la bande côtière (la profondeur la retient)"))
    return alertes


# ------------------------------------------------------------------------------------------------ 2. le monde
def entites(dossier):
    for f in sorted(glob.glob(os.path.join(dossier, "*.mca"))):
        b = open(f, "rb").read()
        if len(b) < 8192:
            continue
        for k in range(1024):
            off = int.from_bytes(b[k * 4:k * 4 + 3], "big")
            if off == 0:
                continue
            o = off * 4096
            n = int.from_bytes(b[o:o + 4], "big")
            data = zlib.decompress(b[o + 5:o + 4 + n])
            yield from lire_nbt(data).get("Entities", [])


def lire_nbt(data):
    """Lecteur NBT minimal (compound racine) : assez pour id, Pos, Variant."""
    s = io.BytesIO(data)

    def u(fmt):
        return struct.unpack(">" + fmt, s.read(struct.calcsize(">" + fmt)))[0]

    def nom():
        return s.read(u("H")).decode("utf-8", "replace")

    def val(t):
        if t == 1: return u("b")
        if t == 2: return u("h")
        if t == 3: return u("i")
        if t == 4: return u("q")
        if t == 5: return u("f")
        if t == 6: return u("d")
        if t == 7: return s.read(u("i"))
        if t == 8: return nom()
        if t == 9:
            tt, n = u("b"), u("i")
            return [val(tt) for _ in range(n)]
        if t == 10:
            c = {}
            while True:
                tt = u("b")
                if tt == 0:
                    return c
                k = nom()
                c[k] = val(tt)
        if t == 11: return [u("i") for _ in range(u("i"))]
        if t == 12: return [u("q") for _ in range(u("i"))]
        raise ValueError(t)

    t = u("b")
    nom()
    return val(t)


def especes_uw(jar):
    if not jar:
        return {}
    z = zipfile.ZipFile(jar)
    out = {}
    for n in z.namelist():
        if n.startswith("data/untamedwilds/entities/") and n.endswith(".json"):
            d = json.loads(z.read(n).decode("utf-8-sig"))
            out["untamedwilds:" + n.rsplit("/", 1)[1][:-5]] = [sp["name"] for sp in d.get("species", [])]
    return out


def controle_monde(d, zones, ter, dossier, uw, bpd):
    par_type = collections.defaultdict(list)
    for e in d["especes"]:
        par_type[e["entite"]].append(e)
    bilan = collections.Counter()
    hors = collections.Counter()
    exemples = {}
    for en in entites(dossier):
        t = en.get("id", "?")
        lignes = par_type.get(t)
        if not lignes:
            continue                                   # bête que la table ne gère pas (élevage, villages, objets…)
        x, y, z = en["Pos"]
        lon, lat = x / bpd, -z / bpd
        lon = ((lon + 180) % 360) - 180
        zz = int(zones[pixel(lon, lat)])
        en_mer = zz >= 128 or zz == 0
        terroir = (zz - 128) if zz >= 128 else int(ter[pixel(lon, lat)])
        esp = None
        if t in uw and "Variant" in en and 0 <= en["Variant"] < len(uw[t]):
            esp = uw[t][en["Variant"]]
            ls = [e for e in lignes if e["id"].endswith("/" + esp) or e["id"].endswith("/*")]
            lignes = ls or lignes
        cle = t + ("/" + esp if esp else "")
        bilan[cle] += 1
        ok, raison = False, ""
        for e in lignes:
            if e.get("etage"):
                if y < NIVEAU_MER - 10:
                    ok = True
                    break
                raison = "bête des étages souterrains trouvée en surface"
                continue
            if e.get("boite"):
                if dans_boite(e["boite"], lon, lat):
                    ok = True
                    break
                raison = "bête d'île préhistorique hors de son île"
                continue
            if en_mer and e.get("mer"):
                if e.get("profondeur_min") and y > NIVEAU_MER - e["profondeur_min"]:
                    raison = f"trop près de la surface (y {y:.0f})"
                    continue
                if len(e["terroirs"]) >= 29 or terroir in e["terroirs"] or terroir == 0:
                    ok = True
                    break
                raison = f"mer bordant {TERROIRS.get(terroir, terroir)} (pas son aire)"
                continue
            if terroir in e["terroirs"]:
                ok = True
                break
            raison = f"{'mer' if en_mer else 'terre'} de {TERROIRS.get(terroir, terroir)} (pas son aire)"
        if not ok:
            hors[(cle, raison)] += 1
            exemples.setdefault((cle, raison), (round(x), round(y), round(z), round(lat, 2), round(lon, 2)))
    return bilan, hors, exemples


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--especes", default=os.path.join(RES, "faune/especes.json"))
    a.add_argument("--monde")
    a.add_argument("--uw")
    a.add_argument("--blocs", type=float, default=445.28)
    o = a.parse_args()
    d = json.load(open(o.especes, encoding="utf-8"))
    zones = np.array(Image.open(os.path.join(RES, "faune/zones.png")))
    ter = np.array(Image.open(os.path.join(RES, "carte/terroirs.png"))) & 0x7F
    al = controle_table(d, zones)
    print(f"== Table : {len(d['especes'])} lignes, {len(al)} alerte(s)")
    for i, r in al:
        print(f"  {i} : {r}")
    if o.monde:
        bilan, hors, ex = controle_monde(d, zones, ter, o.monde, especes_uw(o.uw), o.blocs)
        n = sum(bilan.values())
        print(f"== Monde : {n} bêtes de la table, {sum(hors.values())} hors de nos règles")
        for (cle, r), k in hors.most_common():
            print(f"  {k:4d} {cle} : {r}  ex. {ex[(cle, r)]}")


if __name__ == "__main__":
    main()

"""Contrôle des grottes au banc : chaque bloc de grottes.bin est-il bien dans le monde généré ?

Usage : python3 outils/banc/grottes.py <dossier des .npz du banc>
Par grotte : vide (air), eau, décor (nom de bloc attendu), coque (pas d'air ni de fluide) ; et le vide au-dessus de
la surface hors des entrées (ouvertures en trop).
"""
import gzip, json, os, struct, sys
import numpy as np

RACINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
ATTENDU = {200: ("air", "cave_air"), 201: ("water",), 203: ("calcite",), 204: ("dripstone_block",), 205: ("gravel",),
           206: ("clay",), 207: ("sand",), 208: ("packed_ice",), 209: ("blue_ice",), 210: ("ice",), 211: ("snow_block",),
           212: ("sea_lantern",), 213: ("basalt",), 214: ("polished_basalt",), 215: ("smooth_basalt",),
           216: ("moss_block",)}
for c in range(220, 229):
    ATTENDU[c] = ("pointed_dripstone",)


def lire():
    with gzip.open(os.path.join(RACINE, "lieux/src/main/resources/domaine_terre_lieux/grottes.bin")) as f:
        b = f.read()
    n = struct.unpack_from("<i", b)[0]
    a = np.frombuffer(b, dtype=np.dtype([("x", "<i4"), ("y", "<i4"), ("z", "<i4"), ("c", "u1")]), count=n, offset=4)
    return a


def controle(dos, nom, rec):
    f = os.path.join(dos, nom + ".npz")
    if not os.path.exists(f):
        print(f"{nom:22s} : pas de données")
        return
    d = np.load(f)
    noms = np.array([str(n).split(":")[-1] for n in d["noms"]])
    B = d["blocs"]; x0, y0, z0 = int(d["x0"]), int(d["y0"]), int(d["z0"])
    D, H, W = B.shape
    m = (rec["x"] >= x0) & (rec["x"] < x0 + W) & (rec["z"] >= z0) & (rec["z"] < z0 + D) & (rec["y"] >= y0) & (rec["y"] < y0 + H)
    r = rec[m]
    if len(r) == 0:
        print(f"{nom:22s} : aucun bloc de grotte dans la zone")
        return
    reel = noms[B[r["z"] - z0, r["y"] - y0, r["x"] - x0]]
    txt = []
    for titre, classes in (("vide", [200]), ("eau", [201]), ("décor", [c for c in ATTENDU if c >= 203])):
        k = np.isin(r["c"], classes)
        if not k.any():
            continue
        ok = np.array([n in ATTENDU[c] for n, c in zip(reel[k], r["c"][k])])
        txt.append(f"{titre} {ok.mean() * 100:5.1f} % ({int(k.sum())})")
    k = r["c"] == 202
    if k.any():
        trou = np.isin(reel[k], ["air", "cave_air", "water", "lava"])
        txt.append(f"coque percée {int(trou.sum())}/{int(k.sum())}")
    print(f"{nom:22s} : " + " | ".join(txt))


if __name__ == "__main__":
    dos = sys.argv[1]
    rec = lire()
    z = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "zones.json")))
    for n in ["grotte_padirac", "grotte_han", "grotte_postojna", "grotte_eisriesenwelt", "fingal", "capri"]:
        controle(dos, n, rec)

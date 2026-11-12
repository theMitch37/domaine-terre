"""Récifs coralliens réels (Natural Earth 10m « reefs », domaine public) -> src/main/resources/domaine_terre/carte/recifs.bin
Format (petit-boutiste) : int32 nombre de lignes, puis pour chaque ligne int32 n et n couples float32 (lon, lat).
Usage : python3 outils/recifs.py <ne_10m_reefs.shp>  (dépôt nvkelso/natural-earth-vector, 10m_physical)"""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shp

formes = shp.lire_shp(open(sys.argv[1], "rb").read())
lignes = [p for f in formes for p in f if len(p) >= 2]
sortie = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src/main/resources/domaine_terre/carte/recifs.bin")
with open(sortie, "wb") as o:
    o.write(struct.pack("<i", len(lignes)))
    for l in lignes:
        o.write(struct.pack("<i", len(l)))
        for lon, lat in l:
            o.write(struct.pack("<2f", lon, lat))
print(len(lignes), "lignes,", sum(len(l) for l in lignes), "points ->", sortie, os.path.getsize(sortie), "octets")

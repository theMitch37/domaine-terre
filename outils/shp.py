"""Lecteur minimal de shapefiles (polygones, polylignes) et de tables DBF, sans dépendance."""
import struct
import zipfile


def lire_zip(chemin):
    z = zipfile.ZipFile(chemin)
    shp = next(n for n in z.namelist() if n.endswith(".shp"))
    dbf = next(n for n in z.namelist() if n.endswith(".dbf"))
    return lire_shp(z.read(shp)), lire_dbf(z.read(dbf))


def lire_shp(b):
    """Renvoie une liste de formes ; chaque forme = liste de parties ; partie = liste de (lon, lat)."""
    formes = []
    pos = 100
    while pos + 8 <= len(b):
        _, longueur = struct.unpack(">ii", b[pos:pos + 8])
        contenu = b[pos + 8:pos + 8 + longueur * 2]
        pos += 8 + longueur * 2
        typ = struct.unpack("<i", contenu[:4])[0]
        if typ == 0:
            formes.append([])
            continue
        # 3 = polyligne, 5 = polygone (et variantes Z/M : 13, 15, 23, 25)
        nparts, npts = struct.unpack("<ii", contenu[36:44])
        parts = list(struct.unpack(f"<{nparts}i", contenu[44:44 + 4 * nparts]))
        off = 44 + 4 * nparts
        pts = struct.unpack(f"<{2 * npts}d", contenu[off:off + 16 * npts])
        xy = list(zip(pts[0::2], pts[1::2]))
        parts.append(npts)
        formes.append([xy[parts[i]:parts[i + 1]] for i in range(nparts)])
    return formes


def lire_dbf(b):
    nrec, hlen, rlen = struct.unpack("<IHH", b[4:12])
    champs = []
    p = 32
    while b[p] != 0x0D:
        nom = b[p:p + 11].split(b"\0")[0].decode("latin1")
        typ = chr(b[p + 11]); lg = b[p + 16]
        champs.append((nom, typ, lg))
        p += 32
    lignes = []
    for i in range(nrec):
        r = b[hlen + i * rlen + 1: hlen + (i + 1) * rlen]
        d = {}; o = 0
        for nom, typ, lg in champs:
            v = r[o:o + lg].decode("utf-8", "replace").strip("\x00 "); o += lg
            if typ in "NF":
                try: v = float(v)
                except ValueError: v = None
            d[nom] = v
        lignes.append(d)
    return lignes

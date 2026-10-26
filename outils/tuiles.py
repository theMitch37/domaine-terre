"""Tuiles sculptées : la carte est un damier de tuiles de 512 x 512 blocs (une région Minecraft), en 1:250.

Une tuile normale n'existe pas en fichier : son terrain est calculé par le mod Terre (terre_py.sol_exact au bloc près).
Une tuile sculptée (un lieu, ou un bout de lieu) est un fichier qui donne, colonne par colonne, soit « terrain
calculé », soit la hauteur exacte voulue. Ses colonnes sculptées rejoignent le terrain calculé à leur bord : pas
de poids, pas de fondu. Resculpter un lieu ne réécrit que les tuiles qu'il touche.

Fichier lieux/src/main/resources/domaine_terre_lieux/tuiles/<tx>_<tz>.bin (gzip sans date, petit-boutiste) :
  int32 MAGIE 0x454C5554 (« TULE »), int32 version 1, int32 tx, int32 tz, int32 n lieux, puis pour chaque lieu
  int16 longueur + identifiant UTF-8 ; puis 512 x 512 valeurs (ligne z, colonne x, du nord-ouest) de :
  int16 HAUT = y visé x 16 (-32768 = terrain calculé), int16 SOMMET = repère des couches x 16,
  uint8 TYPE = classe + drapeaux (comme LieuGrille), uint8 LIEU = numéro du lieu + 1 (0 = aucun).
Index : tuiles/index.txt, une ligne « tx tz » par tuile.
"""
import gzip, io, os, struct
import numpy as np

T = 512
MAGIE, VERSION, VIDE = 0x454C5554, 1, -32768
DOSSIER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                       "lieux/src/main/resources/domaine_terre_lieux/tuiles/")


def chemin(tx, tz):
    return os.path.join(DOSSIER, f"{tx}_{tz}.bin")


class Tuile:
    def __init__(self, tx, tz):
        self.tx, self.tz = tx, tz
        self.lieux = []
        self.haut = np.full((T, T), VIDE, np.int16)
        self.sommet = np.zeros((T, T), np.int16)
        self.type = np.zeros((T, T), np.uint8)
        self.lieu = np.zeros((T, T), np.uint8)

    @staticmethod
    def lire(tx, tz):
        t = Tuile(tx, tz)
        if not os.path.exists(chemin(tx, tz)):
            return t
        b = gzip.open(chemin(tx, tz)).read()
        magie, version, ftx, ftz, n = struct.unpack_from("<5i", b, 0)
        assert magie == MAGIE and version == VERSION and (ftx, ftz) == (tx, tz), chemin(tx, tz)
        p = 20
        for _ in range(n):
            (l,) = struct.unpack_from("<h", b, p); p += 2
            t.lieux.append(b[p:p + l].decode("utf-8")); p += l
        N = T * T
        t.haut = np.frombuffer(b, "<i2", N, p).reshape(T, T).copy(); p += 2 * N
        t.sommet = np.frombuffer(b, "<i2", N, p).reshape(T, T).copy(); p += 2 * N
        t.type = np.frombuffer(b, "u1", N, p).reshape(T, T).copy(); p += N
        t.lieu = np.frombuffer(b, "u1", N, p).reshape(T, T).copy()
        return t

    def retirer(self, nom):
        """Efface toutes les colonnes du lieu (avant de le resculpter) ; renumérote les autres."""
        if nom not in self.lieux:
            return
        k = self.lieux.index(nom) + 1
        m = self.lieu == k
        self.haut[m] = VIDE; self.sommet[m] = 0; self.type[m] = 0; self.lieu[m] = 0
        self.lieu[self.lieu > k] -= 1
        self.lieux.remove(nom)

    def ecrire(self):
        os.makedirs(DOSSIER, exist_ok=True)
        if not self.lieux:
            if os.path.exists(chemin(self.tx, self.tz)):
                os.remove(chemin(self.tx, self.tz))
            return
        blob = struct.pack("<5i", MAGIE, VERSION, self.tx, self.tz, len(self.lieux))
        for nom in self.lieux:
            e = nom.encode("utf-8"); blob += struct.pack("<h", len(e)) + e
        blob += self.haut.astype("<i2").tobytes() + self.sommet.astype("<i2").tobytes()
        blob += self.type.astype("u1").tobytes() + self.lieu.astype("u1").tobytes()
        tampon = io.BytesIO()
        with gzip.GzipFile(fileobj=tampon, mode="wb", compresslevel=9, mtime=0) as f:   # sans date : rien ne change si la forme ne change pas
            f.write(blob)
        with open(chemin(self.tx, self.tz), "wb") as f:
            f.write(tampon.getvalue())


def index():
    """Tuiles présentes, d'après les fichiers."""
    if not os.path.isdir(DOSSIER):
        return []
    l = []
    for f in os.listdir(DOSSIER):
        if f.endswith(".bin"):
            tx, tz = f[:-4].split("_")
            l.append((int(tx), int(tz)))
    return sorted(l)


def ecrire_index():
    with open(os.path.join(DOSSIER, "index.txt"), "w") as f:
        for tx, tz in index():
            f.write(f"{tx} {tz}\n")


def poser(nom, x0, z0, y, sommet, typ, actif):
    """Sculpte le lieu `nom` dans les tuiles : grille de colonnes à partir de (x0, z0) ; seules les colonnes `actif`
    sont sculptées (hauteur exacte y), les autres restent « terrain calculé ». Efface d'abord l'ancien lieu partout.
    Rend la liste des tuiles écrites."""
    D, W = y.shape
    touchees = {(tx, tz) for tx, tz in index()}
    for tx in range(x0 // T, (x0 + W - 1) // T + 1):
        for tz in range(z0 // T, (z0 + D - 1) // T + 1):
            touchees.add((tx, tz))
    ecrites = []
    for tx, tz in sorted(touchees):
        t = Tuile.lire(tx, tz)
        avant = nom in t.lieux
        t.retirer(nom)
        # partie de la grille du lieu dans cette tuile
        i0, i1 = max(tx * T - x0, 0), min((tx + 1) * T - x0, W)
        j0, j1 = max(tz * T - z0, 0), min((tz + 1) * T - z0, D)
        a = actif[j0:j1, i0:i1] if i1 > i0 and j1 > j0 else np.zeros((0, 0), bool)
        if a.any():
            if len(t.lieux) >= 254:
                raise ValueError("trop de lieux dans une tuile")
            autre = (t.lieu[j0 + z0 - tz * T:j1 + z0 - tz * T, i0 + x0 - tx * T:i1 + x0 - tx * T] > 0) & a
            if autre.any():
                raise ValueError(f"{nom} chevauche un autre lieu dans la tuile {tx} {tz}")
            t.lieux.append(nom); k = len(t.lieux)
            sj = slice(j0 + z0 - tz * T, j1 + z0 - tz * T); si = slice(i0 + x0 - tx * T, i1 + x0 - tx * T)
            for grille, val in ((t.haut, np.round(y * 16)), (t.sommet, np.round(sommet * 16)), (t.type, typ), (t.lieu, k)):
                v = np.broadcast_to(val, y.shape)[j0:j1, i0:i1]
                grille[sj, si] = np.where(a, v, grille[sj, si])
        if a.any() or avant:
            t.ecrire(); ecrites.append((tx, tz))
    ecrire_index()
    return ecrites


def lire_zone(x0, z0, W, D):
    """Grilles (haut x16, sommet x16, type, nom du lieu) d'une zone, depuis les tuiles (contrôles, rendus)."""
    haut = np.full((D, W), VIDE, np.int32); sommet = np.zeros((D, W)); typ = np.zeros((D, W), np.int32)
    lieu = np.full((D, W), "", object)
    for tx in range(x0 // T, (x0 + W - 1) // T + 1):
        for tz in range(z0 // T, (z0 + D - 1) // T + 1):
            if not os.path.exists(chemin(tx, tz)):
                continue
            t = Tuile.lire(tx, tz)
            i0, i1 = max(tx * T - x0, 0), min((tx + 1) * T - x0, W)
            j0, j1 = max(tz * T - z0, 0), min((tz + 1) * T - z0, D)
            sj = slice(j0 + z0 - tz * T, j1 + z0 - tz * T); si = slice(i0 + x0 - tx * T, i1 + x0 - tx * T)
            haut[j0:j1, i0:i1] = t.haut[sj, si]; sommet[j0:j1, i0:i1] = t.sommet[sj, si] / 16
            typ[j0:j1, i0:i1] = t.type[sj, si]
            noms = np.array([""] + t.lieux, object)
            lieu[j0:j1, i0:i1] = noms[t.lieu[sj, si]]
    return haut, sommet, typ, lieu

"""Grottes célèbres d'Europe (MAJ 1) : volumes creusés sous terre, à leurs vraies coordonnées, avec leur vraie entrée
et aucun repère. Sous terre, les dimensions sont largement exagérées (accord de Maxime le 31/10) ; la surface n'est
touchée qu'à l'entrée réelle.

Sortie : lieux/src/main/resources/domaine_terre_lieux/grottes.bin (gzip : nombre d'enregistrements, puis x, y, z
en int32 et la classe en octet), posé par GrottesFeature (toutes les biomes de l'Overworld, étape « décoration
souterraine », après les grottes vanilla). Autour de chaque grotte, une coque de 3 blocs rebouche les grottes et
lacs vanilla qui la traverseraient (classe PLEIN).

Usage : python3 outils/grottes.py [grotte ...] [--apercu]
"""
import gzip, os, struct, sys
import numpy as np
from scipy import ndimage
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import terre_py as T

SORTIE = os.path.join(T.RACINE, "lieux/src/main/resources/domaine_terre_lieux/grottes.bin")
APERCU = "--apercu" in sys.argv

# classes (GrottesFeature.java)
AIR, EAU, PLEIN = 200, 201, 202
CALCITE, DRIPSTONE, GRAVIER, ARGILE, SABLE = 203, 204, 205, 206, 207
GLACE_TASSEE, GLACE_BLEUE, GLACE, NEIGE = 208, 209, 210, 211
LANTERNE, BASALTE, BASALTE_POLI, BASALTE_LISSE, MOUSSE = 212, 213, 214, 215, 216
# concrétions (pointed dripstone) : vers le haut base, milieu, tronc, pointe ; vers le bas idem
STALAGMITE = (220, 221, 222, 223)
STALACTITE = (225, 226, 227, 228)


class Grotte:
    """Volume d'une grotte sur une boîte de blocs [x0, x1) x [y0, y1) x [z0, z1). Le champ f (> 0 : vide) est le
    maximum des formes (galeries, salles, puits) ; une rugosité 3D le déforme ; tout vide sous le niveau d'eau W est
    de l'eau (aucune eau à côté de l'air au même niveau : rien ne coule)."""

    def __init__(self, nom, x0, x1, z0, z1, y0, y1, sol=None, graine=0, rugosite=0.22, eau=None):
        self.nom, self.x0, self.z0, self.y0 = nom, int(x0), int(z0), int(y0)
        self.W, self.D, self.H = int(x1 - x0), int(z1 - z0), int(y1 - y0)
        self.sol = T.sol_exact(self.x0, self.z0, self.W, self.D).astype(float) if sol is None else sol
        self.f = np.full((self.H, self.D, self.W), -9.0, np.float32)
        self.entree = np.zeros((self.H, self.D, self.W), bool)       # là où la grotte peut percer la surface
        self.rng = np.random.default_rng(graine)
        r = self.rng.standard_normal((self.H, self.D, self.W)).astype(np.float32)
        # 04/11 (test en jeu) : moins de petit bruit, il hérissait les parois de pointes et de blocs isolés
        b = ndimage.gaussian_filter(r, 2.2) + 0.2 * ndimage.gaussian_filter(r, 0.9)
        self.bruit = (b / (b.std() + 1e-9)).astype(np.float32)
        self.rugosite, self.niveau_eau = rugosite, eau

    def _boite(self, cx, cy, cz, rx, ry, rz):
        # assez large pour que la rugosité ne bute jamais sur le bord de la boîte (sinon : salles carrées)
        mx, my, mz = rx * 0.7 + 4, ry * 0.7 + 4, rz * 0.7 + 4
        i0, i1 = max(int(cx - rx - mx) - self.x0, 0), min(int(cx + rx + mx) - self.x0, self.W)
        k0, k1 = max(int(cz - rz - mz) - self.z0, 0), min(int(cz + rz + mz) - self.z0, self.D)
        j0, j1 = max(int(cy - ry - my) - self.y0, 0), min(int(cy + ry + my) - self.y0, self.H)
        return j0, j1, k0, k1, i0, i1

    def ellipsoide(self, c, rx, ry, rz, sol_plat=None, entree=False):
        """Salle (ellipsoïde) ; sol_plat : y du sol plat (le bas de l'ellipsoïde est coupé)."""
        cx, cy, cz = c
        j0, j1, k0, k1, i0, i1 = self._boite(cx, cy, cz, rx, ry, rz)
        if j0 >= j1 or k0 >= k1 or i0 >= i1:
            return
        Y, Zz, X = np.mgrid[j0:j1, k0:k1, i0:i1]
        Y = Y + self.y0 + 0.5; Zz = Zz + self.z0 + 0.5; X = X + self.x0 + 0.5
        d = np.sqrt(((X - cx) / rx) ** 2 + ((Y - cy) / ry) ** 2 + ((Zz - cz) / rz) ** 2)
        v = 1 - d
        if sol_plat is not None:
            v = np.where(Y < sol_plat, -9.0, v)
        sl = (slice(j0, j1), slice(k0, k1), slice(i0, i1))
        self.f[sl] = np.maximum(self.f[sl], v)
        if entree:
            self.entree[sl] |= v > -0.5

    def galerie(self, pts, rx, ry, plancher=0.55, entree=False, pas=1.0):
        """Galerie le long d'une polyligne (points x, y, z) : section elliptique de demi-largeur rx (horizontale) et
        demi-hauteur ry (rx, ry : nombre ou une valeur par point), sol plat à plancher x ry sous l'axe."""
        pts = np.asarray(pts, float)
        n = len(pts)
        rxs = np.broadcast_to(np.asarray(rx, float), (n,)); rys = np.broadcast_to(np.asarray(ry, float), (n,))
        for a in range(n - 1):
            p, q = pts[a], pts[a + 1]
            L = np.linalg.norm(q - p)
            m = max(int(L / pas), 1)
            for t in np.linspace(0, 1, m, endpoint=False):
                c = p + (q - p) * t
                rxt = rxs[a] + (rxs[a + 1] - rxs[a]) * t
                ryt = rys[a] + (rys[a + 1] - rys[a]) * t
                self.ellipsoide(c, rxt, ryt, rxt, sol_plat=c[1] - ryt * plancher, entree=entree)
        self.ellipsoide(pts[-1], rxs[-1], rys[-1], rxs[-1], sol_plat=pts[-1][1] - rys[-1] * plancher, entree=entree)

    def puits(self, cx, cz, r, y_bas, y_haut, entree=True):
        """Puits vertical (cylindre irrégulier), du fond jusqu'au-dessus de la surface si entree."""
        i0, i1 = max(int(cx - 1.7 * r - 4) - self.x0, 0), min(int(cx + 1.7 * r + 4) - self.x0, self.W)
        k0, k1 = max(int(cz - 1.7 * r - 4) - self.z0, 0), min(int(cz + 1.7 * r + 4) - self.z0, self.D)
        j0, j1 = max(int(y_bas) - self.y0, 0), min(int(y_haut) - self.y0, self.H)
        Y, Zz, X = np.mgrid[j0:j1, k0:k1, i0:i1]
        X = X + self.x0 + 0.5; Zz = Zz + self.z0 + 0.5
        v = 1 - np.hypot(X - cx, Zz - cz) / r
        sl = (slice(j0, j1), slice(k0, k1), slice(i0, i1))
        self.f[sl] = np.maximum(self.f[sl], v)
        if entree:
            self.entree[sl] |= v > -0.5

    def finir(self, marge_sol=6):
        """Vide, eau, coque. Hors des entrées, rien à moins de marge_sol blocs de la surface."""
        vide = (self.f + self.rugosite * self.bruit) > 0
        Y = (np.arange(self.H) + self.y0)[:, None, None]
        sol = self.sol[None, :, :]
        vide &= (Y < sol - marge_sol) | self.entree
        vide &= Y > -60
        # pas de petits morceaux isolés
        lab, n = ndimage.label(vide)
        if n > 1:
            t = ndimage.sum(np.ones(vide.shape), lab, range(1, n + 1))
            vide = np.isin(lab, np.flatnonzero(t >= 30) + 1)
        # 04/11 : pas de rochers qui flottent dans le vide (morceaux de roche détachés par la rugosité)
        lab, n = ndimage.label(~vide)
        if n > 1:
            t = ndimage.sum(np.ones(vide.shape), lab, range(1, n + 1))
            garde = np.zeros(n + 1, bool); garde[1:] = t >= 400
            vide |= ~garde[lab] & (lab > 0)
        self.vide = vide
        W = self.niveau_eau
        self.eau = vide & (Y < W) if W is not None else np.zeros(vide.shape, bool)
        # coque : rebouche les vides vanilla autour (sous la surface seulement)
        st = ndimage.generate_binary_structure(3, 1)
        coque = ndimage.binary_dilation(vide, st, iterations=3) & ~vide & (Y < sol - 2)
        self.coque = coque
        # 12/11/2026 (test en jeu : stalactites suspendues dans le ciel au-dessus des gouffres, calcite et glace
        # flottantes au bord des entrées) : au-dessus de la surface, ce qui n'est pas vide est de l'air, pas de la roche
        self.sous_sol = np.broadcast_to(Y < np.floor(sol), vide.shape)
        self.deco = {}                                  # (j, k, i) -> classe : blocs posés dans la roche ou le vide
        return self

    # ---------------------------------------------------------------- décor

    def voisins(self):
        v = self.vide
        r = ~v & self.sous_sol                          # roche (pas l'air au-dessus de la surface)
        dessus_plein = np.zeros_like(v); dessus_plein[:-1] = r[1:]
        dessous_plein = np.zeros_like(v); dessous_plein[1:] = r[:-1]
        return dessus_plein, dessous_plein

    def concretions(self, densite_plafond=0.03, densite_sol=0.02, longueur=4, zone=None):
        """Stalactites (du plafond) et stalagmites (du sol hors de l'eau), en dripstone pointu."""
        v, e = self.vide, self.eau
        dp, dsol = self.voisins()
        z = np.ones(v.shape, bool) if zone is None else zone
        plafond = v & dp & z
        sol = v & dsol & ~e & z
        for masque, dens, classes, sens in ((plafond, densite_plafond, STALACTITE, -1), (sol, densite_sol, STALAGMITE, 1)):
            jj, kk, ii = np.nonzero(masque & (self.rng.random(v.shape) < dens))
            for j, k, i in zip(jj, kk, ii):
                L = int(self.rng.integers(1, longueur + 1))
                cells = []
                for s in range(L):
                    jj2 = j + sens * s
                    if not (0 <= jj2 < self.H) or not v[jj2, k, i] or e[jj2, k, i] or (jj2, k, i) in self.deco:
                        break
                    cells.append(jj2)
                if not cells:
                    continue
                n = len(cells)
                for s, jj2 in enumerate(cells):
                    if s == n - 1:
                        c = classes[3]
                    elif s == n - 2:
                        c = classes[2]
                    elif s == 0:
                        c = classes[0]
                    else:
                        c = classes[1]
                    self.deco[(jj2, k, i)] = c
                # bloc de dripstone dans la roche, au point d'attache
                ja = j - sens
                if 0 <= ja < self.H and not v[ja, k, i] and self.sous_sol[ja, k, i]:
                    self.deco[(ja, k, i)] = DRIPSTONE

    def parois(self, classe, proportion=0.3, graine=0, zone=None, sol_seul=False, plafond_seul=False):
        """Habille la roche au contact du vide (coulées de calcite, glace, basalte…) par plaques."""
        v = self.vide
        st = ndimage.generate_binary_structure(3, 1)
        contact = ndimage.binary_dilation(v, st) & ~v
        dp, dsol = self.voisins()
        if sol_seul:
            contact = np.zeros_like(v); contact[:-1] = v[1:] & ~v[:-1]     # roche juste sous un vide
        if plafond_seul:
            contact = np.zeros_like(v); contact[1:] = v[:-1] & ~v[1:]
        contact &= self.sous_sol
        if zone is not None:
            contact &= zone
        b = ndimage.gaussian_filter(np.random.default_rng(graine).standard_normal(v.shape).astype(np.float32), 1.5)
        seuil = np.quantile(b, 1 - proportion)
        jj, kk, ii = np.nonzero(contact & (b > seuil))
        for j, k, i in zip(jj, kk, ii):
            self.deco.setdefault((j, k, i), classe if not callable(classe) else classe(j, k, i))

    def colonne(self, cx, cz, r, y_bas, y_haut, classe):
        """Pilier plein (stalagmite géante, colonne de glace) dans le vide."""
        for j in range(max(int(y_bas) - self.y0, 0), min(int(y_haut) - self.y0, self.H)):
            for k in range(max(int(cz - r) - self.z0, 0), min(int(cz + r) + 1 - self.z0, self.D)):
                for i in range(max(int(cx - r) - self.x0, 0), min(int(cx + r) + 1 - self.x0, self.W)):
                    if np.hypot(i + self.x0 + 0.5 - cx, k + self.z0 + 0.5 - cz) <= r and self.vide[j, k, i]:
                        self.deco[(j, k, i)] = classe

    # ---------------------------------------------------------------- sortie

    def enregistrements(self):
        out = []
        jj, kk, ii = np.nonzero(self.coque)
        for j, k, i in zip(jj, kk, ii):
            if (j, k, i) not in self.deco:
                out.append((i + self.x0, j + self.y0, k + self.z0, PLEIN))
        jj, kk, ii = np.nonzero(self.vide)
        for j, k, i in zip(jj, kk, ii):
            if (j, k, i) in self.deco:
                continue
            out.append((i + self.x0, j + self.y0, k + self.z0, EAU if self.eau[j, k, i] else AIR))
        # 04/11 : aucun décor au-dessus du sol (calcite, dripstone et glace qui flottaient autour des entrées)
        for (j, k, i), c in self.deco.items():
            if j + self.y0 >= self.sol[k, i] - 1 and not self.vide[j, k, i]:
                continue
            out.append((i + self.x0, j + self.y0, k + self.z0, c))
        return out

    def bilan(self):
        Y = (np.arange(self.H) + self.y0)[:, None, None] * np.ones(self.vide.shape)
        perce = self.vide & (Y >= self.sol[None] - 1)
        return (f"{self.nom} : {int(self.vide.sum())} blocs de vide ({int(self.eau.sum())} d'eau), y "
                f"{int(Y[self.vide].min())} à {int(Y[self.vide].max())}, {len(self.deco)} blocs de décor, "
                f"coque {int(self.coque.sum())}, ouvertures en surface {int(perce.any(0).sum())} colonnes")


def bloc(lat, lon):
    return np.array([lon * T.BPD, -lat * T.BPD])


def sinueux(rng, p0, p1, n=8, ampl=8.0, dy=None):
    """Polyligne sinueuse de p0 à p1 (x, y, z), écarts latéraux d'ampl blocs."""
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    t = np.linspace(0, 1, n)
    d = p1 - p0
    nrm = np.array([-d[2], 0, d[0]]); nrm /= np.linalg.norm(nrm) + 1e-9
    off = ampl * np.sin(np.pi * t) * (rng.standard_normal(n) * 0.6 + np.sin(t * 7.3 + rng.random() * 6))
    pts = p0[None] + t[:, None] * d[None] + off[:, None] * nrm[None]
    if dy is not None:
        pts[:, 1] += dy * np.sin(np.pi * t)
    return pts


# ---------------------------------------------------------------- les grottes

def padirac():
    """Gouffre de Padirac : le grand puits (≈ 17 blocs de diamètre) s'ouvre dans le causse et tombe d'une
    cinquantaine de blocs jusqu'à la rivière souterraine ; elle serpente sur 250 blocs (eau 2 à 3 blocs, voûte haute,
    navigable en barque), passe le lac de la Pluie (grande stalactite) et finit au Grand Dôme (≈ 60 blocs de haut)."""
    c = bloc(44.8583, 1.7505)
    g = Grotte("padirac", c[0] - 70, c[0] + 380, c[1] - 160, c[1] + 160, -25, 90, graine=301, eau=6)
    rng = g.rng
    sol_c = float(g.sol[int(c[1] - g.z0), int(c[0] - g.x0)])
    g.puits(c[0], c[1], 9.5, 6, sol_c + 3)
    g.ellipsoide((c[0], 12, c[1]), 14, 9, 14, sol_plat=6)               # éboulis au pied du puits
    pts = sinueux(rng, (c[0] + 6, 7, c[1] + 2), (c[0] + 170, 7, c[1] + 50), n=10, ampl=22)
    pts2 = sinueux(rng, pts[-1], (c[0] + 300, 7, c[1] - 20), n=9, ampl=20)
    g.galerie(np.vstack([pts, pts2[1:]]), rx=np.r_[np.full(10, 6.0), np.full(8, 7.5)], ry=np.r_[np.full(10, 12.0), np.full(8, 15.0)],
              plancher=0.4)
    lac = pts[6]
    g.ellipsoide((lac[0], 20, lac[2]), 20, 24, 16, sol_plat=1)            # lac de la Pluie
    dome = pts2[-1]
    g.ellipsoide((dome[0] + 20, 22, dome[2]), 38, 40, 32, sol_plat=6)     # Grand Dôme
    g.finir()
    g.concretions(0.05, 0.02, 5)
    g.parois(CALCITE, 0.25, 302)
    g.parois(ARGILE, 0.5, 303, sol_seul=True)
    # la Grande Pendeloque : stalactite géante qui touche presque l'eau du lac de la Pluie
    g.colonne(lac[0], lac[2], 3.0, 9, 44, DRIPSTONE)
    g.colonne(lac[0], lac[2], 1.6, 7, 9, CALCITE)
    # le Grand Dôme : stalagmites géantes
    for k in range(4):
        a = rng.random() * 2 * np.pi
        px, pz = dome[0] + 20 + 22 * np.cos(a), dome[2] + 18 * np.sin(a)
        g.colonne(px, pz, 2.2, 6, 6 + rng.integers(10, 24), CALCITE)
    return g


def han():
    """Grottes de Han : la Lesse se perd au gouffre de Belvaux (sud-est), traverse la colline sous terre et ressort
    au trou de Han (nord-ouest). Galeries sèches au-dessus (galerie des Draperies), salle du Dôme immense (≈ 50
    blocs de haut) avec son lac ; entrée par un couloir qui descend du flanc de la colline, sortie par la rivière."""
    a = bloc(50.1172, 5.1946)        # Belvaux (perte)
    b = bloc(50.1255, 5.1855)        # trou de Han (résurgence)
    m = (a + b) / 2
    u = (a - b) / np.linalg.norm(a - b)
    # la traversée réelle (1 km, 4 blocs à 1:250) est agrandie : la résurgence et l'entrée sèche (Belvaux) restent à
    # leur vraie place, la rivière s'enfonce sous la colline sur 260 blocs vers le sud-est
    B = b.copy(); A = b + u * 260
    m = (A + B) / 2
    g = Grotte("han", m[0] - 230, m[0] + 230, m[1] - 230, m[1] + 230, -25, 95, graine=311, eau=10)
    rng = g.rng
    riv = sinueux(rng, (A[0], 11, A[1]), (B[0], 11, B[1]), n=14, ampl=24)
    g.galerie(riv, 6.5, 11.0, plancher=0.4)
    dome = riv[7]
    g.ellipsoide((dome[0], 22, dome[2]), 42, 34, 34, sol_plat=4)          # salle du Dôme
    # galerie sèche des Draperies, au-dessus, de l'entrée vers le Dôme
    E = a + np.array([8.0, -8.0])
    sol_E = float(g.sol[int(E[1] - g.z0), int(E[0] - g.x0)])
    ent = [(E[0], sol_E + 2, E[1]), (E[0] + 6, sol_E - 8, E[1] + 6), (E[0] + 14, 46, E[1] + 16)]
    g.galerie(ent, 3.0, 4.5, plancher=0.5, entree=True)
    dr = sinueux(rng, ent[-1], (dome[0] + 20, 44, dome[2] - 10), n=10, ampl=10)
    g.galerie(dr, 4.0, 7.0, plancher=0.45)
    # la résurgence : la rivière ressort au pied de la colline
    sol_B = float(g.sol[int(B[1] - g.z0), int(B[0] - g.x0)])
    sortie = [riv[-1], (B[0] - 10, 24, B[1] - 10), (B[0] - 18, max(sol_B - 4, 30), B[1] - 18), (B[0] - 26, sol_B + 3, B[1] - 26)]
    g.galerie(sortie, 5.0, 6.0, plancher=0.3, entree=True)
    g.finir()
    g.concretions(0.06, 0.04, 5)
    g.parois(CALCITE, 0.35, 312)                                          # draperies
    g.parois(GRAVIER, 0.4, 313, sol_seul=True)
    return g


def postojna():
    """Postojna : la Pivka se perd sous la colline (rivière en bas, à l'entrée) ; au-dessus, un immense réseau sec
    couvert de concrétions — galeries en boucle, la salle de concert (≈ 60 blocs), le « Brillant » (stalagmite
    blanche), les colonnes ; entrée par un couloir depuis la surface."""
    c = bloc(45.7826, 14.2040)
    g = Grotte("postojna", c[0] - 80, c[0] + 420, c[1] - 260, c[1] + 140, -30, 100, graine=321, eau=4, rugosite=0.25)
    rng = g.rng
    sol_c = float(g.sol[int(c[1] - g.z0), int(c[0] - g.x0)])
    # la Pivka : entre sous la colline au pied de l'entrée, coule au fond (niveau 20)
    riv = sinueux(rng, (c[0] + 5, 5, c[1] + 10), (c[0] + 300, 5, c[1] - 180), n=14, ampl=28)
    g.galerie(riv, 6.0, 10.0, plancher=0.4)
    # entrée : couloir qui descend de la surface jusqu'au réseau sec (y 55)
    ent = [(c[0], sol_c + 2, c[1]), (c[0] + 8, sol_c - 10, c[1] - 4), (c[0] + 24, 58, c[1] - 12)]
    g.galerie(ent, 3.5, 5.0, plancher=0.5, entree=True)
    # réseau sec : grande boucle et branches
    boucle = [ent[-1], (c[0] + 120, 55, c[1] - 40), (c[0] + 240, 50, c[1] - 30), (c[0] + 360, 52, c[1] - 120),
              (c[0] + 290, 56, c[1] - 220), (c[0] + 150, 58, c[1] - 200), (c[0] + 70, 57, c[1] - 100), ent[-1]]
    pts = []
    for p, q in zip(boucle[:-1], boucle[1:]):
        pts.append(sinueux(rng, p, q, n=6, ampl=10)[:-1])
    pts = np.vstack(pts + [np.array([boucle[-1]], float)])
    g.galerie(pts, 8.0, 12.0, plancher=0.45)
    concert = (c[0] + 320, 58, c[1] - 170)
    g.ellipsoide(concert, 44, 30, 34, sol_plat=40)                        # salle de concert
    g.ellipsoide((c[0] + 180, 56, c[1] - 35), 18, 14, 16, sol_plat=46)    # salle des Spaghettis
    # gouffre qui relie le réseau sec à la rivière (le « Grand Effondrement »)
    g.ellipsoide((c[0] + 240, 30, c[1] - 30), 22, 34, 18, sol_plat=1)
    g.finir()
    g.concretions(0.09, 0.07, 6)
    g.parois(CALCITE, 0.45, 322)
    g.parois(DRIPSTONE, 0.25, 323)
    g.parois(ARGILE, 0.5, 324, sol_seul=True)
    # le Brillant et des colonnes dans la salle de concert
    g.colonne(concert[0] - 12, concert[2] + 6, 2.0, 40, 58, CALCITE)
    for k in range(6):
        a = rng.random() * 2 * np.pi
        g.colonne(concert[0] + 30 * np.cos(a), concert[2] + 24 * np.sin(a), 2.0, 39, 80, DRIPSTONE)
    return g


def eisriesenwelt():
    """Eisriesenwelt (Tennengebirge) : la plus grande grotte de glace du monde. Le porche s'ouvre dans le flanc de la
    montagne ; derrière, la salle Posselt et le mur de glace (cascade gelée), les sols, colonnes et draperies de
    glace sur la première partie ; plus loin, la roche nue des grandes galeries."""
    c = bloc(47.5036, 13.1897)
    g = Grotte("eisriesenwelt", c[0] - 80, c[0] + 260, c[1] - 160, c[1] + 120, 20, 150, graine=331, rugosite=0.25)
    rng = g.rng
    # porche : là où le flanc est le plus raide autour du point réel
    sol = ndimage.gaussian_filter(g.sol, 2)
    gz, gx = np.gradient(sol)
    k0, i0 = int(c[1] - g.z0), int(c[0] - g.x0)
    sub = np.hypot(gx, gz)[k0 - 30:k0 + 31, i0 - 30:i0 + 31]
    dk, di = np.unravel_index(np.argmax(sub), sub.shape)
    P = np.array([c[0] - 30 + di, c[1] - 30 + dk]); sol_P = float(g.sol[int(P[1] - g.z0), int(P[0] - g.x0)])
    vers = np.array([gx[int(P[1] - g.z0), int(P[0] - g.x0)], gz[int(P[1] - g.z0), int(P[0] - g.x0)]])
    vers = vers / (np.linalg.norm(vers) + 1e-9)                       # vers le haut de la pente (dans la montagne)
    porche = [(P[0] - 6 * vers[0], sol_P + 4, P[1] - 6 * vers[1]), (P[0], sol_P - 2, P[1]),
              (P[0] + 18 * vers[0], sol_P - 16, P[1] + 18 * vers[1])]
    g.galerie(porche, 7.0, 7.0, plancher=0.4, entree=True)
    q = np.array(porche[-1])
    posselt = q + np.array([30 * vers[0], -12, 30 * vers[1]])
    g.ellipsoide(tuple(posselt), 30, 22, 24, sol_plat=posselt[1] - 12)
    g.galerie([q, posselt], 8.0, 10.0, plancher=0.4)
    mur = posselt + np.array([30 * vers[0], 6, 30 * vers[1]])         # le mur de glace monte vers le palais
    g.galerie([posselt, mur], 7.0, 12.0, plancher=0.3)
    palais = mur + np.array([40 * vers[0], 0, 40 * vers[1]])
    g.ellipsoide(tuple(palais), 34, 20, 28, sol_plat=palais[1] - 10)   # palais de glace d'Hymir
    loin = sinueux(rng, palais, palais + np.array([120 * vers[0] + 40 * vers[1], -20, 120 * vers[1] - 40 * vers[0]]),
                   n=10, ampl=18)
    g.galerie(loin, 6.0, 10.0, plancher=0.45)
    g.finir(marge_sol=8)
    Yz = np.ones(g.vide.shape, bool)
    # zone de glace : les 110 premiers blocs depuis le porche
    Xg = (np.arange(g.W) + g.x0)[None, None, :]; Zg = (np.arange(g.D) + g.z0)[None, :, None]
    dist = np.hypot(Xg - P[0], Zg - P[1]) * Yz
    glace = dist < 110
    g.parois(GLACE_TASSEE, 0.95, 332, sol_seul=True, zone=glace)
    g.parois(lambda j, k, i: GLACE_BLEUE if (i + k) % 5 == 0 else GLACE_TASSEE, 0.55, 333, zone=glace)
    g.parois(NEIGE, 0.6, 334, sol_seul=True, zone=(dist < 22))
    g.concretions(0.04, 0.03, 4, zone=~glace)
    # stalagmites de glace et le mur de glace
    for k in range(10):
        a = rng.random() * 2 * np.pi; r = rng.random() * 14
        g.colonne(posselt[0] + r * np.cos(a), posselt[2] + r * np.sin(a), 1.2, posselt[1] - 10, posselt[1] - 10 + rng.integers(3, 9), GLACE)
    for t in np.linspace(0, 1, 12):
        p = posselt + (mur - posselt) * t
        g.colonne(p[0], p[2], 5.5, p[1] - 12, p[1] - 12 + 3 + 12 * t, GLACE_BLEUE if t > 0.5 else GLACE_TASSEE)
    return g


def fingal():
    """Grotte de Fingal (île de Staffa, construite par le lieu « fingal ») : grotte marine de 70 m creusée dans les
    orgues de basalte ; ici une voûte de ~18 blocs au-dessus de la mer, profonde de 45 blocs ; le long de la paroi
    est, une corniche de colonnes brisées où l'on marche au-dessus de l'eau."""
    L = np.load("/tmp/lieu_fingal.npz")
    X, Z, y = L["X"], L["Z"], L["y"]
    a = L["poids"] > 0.5
    sol = np.where(a, y, L["h"])
    x0, z0 = int(X[0, 0]), int(Z[0, 0])
    g = Grotte("fingal", x0, x0 + X.shape[1], z0, z0 + X.shape[0], 30, 100, sol=np.floor(sol), graine=341, eau=63,
               rugosite=0.12)
    e = np.array([float(L["entree_x"]), float(L["entree_z"])]); d = np.array([float(L["dir_x"]), float(L["dir_z"])])
    pts = [(e[0] - 8 * d[0], 70, e[1] - 8 * d[1]), (e[0] + 20 * d[0], 69, e[1] + 20 * d[1]),
           (e[0] + 44 * d[0], 66, e[1] + 44 * d[1])]
    g.galerie(pts, np.array([6.0, 5.0, 3.0]), np.array([13.0, 11.0, 7.0]), plancher=0.9, entree=True)
    g.finir(marge_sol=3)
    # parois en colonnes de basalte : chaque colonne (2 x 2) a sa teinte
    def col(j, k, i):
        h = ((i + g.x0) // 2 * 7919 + (k + g.z0) // 2 * 104729) % 4
        return BASALTE_POLI if h == 0 else (BASALTE_LISSE if h == 1 else BASALTE)
    g.parois(col, 1.0, 342)
    # corniche : colonnes brisées le long de la paroi est, au ras de l'eau
    nrm = np.array([-d[1], d[0]])
    for t in np.linspace(2, 40, 40):
        p = e + d * t + nrm * (4.2 - t * 0.04)
        for dn in (0.0, 1.0):
            q = p + nrm * dn
            i, k = int(q[0]) - g.x0, int(q[1]) - g.z0
            h = 63 + int(((int(q[0]) // 2) * 31 + (int(q[1]) // 2) * 17) % 2)
            for yy in range(30, h + 1):
                j = yy - g.y0
                if 0 <= k < g.D and 0 <= i < g.W and g.vide[j, k, i]:
                    g.deco[(j, k, i)] = BASALTE
    return g


def capri():
    """Grotte bleue de Capri (côte nord-ouest de l'île, lieu « capri ») : une entrée basse au ras de l'eau (2 blocs
    de haut, 3 de large), puis une salle de 40 x 18 blocs dont l'eau, éclairée par le fond, brille en bleu (lanternes
    marines sous le sable blanc)."""
    L = np.load("/tmp/lieu_capri.npz")
    X, Z, y = L["X"], L["Z"], L["y"]
    a = L["poids"] > 0.5
    sol = np.where(a, y, L["h"])
    x0, z0 = int(X[0, 0]), int(Z[0, 0])
    g = Grotte("capri", x0, x0 + X.shape[1], z0, z0 + X.shape[0], 30, 100, sol=np.floor(sol), graine=351, eau=63,
               rugosite=0.12)
    e = np.array([float(L["grotte_x"]), float(L["grotte_z"])]); d = np.array([float(L["grotte_dx"]), float(L["grotte_dz"])])
    # entrée : boyau étroit et bas (l'eau jusqu'à 63, la voûte à 65)
    ent = [(e[0] - 6 * d[0], 63.5, e[1] - 6 * d[1]), (e[0] + 8 * d[0], 63.5, e[1] + 8 * d[1])]
    g.galerie(ent, 1.8, 2.2, plancher=4.0, entree=True)
    salle = e + d * 26
    g.ellipsoide((salle[0], 62, salle[1]), 20, 9, 10, sol_plat=55)
    g.finir(marge_sol=3)
    # fond : sable blanc et lanternes marines (la lumière qui fait briller l'eau)
    jj, kk, ii = np.nonzero(g.vide)
    fond = {}
    for j, k, i in zip(jj, kk, ii):
        if j > 0 and not g.vide[j - 1, k, i]:
            fond[(k, i)] = j - 1
    for (k, i), j in fond.items():
        X_, Z_ = i + g.x0, k + g.z0
        # 04/11 : lanternes semées au hasard (la grille régulière se voyait), une sur quinze
        g.deco[(j, k, i)] = LANTERNE if g.rng.random() < 0.065 else SABLE
    return g


GROTTES = {"padirac": padirac, "han": han, "postojna": postojna, "eisriesenwelt": eisriesenwelt, "fingal": fingal,
           "capri": capri}


def ecrire(liste):
    with gzip.GzipFile(SORTIE, "wb", 9, mtime=0) as f:
        f.write(struct.pack("<i", len(liste)))
        for (x, yy, z, c) in liste:
            f.write(struct.pack("<3iB", int(x), int(yy), int(z), int(c)))
    print(f"{len(liste)} blocs -> {SORTIE} ({os.path.getsize(SORTIE) // 1024} Ko)")


def apercu(g):
    """Coupe et vue de dessus (vide en clair, eau en bleu, décor en couleur) : /tmp/grotte_<nom>.png"""
    from PIL import Image
    v, e = g.vide, g.eau
    dessus = np.zeros((g.D, g.W, 3), np.uint8) + 40
    prof = np.where(v.any(0), v.shape[0] - np.argmax(v[::-1], axis=0), 0)
    dessus[v.any(0)] = np.stack([60 + prof[v.any(0)] * 1.5] * 3, -1).clip(0, 255)
    dessus[e.any(0)] = (50, 110, 220)
    coupe = np.zeros((g.H, g.W, 3), np.uint8) + 40
    cv = v.any(1); ce = e.any(1)
    coupe[cv] = (200, 200, 200); coupe[ce] = (50, 110, 220)
    s = (np.floor(g.sol).max(0) - g.y0).astype(int)
    for i in range(g.W):
        if 0 <= s[i] < g.H:
            coupe[s[i], i] = (90, 170, 60)
    coupe = coupe[::-1]
    im = np.vstack([dessus, np.zeros((4, g.W, 3), np.uint8) + 255, coupe])
    Image.fromarray(im).resize((im.shape[1] * 2, im.shape[0] * 2), Image.NEAREST).save(f"/tmp/grotte_{g.nom}.png")


if __name__ == "__main__":
    noms = [a for a in sys.argv[1:] if not a.startswith("--")] or list(GROTTES)
    import json
    zf = os.path.join(os.path.dirname(os.path.abspath(__file__)), "banc", "zones.json")
    zones = json.load(open(zf))
    toutes = []
    for n in GROTTES:
        if n not in noms and os.path.exists(f"/tmp/grotte_{n}.npy"):
            toutes += [tuple(r) for r in np.load(f"/tmp/grotte_{n}.npy")]
            continue
        if n not in noms:
            print(f"{n} : pas encore calculée (lancer sans argument pour tout refaire)")
            continue
        g = GROTTES[n]()
        print(g.bilan())
        if n not in ("fingal", "capri"):                      # celles-là sont dans la zone de leur île
            zones[f"grotte_{n}"] = [g.x0, g.x0 + g.W, g.z0, g.z0 + g.D]
        r = g.enregistrements()
        np.save(f"/tmp/grotte_{n}.npy", np.array(r, np.int32))
        toutes += r
        if APERCU:
            apercu(g)
    ecrire(toutes)
    open(zf, "w").write(json.dumps(zones, ensure_ascii=False, indent=1) + "\n")

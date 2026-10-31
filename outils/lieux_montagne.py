"""Lieux du lot 2 (montagne, cascades, fjords), en tuiles : Gavarnie, Gullfoss, Skógafoss, Plitvice, Geiranger,
Cervin, Tre Cime, Preikestolen.

Même méthode que le lot 1 (outils/lieux_cotiers.py) : toute la forme est calculée ici au bloc près, en 1:250, sur le
terrain exact du mod (terre_py), puis écrite dans les tuiles (en_tuiles). Nouveau au lot 2 : l'EAU du lieu (tuiles
version 2) — torrents, lacs, bassins en altitude, posés par FleuveFeature comme le lit d'un cours d'eau. Là où une
colonne d'eau touche une colonne d'eau plus basse, l'eau déborde et tombe : c'est ainsi que naissent les cascades
(Grande Cascade de Gavarnie, Gullfoss, Skógafoss, barrages de Plitvice, Sept Sœurs).

Règles d'eau (contrôlées par verifier_eau) :
- une colonne d'eau a son sol sous l'eau : y < eau - 1 (au moins un bloc d'eau) ;
- ses voisines sans eau la retiennent : y >= eau - 0,5 (le bloc du dessus atteint eau - 1) ;
- une voisine d'eau plus basse = une chute voulue (lèvre d'une cascade, bord d'un barrage).
Tout est exagéré (hauteurs et largeurs), comme au lot 1 : à 1:250 le Preikestolen ferait un dixième de bloc.

Usage : python3 outils/lieux_montagne.py [lieu ...] [--apercu]
"""
import os, sys
import numpy as np
from scipy import ndimage
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import terre_py as T
import lieux_cotiers as L
from lieux_cotiers import (bruit, bloc_de, courbe, lisse, en_tuiles, finir_types, PLATEAU, PLAGE, FOND, ROC, PRE,
                           NEIGE, GLACE, EBOULIS, MOUSSE, LIT, TAILLEE, REMBLAI, BIOME, INONDE)

BPD = T.BPD
SANS = np.nan
APERCU = "--apercu" in sys.argv


# ---------------------------------------------------------------- outils communs

def zone(lat, lon, dx, dz):
    """Grille de colonnes centrée sur (lat, lon), demi-largeurs dx (est-ouest) et dz (nord-sud) en blocs."""
    c = bloc_de(lat, lon)
    x0, z0 = int(np.floor(c[0] - dx)), int(np.floor(c[1] - dz))
    X, Z = np.meshgrid(np.arange(x0, x0 + 2 * dx, dtype=float), np.arange(z0, z0 + 2 * dz, dtype=float))
    return X, Z, c


def polyligne(X, Z, P):
    """Distance de chaque colonne à une polyligne P (liste de points en blocs) et abscisse le long de celle-ci."""
    P = np.asarray(P, float)
    d = np.full(X.shape, 1e9); s = np.zeros(X.shape); acc = 0.0
    for a, b in zip(P[:-1], P[1:]):
        ab = b - a; L2 = float(ab @ ab); Ls = np.sqrt(L2)
        u = np.clip(((X - a[0]) * ab[0] + (Z - a[1]) * ab[1]) / L2, 0, 1)
        di = np.hypot(X - a[0] - u * ab[0], Z - a[1] - u * ab[1])
        m = di < d
        d = np.where(m, di, d); s = np.where(m, acc + u * Ls, s)
        acc += Ls
    return d, s, acc


def lisser_trace(P, n=400, sigma=1.0):
    """Tracé lissé et rééchantillonné (points en blocs)."""
    P = np.asarray(P, float)
    t = np.r_[0, np.cumsum(np.hypot(*np.diff(P, axis=0).T))]
    u = np.linspace(0, t[-1], n)
    xs = np.interp(u, t, ndimage.gaussian_filter1d(P[:, 0], sigma, mode="nearest"))
    zs = np.interp(u, t, ndimage.gaussian_filter1d(P[:, 1], sigma, mode="nearest"))
    return np.c_[xs, zs]


def verifier_eau(nom, y, eau, chutes_ok=True):
    """Contrôle des règles d'eau ; rend le nombre de fuites (voisine sans eau trop basse)."""
    w = np.isfinite(eau)
    fond_haut = w & (y >= eau - 1.0)
    fuites = 0; chutes = 0
    for dj, di in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        yv = np.roll(np.roll(y, dj, 0), di, 1); ev = np.roll(np.roll(eau, dj, 0), di, 1)
        wv = np.isfinite(ev)
        f = w & ~wv & (yv < eau - 0.5)
        f[[0, -1], :] = False; f[:, [0, -1]] = False
        fuites += int(f.sum())
        chutes += int((w & wv & (ev < eau)).sum())
    print(f"  eau {nom} : {int(w.sum())} colonnes, sol trop haut {int(fond_haut.sum())}, fuites {fuites}, "
          f"bords de chute {chutes}")
    return fuites


def retenir(y, eau, iterations=3):
    """Relève les voisines sans eau trop basses (bord d'un bassin) pour qu'elles retiennent l'eau."""
    w = np.isfinite(eau)
    for _ in range(iterations):
        besoin = np.full(y.shape, -np.inf)
        for dj, di in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            ev = np.roll(np.roll(np.where(w, eau, -np.inf), dj, 0), di, 1)
            besoin = np.maximum(besoin, ev - 0.5)
        y = np.where(~w & (y < besoin), besoin + 0.05, y)
    # rapides : l'eau d'un bief qui coule sur le bief suivant (marche de 1 à 3 blocs) s'étale jusqu'à 7 blocs en aval,
    # au niveau du bief d'amont ; les rives proches d'une marche sont donc tenues à ce niveau (sinon l'eau déborde)
    from scipy import ndimage
    E = np.where(w, eau, -np.inf)
    amont = ndimage.maximum_filter(E, size=15)
    propre = ndimage.minimum_filter(np.where(w, eau, np.inf), size=3)     # bief le plus bas qui touche la rive
    rive = ~w & np.isfinite(propre)
    marche = rive & (amont > propre) & (amont - propre <= 3)
    y = np.where(marche & (y < amont - 0.5), amont - 0.45, y)
    return y


def apercu(nom, X, Z, y, eau, typ, palette, haut=None):
    """Aperçu isométrique hors du jeu (mêmes couleurs que le rendu du banc) : /tmp/apercu_<nom>.png."""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "banc"))
    import rendu
    y0 = int(np.floor(np.nanmin(y))) - 4
    y1 = int(np.ceil(max(np.nanmax(y), np.nanmax(np.where(np.isfinite(eau), eau, -1e9))))) + 2
    noms = ["minecraft:air", "minecraft:water", "minecraft:stone", "minecraft:grass_block", "minecraft:snow_block",
            "minecraft:packed_ice", "minecraft:gravel", "minecraft:moss_block", "minecraft:calcite", "minecraft:andesite",
            "minecraft:basalt", "minecraft:deepslate", "minecraft:diorite", "minecraft:tuff", "minecraft:dirt"]
    corps = {"CALCAIRE": 9, "BASALTE": 10, "TRAVERTIN": 8, "GNEISS": 2, "CERVIN": 11, "DOLOMIE": 12, "GRANITE": 9, "ISLANDE": 10, "CHAUSSEE": 10, "CONGLOMERAT": 13, "VOLCAN": 11}[palette]
    D, W = y.shape
    H = y1 - y0
    B = np.zeros((D, H, W), np.uint8)
    t = np.floor(y).astype(int) - y0
    cl = typ & 15
    yy = np.arange(H)[None, :, None]
    solide = yy <= t[:, None, :]
    B[solide] = corps
    bandes = ((yy + y0) % 7 == 0) & solide
    B[bandes] = 13 if corps != 13 else 2
    dessus = {PLATEAU: 3, PRE: 3, NEIGE: 4, GLACE: 5, EBOULIS: 6, MOUSSE: 7, LIT: 6, FOND: 6}
    for k, b in dessus.items():
        m = (cl == k)
        jj, ii = np.nonzero(m)
        tt = np.clip(t[jj, ii], 0, H - 1)
        B[jj, tt, ii] = b
    # terrain du mod hors lieu (typ 0) : herbe dessus
    jj, ii = np.nonzero(cl == 0)
    B[jj, np.clip(t[jj, ii], 0, H - 1), ii] = 3
    if eau is not None:
        e = np.where(np.isfinite(eau), eau - y0, -1).astype(int)
        B[(yy < e[:, None, :]) & ~solide] = 1
    np.savez_compressed(f"/tmp/apercu_{nom}.npz", noms=np.array(noms), blocs=B, x0=int(X[0, 0]), y0=y0, z0=int(Z[0, 0]))
    for suffixe, opts in (("", {}), ("_nord", {"nord": True})):
        rendu.rendu(f"/tmp/apercu_{nom}.npz", f"/tmp/apercu_{nom}{suffixe}.png", K=2, **opts)
    print(f"  aperçu : /tmp/apercu_{nom}.png, /tmp/apercu_{nom}_nord.png")


def loin_des_fleuves(X, Z, w, marge=35.0):
    """Emprise réduite à l'approche de la vallée d'un cours d'eau du mod (le lieu n'y touche pas : en_tuiles l'y
    rabattrait d'un coup)."""
    inf = T.influence_fleuves(X, Z)
    return w * lisse(np.clip((inf - 3.0) / marge, 0, 1))


def ecrire(nom, X, Z, y, h, sommet, typ, sd, eau, palette, marge=10, garder_fleuves=True, vox=None):
    """Contrôles d'eau, écriture dans les tuiles, aperçu éventuel."""
    y = np.where(np.isfinite(eau), np.minimum(y, eau - 1.05), y)          # au moins un bloc d'eau
    y = retenir(y, eau)
    verifier_eau(nom, y, eau)
    typ, actif = en_tuiles(nom, X, Z, y, h, sommet, typ, sd, marge=marge, eau=eau, garder_fleuves=garder_fleuves,
                           vox=vox)
    if APERCU:
        apercu(nom, X, Z, np.where(actif, y, h), np.where(actif, eau, np.nan), np.where(actif, typ, 0), palette)
    return y, typ, actif


# ---------------------------------------------------------------- cirque de Gavarnie

def pente_locale(y):
    """Pente (blocs par bloc) qui ignore une marche voisine : une vire au pied d'un mur reste plate."""
    p = np.zeros(y.shape)
    for ax in (0, 1):
        av = np.abs(np.diff(y, axis=ax, prepend=np.take(y, [0], axis=ax)))
        ap = np.abs(np.diff(y, axis=ax, append=np.take(y, [-1], axis=ax)))
        p = np.maximum(p, np.minimum(av, ap))
    return p


def crete(X, Z, graine, echelle=16.0):
    """Bruit de crêtes (arêtes vives, pics) ~[0, 1]."""
    n = 1 - np.abs(bruit(X, Z, echelle, graine))
    return n ** 2


def gavarnie():
    """Cirque de Gavarnie (Pyrénées) : amphithéâtre calcaire ouvert au nord, trois étages de parois séparés par des
    vires (enneigées en haut), crête découpée de pics (Marboré, Casque, Taillon) et la Brèche de Roland ; la Grande
    Cascade (422 m) tombe du fond du cirque ; le gave de Pau en sort vers le village de Gavarnie.
    En vrai ~3,5 km de large (14 blocs), parois de 1 500 m : ici ~70 blocs de large, parois de ~60 blocs."""
    X, Z, c = zone(42.697, -0.010, 215, 200)
    h, sd = T.hauteur_base(X, Z)
    dx, dz = X - c[0], Z - c[1]
    r = np.hypot(dx / 1.22, dz)                                  # plus large que profond (un fer à cheval)
    th = np.degrees(np.arctan2(dx, dz))                         # 0 = sud (fond du cirque), ±180 = nord (ouverture)
    R0 = 31 + 3.5 * bruit(X, Z, 25, 101) + 1.5 * np.sin(np.radians(th) * 7) + 2.5 * np.sin(np.radians(th) * 3 + 1)
    e = r - R0
    A = lisse(np.clip((160 - np.abs(th)) / 45, 0, 1))          # parois pleines au fond, nulles vers l'ouverture
    # gave de Pau : du pied de la Grande Cascade vers le nord, en méandres
    th_c = 18.0
    ax = np.array([np.sin(np.radians(th_c)), np.cos(np.radians(th_c))])
    pied = c + ax * 31.0
    trace = lisser_trace([pied, c + np.array([2, 10]), c + np.array([-5, -15]), c + np.array([-12, -45]),
                          c + np.array([-4, -72]), c + np.array([-14, -100]), c + np.array([-8, -128]),
                          c + np.array([-16, -150])], 400, 1.0)
    d_g, s_g, L_g = polyligne(X, Z, trace)
    # fond : le cirque (légère pente vers le nord), puis la vallée qui descend le long du gave
    sol_c = 123.6 + 0.04 * np.minimum(dz, 0) + 0.6 * bruit(X, Z, 14, 102)
    sol_v = 123.6 - 0.075 * s_g + 0.6 * bruit(X, Z, 14, 102)
    vallee = (dz < 8) & (d_g < 15 + 0.07 * s_g + 3 * bruit(X, Z, 20, 108)) & (e > -6)
    dans = (e < 0) | vallee
    sol = np.where(e < 0, sol_c, sol_v)
    # profil des parois : trois murs verticaux et deux vires, en fonction de la distance au pied e
    j = 1.3 * bruit(X, Z, 9, 103)
    m1, m2, m3 = 0.0 + j, 6.0 + j * 0.8, 11.0 + j * 0.6
    h1 = 22.0 + 2.0 * bruit(X, Z, 30, 104)
    h2 = 41.0 + 2.5 * bruit(X, Z, 33, 105)
    h3 = 60.5 + 3.0 * bruit(X, Z, 40, 106)
    P = np.where(e < m1, 0.0, h1 + 1.2 * lisse((e - m1) / 5))
    P = np.where(e >= m2, h2 + 1.0 * lisse((e - m2) / 4), P)
    P = np.where(e >= m3, h3 + 2.0 * lisse((e - m3) / 4), P)
    # crête découpée : pics et cols au-dessus du mur du haut, puis versants rocheux qui redescendent (peuvent passer
    # sous le terrain du mod : le relief réel reprend)
    pics = 9.0 * crete(X, Z, 109, 13) + 4.0 * crete(X, Z, 110, 6)
    haut_crete = h3 + 2.0 + pics * lisse(np.clip((e - m3) / 5, 0, 1))
    # versants extérieurs rocheux : arêtes et couloirs (bruit de crêtes), pas un dôme lisse
    aretes = 7.0 * crete(X, Z, 116, 15) + 3.0 * crete(X, Z, 117, 6) - 4.0
    P = np.where(e >= m3 + 4, haut_crete - 0.75 * np.maximum(e - m3 - 9, 0)
                 + (2.5 * bruit(X, Z, 11, 111) + aretes) * lisse(np.clip((e - m3 - 6) / 10, 0, 1)), P)
    # Brèche de Roland : entaille carrée dans la crête, à l'ouest-sud-ouest
    th_b = -42.0
    ab = np.array([np.sin(np.radians(th_b)), np.cos(np.radians(th_b))])
    vb = np.abs(dx * ab[1] - dz * ab[0]); ub = dx * ab[0] + dz * ab[1]
    breche = (vb < 2.5) & (e > m3 + 1) & (ub > 0)
    P = np.where(breche, np.minimum(P, h3 - 1.0), P)
    Hc = sol + A * P
    d_fond = ndimage.distance_transform_edt(~dans)
    V = np.minimum(h, sol_v + 0.8 * d_fond + 1.5 * bruit(X, Z, 17, 112))
    y = np.where(dans, sol, np.maximum(V, Hc))
    # éboulis au pied des parois (cônes)
    ebo = (e < 0) & (e > -8) & (A > 0.3)
    y = np.where(ebo, y + 4.0 * A * lisse((e + 8) / 8) ** 1.6 * (0.7 + 0.3 * bruit(X, Z, 5, 113)), y)
    # raccord au terrain du mod loin du cirque ; la vallée du gave reste creusée plus loin vers le nord
    w_r = 1 - lisse(np.clip((r - 125) / 40, 0, 1))
    w_v = lisse(np.clip((24 + 0.07 * s_g - d_g) / 14, 0, 1)) * (1 - lisse(np.clip((s_g - L_g + 8) / 20, 0, 1)))
    w = np.maximum(w_r, w_v)
    y = h + (y - h) * w
    # ---- eau : torrent sur le replat du haut, fente de la Grande Cascade, bassin, gave, lac au bout
    eau = np.full(X.shape, np.nan)
    u = dx * ax[0] + dz * ax[1]; v = dx * ax[1] - dz * ax[0]
    tor = (np.abs(v) <= 1.6) & (e > m3 + 0.3) & (e < m3 + 7) & (u > 0) & (A > 0.5)
    niv_haut = float(np.floor(np.nanmin(np.where(tor, y, np.nan))))
    eau = np.where(tor, niv_haut, eau)
    y = np.where(tor, np.minimum(y, niv_haut - 2.2), y)
    fente = (np.abs(v) <= 1.6) & (e >= -3) & (e <= m3 + 0.3) & (u > 0)
    bassin = (np.hypot(X - pied[0], Z - pied[1]) < 5.5) | fente
    niv_bas = float(np.round(np.nanmean(np.where(bassin & ~fente, sol, np.nan))))
    eau = np.where(bassin, niv_bas, eau)
    y = np.where(bassin, np.minimum(y, niv_bas - 2.6), y)
    gave = (d_g < 2.0 + 0.008 * s_g) & ~bassin & (s_g > 1) & (s_g < L_g - 6)
    niv_g = np.floor(niv_bas - 0.075 * s_g)
    eau = np.where(gave, niv_g, eau)
    y = np.where(gave, np.minimum(y, niv_g - 1.6), y)
    fin = trace[-1] - (trace[-1] - trace[-12]) * 0.5
    rl = np.hypot(X - fin[0], Z - fin[1]) / (7 + 1.5 * bruit(X, Z, 6, 107))
    lac = rl < 1
    niv_lac = float(np.floor(niv_bas - 0.075 * (L_g - 6)))
    eau = np.where(lac, niv_lac, eau)
    y = np.where(lac, np.minimum(y, niv_lac - 2.5 - 1.5 * lisse(1 - rl)), y)
    # ---- classes
    pl = pente_locale(y)
    typ = np.full(X.shape, PLATEAU | TAILLEE, np.int32)
    roc = pl > 1.3
    typ[roc] = ROC | TAILLEE
    eb2 = ~roc & (pl > 0.55) & (y > 140) & (bruit(X, Z, 7, 114) > -0.2)
    typ[eb2] = EBOULIS | TAILLEE
    typ[~roc & (pl <= 0.7) & (y > 160 + 4 * bruit(X, Z, 12, 115))] = NEIGE | TAILLEE
    typ[ebo & ~roc] = EBOULIS | TAILLEE
    typ[np.isfinite(eau)] = LIT | TAILLEE
    typ = typ | BIOME
    sommet = y.copy()
    typ[w < 0.02] = 0
    print(f"gavarnie : fond y {niv_bas:.0f}, crête y {np.nanmax(y):.0f}, torrent y {niv_haut:.0f} -> chute de "
          f"{niv_haut - niv_bas:.0f} blocs ; gave {L_g:.0f} blocs, lac y {niv_lac:.0f}")
    return ecrire("gavarnie", X, Z, y, h, sommet, typ, sd, eau, "CALCAIRE")


def creuser_riviere(X, Z, y, eau, trace, niv, larg, prof=2.0, pente=0.7, rive=0.4, masque=None, large=60):
    """Creuse un cours d'eau le long d'un tracé (points en blocs) : lit de largeur larg(s), eau au niveau niv(s)
    (entier, par marches : une marche = une chute en travers du lit), berges qui remontent en pente `pente` jusqu'au
    terrain. Rend y, eau, d (distance au tracé), s (abscisse), L (longueur)."""
    d, s, Ltot = polyligne(X, Z, trace)
    n = np.floor(niv(s)); lg = larg(s)
    m = np.ones(X.shape, bool) if masque is None else masque
    lit = (d < lg) & m
    eau = np.where(lit, n, eau)
    fond = n - 1.15 - prof * lisse(np.clip(1 - d / np.maximum(lg, 0.5), 0, 1))
    y = np.where(lit, np.minimum(y, fond), y)
    berge = ~lit & (d < lg + large) & m
    y = np.where(berge, np.minimum(y, np.maximum(n - 0.5 + rive, n + rive + pente * (d - lg))), y)
    return y, eau, d, s, Ltot


def fleuve_du_mod(X, Z, h):
    """Le cours d'eau du mod tel quel (pour un lieu qui s'y raccorde) : eau de son lit, terrain h inchangé."""
    pres, d, hw, prof, niv, w = T.rivieres(X, Z)
    lit = pres & (d <= hw)
    return np.where(lit, w.astype(float), np.nan), pres & (d <= hw + 64)


def gullfoss():
    """Gullfoss (Islande) : la Hvítá descend en rapides, tombe une première fois (11 m) en travers de son lit, tourne
    à angle droit puis plonge (21 m) dans une gorge étroite de basalte. Plateau moussu. La gorge rejoint ici la
    Þjórsá du mod (la seule rivière du tracé Natural Earth dans le coin).
    Exagéré : chutes de 7 et 13 blocs, gorge de 8 blocs de large et ~15 de profondeur."""
    X, Z, c = zone(64.3271, -20.1199, 160, 200)
    h, sd = T.hauteur_base(X, Z)
    dx, dz = X - c[0], Z - c[1]
    r = np.hypot(dx, dz)
    eau_mod, vallee_mod = fleuve_du_mod(X, Z, h)
    # plateau de lave relevé autour des chutes (la gorge s'y enfonce)
    bosse = 81.5 + 1.2 * bruit(X, Z, 20, 201) - 0.15 * np.maximum(r - 40, 0)
    y = np.maximum(h, bosse)
    # tracé : la Hvítá arrive du nord-nord-est, chute 1 au point c, tourne à droite (ouest), chute 2 dans la gorge
    # qui part vers le sud-ouest, jusqu'à la Þjórsá
    P = [c + np.array([30, -150]), c + np.array([22, -110]), c + np.array([8, -70]), c + np.array([4, -35]),
         c + np.array([0, -10]), c + np.array([0, 0]), c + np.array([0, 6]), c + np.array([-8, 10]),
         c + np.array([-14, 10]), c + np.array([-20, 16]), c + np.array([-34, 40]), c + np.array([-50, 70]),
         c + np.array([-62, 100]), c + np.array([-70, 128]), c + np.array([-74, 150])]
    trace = lisser_trace(P, 700, 0.6)
    d0, s0, L = polyligne(X, Z, trace)
    s_c1 = float(s0[int(round(c[1] - Z[0, 0])), int(round(c[0] - X[0, 0]))])   # abscisse de la chute 1
    s_c2 = s_c1 + 19.0                                                     # chute 2, après le virage
    s_src = 26.0                                                           # lac de départ
    def niv(s):
        amont = np.minimum(86.0 + np.floor(np.clip(s_c1 - 8 - s, 0, None) / 16.0), 93.0)
        aval = np.maximum(66.0 - np.floor(np.clip(s - s_c2, 0, None) / 45.0), 64.0)
        return np.where(s < s_c1, amont, np.where(s < s_c2, 79.0, aval))
    def larg(s):
        ondule = 1.6 * np.sin(s / 23.0) + 0.9 * np.sin(s / 9.0 + 1.3)          # rives irrégulières
        return np.where(s < s_c1, 8.0 + ondule, np.where(s < s_c2, 8.0, 4.2))
    # en amont de la chute, la Hvítá coule dans le plateau (pas sur une digue) : le plateau monte avec elle, ses rives
    # s'élèvent doucement de part et d'autre
    berges = niv(s0) + 1.4 + 0.08 * np.maximum(d0 - 9, 0) + 0.8 * bruit(X, Z, 8, 209)
    f_b = lisse(np.clip((75 - d0) / 35, 0, 1)) * lisse(np.clip((s_c1 + 3 - s0) / 22, 0, 1))
    y = np.maximum(y, y + (berges - y) * f_b)
    y, eau, d, s, L = creuser_riviere(X, Z, y, np.full(X.shape, np.nan), trace, niv, larg, prof=1.6, pente=0.55)
    # rochers et îlots moussus dans les rapides de la Hvítá (en amont de la première chute)
    ilot = (s < s_c1 - 6) & (d < larg(s) - 1.5) & (bruit(X, Z, 3.0, 207) > 0.55)
    eau_il = np.where(ilot, eau, np.nan)
    y = np.where(ilot, np.floor(np.nan_to_num(eau_il)) + 0.3 + 0.5 * (bruit(X, Z, 2.0, 208) > 0.3), y)
    eau = np.where(ilot, np.nan, eau)
    # la gorge : parois verticales jusqu'au plateau (pas de berges en pente) tant que le plateau est haut
    gorge = (s > s_c2 - 1) & (d >= larg(s)) & (d < larg(s) + 1.5)
    y = np.where(gorge, np.maximum(y, bosse), y)
    # lac de départ
    src = trace[int(np.searchsorted(np.linspace(0, L, len(trace)), s_src))]
    rl = np.hypot(X - src[0], Z - src[1]) / (13 + 2 * bruit(X, Z, 7, 202))
    lac = rl < 1
    niv_src = float(niv(np.array([s_src]))[0])
    eau = np.where(lac, niv_src, eau)
    y = np.where(lac, np.minimum(y, niv_src - 1.6 - 1.5 * lisse(1 - rl)), y)
    amont = (s < s_src) & (d < 9.5) & ~lac
    eau = np.where(amont, np.nan, eau)
    y = np.where(amont, np.maximum(y, niv_src + 0.5), y)
    # la Þjórsá reprise telle quelle là où la gorge la rejoint
    y = np.where(np.isfinite(eau_mod) & ~np.isfinite(eau), h, y)
    eau = np.where(np.isfinite(eau_mod) & ~np.isfinite(eau), eau_mod, eau)
    # raccord : le lieu suit le tracé (après le lac de départ) et les chutes ; la vallée de la Þjórsá reste celle du mod
    w = 1 - lisse(np.clip((r - 95) / 35, 0, 1))
    w = np.maximum(w, (1 - lisse(np.clip((d0 - 26) / 22, 0, 1))) * lisse(np.clip((s0 - 8) / 10, 0, 1)))
    w = np.maximum(w, 1 - lisse(np.clip((rl - 1) * 13 / 20, 0, 1)))
    jonction = np.hypot(X - trace[-1][0], Z - trace[-1][1]) < 40
    w = np.where(vallee_mod & ~jonction, np.minimum(w, 0.0), w)
    w = ndimage.gaussian_filter(w, 2.0)
    w = np.where(np.isfinite(eau) & ~np.isfinite(eau_mod), 1.0, w)
    y = h + (y - h) * w
    eau = np.where(w > 0.97, eau, np.nan)
    pl = pente_locale(y)
    typ = np.full(X.shape, PLATEAU | TAILLEE, np.int32)
    mousse = (bruit(X, Z, 9, 203) * 0.5 + (1 - r / 85)) > 0.35
    typ[mousse] = MOUSSE | TAILLEE
    typ[pl > 1.2] = ROC | TAILLEE
    typ[np.isfinite(eau)] = LIT | TAILLEE
    typ[ilot & (w > 0.97)] = MOUSSE | TAILLEE
    # Geysir (Haukadalur), à sa vraie place dans la zone, 80 blocs à l'ouest des chutes : Strokkur (vasque de 3 blocs
    # de rayon, le geyser au fond, qui jaillit toutes les 45 s environ), le Grand Geysir (endormi) 12 blocs au
    # nord-nord-ouest, des sources chaudes bleues et des fumerolles sur un tablier de geysérite (calcite)
    vox = []
    rng = np.random.default_rng(2101)
    g0 = bloc_de(64.3104, -20.3024)
    sources = [(g0, 3.0, True), (g0 + np.array([-5.0, -11.0]), 4.0, False)]
    for k in range(7):
        ang = rng.random() * 2 * np.pi; dist = 9 + rng.random() * 14
        sources.append((g0 + dist * np.array([np.cos(ang), np.sin(ang)]), 1.0 + rng.random() * 1.2, False))
    tablier = np.zeros(X.shape, bool)
    for (cs, r, geyser) in sources:
        rr = np.hypot(X - cs[0], Z - cs[1])
        niv_g = float(np.floor(np.median(y[rr < r + 3]))) + 1.0
        tablier |= rr < r + 3.5 + 1.5 * bruit(X, Z, 3, 2102)
        y = np.where(rr < r + 3.5, np.maximum(np.minimum(y, niv_g - 0.4 + 0.1 * (rr - r)), niv_g - 0.4), y)
        bassin = rr < r
        eau = np.where(bassin, niv_g, eau)
        y = np.where(bassin, niv_g - 1.2 - min(3.0, r) * lisse(np.clip(1 - rr / r, 0, 1)), y)
        j, i = int(round(cs[1] - Z[0, 0])), int(round(cs[0] - X[0, 0]))
        if geyser:
            vox.append((int(cs[0]), int(np.floor(y[j, i])), int(cs[1]), 102))      # Strokkur
        elif r < 2.5 and rng.random() < 0.7:
            vox.append((int(cs[0]) + 1 + int(r), int(np.floor(y[j, i + 1 + int(r)])), int(cs[1]), 101))  # fumerolle
    typ[tablier & ~np.isfinite(eau)] = PLAGE | TAILLEE                   # geysérite
    typ[tablier & np.isfinite(eau)] = LIT | TAILLEE
    print(f"  Geysir : {len(sources)} sources, Strokkur en {g0.round(0)}")
    typ = typ | BIOME
    typ[w < 0.02] = 0
    sommet = y.copy()
    print(f"gullfoss : chute 1 de {86 - 79} blocs puis chute 2 de {79 - 66} ; gorge {L - s_c2:.0f} blocs")
    return ecrire("gullfoss", X, Z, y, h, sommet, typ, sd, eau, "BASALTE", garder_fleuves=False, vox=vox)


def skogafoss():
    """Skógafoss (Islande) : la Skógá tombe d'une ancienne falaise côtière (60 m, 25 m de large) en un rideau d'eau,
    puis rejoint la mer à 5 km à travers la plaine. Falaise de basalte moussue qui court d'est en ouest.
    Exagéré : falaise de ~23 blocs, chute de 7 blocs de large."""
    X, Z, c = zone(63.5321, -19.5113, 160, 150)
    h, sd = T.hauteur_base(X, Z)
    dx, dz = X - c[0], Z - c[1]
    mer = sd < 0
    # ligne de la falaise : est-ouest, un peu au nord des chutes, festonnée (anciennes criques), droite à la chute
    zf = -3.0 + (6.0 * bruit(X, Z, 40, 301) + 2.0 * bruit(X, Z, 11, 302)) * lisse(np.clip((np.abs(dx) - 6) / 14, 0, 1))
    e = zf - dz                                                  # > 0 au nord de la falaise (sur le plateau)
    hf = 24.0 * (1 - lisse(np.clip((np.abs(dx) - 60) / 45, 0, 1)))    # s'abaisse vers les bouts
    bas = 66.6
    haut = bas + hf + 1.0 * bruit(X, Z, 17, 303) * lisse(np.clip((np.abs(dx) - 6) / 10, 0, 1))
    plateau = np.maximum(h, haut)
    plaine = np.where(mer, h, np.maximum(np.minimum(h, bas + 0.03 * np.maximum(dz, 0)), np.minimum(h, bas)))
    plaine = np.where(mer, h, np.maximum(plaine, np.minimum(bas, h + 2)))
    y = np.where(e > 0, plateau, plaine)
    # la Skógá : du nord (petit lac sur le plateau) jusqu'à la falaise (x fixe), puis vers la mer au sud
    xs = c[0] + 2.0
    P = [np.array([xs + 18, c[1] - 95]), np.array([xs + 10, c[1] - 60]), np.array([xs + 3, c[1] - 30]),
         np.array([xs, c[1] - 12]), np.array([xs, c[1] + 12]), np.array([xs - 4, c[1] + 30]),
         np.array([xs + 3, c[1] + 55]), np.array([xs - 2, c[1] + 80]), np.array([xs + 2, c[1] + 115])]
    trace = lisser_trace(P, 500, 0.7)
    d0, s0, L = polyligne(X, Z, trace)
    ss = np.linspace(0, L, len(trace))
    z_f = c[1] - 3.0                                             # la falaise passe en z_f à la chute
    s_f = float(np.interp(z_f, trace[:, 1], ss))
    lev = float(np.floor(bas + 24.0)) - 1.0                       # eau au bord de la falaise
    def niv(s):
        amont = np.minimum(lev + np.floor(np.clip(s_f - 8 - s, 0, None) / 14.0), lev + 6)
        aval = np.maximum(66.0 - np.floor(np.clip(s - s_f - 14, 0, None) / 25.0), 63.0)
        return np.where(s < s_f, amont, aval)
    def larg(s):
        return np.where(s < s_f, 3.6, 3.3)
    eau = np.full(X.shape, np.nan)
    y, eau, d, s, L = creuser_riviere(X, Z, y, eau, trace, niv, larg, prof=1.4, pente=1.6, masque=(e > 0))
    y, eau, d, s, L = creuser_riviere(X, Z, y, eau, trace, niv, larg, prof=1.2, pente=0.5, masque=(e <= 0) & ~mer)
    # bassin au pied, contre la falaise, sous la lèvre (la lèvre le touche : l'eau déborde et tombe)
    pied = np.array([xs, z_f + 7.5])
    rb = np.hypot((X - pied[0]) / 1.25, Z - pied[1]) / 7.5
    bassin = (rb < 1) & (e <= 0)
    eau = np.where(bassin, 66.0, eau)
    y = np.where(bassin, np.minimum(y, 66.0 - 2.4 - 1.2 * lisse(1 - rb)), y)
    # source : petit lac sur le plateau
    k = 25
    src = trace[k]
    rl = np.hypot(X - src[0], Z - src[1]) / (9 + 1.5 * bruit(X, Z, 6, 304))
    niv_src = float(niv(np.array([ss[k]]))[0])
    lac = rl < 1
    eau = np.where(lac, niv_src, eau)
    y = np.where(lac, np.minimum(y, niv_src - 1.6 - lisse(1 - rl)), y)
    amont = (s < ss[k]) & ~lac & (d < 6)
    eau = np.where(amont, np.nan, eau)
    y = np.where(amont, np.maximum(y, niv_src + 0.5), y)
    # embouchure : le lit s'arrête au rivage, la mer prend le relais (même niveau)
    eau = np.where(mer, np.nan, eau)
    # raccord au terrain
    w = (1 - lisse(np.clip((np.abs(dx) - 105) / 35, 0, 1))) * (1 - lisse(np.clip((-dz - 60) / 40, 0, 1)))
    w = np.where(dz > 0, (1 - lisse(np.clip((np.abs(dx) - 50) / 30, 0, 1))) * (1 - lisse(np.clip((dz - 40) / 25, 0, 1))), w)
    w = np.maximum(w, (1 - lisse(np.clip((d0 - 12) / 14, 0, 1))) * lisse(np.clip((s0 - 10) / 10, 0, 1)))
    w = np.maximum(w, 1 - lisse(np.clip((rl - 1) * 9 / 14, 0, 1)))
    w = np.where(mer, 0.0, w)
    w = ndimage.gaussian_filter(w, 1.5)
    w = np.where(np.isfinite(eau), 1.0, w)
    y = h + (y - h) * w
    eau = np.where(w > 0.97, eau, np.nan)
    y = np.where(mer, h, y)
    pl = pente_locale(y)
    typ = np.full(X.shape, PRE | TAILLEE, np.int32)
    typ[(e > 0) & (pl < 1.2) & (bruit(X, Z, 8, 305) * 0.6 + w > 0.85)] = MOUSSE | TAILLEE
    typ[pl >= 1.2] = ROC | TAILLEE
    typ[np.isfinite(eau)] = LIT | TAILLEE
    typ = typ | BIOME
    typ[(w < 0.02) | mer] = 0
    sommet = y.copy()
    print(f"skogafoss : lèvre y {lev:.0f}, bassin y 66 -> chute de {lev - 66:.0f} blocs ; rivière {L:.0f} blocs")
    return ecrire("skogafoss", X, Z, y, h, sommet, typ, sd, eau, "BASALTE")


def plitvice():
    """Lacs de Plitvice (Croatie) : seize lacs turquoise en escalier, séparés par des barrages de travertin moussus
    d'où l'eau tombe en mille petites cascades ; lacs du haut dans une vallée boisée, Kozjak le plus grand, lacs du
    bas au fond d'un canyon calcaire, et le Veliki slap (78 m) qui tombe du bord du canyon là où naît la Korana.
    Exagéré : 8 km (32 blocs) étirés à ~180 blocs, 10 lacs, 135 m de dénivelé portés à ~25 blocs."""
    X, Z, c = zone(44.879, 15.607, 130, 220)
    h, sd = T.hauteur_base(X, Z)
    dx, dz = X - c[0], Z - c[1]
    # axe des lacs, du sud (amont) au nord, sinueux
    P = [c + np.array([-6, 96]), c + np.array([4, 70]), c + np.array([-4, 44]), c + np.array([8, 18]),
         c + np.array([2, -10]), c + np.array([-10, -36]), c + np.array([-4, -58]), c + np.array([6, -78]),
         c + np.array([2, -98]), c + np.array([-6, -125])]
    trace = lisser_trace(P, 600, 0.7)
    d0, s0, L = polyligne(X, Z, trace)
    # lacs : (début, fin, demi-largeur, niveau) le long de l'axe ; la fin d'un lac touche le début du suivant
    lacs = [(4, 30, 11, 97), (30, 41, 6, 95), (41, 52, 7, 93), (52, 68, 9, 91), (68, 82, 9, 89), (82, 118, 15, 86),
            (118, 129, 5.5, 83), (129, 137, 4.5, 80), (137, 146, 4.5, 77), (146, 156, 4.0, 74)]
    s_canyon = 118.0
    eau = np.full(X.shape, np.nan)
    niv_s = np.full(X.shape, np.nan)
    fond = np.full(X.shape, np.nan)
    ile = np.zeros(X.shape, bool)
    for k, (a, b2, hw, nv) in enumerate(lacs):
        # largeur qui gonfle au milieu du lac, se resserre au barrage
        t = np.clip((s0 - a) / (b2 - a), 0, 1)
        lg = hw * (0.55 + 0.45 * np.sin(np.pi * np.clip(t * 1.1, 0, 1)) ** 0.6) * (1 + 0.25 * bruit(X, Z, 11, 440 + k)) \
            + 1.8 * bruit(X, Z, 6, 400 + k)
        dans = (s0 >= a) & (s0 < b2) & (d0 < lg)
        prof = (1.5 + 0.12 * hw) * lisse(np.clip(1 - d0 / np.maximum(lg, 1), 0, 1)) * lisse(np.clip((b2 - s0) / 4, 0, 1))
        eau = np.where(dans, nv, eau)
        niv_s = np.where(dans, nv, niv_s)
        fond = np.where(dans, nv - 1.15 - prof, fond)
        # barrage : îlots de travertin moussus sur les 2,5 derniers blocs, entre les filets d'eau
        barrage = dans & (s0 > b2 - 2.5) & (bruit(X, Z, 3.2, 420 + k) > 0.15) & (k < len(lacs) - 1)
        ile |= barrage
    # niveau de référence le long de l'axe (pour les berges)
    nv_axe = np.interp(s0, [a for a, _, _, _ in lacs] + [lacs[-1][1]], [n for _, _, _, n in lacs] + [lacs[-1][3]])
    canyon = s0 > s_canyon - 4
    # plateau : le terrain du mod, relevé au besoin au-dessus des lacs ; le canyon s'y enfonce
    pres_axe = lisse(np.clip((55 - d0) / 30, 0, 1))
    releve = nv_axe + np.where(canyon, 15.0, 5.0) * lisse(np.clip((s0 - s_canyon + 14) / 10, 0, 1) * 0 + 1) \
        + 2.0 * bruit(X, Z, 25, 430)
    releve = np.where(canyon, nv_axe + 5.0 + 10.0 * lisse(np.clip((s0 - s_canyon + 4) / 8, 0, 1)), releve)
    plat = np.maximum(h, h + (np.maximum(releve, h) - h) * pres_axe)
    lgx = np.interp(s0, [a for a, _, _, _ in lacs], [hw for _, _, hw, _ in lacs])
    dd = d0 - lgx
    berge_douce = np.minimum(plat, nv_axe + 0.6 + 0.45 * np.maximum(dd, 0) + 0.5 * bruit(X, Z, 7, 431))
    berge_raide = np.where(dd < 1.5, nv_axe + 0.6 + 6.0 * np.maximum(dd, 0), plat)
    kc = lisse(np.clip((s0 - s_canyon + 6) / 6, 0, 1))
    y = berge_douce + (np.minimum(plat, berge_raide) - berge_douce) * kc
    y = np.where(np.isfinite(fond), fond, y)
    y = np.where(ile, niv_s + 0.25, y)
    eau = np.where(ile, np.nan, eau)
    # Veliki slap : la Plitvica arrive de l'ouest sur le plateau et tombe dans le dernier lac
    pied = trace[int(np.searchsorted(np.linspace(0, L, len(trace)), 151))]
    Q = [pied + np.array([-70, 8]), pied + np.array([-45, 2]), pied + np.array([-22, 3]), pied + np.array([-4, 0])]
    tr2 = lisser_trace(Q, 200, 0.6)
    d2, s2, L2 = polyligne(X, Z, tr2)
    niv_haut = float(np.floor(np.nanmin(np.where((d2 < 4) & (s2 > L2 - 12), plat, np.nan)))) - 1
    pl_ = (d2 < 1.8) & (s2 > 6) & ~np.isfinite(eau)
    nv2 = np.minimum(niv_haut + np.floor((L2 - s2) / 15.0), niv_haut + 4)
    eau = np.where(pl_, nv2, eau)
    y = np.where(pl_, nv2 - 1.9, y)
    y = np.where((d2 >= 1.8) & (d2 < 6) & (s2 > 6) & ~np.isfinite(eau), np.maximum(y, nv2 + 0.4), y)
    src2 = (np.hypot(X - tr2[8][0], Z - tr2[8][1]) < 6)
    eau = np.where(src2 & ~np.isfinite(eau), niv_haut + 4, eau)
    y = np.where(src2, np.minimum(y, niv_haut + 4 - 2.2), y)
    # la Korana : du dernier lac vers le nord, puis un étang au bout
    a_k = lacs[-1][1]
    korana = (s0 >= a_k) & (d0 < 3.5) & (s0 < L - 8)
    nk = 72.0 - np.floor(np.clip(s0 - a_k, 0, None) / 30)
    eau = np.where(korana, nk, eau)
    y = np.where(korana, nk - 2.2, y)
    fin = trace[-1] - (trace[-1] - trace[-30]) * 0.4
    rl = np.hypot(X - fin[0], Z - fin[1]) / 8
    et = rl < 1
    nf = float(72.0 - np.floor((L - 8 - a_k) / 30))
    eau = np.where(et, nf, eau)
    y = np.where(et, np.minimum(y, nf - 1.8 - lisse(1 - rl)), y)
    # raccord
    w = 1 - lisse(np.clip((d0 - 40) / 35, 0, 1))
    w = np.maximum(w, (1 - lisse(np.clip((d2 - 14) / 20, 0, 1))) * lisse(np.clip((s2 + 6) / 10, 0, 1)))
    w = w * (1 - lisse(np.clip((-s0 + 2) / 8, 0, 1)))
    w = ndimage.gaussian_filter(w, 1.5)
    w = np.where(np.isfinite(eau) | ile, 1.0, w)
    y = h + (y - h) * w
    eau = np.where(w > 0.97, eau, np.nan)
    pl = pente_locale(y)
    typ = np.full(X.shape, PLATEAU | TAILLEE, np.int32)
    typ[pl > 1.2] = ROC | TAILLEE
    typ[ile] = MOUSSE | TAILLEE
    bord = ndimage.binary_dilation(np.isfinite(eau), iterations=1) & ~np.isfinite(eau)
    typ[bord & (bruit(X, Z, 4, 432) > -0.1)] = MOUSSE | TAILLEE
    typ[np.isfinite(eau)] = LIT | TAILLEE
    typ = typ | BIOME
    typ[w < 0.02] = 0
    sommet = y.copy()
    print(f"plitvice : {len(lacs)} lacs de y {lacs[0][3]} à {lacs[-1][3]}, Veliki slap de y {niv_haut:.0f} à 74 "
          f"({niv_haut - 74:.0f} blocs), Korana")
    return ecrire("plitvice", X, Z, y, h, sommet, typ, sd, eau, "TRAVERTIN")


def fjord(X, Z, h, sd, c, R, H, elargir, graine):
    """Fjord exagéré : la mer de la carte (souvent un fil de 2-5 blocs) élargie de `elargir` blocs près du centre,
    parois quasi verticales de H blocs au-dessus de la mer, plateau au-dessus qui rejoint le relief du mod.
    Rend y, eau (63 dans le fjord du lieu), F (eau du fjord), dF (distance au fjord), wf (emprise)."""
    dx, dz = X - c[0], Z - c[1]
    r = np.hypot(dx, dz)
    wf = 1 - lisse(np.clip((r - R) / 45, 0, 1))
    S = sd < 0
    dS = ndimage.distance_transform_edt(~S)
    F = S | (dS < elargir * wf + 0.5 * bruit(X, Z, 9, graine) * wf)
    dF = ndimage.distance_transform_edt(~F)
    dIn = ndimage.distance_transform_edt(F)
    top = 63.5 + H * (0.92 + 0.08 * bruit(X, Z, 30, graine + 1)) + 3.0 * crete(X, Z, graine + 2, 14) * lisse(np.clip((dF - 4) / 6, 0, 1))
    pres = 1 - lisse(np.clip((dF - 18) / 45, 0, 1))
    paroi = np.minimum(top + 0.25 * np.maximum(dF - 3, 0), 63.5 + 24.0 * dF)
    plateau = np.maximum(h, h + (paroi - h) * pres)
    y_terre = h + (plateau - h) * wf
    y_fjord = 61.9 - 15.0 * lisse(np.clip(dIn / 7, 0, 1)) + 1.0 * bruit(X, Z, 7, graine + 3)
    lieu_f = F & ((wf > 0.97) | ~S)                               # le fjord du lieu (le reste : la mer du mod)
    y = np.where(F, np.where(lieu_f, y_fjord, h), y_terre)
    eau = np.where(lieu_f, 63.0, np.nan)
    return y, eau, F, lieu_f, dF, wf, top


def chutes_de_paroi(X, Z, y, eau, F, dF, top, cible, n, ecart, long_=9, larg=1.0):
    """Cascades qui tombent d'une paroi dans le fjord : n torrents sur le haut de la paroi, espacés de `ecart`
    blocs le long de la paroi près de `cible` ; la paroi y est verticale (la lèvre touche l'eau du fjord)."""
    bord = ~F & (dF <= 1.0)
    jj, ii = np.nonzero(bord)
    pts = np.c_[X[jj, ii], Z[jj, ii]]
    k0 = int(np.argmin(np.hypot(pts[:, 0] - cible[0], pts[:, 1] - cible[1])))
    p0 = pts[k0]
    # direction de la paroi : les bords voisins
    voisins = pts[np.hypot(pts[:, 0] - p0[0], pts[:, 1] - p0[1]) < 12]
    u, sv, vt = np.linalg.svd(voisins - voisins.mean(0))
    t = vt[0]
    gz, gx = np.gradient(ndimage.gaussian_filter(dF, 2))
    j0, i0 = int(p0[1] - Z[0, 0]), int(p0[0] - X[0, 0])
    nrm = np.array([gx[j0, i0], gz[j0, i0]]); nrm /= np.linalg.norm(nrm) + 1e-9      # vers l'intérieur des terres
    niveaux = []
    for k in range(n):
        q = p0 + t * (k - (n - 1) / 2) * ecart
        kq = int(np.argmin(np.hypot(pts[:, 0] - q[0], pts[:, 1] - q[1])))
        lev = pts[kq]
        jl, il = int(lev[1] - Z[0, 0]), int(lev[0] - X[0, 0])
        e_ = float(np.floor(top[jl, il])) - 0.0
        # torrent : de la lèvre vers l'intérieur, 1 à 2 blocs de large
        u_ = (X - lev[0]) * nrm[0] + (Z - lev[1]) * nrm[1]
        v_ = (X - lev[0]) * t[0] + (Z - lev[1]) * t[1]
        tor = (np.abs(v_) <= larg * 0.5 + 0.3) & (u_ >= -0.5) & (u_ <= long_) & ~F
        # paroi verticale autour de la lèvre : le haut de la paroi va jusqu'au bord de l'eau
        mur = (np.abs(v_) <= larg * 0.5 + 2.5) & (u_ >= -0.5) & (u_ <= 4) & ~F
        y = np.where(mur, np.maximum(y, e_ + 0.4), y)
        eau = np.where(tor, e_, eau)
        y = np.where(tor, e_ - 1.9, y)
        src = (np.hypot(X - (lev[0] + nrm[0] * long_), Z - (lev[1] + nrm[1] * long_)) < 2.6) & ~F
        eau = np.where(src, e_, eau)
        y = np.where(src, e_ - 2.2, y)
        niveaux.append(e_)
    return y, eau, niveaux


def geiranger():
    """Geirangerfjord (Norvège) : fjord étroit et sinueux entre des parois de 1 400 m, les Sept Sœurs (sept filets
    d'eau côte à côte sur la paroi nord) face au Prétendant (Friaren) sur la paroi sud.
    Exagéré : fjord élargi à ~14 blocs, parois de ~55 blocs, cascades de la hauteur des parois."""
    X, Z, c = zone(62.100, 7.08, 215, 175)
    h, sd = T.hauteur_base(X, Z)
    y, eau, F, lieu_f, dF, wf, top = fjord(X, Z, h, sd, c, 115, 55.0, 5.0, 500)
    soeurs = bloc_de(62.1066, 7.0943)
    y, eau, nv1 = chutes_de_paroi(X, Z, y, eau, F, dF, top, soeurs + np.array([0, -4]), 7, 2.6, long_=9)
    friaren = bloc_de(62.1030, 7.0960)
    y, eau, nv2 = chutes_de_paroi(X, Z, y, eau, F, dF, top, friaren + np.array([0, 6]), 1, 0, long_=12, larg=2.0)
    pl = pente_locale(y)
    typ = np.full(X.shape, PLATEAU | TAILLEE, np.int32)
    typ[pl > 1.2] = ROC | TAILLEE
    typ[(pl < 1.0) & (bruit(X, Z, 6, 503) > 0.3)] = MOUSSE | TAILLEE
    typ[(pl < 0.8) & (y > 128)] = NEIGE | TAILLEE
    typ[np.isfinite(eau)] = LIT | TAILLEE
    typ[lieu_f] = FOND | TAILLEE
    typ = typ | BIOME
    typ[(wf < 0.02) | (F & ~lieu_f)] = 0
    sommet = y.copy()
    print(f"geiranger : Sept Sœurs de y {min(nv1):.0f}-{max(nv1):.0f} (chutes de ~{np.mean(nv1) - 63:.0f} blocs), "
          f"Prétendant y {nv2[0]:.0f}")
    return ecrire("geiranger", X, Z, y, h, sommet, typ, sd, eau, "GNEISS")


def preikestolen():
    """Preikestolen (Norvège) : la « chaire », table de rocher carrée (25 x 25 m) qui surplombe le Lysefjord de
    604 m, fendue à l'arrière. Exagéré : table de ~9 x 8 blocs, 40 blocs au-dessus de l'eau, trois faces à pic sur le
    fjord ; Lysefjord élargi, parois de ~45 blocs."""
    X, Z, c = zone(58.9864, 6.1903, 160, 160)
    h, sd = T.hauteur_base(X, Z)
    y, eau, F, lieu_f, dF, wf, top = fjord(X, Z, h, sd, c, 100, 45.0, 6.0, 600)
    # la chaire : au bord du fjord le plus proche du vrai site, tournée vers l'eau
    bord = ~F & (dF <= 1.0)
    jj, ii = np.nonzero(bord)
    pts = np.c_[X[jj, ii], Z[jj, ii]]
    p0 = pts[int(np.argmin(np.hypot(pts[:, 0] - c[0], pts[:, 1] - c[1])))]
    gz, gx = np.gradient(ndimage.gaussian_filter(dF, 2))
    j0, i0 = int(p0[1] - Z[0, 0]), int(p0[0] - X[0, 0])
    n = -np.array([gx[j0, i0], gz[j0, i0]]); n /= np.linalg.norm(n) + 1e-9   # vers le fjord
    t = np.array([-n[1], n[0]])
    u = (X - p0[0]) * n[0] + (Z - p0[1]) * n[1]                  # + vers le fjord
    v = (X - p0[0]) * t[0] + (Z - p0[1]) * t[1]
    table = (u > -3.0) & (u < 5.5) & (np.abs(v) < 4.5)
    haut_t = 63.5 + 40.2
    # autour de la table, côté fjord et sur les côtés : de l'eau jusqu'au pied (trois faces à pic)
    tour = ~table & (u > -1.0) & (u < 10.0) & (np.abs(v) < 9.5)
    F2 = (F | tour) & ~table
    lieu2 = (lieu_f | tour) & ~table
    dIn = ndimage.distance_transform_edt(F2)
    y = np.where(tour, 61.9 - 15.0 * lisse(np.clip(dIn / 7, 0, 1)), y)
    eau = np.where(lieu2, 63.0, np.nan)
    y = np.where(table, haut_t, y)
    # derrière la table : le versant monte (plateau un peu plus haut), la fente à l'arrière
    derriere = (u <= -3.0) & (u > -16) & (np.abs(v) < 12) & ~tour
    y = np.where(derriere, np.maximum(y, haut_t + 0.6 + 0.35 * (-u - 3.0)), y)
    fente = (np.abs(u + 1.5) < 0.6) & (np.abs(v) < 3.0)
    y = np.where(fente, haut_t - 9.0, y)
    pl = pente_locale(y)
    typ = np.full(X.shape, PLATEAU | TAILLEE, np.int32)
    typ[pl > 1.2] = ROC | TAILLEE
    typ[(pl < 1.0) & (bruit(X, Z, 6, 603) > 0.2)] = MOUSSE | TAILLEE
    typ[table] = ROC | TAILLEE
    typ[lieu2] = FOND | TAILLEE
    typ = typ | BIOME
    typ[(wf < 0.02) | (F2 & ~lieu2)] = 0
    sommet = y.copy()
    print(f"preikestolen : table y {haut_t:.1f} au bord du fjord en {p0}, face vers {n.round(2)}")
    return ecrire("preikestolen", X, Z, y, h, sommet, typ, sd, eau, "GNEISS")


def cervin():
    """Cervin / Matterhorn (4 478 m) : pyramide à quatre faces (nord, est, sud, ouest) séparées par quatre arêtes
    vives (Hörnli, Zmutt, Lion, Furggen), sommet légèrement penché vers l'ouest ; glaciers à ses pieds.
    Exagéré : ~75 blocs au-dessus des glaciers (sommet vers y 252), base de ~110 blocs."""
    X, Z, c = zone(45.9763, 7.6586, 150, 150)
    h, sd = T.hauteur_base(X, Z)
    a = np.radians(12.0)
    dx, dz = X - c[0], Z - c[1]
    u = dx * np.cos(a) - dz * np.sin(a)
    v = dx * np.sin(a) + dz * np.cos(a)
    # face nord plus raide, sommet décalé vers l'ouest
    u2 = u + 3.0 * lisse(np.clip(1 - np.hypot(u, v) / 25, 0, 1))
    v2 = np.where(v < 0, v * 1.18, v)
    N = np.maximum(np.abs(u2), np.abs(v2))                      # carrés : faces planes, arêtes vives aux diagonales
    Nr = np.hypot(u2, v2) / 1.25                                 # plus bas, la base s'arrondit (contreforts, glaciers)
    k = lisse(np.clip((N - 22) / 30, 0, 1))
    N = N * (1 - k) + np.maximum(N, Nr) * k
    S, R = 252.0, 58.0
    base = 168.0
    # faces irrégulières : grands bombements et creux (couloirs), épaule sur l'arête du Hörnli (nord-est)
    N = N * (1 + 0.14 * bruit(X, Z, 18, 706) + 0.05 * bruit(X, Z, 7, 707))
    # faces creusées (couloirs au milieu de chaque face) : les arêtes ressortent
    mn, mx = np.minimum(np.abs(u2), np.abs(v2)), np.maximum(np.abs(u2), np.abs(v2)) + 1e-6
    N = N * (1 + 0.10 * (1 - (mn / mx) ** 2) * lisse(np.clip(N / 15, 0, 1)))
    epaule = np.exp(-((u2 - 14) ** 2 + (v2 + 14) ** 2) / 40.0) * 5.0
    yp = S - (S - base) * np.clip(N / R, 0, None) ** 0.72 + epaule
    arete = np.abs(np.abs(u2) - np.abs(v2)) < 1.5
    yp += (1.6 * bruit(X, Z, 5.5, 701) + 1.0 * bruit(X, Z, 2.5, 702)) * lisse(np.clip(N / 8, 0, 1))
    yp -= 0.8 * (np.mod(yp, 7.0) < 1.2) * ~arete
    y = np.maximum(h, yp)
    # glaciers : nappes de glace autour du pied (rondes, bord irrégulier), qui descendent vers les vallées
    rr = np.hypot(u, v)
    gl_niv = 182.0 - 0.10 * np.maximum(rr - 45, 0) + 2.0 * bruit(X, Z, 25, 703)
    # la glace ne fait jamais plus de 3 blocs d'épaisseur au-dessus du terrain : pas de falaise de glace au bord
    gl_niv = np.minimum(gl_niv, h + 3.0 * lisse(np.clip((95 - rr) / 25, 0, 1)) + 0.3)
    glacier = (rr > 30) & (rr < 95 + 12 * bruit(X, Z, 30, 708)) & (yp < gl_niv + 1.0) & (gl_niv > h + 0.4)
    y = np.where(glacier, np.maximum(y, gl_niv + 0.4 * bruit(X, Z, 9, 704)), y)
    N = np.maximum(N, rr / 1.6)
    w = 1 - lisse(np.clip((N - R * 1.4) / 35, 0, 1))
    w = loin_des_fleuves(X, Z, ndimage.gaussian_filter(w, 2))
    y = h + (y - h) * w
    pl = pente_locale(y)
    typ = np.full(X.shape, ROC | TAILLEE, np.int32)            # roche nue (couleurs du gneiss sombre)
    typ[(pl < 1.1) & (y > 182)] = NEIGE | TAILLEE
    typ[(pl < 0.5) & (y <= 182)] = PRE | TAILLEE
    typ[glacier & (pl < 0.9)] = GLACE | TAILLEE
    typ[(pl > 0.5) & (pl < 1.1) & (y <= 182) & (bruit(X, Z, 6, 705) > 0)] = EBOULIS | TAILLEE
    typ = typ | BIOME
    typ[w < 0.02] = 0
    sommet = y.copy()
    print(f"cervin : sommet y {y.max():.0f}, glaciers y ~{np.nanmedian(np.where(glacier, y, np.nan)):.0f}")
    return ecrire("cervin", X, Z, y, h, sommet, typ, sd, np.full(X.shape, np.nan), "CERVIN")


def tre_cime():
    """Tre Cime di Lavaredo (Dolomites) : trois tours de dolomie (Cima Ovest, Cima Grande, Cima Piccola) aux parois
    verticales de 500 m, alignées d'ouest en est sur un socle de pierriers clairs.
    Exagéré : tours de ~45 blocs, espacées de ~17 blocs (400 m en vrai)."""
    X, Z, c = zone(46.6187, 12.3027, 150, 120)
    h, sd = T.hauteur_base(X, Z)
    hs = ndimage.gaussian_filter(h, 6)
    a = np.radians(-8.0)                                        # axe des tours, à peu près ouest-est
    t = np.array([np.cos(a), np.sin(a)]); n = np.array([-t[1], t[0]])
    dx, dz = X - c[0], Z - c[1]
    u = dx * t[0] + dz * t[1]; v = dx * n[0] + dz * n[1]
    socle = hs.max() * 0 + float(np.median(hs[np.hypot(dx, dz) < 30])) + 9.0
    # socle : un massif bas allongé qui porte les tours, pierriers tout autour
    ms = np.hypot(u / 46, v / 22)
    y = np.maximum(h, h + (socle - h) * (1 - lisse(np.clip((ms - 0.55) / 0.9, 0, 1))))
    tours = [(-18.0, 0.0, 7.5, 5.5, 46.0, 711), (0.0, 1.0, 8.5, 6.0, 49.0, 712), (16.0, 0.5, 5.5, 4.2, 38.0, 713)]
    dans_tour = np.zeros(X.shape, bool)
    for (cu, cv, ru, rv, H, g) in tours:
        nn = (np.abs((u - cu) / ru) ** 3 + np.abs((v - cv) / rv) ** 3) ** (1 / 3)
        nn = nn + 0.08 * bruit(X, Z, 3.0, g)
        top = socle + H - 5.0 * nn ** 2 + 2.0 * bruit(X, Z, 2.5, g + 10)
        m = nn < 1.0
        yt = np.where(nn < 0.86, top, socle + 3 + (top - socle - 3) * lisse(np.clip((1 - nn) / 0.14, 0, 1)))
        y = np.where(m, np.maximum(y, yt), y)
        dans_tour |= m
        # pierrier (cône d'éboulis) au pied
        cone = (nn >= 1.0) & (nn < 2.4)
        y = np.where(cone, np.maximum(y, socle + 7.0 * lisse(np.clip((2.4 - nn) / 1.4, 0, 1)) ** 1.5), y)
    w = 1 - lisse(np.clip((ms - 1.6) / 1.2, 0, 1))
    w = loin_des_fleuves(X, Z, ndimage.gaussian_filter(w, 2))
    y = h + (y - h) * w
    pl = pente_locale(y)
    typ = np.full(X.shape, PRE | TAILLEE, np.int32)
    typ[(pl > 0.35) & ~dans_tour] = EBOULIS | TAILLEE
    typ[dans_tour] = ROC | TAILLEE
    typ[dans_tour & (pl < 0.9)] = NEIGE | TAILLEE
    typ[(ms < 1.1) & ~dans_tour & (bruit(X, Z, 5, 714) > -0.3)] = EBOULIS | TAILLEE
    typ = typ | BIOME
    typ[w < 0.02] = 0
    sommet = y.copy()
    print(f"tre_cime : socle y {socle:.0f}, tours jusqu'à y {y.max():.0f}")
    return ecrire("tre_cime", X, Z, y, h, sommet, typ, sd, np.full(X.shape, np.nan), "DOLOMIE")


# les autres lieux du lot 2 sont faits sur le relief réel (outils/lieux_reels.py) ; leurs anciennes versions dessinées
# restent ici pour mémoire mais ne sont plus écrites
LIEUX = {"gullfoss": gullfoss, "skogafoss": skogafoss}

if __name__ == "__main__":
    noms = [a for a in sys.argv[1:] if not a.startswith("--")]
    for n in (noms or LIEUX):
        LIEUX[n]()

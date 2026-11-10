"""Lieux « comme en vrai » aux hautes latitudes (10/11/2026, demande de Maxime : « rends-les juste comme en vrai »).

Le monde est une carte plate (1 degré de longitude = 445 blocs partout) : vers les pôles, tout est étiré d'est en
ouest de 1/cos(latitude) (×4,6 au mont Erebus). Un lieu iso remet les vraies proportions : dans sa zone, le terrain
du mod (carte 3' + relief fin, mêmes règles qu'en jeu) est pris aux positions resserrées
x' = xA + (x - xA) / cos(latA) autour de son ancrage A, qui reste à sa vraie place.

Règle de raccord (pas de doublon) : on ne garde du terrain resserré que le « cœur » — la terre reliée à l'ancrage
au-dessus d'un seuil d'altitude réelle (0 m : l'île entière). Autour, jusqu'au bord de la zone : la mer pour une
île, la plaine du mod au pied du massif sinon. La zone couvre tout le massif étiré du mod (plus une marge), si bien
que son bord tombe dans la mer ou la plaine : le raccord s'y fait sans couture ni second exemplaire du lieu.

Usage : python3 outils/lieux_iso.py <cache des paquets du relief fin> [lieu ...] [--apercu]
"""
import os, sys
import numpy as np
from scipy import ndimage
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import terre_py as T
import lieux_methode as LM
import lieux_montagne as M
from lieux_cotiers import bruit, lisse, FOND, ROC, NEIGE, EBOULIS, GLACE, PRE, TAILLEE, BIOME

BPD = T.BPD
CACHE = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "/tmp/claude-0/methode/cache"
DETAIL = 0.5                                     # ReliefFin.detail (part du détail fin gardée)


def fin_aux(X, Z):
    """Altitude du relief fin (m) au bloc contenant (X, Z) ; NaN = pas de donnée (mer)."""
    xi, zi = np.floor(X).astype(np.int64), np.floor(Z).astype(np.int64)
    x0, z0 = int(xi.min()), int(zi.min())
    A = LM.fin(CACHE, x0, z0, int(xi.max()) - x0 + 1, int(zi.max()) - z0 + 1)
    return A[zi - z0, xi - x0]


def terrain_mod(X, Z):
    """Terrain du mod en jeu (Terrain.hauteurBase avec le relief fin, cours d'eau et lacs compris) aux positions
    (X, Z), même non entières ; rend aussi la distance à la côte et l'altitude réelle (relief fin, sinon carte 3')."""
    h_e, sd = T.hauteur_base(X, Z)
    h_n, _ = T.hauteur_base(X, Z, eaux=False)
    alt = T.relief(X / BPD, -Z / BPD)
    af = fin_aux(X, Z)
    base = T.blocs(np.maximum(alt, 1.0))
    hT = base + (T.blocs(np.maximum(np.nan_to_num(af, nan=1.0), 1.0)) - base) * DETAIL
    terre = T.NIVEAU_MER + 0.6 + (np.maximum(hT, T.NIVEAU_MER + 0.6) - T.NIVEAU_MER - 0.6) * lisse(sd / 2)
    avec_fin = np.isfinite(af) & (sd >= 0)
    h = np.where(avec_fin, h_e + (terre - h_n), h_e)
    return h, sd, np.where(np.isfinite(af), af, alt)


PENTE_MAX = 2.14                                 # ReliefFin.PENTE_MAX (blocs par bloc, 65°)


def limiter(h, s=PENTE_MAX):
    """Enveloppe de pente (ReliefFin.calculerLimitee) : h rabaissé là où il monte plus vite que s depuis un point plus
    bas ; deux passes en chanfrein (pas de 1 et racine de 2)."""
    E = h.astype(float).copy()
    H, W = E.shape
    d2 = s * 2 ** 0.5
    for j in range(H):
        if j:
            E[j] = np.minimum(E[j], E[j - 1] + s)
            E[j, 1:] = np.minimum(E[j, 1:], E[j - 1, :-1] + d2)
            E[j, :-1] = np.minimum(E[j, :-1], E[j - 1, 1:] + d2)
        r = E[j]
        for i in range(1, W):
            if r[i] > r[i - 1] + s:
                r[i] = r[i - 1] + s
    for j in range(H - 1, -1, -1):
        if j < H - 1:
            E[j] = np.minimum(E[j], E[j + 1] + s)
            E[j, 1:] = np.minimum(E[j, 1:], E[j + 1, :-1] + d2)
            E[j, :-1] = np.minimum(E[j, :-1], E[j + 1, 1:] + d2)
        r = E[j]
        for i in range(W - 2, -1, -1):
            if r[i] > r[i + 1] + s:
                r[i] = r[i + 1] + s
    return E


def composante(masque, j, i):
    lab, _ = ndimage.label(masque)
    return lab == lab[j, i] if lab[j, i] else np.zeros(masque.shape, bool)


def lieu_iso(nom, lat_a, lon_a, seuil, marge=70, fondu=50, ile=True, zone=None, rayon_km=None):
    """ile=True : île (mer autour) ; False : massif (plaine du mod autour) ; zone=(ouest, est, nord, sud) en blocs
    depuis l'ancrage : côte (tout le terrain de la zone resserré, l'ancrage pris sur le rivage pour que la côte
    reste à sa place au bord nord et sud)."""
    cx, cz = lon_a * BPD, -lat_a * BPD
    f = np.cos(np.radians(lat_a))
    if zone is not None:
        return lieu_cote(nom, cx, cz, f, zone, fondu)
    # zone : le massif étiré du mod (terre reliée à l'ancrage au-dessus du seuil), plus la marge
    r = int(3.0 * BPD) if rayon_km is None else int(rayon_km / 111.32 * BPD) + 20
    Xg, Zg = np.meshgrid(np.arange(int(cx) - 6 * r, int(cx) + 6 * r, 2.0), np.arange(int(cz) - r, int(cz) + r, 2.0))
    _, sdg, ag = terrain_mod(Xg, Zg)
    jA, iA = r // 2, 3 * r
    dans = np.ones(Xg.shape, bool)
    if rayon_km is not None:                             # massif pris dans un rayon (km réels) autour de l'ancrage
        dans = np.hypot((Xg - cx) * f, Zg - cz) / BPD * 111.32 < rayon_km
    etire = composante((sdg >= 0) & (ag > seuil) & dans, jA, iA)
    jj, ii = np.nonzero(etire)
    x0, x1 = int(Xg[0, ii.min()]) - marge, int(Xg[0, ii.max()]) + marge
    z0, z1 = int(Zg[jj.min(), 0]) - marge, int(Zg[jj.max(), 0]) + marge
    print(f"{nom} : massif étiré du mod {x1 - x0 - 2 * marge} x {z1 - z0 - 2 * marge} blocs ; "
          f"zone {x1 - x0} x {z1 - z0} (x {x0}..{x1}, z {z0}..{z1}), resserrement {1 / f:.2f}")
    X, Z = np.meshgrid(np.arange(x0, x1, dtype=float), np.arange(z0, z1, dtype=float))
    h, sd = T.hauteur_base(X, Z)                         # terrain calculé sans relief fin (raccord des tuiles)
    hm, sdm, _ = terrain_mod(X, Z)                       # terrain en jeu (avec relief fin)
    Xw = cx + (X - cx) / f
    hw, sdw, aw = terrain_mod(Xw, Z)                     # terrain resserré (vraies proportions)
    hm, hw = limiter(hm), limiter(hw)                    # pente limitée comme en jeu
    jA, iA = int(round(cz - z0)), int(round(cx - x0))
    dansw = np.ones(X.shape, bool) if rayon_km is None else np.hypot(X - cx, Z - cz) / BPD * 111.32 < rayon_km
    coeur = composante((sdw >= 0) & (aw > seuil) & dansw, jA, iA)
    print(f"  cœur aux vraies proportions : {int(coeur.sum())} colonnes "
          f"({np.ptp(np.nonzero(coeur)[1]) + 1} x {np.ptp(np.nonzero(coeur)[0]) + 1} blocs)")
    dC = ndimage.distance_transform_edt(~coeur)
    if ile:
        # autour de l'île : près d'elle, son plateau sous-marin aux vraies proportions ; plus loin, le fond de la mer
        # du mod (lissé ; sous les terres étirées du mod, que le lieu remplace par la mer, le fond voisin prolongé)
        mer_m = sdm < 0
        g = 30.0
        num = ndimage.gaussian_filter(np.where(mer_m, np.minimum(hm, 60.0), 0.0), g)
        den_ = ndimage.gaussian_filter(mer_m.astype(float), g)
        rempli = np.where(den_ > 1e-4, num / np.maximum(den_, 1e-4), 56.0)
        ext = np.minimum(np.where(mer_m, np.minimum(hm, 60.0), rempli), 60.0)
        ext = ndimage.gaussian_filter(ext, 6.0)
        plateau = np.minimum(np.where(sdw < 0, hw, 61.0), 61.0)
        wI = 1 - lisse(np.clip((dC - 12) / 80, 0, 1))
        y = ext + (plateau - ext) * wI
        y = np.where(coeur | ((dC <= 3) & (sdw >= 0)), hw, y)
    else:
        # au pied du massif : la plaine du mod, rabotée au niveau du seuil (le massif étiré y disparaît)
        pied = T.blocs(seuil) + 2.0
        ext = np.minimum(hm, pied)
        wc = lisse(np.clip(ndimage.distance_transform_edt(coeur) / 12.0, 0, 1))
        y = ext + (np.maximum(hw, ext) - ext) * wc
    # bord de la zone : retour au terrain du mod (mer pour une île)
    H, W = X.shape
    jj, ii = np.mgrid[0:H, 0:W]
    de = np.minimum(np.minimum(ii, W - 1 - ii), np.minimum(jj, H - 1 - jj)).astype(float)
    den = np.maximum(de - 14 * (0.5 + 0.5 * bruit(X, Z, 22, 1977)), 0)
    a = lisse(np.clip((den - 4) / (fondu - 4), 0, 1))
    y = y * a + ext * (1 - a)
    # dernier fondu sur les 23 derniers blocs vers le terrain calculé (le jeu y ajoute l'écart du relief fin)
    wy = lisse(np.clip((de - 13) / 10, 0, 1))
    y = h + (y - h) * wy
    # mer : sous le niveau de la mer et reliée à la mer du mod au bord
    mer = y < 62.9
    lab, n = ndimage.label(mer)
    dehors = lab[(de < 3) & (sd < 0)]
    mer = np.isin(lab, np.unique(dehors[dehors > 0]))
    y = np.where(wy > 0.02, np.where(mer, np.minimum(y, 61.9), np.maximum(y, 63.6)), y)   # pas au bord : terrain calculé
    eau = np.where(mer & (wy > 0.02), 63.0, np.nan)
    return dict(X=X, Z=Z, y=y, h=h, sd=sd, eau=eau, mer=mer, coeur=coeur, alt=aw, de=de, wy=wy)


def lieu_cote(nom, cx, cz, f, zone, fondu):
    x0, x1 = int(cx) - zone[0], int(cx) + zone[1]
    z0, z1 = int(cz) - zone[2], int(cz) + zone[3]
    print(f"{nom} : zone {x1 - x0} x {z1 - z0} (x {x0}..{x1}, z {z0}..{z1}), resserrement {1 / f:.2f}")
    X, Z = np.meshgrid(np.arange(x0, x1, dtype=float), np.arange(z0, z1, dtype=float))
    h, sd = T.hauteur_base(X, Z)
    hm, sdm, _ = terrain_mod(X, Z)
    hw, sdw, aw = terrain_mod(cx + (X - cx) / f, Z)
    hm, hw = limiter(hm), limiter(hw)
    H, W = X.shape
    jj, ii = np.mgrid[0:H, 0:W]
    de = np.minimum(np.minimum(ii, W - 1 - ii), np.minimum(jj, H - 1 - jj)).astype(float)
    den = np.maximum(de - 14 * (0.5 + 0.5 * bruit(X, Z, 22, 1977)), 0)
    a = lisse(np.clip((den - 4) / (fondu - 4), 0, 1))
    y = hw * a + hm * (1 - a)
    wy = lisse(np.clip((de - 13) / 10, 0, 1))
    y = h + (y - h) * wy
    mer = y < 62.9
    lab, n = ndimage.label(mer)
    dehors = lab[(de < 3) & (sd < 0)]
    mer = np.isin(lab, np.unique(dehors[dehors > 0]))
    y = np.where(wy > 0.02, np.where(mer, np.minimum(y, 61.9), np.maximum(y, 63.6)), y)   # pas au bord : terrain calculé
    eau = np.where(mer & (wy > 0.02), 63.0, np.nan)
    return dict(X=X, Z=Z, y=y, h=h, sd=sd, eau=eau, mer=mer, coeur=a > 0.5, alt=aw, de=de, wy=wy)


def neige_glace(L, ligne_neige, roche=1.2, biome_seuil=None):
    """Surface des terres froides : neige, glace sur les pentes douces basses, roche sur les pentes raides."""
    X, Z, y = L["X"], L["Z"], L["y"]
    pl = M.pente_locale(y)
    typ = np.full(X.shape, PRE | TAILLEE, np.int32)
    typ[L["alt"] > ligne_neige + 150 * bruit(X, Z, 9, 1901)] = NEIGE | TAILLEE
    typ[(typ == NEIGE | TAILLEE) & (pl < 0.35) & (L["alt"] < ligne_neige + 600)] = GLACE | TAILLEE
    typ[pl > roche * 0.75] = EBOULIS | TAILLEE
    typ[pl > roche] = ROC | TAILLEE
    typ[L["mer"]] = FOND | TAILLEE
    if biome_seuil is not None:
        typ = np.where(L["coeur"] & (L["alt"] > biome_seuil), typ | BIOME, typ)
    typ[(L["wy"] < 0.02) & ~np.isfinite(L["eau"])] = 0
    return typ


def erebus():
    """Île de Ross et mont Erebus (Antarctique, 77,5° S) : l'île aux vraies proportions (étirée ×4,6 par la carte),
    neige et glace partout, roche volcanique sur les pentes raides ; mer autour jusqu'au bord de la zone."""
    L = lieu_iso("erebus", -77.529, 167.153, 60.0, ile=True)   # au-dessus de la barrière de Ross (15-40 m)
    typ = neige_glace(L, ligne_neige=-1000.0, roche=3.0, biome_seuil=60.0)   # calotte de glace : roche aux seules falaises
    return M.ecrire("erebus", L["X"], L["Z"], L["y"], L["h"], L["y"].copy(), typ, L["sd"], L["eau"], "VOLCAN",
                    garder_fleuves=False)


def kamtchatka():
    """Volcans du groupe de la Klioutchevskaïa (Kamtchatka, 56° N) : le massif aux vraies proportions (étiré ×1,8),
    posé sur la dépression centrale du mod ; neige au-dessus de 1 900 m, glaciers sur les pentes douces."""
    L = lieu_iso("kamtchatka", 56.056, 160.642, 800.0, ile=False, rayon_km=45.0)
    typ = neige_glace(L, ligne_neige=1900.0, biome_seuil=1000.0)
    return M.ecrire("kamtchatka", L["X"], L["Z"], L["y"], L["h"], L["y"].copy(), typ, L["sd"], L["eau"], "VOLCAN")


def icebergs(L, masque, n, graine, pres=None, h_max=6.0, r_max=4.5):
    """Icebergs posés dans l'eau du masque : blocs de glace de 1 à h_max blocs au-dessus de l'eau (plus gros près de
    `pres`, distance en blocs au front du glacier). Rend le masque des colonnes de glace."""
    X, Z = L["X"], L["Z"]
    rng = np.random.default_rng(graine)
    ice = np.zeros(X.shape, bool)
    masque = masque & (L["wy"] > 0.6)                    # pas sur la bande du bord (terrain calculé)
    jj, ii = np.nonzero(masque)
    for k in (rng.choice(len(jj), size=min(len(jj), n), replace=False) if len(jj) else []):
        j, i = jj[k], ii[k]
        p = 1.0 if pres is None else float(np.clip(1 - pres[j, i] / 150, 0.15, 1))
        if rng.random() > 0.3 + 0.7 * p:
            continue
        r = 1.0 + rng.random() * (1.0 + (r_max - 1.0) * p)
        hg = 1.0 + rng.random() * (h_max - 1.0) * p
        nn = np.hypot((X - X[j, i]) / r, (Z - Z[j, i]) / (r * (0.6 + 0.8 * rng.random())))
        m = (nn < 1) & masque
        L["y"] = np.where(m, np.maximum(L["y"], 63.0 + hg * (1 - 0.5 * nn ** 2) + 0.4 * bruit(X, Z, 1.5, graine + 1)),
                          L["y"])
        ice |= m
    L["eau"] = np.where(ice, np.nan, L["eau"])
    return ice


def ilulissat():
    """Fjord glacé d'Ilulissat (Groenland, 69° N) aux vraies proportions (étiré ×2,8 est-ouest) : le fjord de Kangia,
    rempli d'icebergs, du glacier Sermeq Kujalleq (inlandsis) à la baie de Disko ; ancré à l'embouchure, si bien que
    la côte reste à sa place aux bords nord et sud."""
    L = lieu_iso("ilulissat", 69.13, -51.12, 0.0, zone=(150, 450, 220, 220), fondu=60)
    X, Z, mer = L["X"], L["Z"], L["mer"]
    cx = -51.12 * BPD
    fjord = mer & (X > cx + 4)
    dTerre = ndimage.distance_transform_edt(mer)
    # front du glacier : bout est du fjord
    front = np.zeros(X.shape)
    if fjord.any():
        xf = X[fjord].max()
        front = np.abs(X - xf)
    ice = icebergs(L, fjord & (dTerre > 0.8), 900, 2101, pres=front)
    ice |= icebergs(L, mer & (X <= cx + 4) & (dTerre > 3), 60, 2103, h_max=8.0, r_max=5.0)
    typ = neige_glace(L, ligne_neige=600.0, biome_seuil=None)
    typ[ice] = GLACE | TAILLEE
    print(f"ilulissat : fjord {int(fjord.sum())} colonnes, glace flottante {int(ice.sum())} colonnes")
    return M.ecrire("ilulissat", X, Z, L["y"], L["h"], L["y"].copy(), typ, L["sd"], L["eau"], "GRANITE")


# Essais écartés (10/11/2026) : Kamtchatka (massif) et Ilulissat (côte). Sur un continent, le terrain resserré ne
# rejoint pas le terrain étiré du mod au bord de la zone (plateau carré, mur de 50 blocs) ; seule une île entourée
# de mer (Erebus) se raccorde proprement. Gardés pour mémoire, pas inscrits.
LIEUX = {"erebus": erebus}
ESSAIS = {"kamtchatka": kamtchatka, "ilulissat": ilulissat}

if __name__ == "__main__":
    noms = [a for a in sys.argv[2:] if not a.startswith("--")]
    for n in (noms or LIEUX):
        (LIEUX.get(n) or ESSAIS[n])()

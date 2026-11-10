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


def composante(masque, j, i):
    lab, _ = ndimage.label(masque)
    return lab == lab[j, i] if lab[j, i] else np.zeros(masque.shape, bool)


def lieu_iso(nom, lat_a, lon_a, seuil, marge=70, fondu=50, ile=True):
    cx, cz = lon_a * BPD, -lat_a * BPD
    f = np.cos(np.radians(lat_a))
    # zone : le massif étiré du mod (terre reliée à l'ancrage au-dessus du seuil), plus la marge
    r = int(3.0 * BPD)
    Xg, Zg = np.meshgrid(np.arange(int(cx) - 6 * r, int(cx) + 6 * r, 2.0), np.arange(int(cz) - r, int(cz) + r, 2.0))
    _, sdg, ag = terrain_mod(Xg, Zg)
    jA, iA = r // 2, 3 * r
    etire = composante((sdg >= 0) & (ag > seuil), jA, iA)
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
    jA, iA = int(round(cz - z0)), int(round(cx - x0))
    coeur = composante((sdw >= 0) & (aw > seuil), jA, iA)
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
    y = np.where(mer, np.minimum(y, 61.9), np.maximum(y, 63.6))
    eau = np.where(mer & (wy > 0.02), 63.0, np.nan)
    return dict(X=X, Z=Z, y=y, h=h, sd=sd, eau=eau, mer=mer, coeur=coeur, alt=aw, de=de, wy=wy)


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
    typ = neige_glace(L, ligne_neige=-1000.0, biome_seuil=60.0)
    return M.ecrire("erebus", L["X"], L["Z"], L["y"], L["h"], L["y"].copy(), typ, L["sd"], L["eau"], "VOLCAN",
                    garder_fleuves=False)


LIEUX = {"erebus": erebus}

if __name__ == "__main__":
    noms = [a for a in sys.argv[2:] if not a.startswith("--")]
    for n in (noms or LIEUX):
        LIEUX[n]()

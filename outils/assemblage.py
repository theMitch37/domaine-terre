"""Assemblage d'un lieu et de ses tuiles voisines (3 x 3 tuiles de 512 blocs) : vue de dessus ombrée, telle que le
monde sera généré (sol au bloc près : terre_py.sol_exact, validé par le banc ; lieux lus dans les tuiles sculptées ;
eau de mer, des fleuves, des lacs et des lieux).

Limites : pas d'arbres ni d'herbes (ce sont des « features » du jeu), couleurs du sol simplifiées hors des lieux
(herbe, roche des pentes, neige d'altitude), pas de lumière du jeu.
Usage : python3 outils/assemblage.py <lieu> [<lieu> ...] [--sortie=<dossier>]
Sortie : <dossier>/assemblage_<lieu>.png (1 px = 1 bloc, traits rouges = bords des tuiles, jaune = bord du lieu)
"""
import json, os, sys
import numpy as np
from PIL import Image
from scipy import ndimage
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import terre_py as T
import tuiles as tu

TT = tu.T
SANS = np.iinfo(np.int64).min


def tuile_calculee(tx, tz):
    """Sol, eau (niveau, NaN sinon), type de lieu et nom du lieu d'une tuile."""
    x0, z0 = tx * TT, tz * TT
    sol = T.sol_exact(x0, z0, TT, TT).astype(float)
    X, Z = np.meshgrid(np.arange(x0, x0 + TT, dtype=float), np.arange(z0, z0 + TT, dtype=float))
    sd = T.distance_cote(X, Z)
    eau = np.where(sd < 0, float(T.NIVEAU_MER), np.nan)
    pres, d, hw, _, _, w = T.rivieres(X, Z)
    eau = np.where(pres & (d <= hw) & (sd >= 0), w.astype(float), eau)
    _, _, nivl, presl = T.niveaux_lacs(X, Z, sd)
    lb = pres & (d <= hw + T.BERGE_RIVIERE)
    _, eau_lac, _ = T.appliquer_lacs(np.zeros(X.shape), X, Z, sd, lb)
    eau = np.where((eau_lac != SANS) & (eau_lac > sol), eau_lac.astype(float), eau)
    haut, sommet, typ, lieu = tu.lire_zone(x0, z0, TT, TT)
    el = tu.lire_zone.eau
    dans = haut != tu.VIDE
    sol = np.where(dans, np.floor(np.round(haut) / 16.0), sol)
    eau_l = np.where(el != tu.VIDE, el.astype(float), np.nan)
    eau = np.where(dans, np.where(np.isfinite(eau_l), eau_l, np.where(sd < 0, eau, np.nan)), eau)
    eau = np.where(np.isfinite(eau) & (eau <= sol + 0.5), np.nan, eau)
    return sol, eau, np.where(dans, typ, 0), lieu


COULEURS = {1: (108, 150, 72), 2: (205, 196, 150), 3: (120, 115, 100), 4: (128, 128, 130), 9: (100, 150, 70),
            11: (244, 246, 252), 12: (175, 210, 240), 13: (150, 145, 138), 14: (88, 125, 62), 15: (130, 125, 115)}


def image(sol, eau, typ, lieu, nom):
    gz, gx = np.gradient(sol)
    ombre = np.clip(0.78 + 0.22 * (-gx - gz) / np.sqrt(1 + gx ** 2 + gz ** 2) * 1.6, 0.35, 1.15)[..., None]
    pente = np.hypot(gx, gz)
    rgb = np.zeros(sol.shape + (3,))
    herbe = np.array([104, 152, 74]) * (1 - np.clip((sol - 110) / 120, 0, 0.35))[..., None]
    rgb[:] = herbe
    rgb[pente > 1.3] = (128, 126, 122)
    rgb[(sol > 185) & (pente < 1.1)] = (240, 242, 248)
    rgb[(sol < 66) & (pente < 0.6)] = (205, 196, 150)                    # rivages bas
    cl = typ & 15
    for k, c in COULEURS.items():
        rgb[(cl == k) & (lieu != "")] = c
    rgb = rgb * ombre
    w = np.isfinite(eau)
    prof = np.where(w, eau - sol, 0)
    rgb[w] = (np.array([60, 120, 210]) * (1 - np.clip(prof[w] / 30, 0, 0.65))[:, None])
    bord = (lieu == nom) & ndimage.binary_dilation(lieu != nom)
    rgb[bord] = (255, 220, 0)
    return np.clip(rgb, 0, 255).astype(np.uint8)


def assemblage(nom, sortie):
    z = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "banc", "zones.json")))
    x0, x1, z0, z1 = z[nom]
    tx, tz = ((x0 + x1) // 2) // TT, ((z0 + z1) // 2) // TT
    W = 3 * TT
    out = np.zeros((W, W, 3), np.uint8)
    for dj in (-1, 0, 1):
        for di in (-1, 0, 1):
            sol, eau, typ, lieu = tuile_calculee(tx + di, tz + dj)
            out[(dj + 1) * TT:(dj + 2) * TT, (di + 1) * TT:(di + 2) * TT] = image(sol, eau, typ, lieu, nom)
    for k in (TT, 2 * TT):
        out[k - 1:k + 1, :] = (220, 40, 40)
        out[:, k - 1:k + 1] = (220, 40, 40)
    chemin = os.path.join(sortie, f"assemblage_{nom}.png")
    Image.fromarray(out).save(chemin)
    print(f"{nom} : tuiles {tx - 1}..{tx + 1} x {tz - 1}..{tz + 1} -> {chemin}")
    return chemin


if __name__ == "__main__":
    sortie = next((a[9:] for a in sys.argv[1:] if a.startswith("--sortie=")), "/tmp")
    for n in [a for a in sys.argv[1:] if not a.startswith("--")]:
        assemblage(n, sortie)

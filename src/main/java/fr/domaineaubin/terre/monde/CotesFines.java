package fr.domaineaubin.terre.monde;

import fr.domaineaubin.terre.DomaineTerre;

import java.io.IOException;
import java.io.InputStream;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.concurrent.ConcurrentHashMap;
import java.util.zip.DataFormatException;
import java.util.zip.Inflater;

/**
 * Le vrai trait de côte au bloc près (Terre 0.3.2, « mer fidèle ») : GSHHG 2.3.7 full, construit par
 * outils/cotes_fines.py (format décrit là-bas). Une case = un bloc à l'échelle 1:250 (445,28 cases par degré).
 *
 * distance(lon, lat) : distance signée à la côte en cases, positive dans les terres, bornée à ±RAYON.
 * Calculée par tuile de 256 x 256 cases (transformée de distance exacte sur la tuile et une marge de RAYON
 * prise chez ses voisines), puis gardée en cache.
 */
public final class CotesFines {

    public static final double CASES_PAR_DEGRE = 445.28;
    /** Au-delà, on ne mesure plus finement : la carte grossière (3') prend le relais. */
    public static final int RAYON = 48;
    private static final int T = 256;
    private static final int MAX_CACHE = 768;

    private final int tx, ty;
    private final byte[] etat;                    // 0 mer, 1 terre, 2 mixte
    private final int[] debut, longueur;          // par tuile mixte : position dans `donnees`, -1 sinon
    private final byte[] donnees;
    private final ConcurrentHashMap<Integer, byte[]> masques = new ConcurrentHashMap<>();
    private final ConcurrentHashMap<Integer, short[]> distances = new ConcurrentHashMap<>();

    private CotesFines(int tx, int ty, byte[] etat, int[] debut, int[] longueur, byte[] donnees) {
        this.tx = tx;
        this.ty = ty;
        this.etat = etat;
        this.debut = debut;
        this.longueur = longueur;
        this.donnees = donnees;
    }

    /** Charge la carte des côtes fines, ou null si elle est absente (le mod garde alors la carte 3'). */
    public static CotesFines charger() {
        try (InputStream brut = CotesFines.class.getResourceAsStream("/domaine_terre/carte/cotes_fines.bin")) {
            if (brut == null) {
                DomaineTerre.LOGGER.warn("Côtes fines absentes : trait de côte de la carte 3'");
                return null;
            }
            long t0 = System.currentTimeMillis();
            byte[] tout = brut.readAllBytes();
            ByteBuffer b = ByteBuffer.wrap(tout).order(ByteOrder.LITTLE_ENDIAN);
            byte[] magie = new byte[4];
            b.get(magie);
            if (!"COTE".equals(new String(magie)) || b.getInt() != 1) throw new IOException("format inconnu");
            b.getDouble();
            if (b.getInt() != T) throw new IOException("taille de tuile inattendue");
            int tx = b.getInt(), ty = b.getInt();
            byte[] etat = new byte[tx * ty];
            b.get(etat);
            int n = b.getInt();
            int[] debut = new int[tx * ty], longueur = new int[tx * ty];
            java.util.Arrays.fill(debut, -1);
            int[] cles = new int[n];
            for (int i = 0; i < n; i++) {
                cles[i] = b.getInt();
                longueur[cles[i]] = b.getInt();
            }
            int pos = b.position();
            for (int i = 0; i < n; i++) {
                debut[cles[i]] = pos;
                pos += longueur[cles[i]];
            }
            DomaineTerre.LOGGER.info("Côtes fines chargées : {} tuiles côtières en {} ms", n, System.currentTimeMillis() - t0);
            return new CotesFines(tx, ty, etat, debut, longueur, tout);
        } catch (IOException e) {
            DomaineTerre.LOGGER.error("Côtes fines illisibles, trait de côte de la carte 3'", e);
            return null;
        }
    }

    /** Distance signée à la côte en cases (≈ blocs à 1:250), positive dans les terres, bornée à ±RAYON. */
    public double distance(double lon, double lat) {
        long gx = (long) Math.floor((lon + 180.0) * CASES_PAR_DEGRE);
        long gy = (long) Math.floor((90.0 - lat) * CASES_PAR_DEGRE);
        int cx = (int) Math.floorDiv(gx, T), cy = (int) Math.floorDiv(gy, T);
        int ix = (int) Math.floorMod(gx, T), iy = (int) Math.floorMod(gy, T);
        cx = Math.floorMod(cx, tx);
        if (cy < 0 || cy >= ty) return cy < 0 ? -RAYON : RAYON;    // pôles : mer au nord, Antarctique au sud
        short[] d = tuileDistances(cx, cy);
        if (d == null) return etat(cx, cy) == 1 ? RAYON : -RAYON;
        return d[iy * T + ix] / 16.0;
    }

    private int etat(int cx, int cy) {
        if (cy < 0) return 0;
        if (cy >= ty) return 1;
        return etat[cy * tx + Math.floorMod(cx, tx)];
    }

    /** Distances d'une tuile, ou null si la tuile et ses voisines sont toutes du même état (loin des côtes). */
    private short[] tuileDistances(int cx, int cy) {
        int e0 = etat(cx, cy);
        boolean uniforme = e0 != 2;
        for (int dy = -1; dy <= 1 && uniforme; dy++)
            for (int dx = -1; dx <= 1 && uniforme; dx++)
                if (etat(cx + dx, cy + dy) != e0) uniforme = false;
        if (uniforme) return null;
        int cle = cy * tx + cx;
        short[] d = distances.get(cle);
        if (d != null) return d;
        if (distances.size() > MAX_CACHE) distances.clear();
        d = calculer(cx, cy);
        distances.put(cle, d);
        return d;
    }

    /** Terre (true) ou mer pour la case (i, j) de la tuile (cx, cy), voisines comprises. */
    private boolean terre(int cx, int cy, int i, int j) {
        int e = etat(cx, cy);
        if (e != 2) return e == 1;
        byte[] m = masque(cy * tx + Math.floorMod(cx, tx));
        int k = j * T + i;
        return (m[k >> 3] & (0x80 >> (k & 7))) != 0;
    }

    private byte[] masque(int cle) {
        byte[] m = masques.get(cle);
        if (m != null) return m;
        if (masques.size() > 4 * MAX_CACHE) masques.clear();
        Inflater inf = new Inflater();
        inf.setInput(donnees, debut[cle], longueur[cle]);
        m = new byte[T * T / 8];
        try {
            int lu = 0;
            while (lu < m.length && !inf.finished()) lu += inf.inflate(m, lu, m.length - lu);
        } catch (DataFormatException e) {
            throw new IllegalStateException("Tuile de côte abîmée " + cle, e);
        } finally {
            inf.end();
        }
        masques.put(cle, m);
        return m;
    }

    /** Transformée de distance exacte (Felzenszwalb) sur la tuile et une marge de RAYON, en seizièmes de case. */
    private short[] calculer(int cx, int cy) {
        int M = RAYON, W = T + 2 * M;
        boolean[] terre = new boolean[W * W];
        for (int j = 0; j < W; j++) {
            int gj = cy * T + j - M;
            int ty2 = Math.floorDiv(gj, T), jj = Math.floorMod(gj, T);
            for (int i = 0; i < W; i++) {
                int gi = cx * T + i - M;
                terre[j * W + i] = terre(Math.floorDiv(gi, T), ty2, Math.floorMod(gi, T), jj);
            }
        }
        double[] versMer = edt(terre, W, true);       // depuis la terre : distance à la mer la plus proche
        double[] versTerre = edt(terre, W, false);
        short[] d = new short[T * T];
        for (int j = 0; j < T; j++) {
            for (int i = 0; i < T; i++) {
                int k = (j + M) * W + (i + M);
                double v = terre[k] ? Math.sqrt(versMer[k]) - 0.5 : -(Math.sqrt(versTerre[k]) - 0.5);
                v = Math.max(-RAYON, Math.min(RAYON, v));
                d[j * T + i] = (short) Math.round(v * 16.0);
            }
        }
        return d;
    }

    /** Distance au carré de chaque case `source` à la case non-`source` la plus proche (Felzenszwalb, exacte). */
    private static double[] edt(boolean[] terre, int W, boolean source) {
        final double INF = 1e20;
        double[] g = new double[W * W];
        for (int k = 0; k < g.length; k++) g[k] = terre[k] == source ? INF : 0.0;
        double[] f = new double[W], d = new double[W], z = new double[W + 1];
        int[] v = new int[W];
        for (int pass = 0; pass < 2; pass++) {
            for (int a = 0; a < W; a++) {
                for (int b = 0; b < W; b++) f[b] = pass == 0 ? g[b * W + a] : g[a * W + b];
                int k = 0;
                v[0] = 0;
                z[0] = -INF;
                z[1] = INF;
                for (int q = 1; q < W; q++) {
                    double s = ((f[q] + (double) q * q) - (f[v[k]] + (double) v[k] * v[k])) / (2.0 * q - 2.0 * v[k]);
                    while (s <= z[k]) {
                        k--;
                        s = ((f[q] + (double) q * q) - (f[v[k]] + (double) v[k] * v[k])) / (2.0 * q - 2.0 * v[k]);
                    }
                    k++;
                    v[k] = q;
                    z[k] = s;
                    z[k + 1] = INF;
                }
                k = 0;
                for (int q = 0; q < W; q++) {
                    while (z[k + 1] < q) k++;
                    d[q] = (double) (q - v[k]) * (q - v[k]) + f[v[k]];
                }
                for (int b = 0; b < W; b++) {
                    if (pass == 0) g[b * W + a] = d[b]; else g[a * W + b] = d[b];
                }
            }
        }
        return g;
    }
}

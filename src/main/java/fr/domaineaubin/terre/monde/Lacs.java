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
 * Les lacs au bloc près (Terre 0.3.2, étape C1) : GSHHG full niveau 2 et l'altitude réelle de leur surface
 * (Copernicus DEM GLO-90), construits par outils/lacs_fins.py (format décrit là-bas). Même grille que
 * {@link CotesFines} : une case = un bloc à 1:250.
 *
 * Pour une case : le lac le plus proche (dans un rayon de RAYON cases) et la distance signée à son rivage,
 * positive dans le lac. Calculé par tuile de 256 x 256 cases (transformée de distance exacte avec la case source,
 * sur la tuile et une marge de RAYON prise chez ses voisines), puis gardé en cache.
 */
public final class Lacs {

    public static final double CASES_PAR_DEGRE = CotesFines.CASES_PAR_DEGRE;
    /** Au-delà, un lac n'a plus d'influence sur le terrain (berges comprises). */
    public static final int RAYON = 48;
    private static final int T = 256;
    private static final int MAX_CACHE = 512;

    /** Lac le plus proche d'une case et distance signée à son rivage (cases, positive dans le lac). */
    public record Proche(int lac, double distance) {
    }

    private final int tx, ty;
    private final float[] altitude, superficie;   // par lac (index 1..L ; 0 inutilisé)
    private final int[] debut, longueur;          // par tuile : position dans `donnees`, -1 sans lac
    private final byte[] donnees;
    private final ConcurrentHashMap<Integer, char[]> ids = new ConcurrentHashMap<>();
    private final ConcurrentHashMap<Integer, long[]> calculs = new ConcurrentHashMap<>();
    private static final char[] VIDE = new char[0];

    private Lacs(int tx, int ty, float[] altitude, float[] superficie, int[] debut, int[] longueur, byte[] donnees) {
        this.tx = tx;
        this.ty = ty;
        this.altitude = altitude;
        this.superficie = superficie;
        this.debut = debut;
        this.longueur = longueur;
        this.donnees = donnees;
    }

    /** Charge la carte des lacs, ou null si elle est absente (pas de lacs en altitude). */
    public static Lacs charger() {
        try (InputStream brut = Lacs.class.getResourceAsStream("/domaine_terre/carte/lacs.bin")) {
            if (brut == null) {
                DomaineTerre.LOGGER.warn("Carte des lacs absente : pas de lacs en altitude");
                return null;
            }
            long t0 = System.currentTimeMillis();
            byte[] tout = brut.readAllBytes();
            ByteBuffer b = ByteBuffer.wrap(tout).order(ByteOrder.LITTLE_ENDIAN);
            byte[] magie = new byte[4];
            b.get(magie);
            if (!"LACS".equals(new String(magie)) || b.getInt() != 1) throw new IOException("format inconnu");
            b.getDouble();
            if (b.getInt() != T) throw new IOException("taille de tuile inattendue");
            int tx = b.getInt(), ty = b.getInt();
            int l = b.getInt();
            float[] alt = new float[l + 1], sup = new float[l + 1];
            for (int k = 1; k <= l; k++) {
                alt[k] = b.getFloat();
                sup[k] = b.getFloat();
            }
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
            DomaineTerre.LOGGER.info("Lacs chargés : {} lacs sur {} tuiles en {} ms", l, n, System.currentTimeMillis() - t0);
            return new Lacs(tx, ty, alt, sup, debut, longueur, tout);
        } catch (IOException e) {
            DomaineTerre.LOGGER.error("Carte des lacs illisible : pas de lacs en altitude", e);
            return null;
        }
    }

    /** Altitude réelle de la surface du lac (m). */
    public double altitude(int lac) {
        return altitude[lac];
    }

    /** Superficie réelle du lac (km²). */
    public double superficie(int lac) {
        return superficie[lac];
    }

    /** Lac le plus proche de la case de (lon, lat) dans un rayon de RAYON cases, ou null. */
    public Proche proche(double lon, double lat) {
        long gx = (long) Math.floor((lon + 180.0) * CASES_PAR_DEGRE);
        long gy = (long) Math.floor((90.0 - lat) * CASES_PAR_DEGRE);
        int cx = (int) Math.floorDiv(gx, T), cy = (int) Math.floorDiv(gy, T);
        int ix = (int) Math.floorMod(gx, T), iy = (int) Math.floorMod(gy, T);
        cx = Math.floorMod(cx, tx);
        if (cy < 0 || cy >= ty) return null;
        long[] c = tuileCalcul(cx, cy);
        if (c == null) return null;
        long v = c[iy * T + ix];
        int lac = (int) (v >>> 16);
        if (lac == 0) return null;
        return new Proche(lac, (short) (v & 0xFFFF) / 16.0);
    }

    private boolean aDesLacs(int cx, int cy) {
        if (cy < 0 || cy >= ty) return false;
        return debut[cy * tx + Math.floorMod(cx, tx)] >= 0;
    }

    /** Lac + distance (16 bits de poids fort : lac, 16 bits : distance en seizièmes) ; null loin de tout lac. */
    private long[] tuileCalcul(int cx, int cy) {
        boolean loin = true;
        for (int dy = -1; dy <= 1 && loin; dy++)
            for (int dx = -1; dx <= 1 && loin; dx++)
                if (aDesLacs(cx + dx, cy + dy)) loin = false;
        if (loin) return null;
        int cle = cy * tx + cx;
        long[] d = calculs.get(cle);
        if (d != null) return d;
        if (calculs.size() > MAX_CACHE) calculs.clear();
        d = calculer(cx, cy);
        calculs.put(cle, d);
        return d;
    }

    private char[] idsTuile(int cx, int cy) {
        if (!aDesLacs(cx, cy)) return VIDE;
        int cle = cy * tx + Math.floorMod(cx, tx);
        char[] m = ids.get(cle);
        if (m != null) return m;
        if (ids.size() > 4 * MAX_CACHE) ids.clear();
        Inflater inf = new Inflater();
        inf.setInput(donnees, debut[cle], longueur[cle]);
        byte[] brut = new byte[T * T * 2];
        try {
            int lu = 0;
            while (lu < brut.length && !inf.finished()) lu += inf.inflate(brut, lu, brut.length - lu);
        } catch (DataFormatException e) {
            throw new IllegalStateException("Tuile de lacs abîmée " + cle, e);
        } finally {
            inf.end();
        }
        m = new char[T * T];
        ByteBuffer.wrap(brut).order(ByteOrder.LITTLE_ENDIAN).asCharBuffer().get(m);
        ids.put(cle, m);
        return m;
    }

    /** Transformée de distance exacte (Felzenszwalb) avec la case source, sur la tuile et une marge de RAYON. */
    private long[] calculer(int cx, int cy) {
        int M = RAYON, W = T + 2 * M;
        char[] lac = new char[W * W];
        for (int j = 0; j < W; j++) {
            int gj = cy * T + j - M;
            int ty2 = Math.floorDiv(gj, T), jj = Math.floorMod(gj, T);
            for (int i = 0; i < W; i++) {
                int gi = cx * T + i - M;
                char[] m = idsTuile(Math.floorDiv(gi, T), ty2);
                lac[j * W + i] = m.length == 0 ? 0 : m[jj * T + Math.floorMod(gi, T)];
            }
        }
        boolean[] eau = new boolean[W * W];
        for (int k = 0; k < eau.length; k++) eau[k] = lac[k] != 0;
        int[] srcHors = new int[W * W], srcDans = new int[W * W];
        double[] versLac = edt(eau, W, true, srcHors);     // hors du lac : distance au lac le plus proche (et sa case)
        double[] versRive = edt(eau, W, false, srcDans);   // dans le lac : distance à la rive
        long[] d = new long[T * T];
        for (int j = 0; j < T; j++) {
            for (int i = 0; i < T; i++) {
                int k = (j + M) * W + (i + M);
                int id;
                double v;
                if (eau[k]) {
                    id = lac[k];
                    v = Math.sqrt(versRive[k]) - 0.5;
                } else {
                    if (versLac[k] >= 1e19) { d[j * T + i] = 0; continue; }
                    id = lac[srcHors[k]];
                    v = -(Math.sqrt(versLac[k]) - 0.5);
                }
                if (v < -RAYON) { d[j * T + i] = 0; continue; }
                v = Math.min(RAYON, v);
                d[j * T + i] = ((long) id << 16) | (Math.round(v * 16.0) & 0xFFFF);
            }
        }
        return d;
    }

    /**
     * Distance au carré de chaque case à la case `cible` la plus proche (Felzenszwalb, exacte) ; `source` reçoit
     * l'index de cette case. `cible` = true : vers les cases d'eau ; false : vers les cases hors de l'eau.
     */
    private static double[] edt(boolean[] eau, int W, boolean cible, int[] source) {
        final double INF = 1e20;
        double[] g = new double[W * W];
        int[] ligne = new int[W * W];                       // passe 1 : ligne de la case la plus proche dans la colonne
        for (int k = 0; k < g.length; k++) g[k] = eau[k] == cible ? 0.0 : INF;
        double[] f = new double[W], out = new double[W], z = new double[W + 1];
        int[] v = new int[W], arg = new int[W];
        // passe 1 : colonnes
        for (int a = 0; a < W; a++) {
            for (int b = 0; b < W; b++) f[b] = g[b * W + a];
            unDim(f, W, out, arg, v, z);
            for (int b = 0; b < W; b++) { g[b * W + a] = out[b]; ligne[b * W + a] = arg[b]; }
        }
        // passe 2 : lignes
        double[] r = new double[W * W];
        for (int b = 0; b < W; b++) {
            for (int a = 0; a < W; a++) f[a] = g[b * W + a];
            unDim(f, W, out, arg, v, z);
            for (int a = 0; a < W; a++) {
                r[b * W + a] = out[a];
                int col = arg[a];
                source[b * W + a] = ligne[b * W + col] * W + col;
            }
        }
        return r;
    }

    /** Enveloppe inférieure des paraboles (Felzenszwalb & Huttenlocher), avec l'indice de la parabole retenue. */
    private static void unDim(double[] f, int n, double[] d, int[] arg, int[] v, double[] z) {
        final double INF = 1e20;
        int k = 0;
        v[0] = 0;
        z[0] = -INF;
        z[1] = INF;
        for (int q = 1; q < n; q++) {
            if (f[q] >= INF) continue;
            if (f[v[k]] >= INF) { v[k] = q; continue; }
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
        for (int q = 0; q < n; q++) {
            while (z[k + 1] < q) k++;
            double dq = q - v[k];
            if (f[v[k]] >= INF) { d[q] = INF; arg[q] = v[k]; continue; }
            d[q] = dq * dq + f[v[k]];
            arg[q] = v[k];
        }
    }
}

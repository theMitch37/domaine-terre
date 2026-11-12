package fr.domaineaubin.terre.monde;

import fr.domaineaubin.terre.DomaineTerre;
import it.unimi.dsi.fastutil.ints.IntArrayList;
import it.unimi.dsi.fastutil.longs.Long2ObjectOpenHashMap;
import net.minecraft.world.level.WorldGenLevel;

import java.io.InputStream;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;

/**
 * Récifs coralliens réels (12/11/2026, demande de Maxime : « des barrières de corail là où elles existent en vrai », et
 * plus de corail aux embouchures). Lignes de récifs de Natural Earth 10m (domaine public, outils/recifs.py) : le corail
 * du jeu (CoralFeature, via CoralMixin) ne pousse qu'à moins de RAYON_KM d'une ligne de récif, et jamais à moins de
 * 48 blocs du lit d'un cours d'eau du mod (eau douce et vase). Ailleurs, les mers chaudes gardent herbiers et sable.
 */
public final class Recifs {
    /** Demi-largeur de la bande de récif autour d'une ligne (km réels), au moins 6 blocs. */
    private static final double RAYON_KM = 4.0;
    /** Taille d'une case de l'index (degrés) et marge autour d'un segment (degrés). */
    private static final double CASE = 0.5, MARGE = 0.2;

    private static volatile Recifs instance;
    private final float[] lon1, lat1, lon2, lat2;          // segments
    private final Long2ObjectOpenHashMap<int[]> index = new Long2ObjectOpenHashMap<>();

    private Recifs(float[] a, float[] b, float[] c, float[] d) {
        lon1 = a; lat1 = b; lon2 = c; lat2 = d;
        Long2ObjectOpenHashMap<IntArrayList> tmp = new Long2ObjectOpenHashMap<>();
        for (int i = 0; i < a.length; i++) {
            int x0 = (int) Math.floor((Math.min(a[i], c[i]) - MARGE) / CASE), x1 = (int) Math.floor((Math.max(a[i], c[i]) + MARGE) / CASE);
            int y0 = (int) Math.floor((Math.min(b[i], d[i]) - MARGE) / CASE), y1 = (int) Math.floor((Math.max(b[i], d[i]) + MARGE) / CASE);
            for (int x = x0; x <= x1; x++) for (int y = y0; y <= y1; y++) tmp.computeIfAbsent(cle(x, y), k -> new IntArrayList()).add(i);
        }
        for (var e : tmp.long2ObjectEntrySet()) index.put(e.getLongKey(), e.getValue().toIntArray());
    }

    private static long cle(int x, int y) {
        return ((long) x << 32) ^ (y & 0xFFFFFFFFL);
    }

    public static Recifs get() {
        Recifs r = instance;
        if (r != null) return r;
        synchronized (Recifs.class) {
            if (instance != null) return instance;
            float[] a = new float[0], b = a, c = a, d = a;
            try (InputStream in = Recifs.class.getResourceAsStream("/domaine_terre/carte/recifs.bin")) {
                if (in != null) {
                    ByteBuffer buf = ByteBuffer.wrap(in.readAllBytes()).order(ByteOrder.LITTLE_ENDIAN);
                    int n = buf.getInt();
                    it.unimi.dsi.fastutil.floats.FloatArrayList la = new it.unimi.dsi.fastutil.floats.FloatArrayList(),
                            lb = new it.unimi.dsi.fastutil.floats.FloatArrayList(), lc = new it.unimi.dsi.fastutil.floats.FloatArrayList(),
                            ld = new it.unimi.dsi.fastutil.floats.FloatArrayList();
                    for (int i = 0; i < n; i++) {
                        int m = buf.getInt();
                        float px = buf.getFloat(), py = buf.getFloat();
                        for (int j = 1; j < m; j++) {
                            float qx = buf.getFloat(), qy = buf.getFloat();
                            if (Math.abs(qx - px) < 10f) { la.add(px); lb.add(py); lc.add(qx); ld.add(qy); }
                            px = qx; py = qy;
                        }
                    }
                    a = la.toFloatArray(); b = lb.toFloatArray(); c = lc.toFloatArray(); d = ld.toFloatArray();
                }
            } catch (Exception e) {
                DomaineTerre.LOGGER.error("Récifs : recifs.bin illisible", e);
            }
            DomaineTerre.LOGGER.info("Récifs : {} segments", a.length);
            instance = new Recifs(a, b, c, d);
            return instance;
        }
    }

    /** Distance (degrés) au récif le plus proche, ou +infini au-delà de la marge de l'index. */
    private double distanceDeg(double lon, double lat) {
        int[] l = index.get(cle((int) Math.floor(lon / CASE), (int) Math.floor(lat / CASE)));
        if (l == null) return Double.POSITIVE_INFINITY;
        double best = Double.POSITIVE_INFINITY;
        for (int i : l) {
            double ax = lon1[i], ay = lat1[i], dx = lon2[i] - ax, dy = lat2[i] - ay, l2 = dx * dx + dy * dy;
            double u = l2 > 0 ? Math.max(0, Math.min(1, ((lon - ax) * dx + (lat - ay) * dy) / l2)) : 0;
            double ex = lon - (ax + u * dx), ey = lat - (ay + u * dy);
            best = Math.min(best, ex * ex + ey * ey);
        }
        return Math.sqrt(best);
    }

    /** Le corail peut-il pousser en (x, z) ? (monde Terre seulement ; ailleurs, le jeu décide) */
    public static boolean corail(WorldGenLevel niveau, int x, int z) {
        if (!FauneSpawns.terre(niveau)) return true;
        Terrain t = Terrain.get();
        if (t.distanceCoursDEau(x, z) < 48.0) return false;
        double rayonDeg = Math.max(RAYON_KM / 111.32, 6.0 / Terrain.BLOCS_PAR_DEGRE);
        return get().distanceDeg(Terrain.lon(x), Terrain.lat(z)) <= rayonDeg;
    }
}

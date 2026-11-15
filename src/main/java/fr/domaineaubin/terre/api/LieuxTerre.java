package fr.domaineaubin.terre.api;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;

/**
 * Registre des lieux uniques. Un addon y inscrit ses lieux dans le constructeur de son mod
 * (avant le chargement de tout monde).
 *
 * 1.0.7 (optimisation, profil du 15/11/2026 : ~10 % du temps de génération à tester chaque lieu pour chaque colonne) :
 * index par cases de 256 blocs : pour chaque case, les seuls lieux qui peuvent la concerner ({@link Lieu#pres}).
 */
public final class LieuxTerre {
    private static final List<Lieu> LIEUX = new CopyOnWriteArrayList<>();
    private static final int CASE = 256;
    private static final int[] AUCUN = new int[0];
    private static final ConcurrentHashMap<Long, int[]> INDEX = new ConcurrentHashMap<>();

    private LieuxTerre() {
    }

    public static void inscrire(Lieu lieu) {
        LIEUX.add(lieu);
        INDEX.clear();
    }

    public static List<Lieu> liste() {
        return LIEUX;
    }

    /** Numéros (dans {@link #liste()}) des lieux qui peuvent concerner la colonne, dans l'ordre de la liste. */
    public static int[] proches(int x, int z) {
        if (LIEUX.isEmpty()) return AUCUN;
        int cx = Math.floorDiv(x, CASE), cz = Math.floorDiv(z, CASE);
        long cle = ((long) cx << 32) ^ (cz & 0xFFFFFFFFL);
        int[] r = INDEX.get(cle);
        if (r != null) return r;
        if (INDEX.size() > 200_000) INDEX.clear();
        List<Integer> l = new ArrayList<>();
        int x0 = cx * CASE, z0 = cz * CASE;
        for (int i = 0; i < LIEUX.size(); i++) {
            if (LIEUX.get(i).pres(x0, z0, x0 + CASE - 1, z0 + CASE - 1)) l.add(i);
        }
        r = l.isEmpty() ? AUCUN : l.stream().mapToInt(Integer::intValue).toArray();
        INDEX.put(cle, r);
        return r;
    }

    /** Premier lieu qui concerne cette colonne, ou null. */
    public static Lieu a(int x, int z) {
        for (int i : proches(x, z)) {
            Lieu l = LIEUX.get(i);
            if (l.concerne(x, z)) return l;
        }
        return null;
    }
}

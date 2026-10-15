package fr.domaineaubin.terre.api;

import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;

/**
 * Registre des lieux uniques. Un addon y inscrit ses lieux dans le constructeur de son mod
 * (avant le chargement de tout monde).
 */
public final class LieuxTerre {
    private static final List<Lieu> LIEUX = new CopyOnWriteArrayList<>();

    private LieuxTerre() {
    }

    public static void inscrire(Lieu lieu) {
        LIEUX.add(lieu);
    }

    public static List<Lieu> liste() {
        return LIEUX;
    }

    /** Premier lieu qui concerne cette colonne, ou null. */
    public static Lieu a(int x, int z) {
        for (Lieu l : LIEUX) if (l.concerne(x, z)) return l;
        return null;
    }
}

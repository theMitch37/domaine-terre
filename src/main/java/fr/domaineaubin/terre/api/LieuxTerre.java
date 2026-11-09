package fr.domaineaubin.terre.api;

import fr.domaineaubin.terre.monde.Terrain;

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

    /** Lieux du monde chargé : aucun dans un monde 1:30 (réglés pour le 1:250). */
    public static List<Lieu> liste() {
        if (Terrain.echelle() < 250) return List.of();
        return LIEUX;
    }

    /**
     * Premier lieu qui concerne cette colonne, ou null. Les lieux sont réglés pour le 1:250 : dans un monde 1:30, ils ne
     * sont pas posés (le vrai relief à 30 m en tient lieu, 09/11/2026).
     */
    public static Lieu a(int x, int z) {
        if (Terrain.echelle() < 250) return null;
        for (Lieu l : LIEUX) if (l.concerne(x, z)) return l;
        return null;
    }
}

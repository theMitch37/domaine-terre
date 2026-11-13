package fr.domaineaubin.terre.api;

import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Structures vanilla rallumées par un addon (13/11/2026). Sans addon, le mod Terre coupe toutes les structures
 * vanilla sauf les forteresses (monde vierge) ; Domaine Village les rallume ici, une par une, et les place lui-même.
 */
public final class StructuresTerre {
    private static final Set<String> RALLUMEES = ConcurrentHashMap.newKeySet();

    private StructuresTerre() {
    }

    /** Rallume la structure vanilla {@code minecraft:<chemin>} (ex. « village_plains »). */
    public static void rallumer(String chemin) {
        RALLUMEES.add(chemin);
    }

    public static boolean rallumee(String chemin) {
        return RALLUMEES.contains(chemin);
    }
}

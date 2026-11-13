package fr.domaineaubin.village;

import net.minecraft.world.level.ChunkPos;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Listes de points fixes (resources domaine_terre_village/<liste>.csv : x;z en blocs à l'échelle 1:250, première
 * ligne = en-têtes). Chargées une fois, rangées par case.
 */
public final class Points {
    /** Monde Terre en cours (posé au démarrage du serveur). */
    public static volatile boolean terre = false;

    private static final Map<String, Map<Long, ChunkPos>> LISTES = new ConcurrentHashMap<>();

    private Points() {
    }

    static long cle(int cx, int cz) {
        return ((long) cx << 32) ^ (cz & 0xFFFFFFFFL);
    }

    static Map<Long, ChunkPos> liste(String nom, int taille) {
        return LISTES.computeIfAbsent(nom + "@" + taille, k -> charger(nom, taille));
    }

    /** Forteresses de l'End (une par continent). */
    public static java.util.List<ChunkPos> forteresses() {
        return new java.util.ArrayList<>(liste("forteresses", PlacementFixe.CASE).values());
    }

    public static int taille(String nom, int taille) {
        return liste(nom, taille).size();
    }

    private static Map<Long, ChunkPos> charger(String nom, int taille) {
        Map<Long, ChunkPos> m = new HashMap<>();
        String chemin = "/domaine_terre_village/" + nom + ".csv";
        try (InputStream in = Points.class.getResourceAsStream(chemin)) {
            if (in == null) {
                DomaineVillage.LOGGER.error("Domaine Village : liste {} introuvable", chemin);
                return m;
            }
            BufferedReader r = new BufferedReader(new InputStreamReader(in, StandardCharsets.UTF_8));
            String l = r.readLine();                                    // en-têtes
            while ((l = r.readLine()) != null) {
                String[] c = l.split(";");
                if (c.length < 2) continue;
                int x = (int) Math.floor(Double.parseDouble(c[0])), z = (int) Math.floor(Double.parseDouble(c[1]));
                int chx = x >> 4, chz = z >> 4;
                m.putIfAbsent(cle(Math.floorDiv(chx, taille), Math.floorDiv(chz, taille)), new ChunkPos(chx, chz));
            }
        } catch (Exception e) {
            DomaineVillage.LOGGER.error("Domaine Village : liste {} illisible", chemin, e);
        }
        DomaineVillage.LOGGER.info("Domaine Village : {} points pour {}", m.size(), nom);
        return m;
    }
}

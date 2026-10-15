package fr.domaineaubin.terre.monde;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import fr.domaineaubin.terre.DomaineTerre;
import it.unimi.dsi.fastutil.ints.IntArrayList;
import it.unimi.dsi.fastutil.longs.Long2ObjectOpenHashMap;

import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;

/**
 * Tracés réels des fleuves (Natural Earth), convertis en segments en coordonnées de blocs,
 * avec une grille d'index pour trouver vite le segment le plus proche.
 */
public final class Fleuves {
    private static final int CELLULE = 128;
    /** Rayon (blocs) dans lequel le segment le plus proche est garanti trouvé. */
    public static final double RAYON_INDEX = 256.0;

    /** Résultat d'une recherche : distance au lit, classe, point le plus proche sur l'axe du lit. */
    public record Proche(double distance, int classe, double cx, double cz, int niveau) {
    }

    /** Calcule le niveau d'eau d'un segment à partir d'un point (coordonnées de blocs). */
    public interface CalculNiveau {
        int niveau(double x, double z);
    }

    private final float[] ax, az, bx, bz;
    private final byte[] classe;
    private final short[] niveauA, niveauB;
    private final Long2ObjectOpenHashMap<int[]> grille;

    private Fleuves(float[] ax, float[] az, float[] bx, float[] bz, byte[] classe, short[] niveauA, short[] niveauB, Long2ObjectOpenHashMap<int[]> grille) {
        this.ax = ax; this.az = az; this.bx = bx; this.bz = bz;
        this.classe = classe;
        this.niveauA = niveauA;
        this.niveauB = niveauB;
        this.grille = grille;
    }

    private static long cle(int cx, int cz) {
        return ((long) cx << 32) ^ (cz & 0xFFFFFFFFL);
    }

    public static Fleuves charger(double blocsParDegre, CalculNiveau calcul) {
        long t0 = System.currentTimeMillis();
        JsonArray tab;
        try (InputStream in = Fleuves.class.getResourceAsStream("/domaine_terre/carte/fleuves.json")) {
            if (in == null) throw new IOException("fleuves.json introuvable");
            tab = JsonParser.parseReader(new InputStreamReader(in, StandardCharsets.UTF_8)).getAsJsonArray();
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
        int n = 0;
        for (JsonElement e : tab) n += Math.max(0, e.getAsJsonObject().getAsJsonArray("p").size() / 2 - 1);
        float[] ax = new float[n], az = new float[n], bx = new float[n], bz = new float[n];
        byte[] cl = new byte[n];
        short[] nva = new short[n], nvb = new short[n];
        Long2ObjectOpenHashMap<IntArrayList> tmp = new Long2ObjectOpenHashMap<>();
        int i = 0;
        for (JsonElement e : tab) {
            JsonObject o = e.getAsJsonObject();
            int c = o.get("c").getAsInt();
            JsonArray p = o.getAsJsonArray("p");
            double marge = Math.max(Terrain.demiLargeur(c) + Terrain.VALLEE_MAX, RAYON_INDEX);
            for (int k = 0; k + 3 < p.size(); k += 2) {
                double x1 = p.get(k).getAsDouble() * blocsParDegre, z1 = -p.get(k + 1).getAsDouble() * blocsParDegre;
                double x2 = p.get(k + 2).getAsDouble() * blocsParDegre, z2 = -p.get(k + 3).getAsDouble() * blocsParDegre;
                ax[i] = (float) x1; az[i] = (float) z1; bx[i] = (float) x2; bz[i] = (float) z2; cl[i] = (byte) c;
                nva[i] = (short) calcul.niveau(x1, z1);
                nvb[i] = (short) calcul.niveau(x2, z2);
                int c0x = (int) Math.floor((Math.min(x1, x2) - marge) / CELLULE), c1x = (int) Math.floor((Math.max(x1, x2) + marge) / CELLULE);
                int c0z = (int) Math.floor((Math.min(z1, z2) - marge) / CELLULE), c1z = (int) Math.floor((Math.max(z1, z2) + marge) / CELLULE);
                for (int gx = c0x; gx <= c1x; gx++)
                    for (int gz = c0z; gz <= c1z; gz++)
                    {
                        long cg = cle(gx, gz);
                        IntArrayList liste = tmp.get(cg);
                        if (liste == null) {
                            liste = new IntArrayList();
                            tmp.put(cg, liste);
                        }
                        liste.add(i);
                    }
                i++;
            }
        }
        Long2ObjectOpenHashMap<int[]> grille = new Long2ObjectOpenHashMap<>(tmp.size());
        tmp.long2ObjectEntrySet().forEach(en -> grille.put(en.getLongKey(), en.getValue().toIntArray()));
        DomaineTerre.LOGGER.info("Fleuves chargés : {} segments en {} ms", n, System.currentTimeMillis() - t0);
        return new Fleuves(ax, az, bx, bz, cl, nva, nvb, grille);
    }

    /**
     * Segment qui « domine » ce point : celui dont le bord du lit est le plus proche
     * (un grand fleuve l'emporte sur une rivière voisine). null si aucun dans la cellule.
     */
    public Proche proche(double x, double z) {
        int[] ids = grille.get(cle((int) Math.floor(x / CELLULE), (int) Math.floor(z / CELLULE)));
        if (ids == null) return null;
        double meilleur = Double.MAX_VALUE;
        Proche res = null;
        for (int id : ids) {
            double x1 = ax[id], z1 = az[id], dx = bx[id] - x1, dz = bz[id] - z1;
            double l2 = dx * dx + dz * dz;
            double t = l2 > 0 ? ((x - x1) * dx + (z - z1) * dz) / l2 : 0;
            t = Math.max(0, Math.min(1, t));
            double px = x1 + t * dx, pz = z1 + t * dz;
            double d = Math.sqrt((x - px) * (x - px) + (z - pz) * (z - pz));
            double score = d - Terrain.demiLargeur(classe[id]);
            if (score < meilleur) {
                meilleur = score;
                double nv = niveauA[id] + (niveauB[id] - niveauA[id]) * t;
                // biefs plats : le niveau ne change que par paliers de 3 blocs (cascades entre deux)
                int palier = Terrain.NIVEAU_MER + 3 * (int) Math.floor((nv - Terrain.NIVEAU_MER) / 3.0);
                res = new Proche(d, classe[id], px, pz, palier);
            }
        }
        return res;
    }
}

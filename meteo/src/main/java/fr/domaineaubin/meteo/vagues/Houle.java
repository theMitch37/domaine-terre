package fr.domaineaubin.meteo.vagues;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import fr.domaineaubin.meteo.DomaineWeather;
import net.minecraft.core.BlockPos;
import net.minecraft.tags.FluidTags;
import net.minecraft.world.level.Level;
import net.minecraftforge.fml.loading.FMLPaths;

import java.io.Reader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Prototype des vagues « à la GTA » (13/11/2026). Une seule formule de houle (somme de quatre vagues, position +
 * temps) sert à la fois au dessin de la surface et à la barque : les deux ne peuvent pas se désaccorder.
 *
 * Prototype : hauteur fixe (réglable), vagues venant de l'ouest-sud-ouest ; calme près des côtes et sur les hauts-
 * fonds (profondeur d'eau sous la surface de la mer). Plus tard : hauteur selon la mer, la saison, le vent et les
 * orages (météo marine, 0.5). Réglages : config/domaine_weather_vagues.json.
 */
public final class Houle {
    private Houle() {
    }

    public static final class Reglages {
        public String _note = "Prototype des vagues de Domaine Weather. actif : vagues dessinees et barque qui suit la houle ; "
                + "amplitude : hauteur des vagues au large (blocs, du creux a la crete = 2 x amplitude) ; rayon : distance "
                + "de dessin (blocs).";
        public boolean actif = true;
        public double amplitude = 1.0;
        public int rayon = 48;
    }

    private static volatile Reglages reglages;

    public static Reglages reglages() {
        Reglages r = reglages;
        if (r != null) return r;
        synchronized (Houle.class) {
            if (reglages != null) return reglages;
            Path f = FMLPaths.CONFIGDIR.get().resolve("domaine_weather_vagues.json");
            Gson g = new GsonBuilder().setPrettyPrinting().create();
            Reglages lu = null;
            try {
                if (Files.exists(f)) {
                    try (Reader rd = Files.newBufferedReader(f, StandardCharsets.UTF_8)) {
                        lu = g.fromJson(rd, Reglages.class);
                    }
                } else {
                    Files.createDirectories(f.getParent());
                    Files.writeString(f, g.toJson(new Reglages()), StandardCharsets.UTF_8);
                }
            } catch (Exception e) {
                DomaineWeather.LOGGER.error("Domaine Weather : {} illisible", f, e);
            }
            reglages = lu != null ? lu : new Reglages();
            return reglages;
        }
    }

    public static boolean actif() {
        return reglages().actif;
    }

    // ---------------------------------------------------------------- la formule
    // longueur d'onde (blocs), direction (degrés, vers où va la vague), part de l'amplitude, phase
    private static final double[][] VAGUES = {
            {44, 70, 0.55, 0.0}, {27, 55, 0.25, 1.7}, {17, 95, 0.13, 4.1}, {9, 30, 0.07, 2.6}};
    private static final double[] KX = new double[4], KZ = new double[4], W = new double[4];

    static {
        for (int i = 0; i < 4; i++) {
            double k = 2 * Math.PI / VAGUES[i][0];
            double d = Math.toRadians(VAGUES[i][1]);
            KX[i] = k * Math.sin(d);
            KZ[i] = -k * Math.cos(d);
            // eau profonde : ω = √(g k), g réduit pour une houle lisible (vague de 44 blocs : ~7 s)
            W[i] = Math.sqrt(5.6 * k);
        }
    }

    /** Hauteur de la houle (blocs, autour de 0) au point (x, z) au temps t (secondes), pour une amplitude donnée. */
    public static double hauteur(double x, double z, double t, double amplitude) {
        double h = 0;
        for (int i = 0; i < 4; i++) h += VAGUES[i][2] * Math.sin(KX[i] * x + KZ[i] * z - W[i] * t + VAGUES[i][3]);
        return h * amplitude;
    }

    /** Pente de la houle (dh/dx, dh/dz). */
    public static double[] pente(double x, double z, double t, double amplitude) {
        double hx = 0, hz = 0;
        for (int i = 0; i < 4; i++) {
            double c = VAGUES[i][2] * Math.cos(KX[i] * x + KZ[i] * z - W[i] * t + VAGUES[i][3]);
            hx += c * KX[i];
            hz += c * KZ[i];
        }
        return new double[]{hx * amplitude, hz * amplitude};
    }

    /** Temps de la houle (secondes) : le même sur le serveur et le client. */
    public static double temps(Level level, float partiel) {
        return (level.getGameTime() + partiel) / 20.0;
    }

    // ---------------------------------------------------------------- calme près des côtes

    private static final ConcurrentHashMap<Long, Byte> PROFONDEURS = new ConcurrentHashMap<>();

    /** Nombre de blocs d'eau sous la surface de la mer (0 si pas de mer ici), au plus 24. */
    public static int profondeur(Level level, int x, int z) {
        long cle = ((long) x << 32) ^ (z & 0xFFFFFFFFL);
        Byte p = PROFONDEURS.get(cle);
        if (p != null) return p;
        int haut = level.getSeaLevel() - 1;
        int n = 0;
        if (level.isLoaded(new BlockPos(x, haut, z)) && level.getBlockState(new BlockPos(x, haut + 1, z)).isAir()) {
            while (n < 24 && level.getFluidState(new BlockPos(x, haut - n, z)).is(FluidTags.WATER)) n++;
        } else {
            return 0;                                         // pas encore chargé : ne pas mémoriser
        }
        if (PROFONDEURS.size() > 300_000) PROFONDEURS.clear();
        PROFONDEURS.put(cle, (byte) n);
        return n;
    }

    /** Amplitude de la houle ici : nulle sur moins de 4 blocs d'eau, pleine à partir de 16. */
    public static double amplitude(Level level, double x, double z) {
        if (!actif()) return 0;
        int p = profondeur(level, (int) Math.floor(x), (int) Math.floor(z));
        double f = Math.max(0, Math.min(1, (p - 4) / 12.0));
        return reglages().amplitude * f * f * (3 - 2 * f);
    }

    /** À appeler quand un chunk change (bloc posé) : on oublie tout, c'est un prototype. */
    public static void oublier() {
        PROFONDEURS.clear();
    }
}

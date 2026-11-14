package fr.domaineaubin.meteo.vagues;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import fr.domaineaubin.meteo.DomaineWeather;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Holder;
import net.minecraft.resources.ResourceKey;
import net.minecraft.tags.BiomeTags;
import net.minecraft.tags.FluidTags;
import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.Level;
import net.minecraftforge.fml.loading.FMLPaths;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.fml.DistExecutor;

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

    private static Path fichier() {
        return FMLPaths.CONFIGDIR.get().resolve("domaine_weather_vagues.json");
    }

    /** Change les réglages en jeu (/vagues) et les écrit dans le fichier de config. */
    public static synchronized void regler(Double amplitude, Boolean actif, Integer rayon) {
        Reglages r = reglages();
        boolean avant = r.actif;
        if (amplitude != null) r.amplitude = amplitude;
        if (actif != null) r.actif = actif;
        if (rayon != null) r.rayon = rayon;
        try {
            Files.createDirectories(fichier().getParent());
            Files.writeString(fichier(), new GsonBuilder().setPrettyPrinting().create().toJson(r), StandardCharsets.UTF_8);
        } catch (Exception e) {
            DomaineWeather.LOGGER.error("Domaine Weather : impossible d'ecrire {}", fichier(), e);
        }
        PROFONDEURS.clear();
        if (avant != r.actif) DistExecutor.unsafeRunWhenOn(Dist.CLIENT, () -> MasqueEau::rafraichir);
    }

    public static Reglages reglages() {
        Reglages r = reglages;
        if (r != null) return r;
        synchronized (Houle.class) {
            if (reglages != null) return reglages;
            Path f = fichier();
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

    /**
     * Hauteur de la surface au-dessus de l'eau plate du jeu (blocs, de 0 à 2 × amplitude) : les creux touchent l'eau
     * du jeu, rien ne passe jamais dessous (sinon la barque « coule » dans l'eau plate restée dessinée).
     */
    public static double levee(double x, double z, double t, double amplitude) {
        return amplitude + hauteur(x, z, t, amplitude);
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

    // 0.3.3 : une mémoire pour le client et une pour le serveur (en solo, les deux tournent dans le même programme et
    // ne voient pas forcément le monde au même instant), seulement pour le monde normal (avant : une seule mémoire pour
    // tout, qu'une autre dimension ou un instant douteux pouvait remplir de « pas de mer » : trous en lignes).
    private static final ConcurrentHashMap<Long, Byte> PROFONDEURS = new ConcurrentHashMap<>();
    private static final ConcurrentHashMap<Long, Byte> PROFONDEURS_CLIENT = new ConcurrentHashMap<>();

    /** Biome de mer : ceux du mod Terre (domaine_terre:mer/...), sinon les océans du jeu. Fleuves et lacs : non. */
    public static boolean mer(Level level, int x, int y, int z) {
        Holder<Biome> b = level.getBiome(new BlockPos(x, y, z));
        String chemin = b.unwrapKey().map(ResourceKey::location).map(Object::toString).orElse("");
        if (chemin.startsWith("domaine_terre:")) return chemin.startsWith("domaine_terre:mer/");
        return b.is(BiomeTags.IS_OCEAN);
    }

    /** Nombre de blocs d'eau sous la surface de la mer (0 si pas de mer ici, fleuve ou lac compris), au plus 24. */
    public static int profondeur(Level level, int x, int z) {
        if (level.dimension() != Level.OVERWORLD) return 0;
        ConcurrentHashMap<Long, Byte> memoire = level.isClientSide ? PROFONDEURS_CLIENT : PROFONDEURS;
        long cle = ((long) x << 32) ^ (z & 0xFFFFFFFFL);
        Byte p = memoire.get(cle);
        if (p != null) return p;
        int haut = level.getSeaLevel() - 1;
        if (!level.isLoaded(new BlockPos(x, haut, z))) return 0;          // pas encore chargé : ne pas mémoriser
        boolean mer = mer(level, x, haut, z);
        int n = 0;
        if (mer && level.getBlockState(new BlockPos(x, haut + 1, z)).isAir())
            while (n < 24 && level.getFluidState(new BlockPos(x, haut - n, z)).is(FluidTags.WATER)) n++;
        // on ne retient que ce qui est sûr : une vraie mer, ou un biome qui n'est pas de la mer ; un « biome de mer
        // sans eau » (bloc posé, chunk en cours d'arrivée…) est recalculé la fois suivante
        if (n == 0 && mer) return 0;
        if (memoire.size() > 300_000) memoire.clear();
        memoire.put(cle, (byte) n);
        return n;
    }

    /** Amplitude de la houle ici : nulle sur moins de 4 blocs d'eau, pleine à partir de 16. */
    public static double amplitude(Level level, double x, double z) {
        if (!actif()) return 0;
        return amplitudeSelonProfondeur(level, profondeur(level, (int) Math.floor(x), (int) Math.floor(z)));
    }

    /** Amplitude pour une profondeur déjà connue (dessin : une seule lecture par case). */
    public static double amplitudeSelonProfondeur(Level level, int p) {
        double f = Math.max(0, Math.min(1, (p - 4) / 12.0));
        return reglages().amplitude * f * f * (3 - 2 * f);
    }

    /** Haut de l'eau plate du jeu dans un bloc d'eau source (8/9 de bloc), au niveau de la mer. */
    public static double eauPlate(Level level) {
        return level.getSeaLevel() - 1 + 8.0 / 9.0;
    }

    /**
     * Surface de la houle (y) au-dessus du point (x, z) si une entité entre minY et maxY peut s'y trouver, sinon NaN.
     * Tri rapide par la hauteur avant toute lecture du monde (appelé pour chaque entité à chaque tick).
     */
    public static double surface(Level level, double x, double z, double minY, double maxY) {
        if (!actif()) return Double.NaN;
        double plate = eauPlate(level);
        double amp = reglages().amplitude;
        if (minY > plate + 2 * amp || maxY < plate - 0.5) return Double.NaN;
        double a = amplitude(level, x, z);
        if (a <= 0.02) return Double.NaN;
        return plate + levee(x, z, temps(level, 0), a);
    }

    /** Vitesse verticale de la surface de la houle (blocs par tick) au point (x, z). */
    public static double vitesse(Level level, double x, double z) {
        double a = amplitude(level, x, z);
        if (a <= 0.02) return 0;
        double t = temps(level, 0);
        return levee(x, z, t + 0.05, a) - levee(x, z, t, a);
    }

    /** Colonne de mer au sens des vagues (biome de mer, eau au niveau de la mer, air au-dessus). */
    public static boolean colonneDeMer(Level level, int x, int z) {
        return actif() && profondeur(level, x, z) > 0;
    }

    /** À appeler quand un chunk change (bloc posé) : on oublie tout, c'est un prototype. */
    public static void oublier() {
        PROFONDEURS.clear();
        PROFONDEURS_CLIENT.clear();
    }
}

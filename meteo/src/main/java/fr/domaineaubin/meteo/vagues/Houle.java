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
                + "amplitude : multiplicateur de la hauteur des vagues (1 = la regle : vraie houle de la region, mois par "
                + "mois ; hors monde Terre : hauteur fixe en blocs) ; rayon : distance de dessin (blocs).";
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
    // 0.4.0 (vagues par région) : trois états de la mer, chacun avec ses longueurs d'onde fixes ; leur mélange suit
    // l'amplitude, pour que les grosses mers aient de longues houles et les mers calmes un clapot court (cambrure
    // constante). Les longueurs ne changent jamais d'un endroit à l'autre : la surface reste continue partout.
    // longueur d'onde (blocs), direction (degrés, vers où va la vague), part de l'amplitude dans son état, phase
    private static final double[][] VAGUES = {
            // état 0 : clapot (mer calme)
            {12, 75, 0.50, 0.9}, {8, 50, 0.30, 3.3}, {5.5, 100, 0.20, 5.1},
            // état 1 : houle moyenne (celle du prototype, 0.2.1 à 0.3.x)
            {44, 70, 0.55, 0.0}, {27, 55, 0.25, 1.7}, {17, 95, 0.13, 4.1}, {9, 30, 0.07, 2.6},
            // état 2 : grosse houle (mers fortes, tempêtes)
            {110, 65, 0.55, 2.2}, {75, 80, 0.30, 0.4}, {52, 50, 0.15, 3.8}};
    private static final int[] ETAT = {0, 0, 0, 1, 1, 1, 1, 2, 2, 2};
    private static final int N = VAGUES.length;
    private static final double[] KX = new double[N], KZ = new double[N], W = new double[N];

    static {
        for (int i = 0; i < N; i++) {
            double k = 2 * Math.PI / VAGUES[i][0];
            double d = Math.toRadians(VAGUES[i][1]);
            KX[i] = k * Math.sin(d);
            KZ[i] = -k * Math.cos(d);
            // eau profonde : ω = √(g k), g réduit pour une houle lisible (vague de 44 blocs : ~7 s, de 110 : ~11 s)
            W[i] = Math.sqrt(5.6 * k);
        }
    }

    private static double lisse(double a, double b, double v) {
        double f = Math.max(0, Math.min(1, (v - a) / (b - a)));
        return f * f * (3 - 2 * f);
    }

    /** Parts des trois états selon l'amplitude (blocs) : clapot sous ~0,6, grosse houle au-delà de ~1,6. */
    private static double[] etats(double amplitude) {
        double clapot = 1 - lisse(0.25, 0.9, amplitude);
        double grosse = lisse(1.0, 2.2, amplitude);
        double moyenne = Math.max(0, 1 - clapot - grosse);
        double s = clapot + moyenne + grosse;
        return new double[]{clapot / s, moyenne / s, grosse / s};
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
        double[] e = etats(amplitude);
        double h = 0;
        for (int i = 0; i < N; i++) {
            double p = e[ETAT[i]] * VAGUES[i][2];
            if (p > 1e-4) h += p * Math.sin(KX[i] * x + KZ[i] * z - W[i] * t + VAGUES[i][3]);
        }
        return h * amplitude;
    }

    /** Pente de la houle (dh/dx, dh/dz). */
    public static double[] pente(double x, double z, double t, double amplitude) {
        double[] e = etats(amplitude);
        double hx = 0, hz = 0;
        for (int i = 0; i < N; i++) {
            double p = e[ETAT[i]] * VAGUES[i][2];
            if (p <= 1e-4) continue;
            double c = p * Math.cos(KX[i] * x + KZ[i] * z - W[i] * t + VAGUES[i][3]);
            hx += c * KX[i];
            hz += c * KZ[i];
        }
        return new double[]{hx * amplitude, hz * amplitude};
    }

    // ---------------------------------------------------------------- climat des vagues (0.4.0)
    /**
     * Vagues par région (méthode validée par Maxime le 15/11/2026) : hauteur significative réelle (Hs, ERA5 1991-2020,
     * Copernicus / ECMWF) par mois, moyenne et « tempête » (90e centile), sur une grille de 0,5° (houle.bin, fait par
     * outils/vagues/houle_climat.py). Une seule règle partout : amplitude (blocs) = Hs (m) × BLOCS_PAR_METRE ×
     * réglage « amplitude » (1 par défaut), plafonnée ; du creux à la crête : 2 × amplitude.
     */
    public static final double BLOCS_PAR_METRE = 0.375;
    public static final double AMPLITUDE_MAX = 4.0;
    private static final int LIGNES = 360, COLONNES = 720;
    private static volatile byte[] climat;
    private static volatile boolean climatAbsent;

    private static byte[] climat() {
        byte[] c = climat;
        if (c != null || climatAbsent) return c;
        synchronized (Houle.class) {
            if (climat != null || climatAbsent) return climat;
            try (java.io.InputStream in = Houle.class.getResourceAsStream("/domaine_weather/houle.bin")) {
                byte[] b = in == null ? null : in.readAllBytes();
                if (b == null || b.length != 24 * LIGNES * COLONNES) throw new java.io.IOException("houle.bin absent ou incomplet");
                climat = b;
            } catch (Exception e) {
                climatAbsent = true;
                DomaineWeather.LOGGER.error("Domaine Weather : climat des vagues illisible, amplitude fixe", e);
            }
            return climat;
        }
    }

    /** Hs (m) d'une couche (0-11 : moyenne de janvier à décembre, 12-23 : tempête) au point lat/lon (bilinéaire). */
    public static double hsCouche(int couche, double lat, double lon) {
        byte[] c = climat();
        if (c == null) return 1.0 / BLOCS_PAR_METRE;
        double fy = (89.75 - lat) / 0.5, fx = (lon + 179.75) / 0.5;
        int y0 = (int) Math.floor(fy), x0 = (int) Math.floor(fx);
        double ty = fy - y0, tx = fx - x0;
        int ya = Math.max(0, Math.min(LIGNES - 1, y0)), yb = Math.max(0, Math.min(LIGNES - 1, y0 + 1));
        int xa = Math.floorMod(x0, COLONNES), xb = Math.floorMod(x0 + 1, COLONNES);
        int base = couche * LIGNES * COLONNES;
        double v = (c[base + ya * COLONNES + xa] & 255) * (1 - tx) * (1 - ty) + (c[base + ya * COLONNES + xb] & 255) * tx * (1 - ty)
                + (c[base + yb * COLONNES + xa] & 255) * (1 - tx) * ty + (c[base + yb * COLONNES + xb] & 255) * tx * ty;
        return v * 0.05;
    }

    /** Mois en cours (0 = janvier ... 11,99), lu sur le calendrier de Serene Seasons (début du printemps = 1er mars). */
    public static double mois(Level level) {
        long t = level.getGameTime();
        double[] c = level.isClientSide ? MOIS_CLIENT : MOIS_SERVEUR;   // lu une fois par tick (dessin : des milliers d'appels)
        synchronized (c) {
            if (c[0] == t) return c[1];
            double m;
            try {
                m = (2.0 + fr.domaineaubin.meteo.Saisons.fractionAnnee(level) * 12.0) % 12.0;
            } catch (Throwable e) {
                m = 0;
            }
            c[0] = t;
            c[1] = m;
            return m;
        }
    }

    private static final double[] MOIS_CLIENT = {Double.NaN, 0}, MOIS_SERVEUR = {Double.NaN, 0};

    /** Hs moyenne et de tempête (m) ici, ce mois-ci (interpolées entre les deux mois les plus proches). */
    public static double[] hsMois(Level level, double lat, double lon) {
        double m = mois(level) - 0.5;                      // valeurs au milieu de chaque mois
        int m0 = (int) Math.floor(m);
        double f = m - m0;
        int a = Math.floorMod(m0, 12), b = Math.floorMod(m0 + 1, 12);
        double moy = hsCouche(a, lat, lon) * (1 - f) + hsCouche(b, lat, lon) * f;
        double tem = hsCouche(12 + a, lat, lon) * (1 - f) + hsCouche(12 + b, lat, lon) * f;
        return new double[]{moy, Math.max(moy, tem)};
    }

    /**
     * Variation lente propre à chaque région, de -1 (calme) à 1 (tempête du mois) : deux cycles de quelques jours de
     * jeu, décalés d'une région à l'autre (même valeur sur le serveur et le client : temps du monde).
     */
    public static double variation(Level level, double lat, double lon) {
        double jours = level.getGameTime() / 24000.0;
        double p1 = lon / 23.0 + lat / 17.0, p2 = lon / 11.0 - lat / 13.0;
        return 0.6 * Math.sin(2 * Math.PI * jours / 5.3 + p1) + 0.4 * Math.sin(2 * Math.PI * jours / 2.1 + p2);
    }

    /** Hs (m) du moment ici : moyenne du mois, plus ou moins vers la tempête du mois selon la variation. */
    public static double hs(Level level, double x, double z) {
        double lat = fr.domaineaubin.terre.monde.Terrain.lat(z), lon = fr.domaineaubin.terre.monde.Terrain.lon(x);
        lon = ((lon + 180.0) % 360.0 + 360.0) % 360.0 - 180.0;
        double[] h = hsMois(level, lat, lon);
        double v = variation(level, lat, lon);
        return Math.max(0.35 * h[0], h[0] + (h[1] - h[0]) * v);
    }

    /** Amplitude au large ici (blocs), avant le calme des côtes. Hors monde Terre : réglage fixe (prototype). */
    public static double amplitudeRegion(Level level, double x, double z) {
        if (!actif()) return 0;
        if (!fr.domaineaubin.meteo.Saisons.terre(level) || climat() == null) return reglages().amplitude;
        return Math.min(AMPLITUDE_MAX, hs(level, x, z) * BLOCS_PAR_METRE * reglages().amplitude);
    }

    /** Plus grande amplitude possible (tri rapide des entités, avant toute lecture du monde). */
    public static double amplitudeMax() {
        return Math.max(AMPLITUDE_MAX, reglages().amplitude);
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
        Holder<Biome> b = level.getNoiseBiome(x >> 2, y >> 2, z >> 2);   // 0.3.5 : sans le mélange des biomes (plus rapide)
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
        if (level.getChunkSource().getChunk(x >> 4, z >> 4, false) == null) return 0;   // pas encore chargé : ne pas mémoriser
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

    /** Même calcul que {@link #profondeur} sans la mémoire (diagnostic des trous). */
    public static int profondeurDirecte(Level level, int x, int z) {
        int haut = level.getSeaLevel() - 1;
        if (!mer(level, x, haut, z) || !level.getBlockState(new BlockPos(x, haut + 1, z)).isAir()) return 0;
        int n = 0;
        while (n < 24 && level.getFluidState(new BlockPos(x, haut - n, z)).is(FluidTags.WATER)) n++;
        return n;
    }

    /** Valeur gardée en mémoire pour cette colonne (-1 : rien), pour le diagnostic. */
    public static int profondeurGardee(Level level, int x, int z) {
        Byte p = (level.isClientSide ? PROFONDEURS_CLIENT : PROFONDEURS).get(((long) x << 32) ^ (z & 0xFFFFFFFFL));
        return p == null ? -1 : p;
    }

    /** Corrige la valeur gardée pour une colonne. */
    public static void retenir(Level level, int x, int z, int n) {
        (level.isClientSide ? PROFONDEURS_CLIENT : PROFONDEURS).put(((long) x << 32) ^ (z & 0xFFFFFFFFL), (byte) n);
    }

    /** Amplitude de la houle ici : celle de la région, nulle sur moins de 4 blocs d'eau, pleine à partir de 16. */
    public static double amplitude(Level level, double x, double z) {
        if (!actif()) return 0;
        int p = profondeur(level, (int) Math.floor(x), (int) Math.floor(z));
        if (p <= 0) return 0;
        return amplitudeRegion(level, x, z) * calmeCote(p);
    }

    /** Amplitude pour une profondeur déjà connue (dessin : une seule lecture par case). */
    public static double amplitudeSelonProfondeur(Level level, double x, double z, int p) {
        return p <= 0 ? 0 : amplitudeRegion(level, x, z) * calmeCote(p);
    }

    /** Part de l'amplitude selon la profondeur : nulle sur moins de 4 blocs d'eau, pleine à partir de 16. */
    public static double calmeCote(int p) {
        double f = Math.max(0, Math.min(1, (p - 4) / 12.0));
        return f * f * (3 - 2 * f);
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
        double amp = amplitudeMax();
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

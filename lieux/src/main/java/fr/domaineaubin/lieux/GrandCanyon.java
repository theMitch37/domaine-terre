package fr.domaineaubin.lieux;

import fr.domaineaubin.terre.api.Lieu;
import fr.domaineaubin.terre.monde.Terrain;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.util.Mth;
import net.minecraft.util.RandomSource;
import net.minecraft.world.level.levelgen.synth.ImprovedNoise;

/**
 * Grand Canyon (Arizona) : canyon en terrasses creusé le long du Colorado, de Lees Ferry au lac Mead.
 * Le plateau est relevé autour du canyon, le fond descend sous le niveau de la mer : le Colorado
 * y coule tout seul (aquifère), comme les autres fleuves du mod Terre.
 * Réglé pour l'échelle 1:250 (référence du modpack). La hauteur du monde ne change pas avec l'échelle :
 * la largeur ne suit donc l'échelle qu'en partie (racine), pour garder la même allure encaissée partout.
 */
public final class GrandCanyon implements Lieu {
    public static final GrandCanyon INSTANCE = new GrandCanyon();

    /** Emprise géographique : Colorado entre Lees Ferry (est) et Grand Wash Cliffs (ouest). */
    private static final double LON_OUEST = -114.15, LON_EST = -111.45, LAT_SUD = 35.55, LAT_NORD = 37.05;
    /** Début de Marble Canyon (profondeur nulle) et fin du canyon côté lac Mead. */
    private static final double LON_LEES_FERRY = -111.50, LON_LAC_MEAD = -114.10;
    /** Fond du lit (y) : l'eau monte d'elle-même jusqu'à y 62. */
    public static final double FOND = 56.0;

    private final ImprovedNoise bruit;
    private final ImprovedNoise bruitButtes;

    private GrandCanyon() {
        RandomSource r = RandomSource.create(36_1066_112L);
        bruit = new ImprovedNoise(r);
        bruitButtes = new ImprovedNoise(r);
    }

    @Override
    public String id() {
        return "grand_canyon";
    }

    @Override
    public ResourceLocation biome() {
        return new ResourceLocation(DomaineLieux.MOD_ID, "grand_canyon");
    }

    // ---------------------------------------------------------------- géométrie

    /** Échelle de référence : tous les réglages sont faits pour elle. */
    public static final int ECHELLE_REFERENCE = 250;

    /**
     * Demi-largeur du canyon (blocs) : ~90 en 1:250, ~75 en 1:500, ~63 en 1:1000.
     * Elle grandit un peu avec l'échelle, sans la suivre complètement (la profondeur, elle, est fixe).
     */
    public static double demiLargeur() {
        return 75.0 * Math.pow(500.0 / Terrain.echelle(), 0.26);
    }

    private static boolean dansEmprise(int x, int z) {
        double lon = Terrain.lon(x), lat = Terrain.lat(z);
        return lon > LON_OUEST && lon < LON_EST && lat > LAT_SUD && lat < LAT_NORD;
    }

    /** Hauteur du rebord (y) : plateau de Kaibab à l'est (~2 300 m), plus bas vers le lac Mead. */
    private double rebord(int x, int z) {
        double t = Mth.clamp((Terrain.lon(x) - LON_LAC_MEAD) / (LON_LEES_FERRY - LON_LAC_MEAD), 0.0, 1.0);
        return Mth.lerp(t, 130.0, 150.0) + bruit.noise(x / 90.0, 3.0, z / 90.0) * 2.0;
    }

    /** Intensité 0..1 : le canyon naît à Lees Ferry, se creuse dans Marble Canyon, s'ouvre sur le lac Mead. */
    private static double intensite(int x) {
        double lon = Terrain.lon(x);
        double est = Mth.clamp((LON_LEES_FERRY - lon) / 0.45, 0.0, 1.0);
        double ouest = Mth.clamp((lon - LON_LAC_MEAD) / 0.12, 0.0, 1.0);
        return lisse(Math.min(est, ouest));
    }

    /** Distance au Colorado, déformée par du bruit (falaises découpées, canyons latéraux), en blocs ; -1 hors canyon. */
    private double distance(int x, int z) {
        double[] ce = Terrain.get().coursEau(x, z);
        if (ce == null) return -1;
        double d = ce[0];
        double w = demiLargeur();
        if (d > w * 2.0) return -1;
        if (d < 6.0) return d;  // le lit du fleuve reste net
        double n = bruit.noise(x / (w * 0.9), 0.0, z / (w * 0.9)) * w * 0.35
                + bruit.noise(x / 23.0, 1.0, z / 23.0) * w * 0.07;
        return Math.max(6.0, d + n);
    }

    /** Fraction de la profondeur (0 = fond, 1 = rebord) selon la distance relative t = d / demi-largeur. */
    private double profil(int x, int z, double t) {
        double f;
        if (t < 0.05) f = 0.0;                                                   // lit du Colorado
        else if (t < 0.13) f = 0.26 * lisse((t - 0.05) / 0.08);                  // gorge intérieure (schiste), raide
        else if (t < 0.22) f = 0.26 + 0.05 * ((t - 0.13) / 0.09);                // plateau de Tonto, étroit
        else if (t < 1.0) {                                                       // 5 gradins : falaise puis replat
            double s = (t - 0.22) / 0.156;
            int k = Math.min(4, (int) s);
            double u = s - k;
            f = 0.31 + 0.138 * (k + lisse(Math.min(1.0, u / 0.4)));
        } else f = 1.0;
        // buttes et « temples » isolés au milieu du canyon (Vishnu, Zoroaster…)
        if (t > 0.24 && t < 0.95) {
            double w = demiLargeur();
            double b = bruitButtes.noise(x / (w * 0.45), 7.0, z / (w * 0.45));
            if (b > 0.30) f = Math.max(f, 0.31 + 0.60 * lisse(Mth.clamp((b - 0.30) / 0.10, 0.0, 1.0)));
        }
        return f;
    }

    // ---------------------------------------------------------------- Lieu

    @Override
    public boolean concerne(int x, int z) {
        return dansEmprise(x, z) && distance(x, z) >= 0;
    }

    @Override
    public double hauteur(int x, int z, double h) {
        double d = distance(x, z);
        if (d < 0) return h;
        double e = intensite(x);
        if (e <= 0) return h;
        double w = demiLargeur();
        double rebord = rebord(x, z);
        double cible;
        if (d <= w) {
            cible = FOND + profil(x, z, d / w) * (rebord - FOND);
        } else {
            // autour du canyon : rejoint le relief réel en douceur, sur une bande courte
            double v = lisse(Mth.clamp((d - w) / (w * 0.45), 0.0, 1.0));
            cible = Mth.lerp(v, rebord, h);
        }
        return Mth.lerp(e, h, cible);
    }

    @Override
    public boolean dansBiome(int x, int z) {
        if (!dansEmprise(x, z)) return false;
        double d = distance(x, z);
        // couvre toute la zone retouchée (rebord et raccord compris) : pas de biome froid ni de neige sur les bords
        return d >= 0 && d <= demiLargeur() * 1.45 && intensite(x) > 0.02;
    }

    /** Pour les strates : la colonne est-elle dans le canyon, et quel est son rebord ? NaN sinon. */
    public double rebordSiCanyon(int x, int z) {
        if (!dansEmprise(x, z)) return Double.NaN;
        double d = distance(x, z);
        if (d < 0 || d > demiLargeur() * 1.03 || intensite(x) <= 0.02) return Double.NaN;
        return rebord(x, z);
    }

    private static double lisse(double t) {
        return t * t * (3 - 2 * t);
    }
}

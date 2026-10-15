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
 * Largeur exagérée (×3) pour rester grandiose ; hauteur identique à toutes les échelles.
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

    /** Demi-largeur du canyon (blocs) : 8 km réels ×3, au moins 60 blocs. */
    public static double demiLargeur() {
        double blocsParKm = Terrain.BLOCS_PAR_DEGRE / 111.32;
        return Math.max(8.0 * blocsParKm * 3.0, 60.0);
    }

    private static boolean dansEmprise(int x, int z) {
        double lon = Terrain.lon(x), lat = Terrain.lat(z);
        return lon > LON_OUEST && lon < LON_EST && lat > LAT_SUD && lat < LAT_NORD;
    }

    /** Hauteur du rebord (y) : plateau de Kaibab à l'est (~2 300 m), plus bas vers le lac Mead. */
    private double rebord(int x, int z) {
        double t = Mth.clamp((Terrain.lon(x) - LON_LAC_MEAD) / (LON_LEES_FERRY - LON_LAC_MEAD), 0.0, 1.0);
        return Mth.lerp(t, 124.0, 142.0) + bruit.noise(x / 90.0, 3.0, z / 90.0) * 2.0;
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
        if (d > w * 2.2) return -1;
        if (d < 6.0) return d;  // le lit du fleuve reste net
        double n = bruit.noise(x / (w * 0.9), 0.0, z / (w * 0.9)) * w * 0.35
                + bruit.noise(x / 23.0, 1.0, z / 23.0) * w * 0.07;
        return Math.max(6.0, d + n);
    }

    /** Fraction de la profondeur (0 = fond, 1 = rebord) selon la distance relative t = d / demi-largeur. */
    private double profil(int x, int z, double t) {
        double f;
        if (t < 0.06) f = 0.0;                                                   // lit du Colorado
        else if (t < 0.16) f = 0.32 * lisse((t - 0.06) / 0.10);                  // gorge intérieure (schiste)
        else if (t < 0.40) f = 0.32 + 0.08 * ((t - 0.16) / 0.24);                // plateau de Tonto
        else if (t < 1.0) {                                                       // 4 gradins jusqu'au rebord
            double s = (t - 0.40) / 0.15;
            int k = Math.min(3, (int) s);
            double u = s - k;
            f = 0.40 + 0.15 * (k + lisse(Math.min(1.0, u / 0.35)));
        } else f = 1.0;
        // buttes et « temples » isolés au milieu du canyon (Vishnu, Zoroaster…)
        if (t > 0.28 && t < 0.97) {
            double w = demiLargeur();
            double b = bruitButtes.noise(x / (w * 0.45), 7.0, z / (w * 0.45));
            if (b > 0.30) f = Math.max(f, 0.40 + 0.50 * lisse(Mth.clamp((b - 0.30) / 0.10, 0.0, 1.0)));
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
            // plateau autour du canyon : remonte au niveau du rebord puis rejoint le relief réel
            double v = lisse(Mth.clamp((d - w) / (w * 1.2), 0.0, 1.0));
            cible = Mth.lerp(v, rebord, h);
        }
        return Mth.lerp(e, h, cible);
    }

    @Override
    public boolean dansBiome(int x, int z) {
        if (!dansEmprise(x, z)) return false;
        double d = distance(x, z);
        // un peu plus large que le canyon : le rebord est couvert, pas de bande d'un autre biome (ni de neige) sur les parois
        return d >= 0 && d <= demiLargeur() * 1.08 && intensite(x) > 0.02;
    }

    /** Pour les strates : la colonne est-elle dans le canyon, et quel est son rebord ? NaN sinon. */
    public double rebordSiCanyon(int x, int z) {
        if (!dansEmprise(x, z)) return Double.NaN;
        double d = distance(x, z);
        if (d < 0 || d > demiLargeur() * 1.02 || intensite(x) <= 0.02) return Double.NaN;
        return rebord(x, z);
    }

    private static double lisse(double t) {
        return t * t * (3 - 2 * t);
    }
}

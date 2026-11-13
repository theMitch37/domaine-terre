package fr.domaineaubin.meteo;

/**
 * Vents dominants selon la latitude (Domaine Weather 0.2, 13/11/2026).
 *
 * Angles de Weather2 : direction vers laquelle souffle le vent, vecteur (−sin a, cos a) en (x, z) ; z croît vers le
 * sud. Donc a = 0 : vers le sud ; 90 : vers l'ouest ; ±180 : vers le nord ; −90 : vers l'est.
 * - alizés (0-30°) : de nord-est au nord (vers le sud-ouest, a = 45), de sud-est au sud (vers le nord-ouest, 135) ;
 * - vents d'ouest (35-60°) : de sud-ouest au nord (vers le nord-est, −135), de nord-ouest au sud (vers le sud-est, −45) ;
 * - vents d'est polaires (au-delà de 68°) : comme les alizés.
 * Passages progressifs entre 25 et 35° et entre 60 et 68°. Le vent garde ses écarts au hasard autour de cette direction.
 */
public final class Vents {
    private Vents() {
    }

    /** Écart toléré autour de la direction dominante (degrés) avant d'être ramené plus fermement. */
    public static final double ECART = 40;

    /** Direction dominante (angle Weather2) à cette latitude. */
    public static double dominante(double lat) {
        double a = Math.abs(lat);
        // Les deux vents d'un passage soufflent en sens opposés : on tourne par l'ouest et le pôle (au nord : nord-est
        // → nord → nord-ouest → ouest → sud-ouest, comme les vents du nord de l'Égypte ; au sud : sud-est → sud →
        // sud-ouest → ouest → nord-ouest), jamais par le milieu des deux.
        if (lat >= 0) {
            if (a < 25) return 45;                                   // alizé de nord-est
            if (a < 35) return 45 - 180 * (a - 25) / 10;             // vers le vent de sud-ouest
            if (a < 60) return -135;                                 // vents d'ouest (de sud-ouest)
            if (a < 68) return -135 + 180 * (a - 60) / 8;            // vers le vent de nord-est polaire
            return 45;
        }
        if (a < 25) return 135;                                      // alizé de sud-est
        if (a < 35) return normaliser(135 + 180 * (a - 25) / 10);   // vers le vent de nord-ouest
        if (a < 60) return -45;                                      // vents d'ouest (de nord-ouest)
        if (a < 68) return normaliser(315 - 180 * (a - 60) / 8);    // vers le vent de sud-est polaire
        return 135;
    }

    /** Vitesse minimale et maximale du vent (échelle Weather2 0..1) : pot au noir calme, quarantièmes rugissants. */
    public static double[] bornesVitesse(double lat) {
        double a = Math.abs(lat);
        if (a < 5) return new double[]{0, 0.25};                          // pot au noir (zone de convergence)
        if (lat < -38 && lat > -62) return new double[]{0.55, 1.0};        // quarantièmes rugissants, cinquantièmes hurlants
        if (a >= 35 && a <= 60) return new double[]{0.15, 1.0};            // vents d'ouest soutenus
        return new double[]{0, 1.0};
    }

    static double ecart(double d) {
        return d - 360.0 * Math.floor((d + 180.0) / 360.0);
    }

    static double normaliser(double a) {
        return ecart(a);
    }

    /** Nouvel angle : ramené doucement vers la direction dominante, plus fermement s'il s'en écarte trop. */
    public static float tirer(float angle, double lat) {
        double d = ecart(dominante(lat) - angle);
        double k = Math.abs(d) > ECART ? 0.004 : 0.0007;
        return (float) normaliser(angle + d * k);
    }
}

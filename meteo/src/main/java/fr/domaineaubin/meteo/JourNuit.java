package fr.domaineaubin.meteo;

import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.player.Player;

/**
 * Durée du jour et de la nuit selon la saison et la latitude (Domaine Weather 0.1, 13/11/2026).
 *
 * Une journée de Minecraft garde ses 24 000 ticks et ses 20 minutes, mais le jour (ticks 0 à 12 000, soleil
 * au-dessus de l'horizon) et la nuit (12 000 à 24 000) ne défilent plus à la même vitesse : en été à Oslo le soleil
 * reste ~15 minutes sur 20, en hiver ~5. Durée du jour réelle (formule astronomique : déclinaison du Soleil et angle
 * horaire du coucher), adoucie au-delà du cercle polaire (décision de Maxime : toujours un peu de jour et de nuit).
 *
 * Le temps de Minecraft est le même pour tout le monde : il suit le joueur (pensé pour le solo ; à plusieurs, le
 * premier joueur du monde). Les saisons de Serene Seasons avancent avec les ticks de la journée : inchangées.
 */
public final class JourNuit {
    private JourNuit() {
    }

    /** Part du jour au plus (et 1 − part de la nuit au plus) : ~4 h de nuit en plein été polaire, ~4 h de jour en hiver. */
    static final double PART_MIN = 1.0 / 6.0, PART_MAX = 5.0 / 6.0;
    /** Jour de l'année du début du printemps de Serene Seasons (1er mars). */
    static final double DEBUT_PRINTEMPS = 59.0;

    /**
     * Part de la journée (0..1) pendant laquelle le soleil est levé, à cette latitude, à ce moment de l'année
     * (0 = début du printemps au nord). Adoucie aux pôles.
     */
    public static double partDuJour(double latitude, double fractionAnnee) {
        double jour = DEBUT_PRINTEMPS + fractionAnnee * 365.0;
        double decl = Math.toRadians(23.44) * Math.sin(2 * Math.PI * (jour - 80.0) / 365.0);
        double phi = Math.toRadians(Math.max(-89.0, Math.min(89.0, latitude)));
        double c = -Math.tan(phi) * Math.tan(decl);
        double brut = c <= -1 ? 1.0 : c >= 1 ? 0.0 : Math.acos(c) / Math.PI;
        // adoucissement : courbe douce vers les bornes plutôt qu'un plafond net
        double m = (PART_MIN + PART_MAX) / 2, a = (PART_MAX - PART_MIN) / 2;
        return m + a * Math.tanh((brut - 0.5) / a);
    }

    /** Vitesse du temps (ticks de journée par tick réel) à ce moment de la journée. */
    public static double vitesse(long dayTime, double partDuJour) {
        long t = Math.floorMod(dayTime, 24000L);
        return t < 12000 ? 0.5 / partDuJour : 0.5 / (1.0 - partDuJour);
    }

    private static double resteServeur = 0;

    /** Prochaine heure du monde côté serveur (remplace « heure + 1 »). */
    public static long suivanteServeur(ServerLevel level, long proposee) {
        if (!Saisons.terre(level) || level.players().isEmpty()) return proposee;
        Player p = level.players().get(0);
        double part = partDuJour(Saisons.latitude(p.getZ()), Saisons.fractionAnnee(level));
        long avant = proposee - 1;
        resteServeur += vitesse(avant, part);
        long n = (long) Math.floor(resteServeur);
        resteServeur -= n;
        return avant + n;
    }

    // ---------------------------------------------------------------- client : prévision entre deux paquets

    private static long derniereHeure = Long.MIN_VALUE, dernierTemps;
    private static double partClient = 0.5, resteClient = 0;

    /**
     * Paquet d'heure reçu du serveur (toutes les secondes) : la vitesse observée depuis le précédent donne la part du
     * jour en cours (jour : vitesse = 0,5 / part ; nuit : 0,5 / (1 − part)). Le client en déduit lui-même la vitesse
     * de chaque instant, sans à-coups au lever et au coucher du soleil.
     */
    public static void heureRecue(long gameTime, long dayTime) {
        long jour = Math.abs(dayTime);
        if (derniereHeure != Long.MIN_VALUE && gameTime > dernierTemps) {
            double v = (jour - derniereHeure) / (double) (gameTime - dernierTemps);
            boolean memePhase = (Math.floorMod(derniereHeure, 24000L) < 12000) == (Math.floorMod(jour, 24000L) < 12000);
            if (memePhase && v > 0.3 && v < 8) {             // sinon : changement de phase, sommeil, /time…
                double p = Math.floorMod(jour, 24000L) < 12000 ? 0.5 / v : 1.0 - 0.5 / v;
                partClient = Math.max(PART_MIN * 0.9, Math.min(PART_MAX * 1.1, p));
            }
        }
        derniereHeure = jour;
        dernierTemps = gameTime;
    }

    /** Prochaine heure du monde côté client (remplace « heure + 1 ») ; le serveur la recale chaque seconde. */
    public static long suivanteClient(long proposee) {
        if (!Saisons.terreClient) return proposee;
        long avant = proposee - 1;
        resteClient += vitesse(avant, partClient);
        long n = (long) Math.floor(resteClient);
        resteClient -= n;
        return avant + n;
    }

    public static void reinitialiserClient() {
        derniereHeure = Long.MIN_VALUE;
        partClient = 0.5;
        resteClient = 0;
    }
}

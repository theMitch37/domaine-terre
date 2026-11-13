package fr.domaineaubin.meteo;

import fr.domaineaubin.terre.monde.Terrain;
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

    // ---------------------------------------------------------------- serveur

    private static double resteServeur = 0;
    /** Heure solaire locale (0.2) : décalage déjà appliqué (ticks) ; NaN = pas encore calé. */
    private static double decalageApplique = Double.NaN;
    /** Retard à rattraper (ticks) après un pas vers l'ouest : l'horloge ralentit au lieu de reculer. */
    private static double retard = 0;
    /** Au-delà, un recul vers l'ouest (téléportation) saute plutôt au même moment du lendemain. */
    static final double RECUL_MAX = 2000;
    /** Vitesse de l'horloge pendant qu'on rattrape un retard. */
    static final double FREIN = 0.5;

    /** Décalage de l'heure solaire locale (ticks) à la longitude du bloc x : 1 000 ticks par 15°. */
    public static double decalageLocal(double x) {
        return Terrain.lon(x) / 360.0 * 24000.0;
    }

    /** Écart ramené entre −12 000 et 12 000 ticks (la couture du Pacifique ne fait pas sauter un jour). */
    static double ecartCirculaire(double d) {
        return d - 24000.0 * Math.floor((d + 12000.0) / 24000.0);
    }

    private static double partServeur = 0.5, facteurServeur = 1.0;

    /**
     * Prochaine heure du monde côté serveur (remplace « heure + 1 »).
     *
     * Heure solaire locale (décision de Maxime, 13/11) : l'heure suit la longitude du joueur. Vers l'est, l'horloge
     * avance d'autant ; vers l'ouest, elle ne recule jamais (Serene Seasons compte les saisons avec l'horloge, et
     * d'autres mods n'aiment pas le temps qui recule) : un petit pas ralentit l'horloge le temps de rattraper, une
     * téléportation saute au même moment du lendemain.
     */
    public static long suivanteServeur(ServerLevel level, long proposee) {
        if (!Saisons.terre(level) || level.players().isEmpty()) return proposee;
        Player p = level.players().get(0);
        long avant = proposee - 1;
        double saut = 0;
        double cible = decalageLocal(p.getX());
        if (Double.isNaN(decalageApplique)) {
            decalageApplique = cible;                               // calé sur l'heure du monde au premier tick
        } else {
            double d = ecartCirculaire(cible - decalageApplique);
            if (d > 0) saut += d;
            else if (d > -RECUL_MAX) retard += -d;
            else saut += 24000.0 + d;
            decalageApplique = cible;
        }
        double part = partDuJour(Saisons.latitude(p.getZ()), Saisons.fractionAnnee(level));
        double v = vitesse(avant, part);
        double facteur = 1.0;
        if (retard > 0) {
            double frein = Math.min(retard, v * (1 - FREIN));
            retard -= frein;
            facteur = (v - frein) / v;
        }
        resteServeur += v * facteur + saut;
        long n = (long) Math.floor(resteServeur);
        resteServeur -= n;
        partServeur = part;
        facteurServeur = facteur;
        if (level.getGameTime() % 20 == 0) {
            for (var j : level.players()) Reseau.horloge(j, part, facteur);
        }
        return avant + n;
    }

    /** Remet l'heure locale à zéro (nouveau monde, nouveau serveur). */
    public static void reinitialiserServeur() {
        decalageApplique = Double.NaN;
        retard = 0;
        resteServeur = 0;
    }

    // ---------------------------------------------------------------- client

    private static double partClient = 0.5, facteurClient = 1.0, resteClient = 0;
    private static boolean horlogeRecue = false;

    /** Paquet du serveur (chaque seconde) : part du jour et vitesse de l'horloge en ce moment. */
    public static void horlogeRecue(double part, double facteur) {
        partClient = part;
        facteurClient = facteur;
        horlogeRecue = true;
    }

    /** Ancien moyen (0.1) : laissé sans effet, le serveur envoie maintenant la part du jour. */
    public static void heureRecue(long gameTime, long dayTime) {
    }

    /** Prochaine heure du monde côté client (remplace « heure + 1 ») ; le serveur la recale chaque seconde. */
    public static long suivanteClient(long proposee) {
        if (!Saisons.terreClient || !horlogeRecue) return proposee;
        long avant = proposee - 1;
        resteClient += vitesse(avant, partClient) * facteurClient;
        long n = (long) Math.floor(resteClient);
        resteClient -= n;
        return avant + n;
    }

    public static void reinitialiserClient() {
        partClient = 0.5;
        facteurClient = 1.0;
        horlogeRecue = false;
        resteClient = 0;
    }
}

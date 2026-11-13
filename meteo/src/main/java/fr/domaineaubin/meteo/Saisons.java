package fr.domaineaubin.meteo;

import fr.domaineaubin.terre.monde.Terrain;
import fr.domaineaubin.terre.monde.TerroirBiomeSource;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.Level;
import sereneseasons.api.season.SeasonHelper;
import sereneseasons.season.SeasonTime;

/**
 * Saisons par hémisphère (Domaine Weather 0.1, 13/11/2026).
 *
 * Serene Seasons tient une seule saison pour tout le monde. Au sud de l'équateur, on la décale d'une demi-année :
 * l'hiver de l'Australie tombe pendant l'été de l'Europe, et la saison des pluies des tropiques du sud pendant la
 * saison sèche de ceux du nord. Seulement dans un monde Terre (ailleurs, rien ne change).
 */
public final class Saisons {
    private Saisons() {
    }

    /** Monde Terre côté client : annoncé par le serveur à la connexion (voir {@link Reseau}). */
    public static volatile boolean terreClient = false;

    /** Vrai si ce niveau est le monde réel d'un monde Terre. */
    public static boolean terre(Level level) {
        if (level == null || level.dimension() != Level.OVERWORLD) return false;
        if (level instanceof ServerLevel s)
            return s.getChunkSource().getGenerator().getBiomeSource() instanceof TerroirBiomeSource;
        return terreClient;
    }

    /** Latitude (degrés) du bloc z. */
    public static double latitude(double z) {
        return Terrain.lat(z);
    }

    /** Vrai au sud de l'équateur. */
    public static boolean sud(double z) {
        return latitude(z) < 0;
    }

    /** Ticks du cycle des saisons tels qu'on les vit au bloc z (décalés d'une demi-année au sud). */
    public static int ticksLocaux(int ticks, double z) {
        if (!sud(z)) return ticks;
        int cycle = SeasonTime.ZERO.getCycleDuration();
        return Math.floorMod(ticks + cycle / 2, cycle);
    }

    /** Ticks du cycle au bloc z dans ce niveau (inchangés hors monde Terre). */
    public static int ticksLocaux(Level level, int ticks, double z) {
        return terre(level) ? ticksLocaux(ticks, z) : ticks;
    }

    /** Saison au bloc z dans ce niveau. */
    public static SeasonTime locale(Level level, double z) {
        int t = SeasonHelper.getSeasonState(level).getSeasonCycleTicks();
        return new SeasonTime(ticksLocaux(level, t, z));
    }

    /** Position dans l'année au nord (0 = début du printemps, 1 = fin de l'hiver). */
    public static double fractionAnnee(Level level) {
        int cycle = SeasonTime.ZERO.getCycleDuration();
        return Math.floorMod(SeasonHelper.getSeasonState(level).getSeasonCycleTicks(), cycle) / (double) cycle;
    }
}

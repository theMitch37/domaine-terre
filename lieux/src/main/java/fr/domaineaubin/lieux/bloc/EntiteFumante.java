package fr.domaineaubin.lieux.bloc;

import net.minecraft.core.BlockPos;
import net.minecraft.core.particles.ParticleTypes;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.sounds.SoundSource;
import net.minecraft.util.RandomSource;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;

/**
 * Effets d'une fumerolle (fumée continue) ou d'un geyser, comme Strokkur : le geyser bouillonne, la vasque se bombe,
 * puis jaillit environ toutes les 45 s (colonne d'eau et de vapeur de 18 à 30 blocs, parfois une seconde poussée),
 * et laisse un panache de vapeur qui dérive.
 * 12/11/2026 (demande de Maxime : « plus impressionnant », et l'eau d'une source chaude doit brûler) : jet bien plus
 * haut et plus dense, grondement, panache ; côté serveur, le jet brûle et projette en l'air, la vasque échaude.
 */
public class EntiteFumante extends BlockEntity {
    /** Période d'une éruption (ticks), durée du jet, durée du bouillonnement avant, durée du panache après. */
    private static final int PERIODE = 900, JET = 70, BOUILLON = 100, PANACHE = 120;

    public EntiteFumante(BlockPos pos, BlockState etat) {
        super(BlocsLieux.ENTITE_FUMANTE.get(), pos, etat);
    }

    /** Instant dans le cycle (même valeur côté client et serveur). */
    private static long instant(Level niveau, BlockPos pos) {
        return Math.floorMod(niveau.getGameTime() + pos.asLong() * 31L, PERIODE);
    }

    /** Hauteur du jet de cette éruption (18 à 30 blocs), tirée du numéro du cycle. */
    private static double hauteur(Level niveau, BlockPos pos) {
        long cycle = Math.floorDiv(niveau.getGameTime() + pos.asLong() * 31L, PERIODE);
        long h = cycle * 0x9E3779B97F4A7C15L ^ pos.asLong();
        h ^= h >>> 29;
        return 18.0 + Math.floorMod(h, 13);
    }

    /** Une seconde poussée, une éruption sur trois (Strokkur jaillit parfois deux ou trois fois de suite). */
    private static boolean double_(Level niveau, BlockPos pos) {
        return Math.floorMod((long) hauteur(niveau, pos) * 7 + pos.getX(), 3) == 0;
    }

    /** Force du jet à l'instant t (0 à 1) : montée brusque, retombée, seconde poussée éventuelle. */
    private static double force(Level niveau, BlockPos pos, long t) {
        if (t >= JET) return 0.0;
        double f = t < 6 ? t / 6.0 : 1.0 - (t - 6.0) / (JET - 6.0);
        if (double_(niveau, pos) && t >= 34 && t < 50) f = Math.max(f, 0.75 * (1.0 - Math.abs(t - 40) / 10.0));
        return Math.max(0.0, f);
    }

    private static int surface(Level niveau, BlockPos pos) {
        int ys = pos.getY() + 1;
        while (ys < pos.getY() + 6 && !niveau.getFluidState(new BlockPos(pos.getX(), ys, pos.getZ())).isEmpty()) ys++;
        return ys;
    }

    public static void tickServeur(Level niveau, BlockPos pos, BlockState etat, EntiteFumante e) {
        long t = instant(niveau, pos);
        double f = force(niveau, pos, t);
        double x = pos.getX() + 0.5, z = pos.getZ() + 0.5;
        int ys = surface(niveau, pos);
        if (f > 0.05 && t % 5 == 0) {
            // dans le jet : eau bouillante et vapeur, on brûle et on est projeté
            double h = hauteur(niveau, pos) * f;
            AABB jet = new AABB(x - 1.3, ys - 1, z - 1.3, x + 1.3, ys + h, z + 1.3);
            for (LivingEntity v : niveau.getEntitiesOfClass(LivingEntity.class, jet)) {
                v.hurt(niveau.damageSources().hotFloor(), 3.0f);
                Vec3 m = v.getDeltaMovement();
                v.setDeltaMovement(m.x + (v.getX() - x) * 0.15, Math.max(m.y, 0.9 * f), m.z + (v.getZ() - z) * 0.15);
                v.hurtMarked = true;
            }
        }
        if (t % 20 == 0) {
            // la vasque : source chaude, l'eau échaude (moins que le jet)
            AABB vasque = new AABB(x - 3, ys - 4, z - 3, x + 3, ys + 0.5, z + 3);
            for (LivingEntity v : niveau.getEntitiesOfClass(LivingEntity.class, vasque)) {
                if (v.isInWater()) v.hurt(niveau.damageSources().hotFloor(), 1.0f);
            }
        }
    }

    public static void tickClient(Level niveau, BlockPos pos, BlockState etat, EntiteFumante e) {
        RandomSource r = niveau.random;
        double x = pos.getX() + 0.5, z = pos.getZ() + 0.5;
        if (!(etat.getBlock() instanceof BlocFumant b) || !b.geyser) {
            // fumerolle : fumée blanche qui monte lentement, odeur de soufre en plus (pas de son)
            if (r.nextInt(3) == 0) {
                niveau.addAlwaysVisibleParticle(ParticleTypes.CAMPFIRE_COSY_SMOKE, true,
                        x + (r.nextDouble() - 0.5) * 0.6, pos.getY() + 1.0, z + (r.nextDouble() - 0.5) * 0.6,
                        0.0, 0.03 + r.nextDouble() * 0.03, 0.0);
            }
            return;
        }
        int ys = surface(niveau, pos);
        long t = instant(niveau, pos);
        double hMax = hauteur(niveau, pos);
        double f = force(niveau, pos, t);
        if (t < JET) {
            if (t == 0) {
                // détonation sourde puis grondement de l'eau
                niveau.playLocalSound(x, ys, z, SoundEvents.GENERIC_EXPLODE, SoundSource.AMBIENT, 2.0f, 0.55f, false);
                niveau.playLocalSound(x, ys, z, SoundEvents.BUBBLE_COLUMN_UPWARDS_AMBIENT, SoundSource.AMBIENT, 3.0f, 0.6f, false);
                // la bulle qui crève : anneau d'éclaboussures
                for (int k = 0; k < 40; k++) {
                    double a = k * Math.PI / 20;
                    niveau.addParticle(ParticleTypes.SPLASH, x + Math.cos(a) * 1.5, ys + 0.2, z + Math.sin(a) * 1.5,
                            Math.cos(a) * 0.3, 0.4, Math.sin(a) * 0.3);
                }
            }
            if (t == 40 && double_(niveau, pos)) {
                niveau.playLocalSound(x, ys, z, SoundEvents.GENERIC_EXPLODE, SoundSource.AMBIENT, 1.4f, 0.7f, false);
            }
            if (t % 8 == 0) niveau.playLocalSound(x, ys, z, SoundEvents.GENERIC_SPLASH, SoundSource.AMBIENT, 2.0f,
                    0.6f + r.nextFloat() * 0.2f, false);
            if (f <= 0.02) return;
            double h = hMax * f;
            // colonne : vapeur blanche qui file vers le haut (amortie à 0,96 par tick : ~25 × la vitesse en blocs)
            int n = (int) (10 + 26 * f);
            for (int k = 0; k < n; k++) {
                double ec = 0.35 + 0.5 * r.nextDouble();
                niveau.addAlwaysVisibleParticle(ParticleTypes.CLOUD, true, x + (r.nextDouble() - 0.5) * ec, ys,
                        z + (r.nextDouble() - 0.5) * ec, (r.nextDouble() - 0.5) * 0.06,
                        h / 25.0 * (0.6 + 0.4 * r.nextDouble()), (r.nextDouble() - 0.5) * 0.06);
            }
            // l'eau : gouttes le long de toute la colonne, qui retombent en pluie autour
            for (int k = 0; k < (int) (12 + 20 * f); k++) {
                double hy = r.nextDouble() * h;
                double ec = 0.6 + hy / hMax * 2.5;
                niveau.addAlwaysVisibleParticle(ParticleTypes.SPLASH, true, x + (r.nextDouble() - 0.5) * ec, ys + hy,
                        z + (r.nextDouble() - 0.5) * ec, 0, 0, 0);
            }
            for (int k = 0; k < 6; k++) {
                double a = r.nextDouble() * Math.PI * 2, d = 1.0 + r.nextDouble() * (1.5 + hMax * 0.12);
                niveau.addAlwaysVisibleParticle(ParticleTypes.FALLING_WATER, true, x + Math.cos(a) * d,
                        ys + h * (0.5 + 0.5 * r.nextDouble()), z + Math.sin(a) * d, 0, 0, 0);
            }
            // gros flocons de vapeur au sommet
            if (r.nextInt(2) == 0) niveau.addAlwaysVisibleParticle(ParticleTypes.CAMPFIRE_COSY_SMOKE, true,
                    x + (r.nextDouble() - 0.5) * 2, ys + h * 0.9, z + (r.nextDouble() - 0.5) * 2,
                    (r.nextDouble() - 0.5) * 0.05, 0.05, (r.nextDouble() - 0.5) * 0.05);
        } else if (t < JET + PANACHE) {
            // panache de vapeur qui monte et dérive avec le vent, de plus en plus léger
            double reste = 1.0 - (double) (t - JET) / PANACHE;
            if (r.nextDouble() < 0.9 * reste) {
                niveau.addAlwaysVisibleParticle(ParticleTypes.CAMPFIRE_SIGNAL_SMOKE, true,
                        x + (r.nextDouble() - 0.5) * 2.5, ys + r.nextDouble() * hMax * 0.4,
                        z + (r.nextDouble() - 0.5) * 2.5, 0.03, 0.04 + 0.04 * reste, 0.01);
            }
            if (r.nextInt(3) == 0) niveau.addParticle(ParticleTypes.BUBBLE_POP, x + (r.nextDouble() - 0.5) * 3, ys,
                    z + (r.nextDouble() - 0.5) * 3, 0, 0.02, 0);
        } else if (t > PERIODE - BOUILLON) {
            // la vasque se bombe : bouillons de plus en plus forts, vapeur, grondement
            double monte = 1.0 - (double) (PERIODE - t) / BOUILLON;
            for (int k = 0; k < 2 + (int) (8 * monte); k++) {
                niveau.addParticle(ParticleTypes.BUBBLE_POP, x + (r.nextDouble() - 0.5) * 3, ys,
                        z + (r.nextDouble() - 0.5) * 3, 0, 0.05 + 0.1 * monte, 0);
            }
            if (r.nextDouble() < monte) niveau.addParticle(ParticleTypes.SPLASH, x + (r.nextDouble() - 0.5) * 1.5, ys + 0.1,
                    z + (r.nextDouble() - 0.5) * 1.5, 0, 0.2 * monte, 0);
            if (r.nextInt(3) == 0) niveau.addAlwaysVisibleParticle(ParticleTypes.CLOUD, true, x, ys, z, 0, 0.1 + 0.2 * monte, 0);
            if (t % 20 == 0) niveau.playLocalSound(x, ys, z, SoundEvents.BUBBLE_COLUMN_UPWARDS_AMBIENT, SoundSource.AMBIENT,
                    0.6f + monte, 0.7f, false);
            // juste avant le jet, la bulle bleue : l'eau se soulève en dôme
            if (PERIODE - t < 12) {
                for (int k = 0; k < 10; k++) {
                    double a = r.nextDouble() * Math.PI * 2, d = r.nextDouble() * 1.2;
                    niveau.addParticle(ParticleTypes.BUBBLE, x + Math.cos(a) * d, ys + 0.3 + (1.2 - d) * 0.8,
                            z + Math.sin(a) * d, 0, 0.05, 0);
                }
            }
        } else if (r.nextInt(4) == 0) {
            // vapeur au repos
            niveau.addAlwaysVisibleParticle(ParticleTypes.CAMPFIRE_COSY_SMOKE, true, x + (r.nextDouble() - 0.5) * 3,
                    ys, z + (r.nextDouble() - 0.5) * 3, 0, 0.02, 0);
        }
    }
}

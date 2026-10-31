package fr.domaineaubin.lieux.bloc;

import net.minecraft.core.BlockPos;
import net.minecraft.core.particles.ParticleTypes;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.sounds.SoundSource;
import net.minecraft.util.RandomSource;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.state.BlockState;

/**
 * Effets d'une fumerolle (fumée continue) ou d'un geyser : le geyser bouillonne, puis jaillit environ toutes les 45 s
 * (jet de vapeur et d'eau d'une quinzaine de blocs pendant ~3 s), comme Strokkur. Rien n'est simulé côté serveur.
 */
public class EntiteFumante extends BlockEntity {
    /** Période d'une éruption (ticks), durée du jet, durée du bouillonnement avant. */
    private static final int PERIODE = 900, JET = 60, BOUILLON = 80;

    public EntiteFumante(BlockPos pos, BlockState etat) {
        super(BlocsLieux.ENTITE_FUMANTE.get(), pos, etat);
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
        // geyser : la surface de l'eau est au-dessus du bloc ; on part du haut de la colonne d'eau
        int ys = pos.getY() + 1;
        while (ys < pos.getY() + 6 && !niveau.getFluidState(new BlockPos(pos.getX(), ys, pos.getZ())).isEmpty()) ys++;
        long t = Math.floorMod(niveau.getGameTime() + pos.asLong() * 31L, PERIODE);
        if (t < JET) {
            if (t == 0) niveau.playLocalSound(x, ys, z, SoundEvents.GENERIC_EXPLODE, SoundSource.AMBIENT, 0.6f,
                    1.6f + r.nextFloat() * 0.2f, false);
            double force = 1.0 - (double) t / JET;
            for (int k = 0; k < 14; k++) {
                niveau.addAlwaysVisibleParticle(ParticleTypes.CLOUD, true, x + (r.nextDouble() - 0.5) * 0.8, ys,
                        z + (r.nextDouble() - 0.5) * 0.8, (r.nextDouble() - 0.5) * 0.08,
                        0.6 + 0.9 * force * r.nextDouble(), (r.nextDouble() - 0.5) * 0.08);
            }
            for (int k = 0; k < 8; k++) {
                niveau.addParticle(ParticleTypes.SPLASH, x + (r.nextDouble() - 0.5) * 1.2, ys + r.nextDouble() * 8 * force,
                        z + (r.nextDouble() - 0.5) * 1.2, 0, 0, 0);
            }
            if (t % 10 == 0) niveau.playLocalSound(x, ys, z, SoundEvents.GENERIC_SPLASH, SoundSource.AMBIENT, 1.0f,
                    0.8f, false);
        } else if (t > PERIODE - BOUILLON) {
            // la vasque se bombe : bulles et vapeur
            for (int k = 0; k < 3; k++) {
                niveau.addParticle(ParticleTypes.BUBBLE_POP, x + (r.nextDouble() - 0.5) * 2.5, ys,
                        z + (r.nextDouble() - 0.5) * 2.5, 0, 0.05, 0);
            }
            if (r.nextInt(4) == 0) niveau.addParticle(ParticleTypes.CLOUD, x, ys, z, 0, 0.08, 0);
        } else if (r.nextInt(6) == 0) {
            // vapeur au repos
            niveau.addAlwaysVisibleParticle(ParticleTypes.CAMPFIRE_COSY_SMOKE, true, x + (r.nextDouble() - 0.5) * 2,
                    ys, z + (r.nextDouble() - 0.5) * 2, 0, 0.02, 0);
        }
    }
}

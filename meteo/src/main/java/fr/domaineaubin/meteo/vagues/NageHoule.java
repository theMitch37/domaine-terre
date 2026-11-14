package fr.domaineaubin.meteo.vagues;

import net.minecraft.core.BlockPos;
import net.minecraft.tags.FluidTags;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.event.TickEvent;

/**
 * Prototype des vagues (0.2.3) : le joueur qui nage en surface, en pleine mer, monte et descend avec la houle
 * (même levée que la surface dessinée et la barque). Appliqué par le client du joueur (c'est lui qui pilote ses
 * mouvements). Plongé (tête à plus de 1,5 bloc sous l'eau plate), il n'est plus porté.
 * Limite : sur une crête, le joueur est au-dessus de l'eau plate du jeu : le jeu le croit hors de l'eau (nage rapide
 * coupée le temps de la crête) ; on annule sa chute pour qu'il ne prenne pas de dégâts.
 */
public final class NageHoule {
    private NageHoule() {
    }

    public static void tick(TickEvent.PlayerTickEvent e) {
        if (e.phase != TickEvent.Phase.END || !Houle.actif()) return;
        Player p = e.player;
        if (!p.isLocalPlayer() || p.isPassenger() || p.isSpectator() || p.getAbilities().flying) return;
        Level l = p.level();
        if (l.dimension() != Level.OVERWORLD) return;
        int haut = l.getSeaLevel() - 1;
        double amp = Houle.reglages().amplitude;
        // près de la surface : pieds entre 1,5 bloc sous l'eau plate et la crête la plus haute possible
        if (p.getY() < haut - 1.5 || p.getY() > haut + 1 + 2 * amp + 0.5) return;
        if (!l.getFluidState(BlockPos.containing(p.getX(), haut, p.getZ())).is(FluidTags.WATER)) return;
        if (p.getEyeY() < haut + 1 - 1.5 && p.isUnderWater()) return;          // il plonge : laissé tranquille
        if (p.onGround()) return;                                             // pied posé (haut-fond, berge)
        double a = Houle.amplitude(l, p.getX(), p.getZ());
        if (a <= 0.02) return;
        // tête hors de l'eau : pieds ~0,6 sous la surface de la houle
        double cible = haut + 0.9 + Houle.levee(p.getX(), p.getZ(), Houle.temps(l, 0), a) - 0.6;
        Vec3 v = p.getDeltaMovement();
        if (p.isShiftKeyDown() && v.y < 0) return;                            // il veut descendre
        double dy = (cible - p.getY()) * 0.25;
        double vy = Math.max(-0.3, Math.min(0.3, v.y + (dy - v.y) * 0.5));    // vitesse verticale tirée vers la houle
        p.setDeltaMovement(v.x, vy, v.z);
        p.fallDistance = 0;
    }
}

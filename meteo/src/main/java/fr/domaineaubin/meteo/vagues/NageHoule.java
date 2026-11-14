package fr.domaineaubin.meteo.vagues;

import net.minecraft.world.entity.player.Player;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.event.TickEvent;

/**
 * La houle porte le nageur (0.3.0) : depuis l'eau virtuelle, le joueur nage normalement dans la vague ; on lui ajoute
 * seulement le mouvement vertical de l'eau autour de lui quand il est près de la surface (la vague le soulève puis le
 * redescend). Accroupi ou en plongée profonde : rien.
 */
public final class NageHoule {
    private NageHoule() {
    }

    public static void tick(TickEvent.PlayerTickEvent e) {
        if (e.phase != TickEvent.Phase.START || !Houle.actif()) return;
        Player p = e.player;
        if (!p.isLocalPlayer() || p.isPassenger() || p.isSpectator() || p.getAbilities().flying || !p.isInWater()) return;
        if (p.isShiftKeyDown()) return;
        Level l = p.level();
        if (l.dimension() != Level.OVERWORLD) return;
        double s = Houle.surface(l, p.getX(), p.getZ(), p.getY(), p.getEyeY());
        if (Double.isNaN(s) || Math.abs(p.getEyeY() - s) > 1.5) return;   // loin de la surface : pas porté
        Vec3 v = p.getDeltaMovement();
        p.setDeltaMovement(v.x, v.y + Houle.vitesse(l, p.getX(), p.getZ()) * 0.8, v.z);
    }
}

package fr.domaineaubin.meteo.mixin;

import fr.domaineaubin.meteo.vagues.Houle;
import net.minecraft.core.BlockPos;
import net.minecraft.tags.FluidTags;
import net.minecraft.world.entity.vehicle.Boat;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.Vec3;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/**
 * Prototype des vagues : en pleine mer, la barque monte et descend avec la houle (la même formule que la surface
 * dessinée). Appliqué par celui qui pilote la barque (le client du joueur à bord, sinon le serveur).
 */
@Mixin(Boat.class)
public abstract class BarqueMixin {
    @Inject(method = "tick", at = @At("TAIL"))
    private void domaineWeather$houle(CallbackInfo ci) {
        Boat b = (Boat) (Object) this;
        if (!Houle.actif() || !b.isControlledByLocalInstance()) return;
        Level l = b.level();
        if (l.dimension() != Level.OVERWORLD) return;
        int haut = l.getSeaLevel() - 1;
        if (Math.abs(b.getY() - (haut + 1)) > 3) return;
        if (!l.getFluidState(BlockPos.containing(b.getX(), haut, b.getZ())).is(FluidTags.WATER)) return;
        double a = Houle.amplitude(l, b.getX(), b.getZ());
        if (a <= 0.02) return;
        double cible = haut + 0.9 + Houle.hauteur(b.getX(), b.getZ(), Houle.temps(l, 0), a) - 0.15;
        double y = b.getY() + (cible - b.getY()) * 0.35;
        b.setPos(b.getX(), y, b.getZ());
        Vec3 v = b.getDeltaMovement();
        b.setDeltaMovement(v.x, 0, v.z);
    }
}

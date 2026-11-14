package fr.domaineaubin.meteo.mixin;

import fr.domaineaubin.meteo.vagues.Houle;
import net.minecraft.client.Camera;
import net.minecraft.client.Minecraft;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.material.FogType;
import net.minecraft.world.phys.Vec3;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/**
 * Vue sous-marine dans la vague (0.3.1) : caméra entre l'eau plate et la surface de la houle = sous l'eau (brouillard
 * bleu, son étouffé), comme dans la vraie eau. Sans ça, on voyait le fond « à l'air libre ».
 */
@Mixin(Camera.class)
public abstract class CameraVagueMixin {
    @Shadow public abstract Vec3 getPosition();

    @Inject(method = "getFluidInCamera", at = @At("HEAD"), cancellable = true)
    private void domaineWeather$sousLaVague(CallbackInfoReturnable<FogType> cir) {
        ClientLevel l = Minecraft.getInstance().level;
        if (l == null || l.dimension() != Level.OVERWORLD) return;
        Vec3 p = getPosition();
        if (p.y < Houle.eauPlate(l) - 0.2) return;                         // dans la vraie eau : le jeu sait faire
        double s = Houle.surface(l, p.x, p.z, p.y, p.y);
        if (!Double.isNaN(s) && p.y < s) cir.setReturnValue(FogType.WATER);
    }
}

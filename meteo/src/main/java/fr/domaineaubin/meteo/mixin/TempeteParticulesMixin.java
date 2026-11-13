package fr.domaineaubin.meteo.mixin;

import fr.domaineaubin.meteo.Climat;
import fr.domaineaubin.meteo.Saisons;
import net.minecraft.core.BlockPos;
import net.minecraft.world.level.Level;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;
import weather2.weathersystem.storm.WeatherObjectParticleStorm;

/**
 * Weather2 : tempêtes de sable seulement dans les vrais déserts (BWh, BWk), tempêtes de neige seulement dans les
 * climats froids (D, E, et les C sans été). Vaut aussi pour les dépôts de sable et de neige qu'elles laissent.
 */
@Mixin(value = WeatherObjectParticleStorm.class, remap = false)
public abstract class TempeteParticulesMixin {
    @Inject(method = "canSpawnHere", at = @At("HEAD"), cancellable = true)
    private static void domaineWeather$climat(Level level, BlockPos pos, WeatherObjectParticleStorm.StormType type,
                                              boolean pourNaitre, CallbackInfoReturnable<Boolean> cir) {
        if (!Saisons.terre(level)) return;
        boolean possible = type == WeatherObjectParticleStorm.StormType.SANDSTORM
                ? Climat.sablePossible(pos.getX(), pos.getZ()) : Climat.neigePossible(pos.getX(), pos.getZ());
        if (!possible) cir.setReturnValue(false);
    }
}

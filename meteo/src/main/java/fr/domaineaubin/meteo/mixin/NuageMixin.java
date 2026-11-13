package fr.domaineaubin.meteo.mixin;

import fr.domaineaubin.meteo.Climat;
import fr.domaineaubin.meteo.Saisons;
import net.minecraft.world.level.Level;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
import weather2.weathersystem.storm.StormObject;

/**
 * Weather2, nuages et orages :
 * - un nuage ne pleut que si le climat et la saison locale le permettent (désert presque sec, été méditerranéen sec,
 *   hiver sec des moussons) ;
 * - un orage ne devient tornade que dans une zone à tornades (config/domaine_weather_zones.json) ; ailleurs il
 *   plafonne à la grêle.
 */
@Mixin(value = StormObject.class, remap = false)
public abstract class NuageMixin {
    @Inject(method = "setPrecipitating", at = @At("HEAD"), cancellable = true)
    private void domaineWeather$pluieSelonClimat(boolean pleut, CallbackInfo ci) {
        if (!pleut) return;
        StormObject s = (StormObject) (Object) this;
        Level level = s.manager == null ? null : s.manager.getWorld();
        if (level == null || level.isClientSide || !Saisons.terre(level)) return;
        if (!Climat.nuagePleut(level, s.ID, s.pos.x, s.pos.z)) {
            s.attrib_precipitation = false;
            ci.cancel();
        }
    }

    @Inject(method = "stageNext", at = @At("HEAD"), cancellable = true)
    private void domaineWeather$tornadesASaPlace(CallbackInfo ci) {
        StormObject s = (StormObject) (Object) this;
        if (s.stormType != StormObject.TYPE_LAND || s.levelCurIntensityStage + 1 < StormObject.STATE_FORMING) return;
        Level level = s.manager == null ? null : s.manager.getWorld();
        if (level == null || level.isClientSide || !Saisons.terre(level)) return;
        if (Climat.zoneTornade(s.pos.x, s.pos.z) == null) {
            s.hasStormPeaked = true;
            ci.cancel();
        }
    }
}

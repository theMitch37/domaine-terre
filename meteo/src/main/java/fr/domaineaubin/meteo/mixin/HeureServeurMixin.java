package fr.domaineaubin.meteo.mixin;

import fr.domaineaubin.meteo.JourNuit;
import net.minecraft.server.level.ServerLevel;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.ModifyArg;

/** Durée du jour et de la nuit selon la saison et la latitude, côté serveur (heure de référence). */
@Mixin(ServerLevel.class)
public abstract class HeureServeurMixin {
    @ModifyArg(method = "tickTime", at = @At(value = "INVOKE", target = "Lnet/minecraft/server/level/ServerLevel;setDayTime(J)V"))
    private long domaineWeather$heure(long proposee) {
        return JourNuit.suivanteServeur((ServerLevel) (Object) this, proposee);
    }
}

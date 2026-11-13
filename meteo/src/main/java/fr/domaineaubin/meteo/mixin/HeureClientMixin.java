package fr.domaineaubin.meteo.mixin;

import fr.domaineaubin.meteo.JourNuit;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.world.level.Level;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.ModifyArg;

/** Durée du jour et de la nuit, côté client : le soleil avance à la même vitesse que sur le serveur, sans à-coups. */
@Mixin(ClientLevel.class)
public abstract class HeureClientMixin {
    @ModifyArg(method = "tickTime", at = @At(value = "INVOKE", target = "Lnet/minecraft/client/multiplayer/ClientLevel;setDayTime(J)V"))
    private long domaineWeather$heure(long proposee) {
        if (((ClientLevel) (Object) this).dimension() != Level.OVERWORLD) return proposee;
        return JourNuit.suivanteClient(proposee);
    }
}

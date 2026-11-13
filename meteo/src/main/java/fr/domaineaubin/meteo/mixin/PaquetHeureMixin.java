package fr.domaineaubin.meteo.mixin;

import fr.domaineaubin.meteo.JourNuit;
import net.minecraft.client.multiplayer.ClientPacketListener;
import net.minecraft.network.protocol.game.ClientboundSetTimePacket;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** Chaque heure reçue du serveur sert au client à connaître la part du jour en cours. */
@Mixin(ClientPacketListener.class)
public abstract class PaquetHeureMixin {
    @Inject(method = "handleSetTime", at = @At("TAIL"))
    private void domaineWeather$heureRecue(ClientboundSetTimePacket paquet, CallbackInfo ci) {
        JourNuit.heureRecue(paquet.getGameTime(), paquet.getDayTime());
    }
}

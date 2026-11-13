package fr.domaineaubin.meteo.mixin;

import fr.domaineaubin.meteo.Saisons;
import fr.domaineaubin.meteo.Vents;
import net.minecraft.world.level.Level;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
import weather2.weathersystem.wind.WindManager;

/**
 * Weather2, vents dominants (0.2) : après le tirage au hasard du vent, sa direction est ramenée vers le vent dominant
 * de la latitude du joueur (alizés, vents d'ouest, vents d'est polaires) et sa force bornée (pot au noir calme,
 * quarantièmes rugissants). Les nuages et les tempêtes suivent ce vent.
 */
@Mixin(value = WindManager.class, remap = false)
public abstract class VentMixin {
    @Inject(method = "tick", at = @At("TAIL"))
    private void domaineWeather$ventDominant(CallbackInfo ci) {
        WindManager w = (WindManager) (Object) this;
        Level level = w.manager == null ? null : w.manager.getWorld();
        if (level == null || level.isClientSide || !Saisons.terre(level) || level.players().isEmpty()) return;
        double lat = Saisons.latitude(level.players().get(0).getZ());
        w.windAngleGlobal = Vents.tirer(w.windAngleGlobal, lat);
        double[] b = Vents.bornesVitesse(lat);
        w.windSpeedGlobal = (float) Math.max(b[0], Math.min(b[1], w.windSpeedGlobal));
    }
}

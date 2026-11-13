package fr.domaineaubin.meteo.mixin;

import fr.domaineaubin.meteo.Saisons;
import net.minecraft.core.BlockPos;
import net.minecraft.world.level.Level;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Redirect;
import sereneseasons.api.season.ISeasonState;
import sereneseasons.api.season.Season;
import sereneseasons.init.ModFertility;
import sereneseasons.season.SeasonTime;

/** Serene Seasons : les cultures poussent selon la saison locale (été austral en janvier). */
@Mixin(value = ModFertility.class, remap = false)
public abstract class FertiliteMixin {
    @Redirect(method = "isCropFertile",
            at = @At(value = "INVOKE", target = "Lsereneseasons/api/season/ISeasonState;getSeason()Lsereneseasons/api/season/Season;"))
    private static Season domaineWeather$saisonLocale(ISeasonState etat, String plante, Level level, BlockPos pos) {
        return new SeasonTime(Saisons.ticksLocaux(level, etat.getSeasonCycleTicks(), pos.getZ())).getSeason();
    }
}

package fr.domaineaubin.meteo.mixin;

import fr.domaineaubin.meteo.Saisons;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Holder;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.biome.Biome;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.Redirect;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;
import sereneseasons.api.season.ISeasonState;
import sereneseasons.api.season.Season;
import sereneseasons.season.SeasonHooks;
import sereneseasons.season.SeasonTime;

/**
 * Serene Seasons, saisons par hémisphère : température (neige, gel, tempêtes de neige de Weather2) et saison sèche
 * ou des pluies des tropiques suivent la saison locale.
 */
@Mixin(value = SeasonHooks.class, remap = false)
public abstract class SeasonHooksMixin {
    @Unique
    private static final ThreadLocal<BlockPos> domaineWeather$pos = new ThreadLocal<>();

    @Redirect(method = "getBiomeTemperature(Lnet/minecraft/world/level/Level;Lnet/minecraft/core/Holder;Lnet/minecraft/core/BlockPos;)F",
            at = @At(value = "INVOKE", target = "Lsereneseasons/api/season/ISeasonState;getSeasonCycleTicks()I"))
    private static int domaineWeather$temperatureLocale(ISeasonState etat, Level level, Holder<Biome> biome, BlockPos pos) {
        return Saisons.ticksLocaux(level, etat.getSeasonCycleTicks(), pos.getZ());
    }

    @Inject(method = "getPrecipitationAtSeasonal", at = @At("HEAD"))
    private static void domaineWeather$retenirPosition(Level level, Holder<Biome> biome, BlockPos pos,
                                                       CallbackInfoReturnable<Biome.Precipitation> cir) {
        domaineWeather$pos.set(pos);
    }

    @Inject(method = "getPrecipitationAtSeasonal", at = @At("RETURN"))
    private static void domaineWeather$oublierPosition(Level level, Holder<Biome> biome, BlockPos pos,
                                                       CallbackInfoReturnable<Biome.Precipitation> cir) {
        domaineWeather$pos.remove();
    }

    @Redirect(method = "hasPrecipitationSeasonal",
            at = @At(value = "INVOKE", target = "Lsereneseasons/api/season/ISeasonState;getTropicalSeason()Lsereneseasons/api/season/Season$TropicalSeason;"))
    private static Season.TropicalSeason domaineWeather$tropiquesLocaux(ISeasonState etat, Level level, Holder<Biome> biome) {
        BlockPos p = domaineWeather$pos.get();
        if (p == null) return etat.getTropicalSeason();
        return new SeasonTime(Saisons.ticksLocaux(level, etat.getSeasonCycleTicks(), p.getZ())).getTropicalSeason();
    }
}

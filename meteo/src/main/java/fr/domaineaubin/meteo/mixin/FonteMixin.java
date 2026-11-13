package fr.domaineaubin.meteo.mixin;

import fr.domaineaubin.meteo.Saisons;
import net.minecraft.server.level.ChunkMap;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.chunk.LevelChunk;
import net.minecraftforge.server.ServerLifecycleHooks;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Redirect;
import sereneseasons.api.season.Season;
import sereneseasons.config.SeasonsConfig;
import sereneseasons.init.ModConfig;
import sereneseasons.season.RandomUpdateHandler;

/**
 * Serene Seasons, fonte de la neige et de la glace selon la saison locale. Le tirage se fait pour tout le monde à
 * la fois : on prend la saison des deux hémisphères qui fond le plus, puis chaque chunk garde la chance de sa propre
 * saison (rapportée au nombre de tirages).
 */
@Mixin(value = RandomUpdateHandler.class, remap = false)
public abstract class FonteMixin {
    @Redirect(method = "onWorldTick",
            at = @At(value = "INVOKE", target = "Lsereneseasons/config/SeasonsConfig;getSeasonProperties(Lsereneseasons/api/season/Season$SubSeason;)Lsereneseasons/config/SeasonsConfig$SeasonProperties;"))
    private static SeasonsConfig.SeasonProperties domaineWeather$deuxHemispheres(SeasonsConfig cfg, Season.SubSeason nord) {
        SeasonsConfig.SeasonProperties n = cfg.getSeasonProperties(nord);
        var serveur = ServerLifecycleHooks.getCurrentServer();
        if (serveur == null || !Saisons.terre(serveur.overworld())) return n;
        Season.SubSeason[] v = Season.SubSeason.VALUES;
        SeasonsConfig.SeasonProperties s = cfg.getSeasonProperties(v[(nord.ordinal() + v.length / 2) % v.length]);
        return s.meltRolls() * s.meltChance() > n.meltRolls() * n.meltChance() ? s : n;
    }

    @Redirect(method = "onWorldTick",
            at = @At(value = "INVOKE", target = "Lsereneseasons/season/RandomUpdateHandler;meltInChunk(Lnet/minecraft/server/level/ChunkMap;Lnet/minecraft/world/level/chunk/LevelChunk;F)V"))
    private static void domaineWeather$fonteLocale(ChunkMap map, LevelChunk chunk, float chance) {
        Level level = chunk.getLevel();
        if (Saisons.terre(level)) {
            Season.SubSeason nord = Saisons.locale(level, 0).getSubSeason();
            Season.SubSeason ici = Saisons.locale(level, chunk.getPos().getMiddleBlockZ()).getSubSeason();
            Season.SubSeason[] v = Season.SubSeason.VALUES;
            var a = ModConfig.seasons.getSeasonProperties(nord);
            var b = ModConfig.seasons.getSeasonProperties(v[(nord.ordinal() + v.length / 2) % v.length]);
            var l = ModConfig.seasons.getSeasonProperties(ici);
            int rolls = Math.max(1, Math.max(a.meltRolls(), b.meltRolls()));
            chance = l.meltChance() / 100.0F * l.meltRolls() / rolls;
            if (chance <= 0) return;
        }
        RandomUpdateAcces.domaineWeather$fondre(map, chunk, chance);
    }
}

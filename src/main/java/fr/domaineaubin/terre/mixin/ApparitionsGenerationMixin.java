package fr.domaineaubin.terre.mixin;

import fr.domaineaubin.terre.monde.FauneSpawns;
import net.minecraft.core.Holder;
import net.minecraft.util.RandomSource;
import net.minecraft.util.random.WeightedRandomList;
import net.minecraft.world.entity.MobCategory;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.NaturalSpawner;
import net.minecraft.world.level.ServerLevelAccessor;
import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.biome.MobSpawnSettings;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Redirect;

/**
 * Animaux nés à la génération des chunks : la liste du biome est remplacée par celle de la faune de la Terre
 * (ce chemin ne passe pas par l'événement Forge PotentialSpawns).
 */
@Mixin(NaturalSpawner.class)
public abstract class ApparitionsGenerationMixin {

    @Redirect(method = "spawnMobsForChunkGeneration",
            at = @At(value = "INVOKE", target = "Lnet/minecraft/world/level/biome/MobSpawnSettings;getMobs(Lnet/minecraft/world/entity/MobCategory;)Lnet/minecraft/util/random/WeightedRandomList;"))
    private static WeightedRandomList<MobSpawnSettings.SpawnerData> domaineTerre$fauneGeneration(
            MobSpawnSettings reglages, MobCategory categorie,
            ServerLevelAccessor niveau, Holder<Biome> biome, ChunkPos chunk, RandomSource hasard) {
        return FauneSpawns.generation(niveau, biome, chunk, categorie, reglages.getMobs(categorie));
    }
}

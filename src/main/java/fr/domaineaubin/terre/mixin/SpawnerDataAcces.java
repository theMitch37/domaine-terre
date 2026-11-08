package fr.domaineaubin.terre.mixin;

import net.minecraft.world.entity.EntityType;
import net.minecraft.world.level.biome.MobSpawnSettings;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Mutable;
import org.spongepowered.asm.mixin.gen.Accessor;

/**
 * Type d'une entrée d'apparition. Le constructeur du jeu remplace tout type de la catégorie MISC par le cochon : les
 * bêtes d'Untamed Wilds (rangées en MISC) devenaient des cochons à la génération (test du 08/11/2026).
 */
@Mixin(MobSpawnSettings.SpawnerData.class)
public interface SpawnerDataAcces {
    @Mutable
    @Accessor("type")
    void domaineTerre$type(EntityType<?> type);
}

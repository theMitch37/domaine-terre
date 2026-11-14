package fr.domaineaubin.terre.mixin.compat;

import fr.domaineaubin.terre.DomaineTerre;
import fr.domaineaubin.terre.monde.FauneTerre;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.util.RandomSource;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.SpawnPlacements;
import net.minecraft.world.level.ServerLevelAccessor;
import net.minecraft.world.level.levelgen.Heightmap;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

import java.util.concurrent.atomic.AtomicInteger;

/**
 * Untamed Wilds suit nos règles (14/11/2026, Maxime : « qu'il arrête de faire comme il veut, les mobs spawn selon nos
 * règles »). Toutes ses naissances à la génération des chunks (herbivores, prédateurs, petites bêtes, terriers, mer,
 * eaux douces, grottes) passent par une seule porte, FaunaSpawn.performWorldGenSpawning ; dans un monde Terre :
 * - bête de terre de la table : refusée ici, c'est notre table qui la fait naître (pas de double naissance) ;
 * - bête « pour contrôle » (mer, eau douce) : seulement si la table la permet à cet endroit (terroir, mer, température,
 *   bande, estuaire) ; son espèce est ensuite vérifiée au 2e tick (FauneSpawns.espece) ;
 * - bête que la table ne connaît pas : refusée (aucune autre règle que les nôtres).
 * Facultatif : sans Untamed Wilds, cette mixin est ignorée.
 */
@Pseudo
@Mixin(targets = "untamedwilds.world.FaunaSpawn", remap = false)
public abstract class UntamedWildsPorteMixin {
    private static final AtomicInteger JOURNAL = new AtomicInteger();

    @Inject(method = "performWorldGenSpawning", at = @At("HEAD"), cancellable = true, remap = false)
    private static void domaineTerre$nosRegles(EntityType<?> type, SpawnPlacements.Type placement, Heightmap.Types carte,
                                               ServerLevelAccessor monde, BlockPos pos, RandomSource hasard, int groupe,
                                               CallbackInfoReturnable<Boolean> cir) {
        ServerLevel n = monde.getLevel();
        if (n == null || !fr.domaineaubin.terre.monde.FauneSpawns.terre(n)) return;
        FauneTerre f = FauneTerre.get();
        if (!f.active()) return;
        String raison;
        if (f.dansLaTable(type)) raison = "née par la table";
        else if (!f.controlee(type)) raison = "absente de la table";
        else if (!f.permis(type, pos.getX(), pos.getZ(), monde.getBiome(pos))) raison = "hors de son milieu réel";
        else return;
        cir.setReturnValue(false);
        if (JOURNAL.incrementAndGet() <= 20) DomaineTerre.LOGGER.info("Faune : Untamed Wilds, {} refusé en {} ({})",
                EntityType.getKey(type), pos.toShortString(), raison);
    }
}

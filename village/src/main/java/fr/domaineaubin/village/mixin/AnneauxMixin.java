package fr.domaineaubin.village.mixin;

import fr.domaineaubin.village.Points;
import net.minecraft.core.Holder;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.chunk.ChunkGeneratorStructureState;
import net.minecraft.world.level.levelgen.structure.BuiltinStructureSets;
import net.minecraft.world.level.levelgen.structure.StructureSet;
import net.minecraft.world.level.levelgen.structure.placement.ConcentricRingsStructurePlacement;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

import java.util.List;
import java.util.concurrent.CompletableFuture;

/**
 * Forteresses de l'End : dans un monde Terre, une seule par continent, à un endroit fixe (décision de Maxime) au lieu
 * des 128 des anneaux vanilla. L'œil de l'Ender et /locate suivent ces positions.
 */
@Mixin(ChunkGeneratorStructureState.class)
public abstract class AnneauxMixin {
    @Inject(method = "generateRingPositions", at = @At("HEAD"), cancellable = true)
    private void domaineVillage$forteresses(Holder<StructureSet> ensemble, ConcentricRingsStructurePlacement placement,
                                            CallbackInfoReturnable<CompletableFuture<List<ChunkPos>>> cir) {
        if (Points.terre && ensemble.is(BuiltinStructureSets.STRONGHOLDS))
            cir.setReturnValue(CompletableFuture.completedFuture(Points.forteresses()));
    }
}

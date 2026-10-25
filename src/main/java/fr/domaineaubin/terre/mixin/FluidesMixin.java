package fr.domaineaubin.terre.mixin;

import fr.domaineaubin.terre.monde.Terrain;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.levelgen.Aquifer;
import net.minecraft.world.level.levelgen.NoiseBasedChunkGenerator;
import net.minecraft.world.level.levelgen.NoiseGeneratorSettings;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/**
 * Sous y -54, le jeu remplit tout de lave. Les fosses océaniques descendent jusqu'à y -61 :
 * en mer (d'après la carte), l'eau de la mer y descend aussi. Sous les terres, la lave vanilla reste.
 */
@Mixin(NoiseBasedChunkGenerator.class)
public abstract class FluidesMixin {

    @Inject(method = "createFluidPicker", at = @At("RETURN"), cancellable = true)
    private static void domaineTerre$eauDesFosses(NoiseGeneratorSettings reglages,
                                                  CallbackInfoReturnable<Aquifer.FluidPicker> retour) {
        if (!reglages.defaultFluid().is(Blocks.WATER)) return;
        Aquifer.FluidPicker vanilla = retour.getReturnValue();
        int mer = reglages.seaLevel();
        Aquifer.FluidStatus eau = new Aquifer.FluidStatus(mer, reglages.defaultFluid());
        retour.setReturnValue((x, y, z) -> {
            if (y < Math.min(-54, mer) && Terrain.get().enMer(x, z)) return eau;
            return vanilla.computeFluid(x, y, z);
        });
    }

    /**
     * 0.3.2 : plus de carvers (grottes et ravins creusés) dans aucun biome, vanilla compris
     * (forge:remove_carvers n'existe pas en 1.20.1). Registre : notes/retire-vanilla.md.
     */
    @Inject(method = "applyCarvers", at = @At("HEAD"), cancellable = true)
    private void domaineTerre$sansCarvers(CallbackInfo info) {
        info.cancel();
    }
}

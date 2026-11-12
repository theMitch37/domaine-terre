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
 * Sous y -54, le jeu remplit tout de lave. Les fosses océaniques descendent jusqu'à y -505 (monde agrandi, 10/11/2026) :
 * en mer (d'après la carte), l'eau de la mer y descend aussi. Sous les terres, la lave vanilla reste.
 * Dans un lac (étape C1), l'eau prend le niveau de ce lac au lieu de celui de la mer.
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
        // lacs en altitude (étape C1) : dans un lac, l'eau monte jusqu'au niveau de ce lac
        Aquifer.FluidStatus[] lacs = new Aquifer.FluidStatus[Terrain.Y_MAX - Terrain.Y_MIN];
        Aquifer.FluidStatus sec = new Aquifer.FluidStatus(-2048, Blocks.AIR.defaultBlockState());
        retour.setReturnValue((x, y, z) -> {
            Terrain t = Terrain.get();
            int niv = t.niveauLac(x, z);
            if (niv != Terrain.SANS_LAC && niv > Terrain.Y_MIN && niv < Terrain.Y_MAX) {
                Aquifer.FluidStatus s = lacs[niv - Terrain.Y_MIN];
                if (s == null) lacs[niv - Terrain.Y_MIN] = s = new Aquifer.FluidStatus(niv, reglages.defaultFluid());
                return s;
            }
            if (t.sansAquifere(x, z)) return sec;          // lit d'un cours d'eau : FleuveFeature y met l'eau
            if (y < Math.min(-54, mer) && t.enMer(x, z)) return eau;
            // 12/11/2026 : grottes jusqu'au fond du monde ; sous y -54, le jeu remplirait tout de lave : grottes sèches
            // (les poches d'eau et de lave locales de l'aquifère restent)
            if (y < -54) return sec;
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

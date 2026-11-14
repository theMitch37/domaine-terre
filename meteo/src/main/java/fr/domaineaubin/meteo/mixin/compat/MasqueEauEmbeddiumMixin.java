package fr.domaineaubin.meteo.mixin.compat;

import fr.domaineaubin.meteo.vagues.MasqueEau;
import net.minecraft.core.Direction;
import net.minecraft.world.level.BlockAndTintGetter;
import net.minecraft.world.level.material.Fluid;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/**
 * Rendu de l'eau d'Embeddium : il remplace celui du jeu. Le dessus de la mer est déclaré « caché » (voir
 * {@link MasqueEau}). Facultatif : sans Embeddium, cette mixin est simplement ignorée.
 */
@Pseudo
@Mixin(targets = "me.jellysquid.mods.sodium.client.render.chunk.compile.pipeline.FluidRenderer", remap = false)
public abstract class MasqueEauEmbeddiumMixin {
    @Inject(method = "isFluidOccluded", at = @At("HEAD"), cancellable = true, remap = false)
    private void domaineWeather$masquer(BlockAndTintGetter region, int x, int y, int z, Direction face, Fluid fluide,
                                        CallbackInfoReturnable<Boolean> cir) {
        if (face == Direction.UP && MasqueEau.masquer(region, x, y, z)) cir.setReturnValue(true);
    }
}

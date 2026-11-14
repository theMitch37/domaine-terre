package fr.domaineaubin.meteo.mixin;

import fr.domaineaubin.meteo.vagues.MasqueEau;
import net.minecraft.client.renderer.block.LiquidBlockRenderer;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.world.level.BlockAndTintGetter;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.material.FluidState;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/** Rendu de l'eau du jeu de base (sans Embeddium) : dessus de la mer masqué, voir {@link MasqueEau}. */
@Mixin(LiquidBlockRenderer.class)
public abstract class MasqueEauMixin {
    @Inject(method = "shouldRenderFace", at = @At("HEAD"), cancellable = true)
    private static void domaineWeather$masquer(BlockAndTintGetter region, BlockPos pos, FluidState fluide, BlockState etat,
                                               Direction face, FluidState voisin, CallbackInfoReturnable<Boolean> cir) {
        if (face == Direction.UP && MasqueEau.masquer(region, pos.getX(), pos.getY(), pos.getZ())) cir.setReturnValue(false);
    }
}

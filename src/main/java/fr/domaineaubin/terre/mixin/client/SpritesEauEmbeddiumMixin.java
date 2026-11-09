package fr.domaineaubin.terre.mixin.client;

import fr.domaineaubin.terre.client.EauOpaque;
import net.minecraft.core.BlockPos;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.level.BlockAndTintGetter;
import net.minecraft.world.level.material.FluidState;
import net.minecraftforge.client.extensions.common.IClientFluidTypeExtensions;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Redirect;

/**
 * Rendu de l'eau d'Embeddium (0.3.x, aussi utilisé par Oculus) : mêmes textures que SpritesEauForgeMixin. Sans
 * Embeddium, ce mixin est ignoré.
 */
@Pseudo
@Mixin(targets = "org.embeddedt.embeddium.render.fluid.EmbeddiumFluidSpriteCache", remap = false)
public abstract class SpritesEauEmbeddiumMixin {
    @Redirect(method = "getSprites", remap = false, require = 0, at = @At(value = "INVOKE", remap = false,
            target = "Lnet/minecraftforge/client/extensions/common/IClientFluidTypeExtensions;getStillTexture(Lnet/minecraft/world/level/material/FluidState;Lnet/minecraft/world/level/BlockAndTintGetter;Lnet/minecraft/core/BlockPos;)Lnet/minecraft/resources/ResourceLocation;"))
    private ResourceLocation domaineTerre$immobile(IClientFluidTypeExtensions ext, FluidState s, BlockAndTintGetter l, BlockPos p) {
        return EauOpaque.immobile(ext, s, l, p);
    }

    @Redirect(method = "getSprites", remap = false, require = 0, at = @At(value = "INVOKE", remap = false,
            target = "Lnet/minecraftforge/client/extensions/common/IClientFluidTypeExtensions;getFlowingTexture(Lnet/minecraft/world/level/material/FluidState;Lnet/minecraft/world/level/BlockAndTintGetter;Lnet/minecraft/core/BlockPos;)Lnet/minecraft/resources/ResourceLocation;"))
    private ResourceLocation domaineTerre$courante(IClientFluidTypeExtensions ext, FluidState s, BlockAndTintGetter l, BlockPos p) {
        return EauOpaque.courante(ext, s, l, p);
    }
}

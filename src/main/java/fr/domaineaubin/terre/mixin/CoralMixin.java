package fr.domaineaubin.terre.mixin;

import fr.domaineaubin.terre.monde.Recifs;
import net.minecraft.core.BlockPos;
import net.minecraft.world.level.levelgen.feature.CoralFeature;
import net.minecraft.world.level.levelgen.feature.FeaturePlaceContext;
import net.minecraft.world.level.levelgen.feature.configurations.NoneFeatureConfiguration;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/** Corail seulement sur les récifs réels et loin des embouchures (voir Recifs, 12/11/2026). */
@Mixin(CoralFeature.class)
public abstract class CoralMixin {

    @Inject(method = "place", at = @At("HEAD"), cancellable = true)
    private void domaineTerre$recif(FeaturePlaceContext<NoneFeatureConfiguration> ctx, CallbackInfoReturnable<Boolean> cir) {
        BlockPos p = ctx.origin();
        if (!Recifs.corail(ctx.level(), p.getX(), p.getZ())) cir.setReturnValue(false);
    }
}

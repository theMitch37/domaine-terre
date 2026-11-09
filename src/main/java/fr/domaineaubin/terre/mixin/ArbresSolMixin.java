package fr.domaineaubin.terre.mixin;

import fr.domaineaubin.terre.monde.ReliefFin;
import fr.domaineaubin.terre.monde.Terrain;
import net.minecraft.core.BlockPos;
import net.minecraft.world.level.levelgen.feature.FeaturePlaceContext;
import net.minecraft.world.level.levelgen.feature.TreeFeature;
import net.minecraft.world.level.levelgen.feature.configurations.TreeConfiguration;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/**
 * Monde 1:30 (09/11/2026) : les arbres suivent la vraie couverture du sol (ESA WorldCover) plutôt que le biome
 * grossier. Forêt et mangrove : comme le biome le prévoit ; broussailles : un arbre sur dix ; prairies, cultures,
 * zones humides : un sur cinquante ; sol nu, neige et glace, mousses et lichens : aucun. Tirage fixé par la position.
 */
@Mixin(TreeFeature.class)
public abstract class ArbresSolMixin {
    @Inject(method = "place", at = @At("HEAD"), cancellable = true)
    private void domaineTerre$couverture(FeaturePlaceContext<TreeConfiguration> ctx, CallbackInfoReturnable<Boolean> r) {
        if (Terrain.echelle() >= 250) return;
        BlockPos o = ctx.origin();
        int s = ReliefFin.sol(o.getX(), o.getZ());
        if (s < 0) return;
        int cov = s & 255;
        double tirage = (Math.floorMod(o.getX() * 73856093 ^ o.getZ() * 19349663, 1000)) / 1000.0;
        boolean garde = switch (cov) {
            case 10, 95 -> true;
            case 20 -> tirage < 0.10;
            case 30, 40, 50, 90 -> tirage < 0.02;
            default -> false;
        };
        if (!garde) r.setReturnValue(false);
    }
}

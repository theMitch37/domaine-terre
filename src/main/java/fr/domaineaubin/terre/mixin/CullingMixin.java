package fr.domaineaubin.terre.mixin;

import fr.domaineaubin.terre.monde.Tailles;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.phys.AABB;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/**
 * Boîte d'affichage des créatures agrandies (08/11/2026 : les baleines disparaissaient quand on tournait la tête) :
 * le jeu ne dessine une créature que si sa boîte est dans le champ de vision ; un modèle agrandi dépasse sa boîte.
 * Untamed Wilds agrandit ses modèles par espèce : sa boîte est élargie d'office.
 */
@Mixin(Entity.class)
public abstract class CullingMixin {
    @Inject(method = "getBoundingBoxForCulling", at = @At("RETURN"), cancellable = true)
    private void domaineTerre$culling(CallbackInfoReturnable<AABB> cir) {
        Entity e = (Entity) (Object) this;
        float f = Tailles.facteur(e.getType());
        boolean uw = net.minecraft.world.entity.EntityType.getKey(e.getType()).getNamespace().equals("untamedwilds");
        if (f <= 1.0f && !uw) return;
        AABB b = cir.getReturnValue();
        double t = Math.max(b.getXsize(), b.getYsize());
        double marge = uw ? Math.max(4.0, t * 4.0) : t * (f - 1.0) + 1.0;
        cir.setReturnValue(b.inflate(marge));
    }
}

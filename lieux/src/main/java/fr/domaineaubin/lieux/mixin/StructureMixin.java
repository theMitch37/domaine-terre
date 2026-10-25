package fr.domaineaubin.lieux.mixin;

import fr.domaineaubin.lieux.ZonesInterdites;
import net.minecraft.world.level.levelgen.structure.Structure;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

import java.util.Optional;

/** Aucune structure vanilla (village, épave, portail en ruine…) ne démarre sur un lieu unique ni juste autour. */
@Mixin(Structure.class)
public abstract class StructureMixin {

    @Inject(method = "findValidGenerationPoint", at = @At("RETURN"), cancellable = true)
    private void domaineLieux$pasSurLesLieux(Structure.GenerationContext contexte,
                                            CallbackInfoReturnable<Optional<Structure.GenerationStub>> retour) {
        Optional<Structure.GenerationStub> point = retour.getReturnValue();
        if (point.isPresent() && ZonesInterdites.interdit((Structure) (Object) this, point.get().position())) {
            retour.setReturnValue(Optional.empty());
        }
    }
}

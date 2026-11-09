package fr.domaineaubin.terre.mixin;

import net.minecraft.core.registries.Registries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.level.levelgen.structure.Structure;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

import java.util.Optional;
import java.util.Set;

/**
 * Terre 0.3.2 : aucune structure vanilla de la surface ni des profondeurs (villages, temples, épaves, avant-postes,
 * cités antiques…) : elles seront réimplantées à notre façon (registre : notes/retire-vanilla.md).
 * Seules restent les forteresses (accès à l'End). Les structures des autres mods ne sont pas touchées.
 */
@Mixin(Structure.class)
public abstract class StructuresMixin {

    private static final Set<String> GARDEES = Set.of("stronghold");

    @Inject(method = "findValidGenerationPoint", at = @At("HEAD"), cancellable = true)
    private void domaineTerre$sansStructuresVanilla(Structure.GenerationContext contexte,
                                                    CallbackInfoReturnable<Optional<Structure.GenerationStub>> retour) {
        // monde 1:30 (09/11/2026) : aucune structure, de tous les mods, le temps des tests (BacASable)
        if (fr.domaineaubin.terre.monde.BacASable.actif()) {
            retour.setReturnValue(Optional.empty());
            return;
        }
        ResourceLocation cle = contexte.registryAccess().registryOrThrow(Registries.STRUCTURE).getKey((Structure) (Object) this);
        if (cle != null && "minecraft".equals(cle.getNamespace()) && !GARDEES.contains(cle.getPath())) {
            retour.setReturnValue(Optional.empty());
        }
    }
}

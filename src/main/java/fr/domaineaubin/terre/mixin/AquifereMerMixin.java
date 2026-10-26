package fr.domaineaubin.terre.mixin;

import fr.domaineaubin.terre.monde.Terrain;
import net.minecraft.world.level.levelgen.Aquifer;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/**
 * Mer peu profonde à sec (26/10, bassin d'Arcachon, Étretat, Douvres…) : l'aquifère vanilla ne prend l'eau de la mer
 * (le « fluide global ») que là où son estimation grossière du sol (preliminary surface level) est sous la mer.
 * Sur un fond à 1-5 blocs sous la surface, cette estimation le voit hors de l'eau : l'aquifère tire alors un niveau
 * local plus bas et laisse le fond à l'air libre.
 * En mer d'après la carte (et hors lac, hors lit de rivière), chaque point de l'aquifère prend donc directement le
 * fluide global (FluidesMixin) : l'eau de mer jusqu'au niveau de la mer, à toute profondeur. Les points de l'aquifère
 * sont espacés de 16 blocs et chaque bloc suit les plus proches : la règle vaut donc aussi à moins de 16 blocs du
 * rivage côté terre (sinon la dernière bande de mer restait à sec) ; la terre y est au-dessus de la mer.
 */
@Mixin(targets = "net.minecraft.world.level.levelgen.Aquifer$NoiseBasedAquifer")
public abstract class AquifereMerMixin {

    /** 16 blocs (à 1:250) en minutes d'arc. */
    private static final double RIVAGE = 16 * 60.0 / 445.28;

    @Shadow @Final private Aquifer.FluidPicker globalFluidPicker;

    @Inject(method = "computeFluid", at = @At("HEAD"), cancellable = true)
    private void domaineTerre$merAuNiveau(int x, int y, int z, CallbackInfoReturnable<Aquifer.FluidStatus> retour) {
        Terrain t = Terrain.get();
        if ((t.enMer(x, z) || t.distanceCote(x, z) < RIVAGE) && t.niveauLac(x, z) == Terrain.SANS_LAC && !t.sansAquifere(x, z)) {
            retour.setReturnValue(globalFluidPicker.computeFluid(x, y, z));
        }
    }
}

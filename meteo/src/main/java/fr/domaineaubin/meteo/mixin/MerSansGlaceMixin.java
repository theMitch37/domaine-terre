package fr.domaineaubin.meteo.mixin;

import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.Registries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.level.LevelReader;
import net.minecraft.world.level.biome.Biome;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/**
 * La mer ne gèle pas hors des mers froides (0.3.2) : avec les saisons de Serene Seasons, l'hiver refroidissait assez
 * les mers tempérées (Atlantique au large de la Bretagne) pour que des plaques de glace s'y forment au hasard. Dans
 * la réalité, seules les mers polaires (et certaines mers froides en hiver) gèlent : la glace reste permise dans
 * domaine_terre:mer/gelee_* et mer/froide_*, jamais dans mer/temperee_*, mer/tiede_*, mer/chaude_*.
 */
@Mixin(Biome.class)
public abstract class MerSansGlaceMixin {
    @Inject(method = "shouldFreeze(Lnet/minecraft/world/level/LevelReader;Lnet/minecraft/core/BlockPos;Z)Z",
            at = @At("HEAD"), cancellable = true)
    private void domaineWeather$merSansGlace(LevelReader level, BlockPos pos, boolean bord,
                                            CallbackInfoReturnable<Boolean> cir) {
        ResourceLocation k = level.registryAccess().registryOrThrow(Registries.BIOME).getKey((Biome) (Object) this);
        if (k == null || !"domaine_terre".equals(k.getNamespace())) return;
        String p = k.getPath();
        if (p.startsWith("mer/temperee") || p.startsWith("mer/tiede") || p.startsWith("mer/chaude")) cir.setReturnValue(false);
    }
}

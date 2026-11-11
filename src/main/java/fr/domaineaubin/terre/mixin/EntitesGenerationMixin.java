package fr.domaineaubin.terre.mixin;

import fr.domaineaubin.terre.monde.FauneSpawns;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.Entity;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

import java.util.stream.Stream;

/**
 * Bêtes nées pendant la génération d'un chunk (apparitions de génération, features d'Untamed Wilds…) : elles entrent
 * dans le monde quand le chunk devient complet, avec un EntityJoinLevelEvent dont loadedFromDisk est faux, comme une
 * bête née d'un œuf. Le drapeau permet à FauneSpawns.arrivee de les reconnaître et de les vérifier (12/11/2026).
 */
@Mixin(ServerLevel.class)
public abstract class EntitesGenerationMixin {

    @Inject(method = "addWorldGenChunkEntities", at = @At("HEAD"))
    private void domaineTerre$debut(Stream<Entity> entites, CallbackInfo ci) {
        FauneSpawns.GENERATION.set(Boolean.TRUE);
    }

    @Inject(method = "addWorldGenChunkEntities", at = @At("RETURN"))
    private void domaineTerre$fin(Stream<Entity> entites, CallbackInfo ci) {
        FauneSpawns.GENERATION.set(Boolean.FALSE);
    }
}

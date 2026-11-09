package fr.domaineaubin.terre.mixin.client;

import com.mojang.serialization.Codec;
import net.minecraft.client.renderer.texture.atlas.SpriteSource;
import net.minecraft.client.renderer.texture.atlas.SpriteSourceType;
import net.minecraft.client.renderer.texture.atlas.SpriteSources;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.gen.Invoker;

/** Inscription d'un type de source d'atlas (Forge 47 n'a pas d'événement pour ça) : voir EauOpaque. */
@Mixin(SpriteSources.class)
public interface SpriteSourcesAcces {
    @Invoker("register")
    static SpriteSourceType inscrire(String nom, Codec<? extends SpriteSource> codec) {
        throw new AssertionError();
    }
}

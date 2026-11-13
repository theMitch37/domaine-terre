package fr.domaineaubin.meteo.mixin;

import net.minecraft.server.level.ChunkMap;
import net.minecraft.world.level.chunk.LevelChunk;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.gen.Invoker;
import sereneseasons.season.RandomUpdateHandler;

@Mixin(value = RandomUpdateHandler.class, remap = false)
public interface RandomUpdateAcces {
    @Invoker("meltInChunk")
    static void domaineWeather$fondre(ChunkMap map, LevelChunk chunk, float chance) {
        throw new AssertionError();
    }
}

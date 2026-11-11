package fr.domaineaubin.terre.monde;

import fr.domaineaubin.terre.DomaineTerre;
import net.minecraft.core.BlockPos;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.chunk.LevelChunk;
import net.minecraft.world.level.levelgen.Heightmap;
import net.minecraftforge.event.level.ChunkEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.registries.ForgeRegistries;

/**
 * Terriers d'Untamed Wilds au fond de l'eau (11/11/2026, test en jeu : « des terriers dans les rivières ») : Untamed
 * Wilds pose ses terriers à la toute dernière étape de la génération, après les cours d'eau du mod, n'importe où à la
 * surface du sol. Au premier chargement d'un chunk neuf, un terrier sous l'eau redevient le sol d'en dessous.
 */
@Mod.EventBusSubscriber(modid = DomaineTerre.MOD_ID, bus = Mod.EventBusSubscriber.Bus.FORGE)
public final class TerriersNoyes {
    private static Block terrier;
    private static boolean cherche;

    private TerriersNoyes() {
    }

    private static Block terrier() {
        if (!cherche) {
            cherche = true;
            ResourceLocation r = new ResourceLocation("untamedwilds", "block_burrow");
            terrier = ForgeRegistries.BLOCKS.containsKey(r) ? ForgeRegistries.BLOCKS.getValue(r) : null;
        }
        return terrier;
    }

    @SubscribeEvent
    public static void charge(ChunkEvent.Load event) {
        if (!event.isNewChunk() || !(event.getLevel() instanceof ServerLevel n) || !FauneSpawns.terre(n)) return;
        if (!(event.getChunk() instanceof LevelChunk c)) return;
        Block t = terrier();
        if (t == null) return;
        int x0 = c.getPos().getMinBlockX(), z0 = c.getPos().getMinBlockZ();
        BlockPos.MutableBlockPos p = new BlockPos.MutableBlockPos();
        for (int dx = 0; dx < 16; dx++) {
            for (int dz = 0; dz < 16; dz++) {
                int y = c.getHeight(Heightmap.Types.OCEAN_FLOOR, dx, dz);
                // le terrier est le bloc de surface du sol, ou juste dessous (sol meuble au-dessus)
                for (int k = 0; k <= 2; k++) {
                    p.set(x0 + dx, y - 1 - k, z0 + dz);
                    if (!c.getBlockState(p).is(t)) continue;
                    if (c.getFluidState(p.above()).isEmpty() && c.getFluidState(p.above(2)).isEmpty()) break;
                    BlockState dessous = c.getBlockState(p.below());
                    BlockState sol = dessous.isAir() || !dessous.getFluidState().isEmpty() ? Blocks.GRAVEL.defaultBlockState() : dessous;
                    c.removeBlockEntity(p);
                    c.setBlockState(p, sol, false);
                    c.setUnsaved(true);
                    break;
                }
            }
        }
    }
}

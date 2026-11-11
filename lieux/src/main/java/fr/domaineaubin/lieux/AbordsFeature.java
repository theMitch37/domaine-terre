package fr.domaineaubin.lieux;

import com.mojang.serialization.Codec;
import fr.domaineaubin.terre.api.LieuxTerre;
import net.minecraft.core.BlockPos;
import net.minecraft.world.level.WorldGenLevel;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.levelgen.Heightmap;
import net.minecraft.world.level.levelgen.feature.Feature;
import net.minecraft.world.level.levelgen.feature.FeaturePlaceContext;
import net.minecraft.world.level.levelgen.feature.configurations.NoneFeatureConfiguration;

/**
 * Abords des lieux sculptés (11/11/2026, Maxime : « une transition plus douce entre la mesa et le désert ») : hors des
 * parois, la surface (3 blocs) prend la couleur de transition que le lieu donne ({@link LieuSculpte#abords}).
 * Dans tous les biomes : les abords sont dans le biome du terrain autour, pas dans celui du lieu.
 */
public class AbordsFeature extends Feature<NoneFeatureConfiguration> {

    public AbordsFeature(Codec<NoneFeatureConfiguration> codec) {
        super(codec);
    }

    @Override
    public boolean place(FeaturePlaceContext<NoneFeatureConfiguration> ctx) {
        if (LieuxTerre.liste().isEmpty()) return false;
        WorldGenLevel niveau = ctx.level();
        int x0 = (ctx.origin().getX() >> 4) << 4;
        int z0 = (ctx.origin().getZ() >> 4) << 4;
        BlockPos.MutableBlockPos pos = new BlockPos.MutableBlockPos();
        boolean modifie = false;
        for (int dx = 0; dx < 16; dx++) {
            for (int dz = 0; dz < 16; dz++) {
                int x = x0 + dx, z = z0 + dz;
                if (!(LieuxTerre.a(x, z) instanceof LieuSculpte lieu)) continue;
                int haut = niveau.getHeight(Heightmap.Types.OCEAN_FLOOR_WG, x, z) - 1;
                if (!niveau.getBlockState(pos.set(x, haut + 1, z)).getFluidState().isEmpty()) continue;
                for (int y = haut; y > haut - 3; y--) {
                    BlockState b = niveau.getBlockState(pos.set(x, y, z));
                    if (!(b.is(Blocks.SAND) || b.is(Blocks.RED_SAND) || b.is(Blocks.SANDSTONE)))
                        break;                      // sable du désert seulement (la forêt du plateau garde son sol)
                    BlockState n = lieu.abords(x, y, z);
                    if (n == null) break;
                    niveau.setBlock(pos, n, 2);
                    modifie = true;
                }
            }
        }
        return modifie;
    }
}

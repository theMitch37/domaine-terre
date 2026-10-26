package fr.domaineaubin.terre.monde;

import com.mojang.serialization.Codec;
import net.minecraft.core.BlockPos;
import net.minecraft.world.level.WorldGenLevel;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.levelgen.Heightmap;
import net.minecraft.world.level.levelgen.feature.Feature;
import net.minecraft.world.level.levelgen.feature.FeaturePlaceContext;
import net.minecraft.world.level.levelgen.feature.configurations.NoneFeatureConfiguration;
import net.minecraft.world.level.material.Fluids;

/**
 * Eau des cours d'eau (étape C2) : remplit le lit, colonne par colonne, jusqu'au niveau du cours d'eau
 * ({@link Terrain#eauLit}), qui descend vers l'aval par marches d'un bloc. Les aquifères ne mettent pas d'eau dans les
 * lits ({@link Terrain#sansAquifere}). Aux marches, l'eau du bief d'amont coule dans celui d'aval (petites chutes).
 * Étape « lakes » : avant les arbres et les plantes. Ne touche que son propre chunk.
 */
public class FleuveFeature extends Feature<NoneFeatureConfiguration> {
    public FleuveFeature(Codec<NoneFeatureConfiguration> codec) {
        super(codec);
    }

    @Override
    public boolean place(FeaturePlaceContext<NoneFeatureConfiguration> ctx) {
        WorldGenLevel niveau = ctx.level();
        int x0 = (ctx.origin().getX() >> 4) << 4, z0 = (ctx.origin().getZ() >> 4) << 4;
        Terrain t = Terrain.get();
        BlockPos.MutableBlockPos pos = new BlockPos.MutableBlockPos();
        BlockState eau = Blocks.WATER.defaultBlockState();
        boolean modifie = false;
        for (int dx = 0; dx < 16; dx++) {
            for (int dz = 0; dz < 16; dz++) {
                int x = x0 + dx, z = z0 + dz;
                int w = t.eauLit(x, z);
                if (w == Terrain.SANS_LAC) continue;
                int bas = niveau.getHeight(Heightmap.Types.OCEAN_FLOOR_WG, x, z);
                for (int y = bas; y < w; y++) {
                    if (niveau.getBlockState(pos.set(x, y, z)).isAir()) {
                        niveau.setBlock(pos, eau, 2);
                        modifie = true;
                    }
                }
                // marche : un voisin du lit est plus bas, l'eau de surface doit couler (sinon un mur d'eau immobile)
                if (w - 1 >= bas && (plusBas(t, x + 1, z, w) || plusBas(t, x - 1, z, w) || plusBas(t, x, z + 1, w)
                        || plusBas(t, x, z - 1, w))) {
                    niveau.scheduleTick(pos.set(x, w - 1, z), Fluids.WATER, 1);
                }
            }
        }
        return modifie;
    }

    private static boolean plusBas(Terrain t, int x, int z, int w) {
        int v = t.eauLit(x, z);
        return v != Terrain.SANS_LAC && v < w;
    }
}

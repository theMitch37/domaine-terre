package fr.domaineaubin.terre.monde;

import com.mojang.serialization.Codec;
import net.minecraft.core.BlockPos;
import net.minecraft.util.Mth;
import net.minecraft.world.level.WorldGenLevel;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.levelgen.Heightmap;
import net.minecraft.world.level.levelgen.feature.Feature;
import net.minecraft.world.level.levelgen.feature.FeaturePlaceContext;
import net.minecraft.world.level.levelgen.feature.configurations.NoneFeatureConfiguration;

/**
 * Habillage des grandes fosses (08/11/2026), sous y -318 seulement (y 2 avant le monde agrandi du 10/11/2026) : parois de basalte, de deepslate et de tuf par
 * plaques, fond de vase et d'argile, quelques éboulis de basalte. Ne touche qu'aux blocs pleins au contact de l'eau.
 */
public class FosseFeature extends Feature<NoneFeatureConfiguration> {
    private static final int HAUT = -318;          // 7 500 m réels

    public FosseFeature(Codec<NoneFeatureConfiguration> codec) {
        super(codec);
    }

    @Override
    public boolean place(FeaturePlaceContext<NoneFeatureConfiguration> ctx) {
        WorldGenLevel niveau = ctx.level();
        int x0 = ctx.origin().getX() & ~15, z0 = ctx.origin().getZ() & ~15;
        if (niveau.getHeight(Heightmap.Types.OCEAN_FLOOR_WG, x0 + 8, z0 + 8) > HAUT + 2) return false;
        BlockPos.MutableBlockPos p = new BlockPos.MutableBlockPos(), v = new BlockPos.MutableBlockPos();
        boolean modifie = false;
        int bas = niveau.getMinBuildHeight() + 2;
        for (int dx = 0; dx < 16; dx++) {
            for (int dz = 0; dz < 16; dz++) {
                int x = x0 + dx, z = z0 + dz;
                int sol = niveau.getHeight(Heightmap.Types.OCEAN_FLOOR_WG, x, z) - 1;
                if (sol > HAUT) continue;
                int plusBas = sol;                               // pied de la paroi : le sol voisin le plus bas
                plusBas = Math.min(plusBas, niveau.getHeight(Heightmap.Types.OCEAN_FLOOR_WG, x + 1, z) - 1);
                plusBas = Math.min(plusBas, niveau.getHeight(Heightmap.Types.OCEAN_FLOOR_WG, x - 1, z) - 1);
                plusBas = Math.min(plusBas, niveau.getHeight(Heightmap.Types.OCEAN_FLOOR_WG, x, z + 1) - 1);
                plusBas = Math.min(plusBas, niveau.getHeight(Heightmap.Types.OCEAN_FLOOR_WG, x, z - 1) - 1);
                for (int y = sol; y >= Math.max(bas, plusBas - 1); y--) {
                    p.set(x, y, z);
                    BlockState b = niveau.getBlockState(p);
                    if (!b.isSolid() || (b.is(Blocks.BEDROCK) && y < -507)) continue;   // bedrock à nu au fond : recouverte
                    boolean dessus = niveau.getBlockState(v.set(x, y + 1, z)).is(Blocks.WATER);
                    boolean cote = !dessus && (eau(niveau, v, x + 1, y, z) || eau(niveau, v, x - 1, y, z)
                            || eau(niveau, v, x, y, z + 1) || eau(niveau, v, x, y, z - 1));
                    if (!dessus && !cote) continue;
                    double n = valeur(x / 7.0, y / 5.0, z / 7.0);
                    BlockState neuf;
                    if (cote) {                                  // paroi
                        neuf = (n < 0.45 ? Blocks.BASALT : n < 0.8 ? Blocks.DEEPSLATE : Blocks.TUFF).defaultBlockState();
                    } else if (sol > -426) {                     // pente au-dessus de la faille : sédiments
                        double m = valeur(x / 9.0, 3.0, z / 9.0);
                        neuf = (m < 0.7 ? Blocks.MUD : m < 0.9 ? Blocks.CLAY : Blocks.DEEPSLATE).defaultBlockState();
                    } else if (sol > -483) {                     // dessus d'une corniche
                        neuf = (n < 0.6 ? Blocks.DEEPSLATE : Blocks.BASALT).defaultBlockState();
                    } else {                                     // fond
                        double m = valeur(x / 5.0, 7.0, z / 5.0);
                        neuf = (m < 0.55 ? Blocks.MUD : m < 0.85 ? Blocks.CLAY : Blocks.BASALT).defaultBlockState();
                    }
                    if (!b.is(neuf.getBlock())) {
                        niveau.setBlock(p, neuf, 2);
                        modifie = true;
                    }
                }
            }
        }
        return modifie;
    }

    private static boolean eau(WorldGenLevel n, BlockPos.MutableBlockPos v, int x, int y, int z) {
        return n.getBlockState(v.set(x, y, z)).is(Blocks.WATER);
    }

    /** Bruit de valeur lissé 3D, entre 0 et 1, fixe pour une position. */
    private static double valeur(double x, double y, double z) {
        int ix = Mth.floor(x), iy = Mth.floor(y), iz = Mth.floor(z);
        double fx = lisse(x - ix), fy = lisse(y - iy), fz = lisse(z - iz);
        double c000 = h(ix, iy, iz), c100 = h(ix + 1, iy, iz), c010 = h(ix, iy + 1, iz), c110 = h(ix + 1, iy + 1, iz);
        double c001 = h(ix, iy, iz + 1), c101 = h(ix + 1, iy, iz + 1), c011 = h(ix, iy + 1, iz + 1), c111 = h(ix + 1, iy + 1, iz + 1);
        return Mth.lerp(fz, Mth.lerp(fy, Mth.lerp(fx, c000, c100), Mth.lerp(fx, c010, c110)),
                Mth.lerp(fy, Mth.lerp(fx, c001, c101), Mth.lerp(fx, c011, c111)));
    }

    private static double lisse(double t) {
        return t * t * (3 - 2 * t);
    }

    private static double h(int x, int y, int z) {
        long k = x * 0x9E3779B97F4A7C15L ^ y * 0xD6E8FEB86659FD93L ^ z * 0xC2B2AE3D27D4EB4FL;
        k ^= k >>> 31;
        k *= 0xBF58476D1CE4E5B9L;
        k ^= k >>> 29;
        return (k >>> 11) * 0x1.0p-53;
    }
}

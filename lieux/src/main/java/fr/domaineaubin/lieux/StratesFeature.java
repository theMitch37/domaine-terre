package fr.domaineaubin.lieux;

import com.mojang.serialization.Codec;
import net.minecraft.core.BlockPos;
import net.minecraft.tags.BlockTags;
import net.minecraft.world.level.WorldGenLevel;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.levelgen.Heightmap;
import net.minecraft.world.level.levelgen.feature.Feature;
import net.minecraft.world.level.levelgen.feature.FeaturePlaceContext;
import net.minecraft.world.level.levelgen.feature.configurations.NoneFeatureConfiguration;

/**
 * Colore les parois du Grand Canyon en strates horizontales (du Kaibab clair au schiste sombre de la gorge).
 * Ne touche que les blocs de son propre chunk, avant la végétation : rien ne peut se retrouver en l'air.
 */
public class StratesFeature extends Feature<NoneFeatureConfiguration> {

    public StratesFeature(Codec<NoneFeatureConfiguration> codec) {
        super(codec);
    }

    @Override
    public boolean place(FeaturePlaceContext<NoneFeatureConfiguration> ctx) {
        WorldGenLevel niveau = ctx.level();
        int x0 = (ctx.origin().getX() >> 4) << 4;
        int z0 = (ctx.origin().getZ() >> 4) << 4;
        BlockPos.MutableBlockPos pos = new BlockPos.MutableBlockPos();
        boolean modifie = false;
        for (int dx = 0; dx < 16; dx++) {
            for (int dz = 0; dz < 16; dz++) {
                int x = x0 + dx, z = z0 + dz;
                double rebord = GrandCanyon.INSTANCE.rebordSiCanyon(x, z);
                if (Double.isNaN(rebord)) continue;
                int sommet = niveau.getHeight(Heightmap.Types.OCEAN_FLOOR_WG, x, z);
                for (int y = sommet; y >= GrandCanyon.FOND - 6; y--) {
                    BlockState b = niveau.getBlockState(pos.set(x, y, z));
                    if (!remplacable(b)) continue;
                    niveau.setBlock(pos, strate(x, y, z, rebord), 2);
                    modifie = true;
                }
            }
        }
        return modifie;
    }

    private static boolean remplacable(BlockState b) {
        if (b.isAir() || !b.getFluidState().isEmpty()) return false;
        return b.is(BlockTags.BASE_STONE_OVERWORLD) || b.is(BlockTags.DIRT) || b.is(Blocks.GRAVEL)
                || b.is(Blocks.SAND) || b.is(Blocks.RED_SAND) || b.is(BlockTags.SNOW) || b.is(Blocks.CLAY);
    }

    /** Strate selon la hauteur relative dans le canyon (0 = fond, 1 = rebord). */
    private static BlockState strate(int x, int y, int z, double rebord) {
        double f = (y - GrandCanyon.FOND) / (rebord - GrandCanyon.FOND);
        // légère ondulation des couches pour éviter des lignes parfaitement droites
        f += (((x * 73856093) ^ (z * 19349663)) & 7) * 0.0015;
        Block bloc;
        if (f >= 0.93) bloc = Blocks.WHITE_TERRACOTTA;            // calcaire de Kaibab
        else if (f >= 0.86) bloc = Blocks.SMOOTH_SANDSTONE;       // grès de Coconino
        else if (f >= 0.78) bloc = Blocks.RED_TERRACOTTA;         // schistes de Hermit
        else if (f >= 0.70) bloc = Blocks.ORANGE_TERRACOTTA;      // groupe de Supai
        else if (f >= 0.64) bloc = Blocks.RED_TERRACOTTA;
        else if (f >= 0.50) bloc = Blocks.TERRACOTTA;             // calcaire de Redwall
        else if (f >= 0.42) bloc = Blocks.LIGHT_GRAY_TERRACOTTA;  // schistes de Bright Angel (Tonto)
        else if (f >= 0.33) bloc = Blocks.BROWN_TERRACOTTA;       // grès de Tapeats
        else if (y <= 61) bloc = Blocks.RED_SAND;                 // lit du Colorado
        else bloc = Blocks.DEEPSLATE;                             // schiste de Vishnu (gorge intérieure)
        return bloc.defaultBlockState();
    }
}

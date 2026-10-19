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
                int sommet = niveau.getHeight(Heightmap.Types.OCEAN_FLOOR_WG, x, z) - 1;
                // sculpture : le sol prend exactement la hauteur nette (falaises verticales, replats), au-dessus de l'eau
                double cible = GrandCanyon.INSTANCE.hauteurNette(x, z);
                if (!Double.isNaN(cible)) {
                    int t = Math.max(SCULPTE_MIN, (int) Math.floor(cible));
                    if (sommet > t) {
                        for (int y = sommet; y > t; y--) {
                            BlockState b = niveau.getBlockState(pos.set(x, y, z));
                            if (b.getFluidState().isEmpty() && !b.isAir()) niveau.setBlock(pos, Blocks.AIR.defaultBlockState(), 2);
                        }
                        sommet = t;
                    } else if (sommet < t) {
                        for (int y = Math.max(sommet + 1, SCULPTE_MIN); y <= t; y++) {
                            niveau.setBlock(pos.set(x, y, z), Blocks.STONE.defaultBlockState(), 2);
                        }
                        sommet = t;
                    }
                    modifie = true;
                }
                // le plateau garde son sol (herbe, forêt) : seules les parois et le fond sont colorés
                int haut = Math.min(sommet, (int) Math.floor(rebord) - 2);
                for (int y = haut; y >= GrandCanyon.FOND - 6; y--) {
                    BlockState b = niveau.getBlockState(pos.set(x, y, z));
                    if (!remplacable(b)) continue;
                    niveau.setBlock(pos, strate(x, y, z, rebord), 2);
                    modifie = true;
                }
            }
        }
        return modifie;
    }

    /** On ne sculpte qu'au-dessus de l'eau (le lit et les lacs restent ceux du terrain, remplis par l'aquifère). */
    private static final int SCULPTE_MIN = 64;

    private static boolean remplacable(BlockState b) {
        if (b.isAir() || !b.getFluidState().isEmpty()) return false;
        return b.is(BlockTags.BASE_STONE_OVERWORLD) || b.is(BlockTags.DIRT) || b.is(Blocks.GRAVEL)
                || b.is(Blocks.SAND) || b.is(Blocks.RED_SAND) || b.is(BlockTags.SNOW) || b.is(Blocks.CLAY);
    }

    /** Couches réelles du Grand Canyon, du rebord au fleuve (voir GrandCanyon). */
    private static final Block[] COUCHES = {
            Blocks.WHITE_TERRACOTTA,       // calcaire de Kaibab (rebord, crème)
            Blocks.TERRACOTTA,             // formation de Toroweap
            Blocks.SMOOTH_SANDSTONE,       // grès de Coconino (bande claire)
            Blocks.RED_TERRACOTTA,         // schistes de Hermit (pente rouge)
            Blocks.ORANGE_TERRACOTTA,      // groupe de Supai : gradins rouges et orangés
            Blocks.RED_TERRACOTTA,
            Blocks.ORANGE_TERRACOTTA,
            Blocks.RED_TERRACOTTA,
            Blocks.TERRACOTTA,             // calcaire de Redwall (grande falaise)
            Blocks.LIGHT_GRAY_TERRACOTTA,  // calcaire de Muav
            Blocks.LIGHT_GRAY_TERRACOTTA,  // schistes de Bright Angel (plateau de Tonto)
            Blocks.BROWN_TERRACOTTA,       // grès de Tapeats
            Blocks.DEEPSLATE,              // schiste de Vishnu (gorge intérieure)
    };

    private static BlockState strate(int x, int y, int z, double rebord) {
        if (y <= 61) return Blocks.SAND.defaultBlockState();          // berges et lit du Colorado
        double f = GrandCanyon.fraction(y, rebord);
        // légère ondulation des couches pour éviter des lignes parfaitement droites
        f += ((((x * 73856093) ^ (z * 19349663)) & 7) - 3.5) * 0.0015;
        return COUCHES[GrandCanyon.couche(f)].defaultBlockState();
    }
}

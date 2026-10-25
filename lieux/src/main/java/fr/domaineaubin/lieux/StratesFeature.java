package fr.domaineaubin.lieux;

import com.mojang.serialization.Codec;
import fr.domaineaubin.terre.api.Lieu;
import fr.domaineaubin.terre.api.LieuxTerre;
import net.minecraft.core.BlockPos;
import net.minecraft.tags.BlockTags;
import net.minecraft.world.level.WorldGenLevel;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.levelgen.Heightmap;
import net.minecraft.world.level.levelgen.feature.Feature;
import net.minecraft.world.level.levelgen.feature.FeaturePlaceContext;
import net.minecraft.world.level.levelgen.feature.configurations.NoneFeatureConfiguration;

/**
 * Sculpte les parois des lieux ({@link LieuSculpte}) bloc par bloc, puis les colore en couches.
 * Ne touche que les blocs de son propre chunk, avant la végétation : rien ne peut se retrouver en l'air.
 * Une seule feature pour tous les lieux : chaque biome de lieu l'appelle, elle demande au lieu de la colonne.
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
                Lieu l = LieuxTerre.a(x, z);
                if (!(l instanceof LieuSculpte lieu)) continue;
                double rebord = lieu.rebordSiParoi(x, z);
                if (Double.isNaN(rebord)) continue;
                int sommet = niveau.getHeight(Heightmap.Types.OCEAN_FLOOR_WG, x, z) - 1;
                int min = lieu.sculpteMin();
                // sculpture : le sol prend exactement la hauteur nette (falaises verticales, replats), au-dessus de l'eau
                double cible = lieu.hauteurNette(x, z);
                boolean taillee = !Double.isNaN(cible);
                if (taillee) {
                    int t = Math.max(min, (int) Math.floor(cible));
                    if (sommet > t) {
                        for (int y = sommet; y > t; y--) {
                            BlockState b = niveau.getBlockState(pos.set(x, y, z));
                            if (b.getFluidState().isEmpty() && !b.isAir()) niveau.setBlock(pos, Blocks.AIR.defaultBlockState(), 2);
                        }
                        sommet = t;
                    } else if (sommet < t && cible >= min) {
                        for (int y = Math.max(sommet + 1, min); y <= t; y++) {
                            niveau.setBlock(pos.set(x, y, z), Blocks.STONE.defaultBlockState(), 2);
                        }
                        sommet = t;
                    }
                    modifie = true;
                } else {
                    double r = lieu.remblai(x, z);
                    if (!Double.isNaN(r) && sommet < Math.floor(r) - 1 && r >= min) {
                        int t = (int) Math.floor(r);
                        for (int y = Math.max(sommet + 1, min); y <= t; y++) {
                            niveau.setBlock(pos.set(x, y, z), Blocks.STONE.defaultBlockState(), 2);
                        }
                        sommet = t;
                        modifie = true;
                    }
                }
                // le plateau garde son sol (herbe, forêt) : seules les parois et le fond sont colorés
                for (int y = sommet; y >= lieu.fondStrates(); y--) {
                    BlockState b = niveau.getBlockState(pos.set(x, y, z));
                    if (!remplacable(b)) continue;
                    if (b.is(BlockTags.DIRT) && lieu.garderSol(y, rebord, sommet, taillee)) continue;
                    niveau.setBlock(pos, y == sommet ? lieu.sommet(x, y, z, rebord) : lieu.strate(x, y, z, rebord), 2);
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

    /** Petite ondulation déterministe des couches (évite des lignes parfaitement droites). */
    public static double ondulation(int x, int z) {
        return ((((x * 73856093) ^ (z * 19349663)) & 7) - 3.5) * 0.0015;
    }
}

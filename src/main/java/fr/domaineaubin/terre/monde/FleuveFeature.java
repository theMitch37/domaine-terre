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
                // de la surface de l'eau vers le bas, tant qu'il y a de l'air (la carte de hauteur du moteur n'est pas
                // fiable ici : un lieu vient peut-être de creuser son lit dans ce chunk, StratesFeature)
                boolean eauEnHaut = false, mouille = false;
                for (int y = w - 1; y >= w - 64; y--) {
                    BlockState b = niveau.getBlockState(pos.set(x, y, z));
                    if (b.isAir()) {
                        niveau.setBlock(pos, eau, 2);
                        modifie = true;
                        mouille = true;
                    } else if (b.getFluidState().isEmpty()) {
                        // fond du lit : les règles de surface l'ont vu à sec (pas d'aquifère dans les lits) et y ont
                        // mis de l'herbe ; sous l'eau, de la terre comme dans le jeu de base (07/11/2026)
                        if (mouille && meuble(b)) {
                            BlockState fond = fond(t, x, z);
                            if (!b.is(fond.getBlock())) {
                                niveau.setBlock(pos, fond, 2);
                                modifie = true;
                            }
                        }
                        break;
                    } else {
                        mouille = true;
                    }
                    if (y == w - 1) eauEnHaut = true;
                }
                // marche : un voisin du lit est plus bas, l'eau de surface doit couler (sinon un mur d'eau immobile)
                if (eauEnHaut && niveau.getBlockState(pos.set(x, w - 1, z)).is(Blocks.WATER)
                        && (plusBas(t, x + 1, z, w) || plusBas(t, x - 1, z, w) || plusBas(t, x, z + 1, w)
                        || plusBas(t, x, z - 1, w))) {
                    niveau.scheduleTick(pos.set(x, w - 1, z), Fluids.WATER, 1);
                }
            }
        }
        return modifie;
    }

    /** Sol meuble posé par les règles de surface (herbe, terre, sable…) ; la roche des lits de montagne reste. */
    private static boolean meuble(BlockState b) {
        return b.is(Blocks.GRASS_BLOCK) || b.is(Blocks.PODZOL) || b.is(Blocks.MYCELIUM) || b.is(Blocks.DIRT_PATH)
                || b.is(Blocks.DIRT) || b.is(Blocks.COARSE_DIRT) || b.is(Blocks.ROOTED_DIRT) || b.is(Blocks.SAND)
                || b.is(Blocks.RED_SAND) || b.is(Blocks.MUD) || b.is(Blocks.GRAVEL) || b.is(Blocks.CLAY)
                || b.is(Blocks.SNOW_BLOCK) || b.is(Blocks.MOSS_BLOCK);
    }

    /** Terroirs aux grands fleuves boueux (mêmes que l'eau boueuse, outils/couleurs_eau.py). */
    private static final java.util.Set<String> BOUEUX = java.util.Set.of("amazonie", "afrique_tropicale", "asie_sud_est",
            "chine", "inde", "sahara_sahel");

    /**
     * Fond du lit (test du 08/11/2026 : mosaïque d'herbe, de terre et de sable sous l'eau du Nil). Plaques de 5 à 6 blocs :
     * fleuves boueux = vase surtout, argile et sable ; autres = gravier et sable, un peu d'argile.
     */
    private static BlockState fond(Terrain t, int x, int z) {
        double v = bruit(x / 5.5, z / 5.5);
        String terroir = t.carte().nomTerroir(t.carte().terroir(Terrain.lon(x + 0.5), Terrain.lat(z + 0.5)));
        if (BOUEUX.contains(terroir)) {
            return (v < 0.55 ? Blocks.MUD : v < 0.8 ? Blocks.CLAY : Blocks.SAND).defaultBlockState();
        }
        return (v < 0.5 ? Blocks.GRAVEL : v < 0.88 ? Blocks.SAND : Blocks.CLAY).defaultBlockState();
    }

    /** Bruit de valeur lissé, entre 0 et 1, fixe pour une position (indépendant de la graine : carte fixe). */
    private static double bruit(double x, double z) {
        int ix = net.minecraft.util.Mth.floor(x), iz = net.minecraft.util.Mth.floor(z);
        double fx = x - ix, fz = z - iz;
        fx = fx * fx * (3 - 2 * fx);
        fz = fz * fz * (3 - 2 * fz);
        double a = hache(ix, iz), b = hache(ix + 1, iz), c = hache(ix, iz + 1), d = hache(ix + 1, iz + 1);
        return net.minecraft.util.Mth.lerp(fz, net.minecraft.util.Mth.lerp(fx, a, b), net.minecraft.util.Mth.lerp(fx, c, d));
    }

    private static double hache(int x, int z) {
        long h = x * 0x9E3779B97F4A7C15L ^ z * 0xC2B2AE3D27D4EB4FL;
        h ^= h >>> 31;
        h *= 0xBF58476D1CE4E5B9L;
        h ^= h >>> 29;
        return (h >>> 11) * 0x1.0p-53;
    }

    private static boolean plusBas(Terrain t, int x, int z, int w) {
        int v = t.eauLit(x, z);
        return v != Terrain.SANS_LAC && v < w;
    }
}

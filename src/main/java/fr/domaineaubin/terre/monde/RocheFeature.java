package fr.domaineaubin.terre.monde;

import com.mojang.serialization.Codec;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Holder;
import net.minecraft.util.Mth;
import net.minecraft.util.RandomSource;
import net.minecraft.world.level.WorldGenLevel;
import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.levelgen.Heightmap;
import net.minecraft.world.level.levelgen.feature.Feature;
import net.minecraft.world.level.levelgen.feature.FeaturePlaceContext;
import net.minecraft.world.level.levelgen.feature.configurations.NoneFeatureConfiguration;
import net.minecraft.world.level.levelgen.synth.ImprovedNoise;

/**
 * Roche et éboulis selon le vrai relief (09/11/2026, monde 1:30) : les biomes viennent d'une carte grossière et
 * couvraient d'herbe les falaises du Cervin comme les parois du Grand Canyon. Ici, chaque colonne regarde sa pente
 * réelle (Terrain.hauteur des voisines) :
 * <ul>
 * <li>plus de ~48° : roche à nu sur 4 blocs (neige comprise : elle ne tient pas sur une paroi) ; dans les climats
 * secs, strates de terre cuite rouge, orange et ocre, comme au Grand Canyon ;</li>
 * <li>de ~35° à ~48° en altitude (au-dessus de ~1 500 m) : éboulis (gravier, terre grossière) par plaques.</li>
 * </ul>
 * Posé avant la végétation : pas d'arbres sur la roche nue. Bruit à graine fixe : la même roche dans tous les mondes.
 */
public class RocheFeature extends Feature<NoneFeatureConfiguration> {
    private static final ImprovedNoise BRUIT = new ImprovedNoise(RandomSource.create(20261109L));
    private static final BlockState[] STRATES_SECHES = {
            Blocks.RED_TERRACOTTA.defaultBlockState(), Blocks.ORANGE_TERRACOTTA.defaultBlockState(),
            Blocks.TERRACOTTA.defaultBlockState(), Blocks.WHITE_TERRACOTTA.defaultBlockState(),
            Blocks.ORANGE_TERRACOTTA.defaultBlockState(), Blocks.BROWN_TERRACOTTA.defaultBlockState(),
            Blocks.RED_SANDSTONE.defaultBlockState(), Blocks.LIGHT_GRAY_TERRACOTTA.defaultBlockState()};

    /** Pente (blocs par bloc) au-delà de laquelle la roche est à nu, et début des éboulis. */
    static final double PAROI = 1.1, EBOULIS = 0.7;
    /** y au-dessus duquel les pentes moyennes sont en éboulis (~1 500 m en 1:30). */
    static final int Y_EBOULIS = 130;

    public RocheFeature(Codec<NoneFeatureConfiguration> codec) {
        super(codec);
    }

    @Override
    public boolean place(FeaturePlaceContext<NoneFeatureConfiguration> ctx) {
        if (Terrain.echelle() >= 250) return false;
        WorldGenLevel n = ctx.level();
        Terrain t = Terrain.get();
        int x0 = ctx.origin().getX() & ~15, z0 = ctx.origin().getZ() & ~15;
        BlockPos.MutableBlockPos p = new BlockPos.MutableBlockPos();
        boolean pose = false;
        // hauteurs visées sur le chunk et une bordure d'un bloc (une seule fois par colonne)
        double[] h = new double[18 * 18];
        for (int dz = -1; dz <= 16; dz++)
            for (int dx = -1; dx <= 16; dx++)
                h[(dz + 1) * 18 + dx + 1] = t.hauteur(x0 + dx, z0 + dz);
        for (int dz = 0; dz < 16; dz++) {
            for (int dx = 0; dx < 16; dx++) {
                int x = x0 + dx, z = z0 + dz, i = (dz + 1) * 18 + dx + 1;
                double gx = (h[i + 1] - h[i - 1]) * 0.5, gz = (h[i + 18] - h[i - 18]) * 0.5;
                double pente = Math.sqrt(gx * gx + gz * gz);
                if (pente < EBOULIS) continue;
                int y = n.getHeight(Heightmap.Types.WORLD_SURFACE_WG, x, z) - 1;
                if (y <= Terrain.NIVEAU_MER) continue;
                BlockState haut = n.getBlockState(p.set(x, y, z));
                if (!haut.getFluidState().isEmpty()) continue;
                double b = BRUIT.noise(x / 9.0, y / 7.0, z / 9.0);
                if (pente >= PAROI + 0.15 * b) {
                    Holder<Biome> bi = n.getBiome(p);
                    boolean sec = !bi.value().hasPrecipitation();
                    for (int k = 0; k < 5; k++) {
                        p.set(x, y - k, z);
                        BlockState s = n.getBlockState(p);
                        if (!sol(s)) {
                            if (k == 0 && (s.is(Blocks.SNOW) || s.canBeReplaced())) {   // neige, herbes : on enlève
                                n.setBlock(p, Blocks.AIR.defaultBlockState(), 2);
                                continue;
                            }
                            if (k > 0) break;
                            continue;
                        }
                        n.setBlock(p, sec ? strate(y - k, x, z) : roche(x, y - k, z), 2);
                        pose = true;
                    }
                } else if (y >= Y_EBOULIS - 8 * b && b > -0.1) {
                    BlockState s = n.getBlockState(p.set(x, y, z));
                    if (sol(s)) {
                        n.setBlock(p, b > 0.25 ? Blocks.GRAVEL.defaultBlockState() : Blocks.COARSE_DIRT.defaultBlockState(), 2);
                        pose = true;
                    }
                }
            }
        }
        return pose;
    }

    /** Couche de sol que la roche ou les éboulis remplacent. */
    private static boolean sol(BlockState s) {
        Block b = s.getBlock();
        return b == Blocks.GRASS_BLOCK || b == Blocks.DIRT || b == Blocks.COARSE_DIRT || b == Blocks.PODZOL
                || b == Blocks.MYCELIUM || b == Blocks.SNOW_BLOCK || b == Blocks.POWDER_SNOW || b == Blocks.SAND
                || b == Blocks.RED_SAND || b == Blocks.GRAVEL || b == Blocks.MUD || b == Blocks.ROOTED_DIRT
                || b == Blocks.MOSS_BLOCK || b == Blocks.CLAY || b == Blocks.SANDSTONE;
    }

    /** Roche des parois : pierre, avec des bancs d'andésite et de tuf. */
    private static BlockState roche(int x, int y, int z) {
        double v = BRUIT.noise(x / 23.0, y / 5.0 + 50, z / 23.0);
        if (v > 0.35) return Blocks.ANDESITE.defaultBlockState();
        if (v < -0.4) return Blocks.TUFF.defaultBlockState();
        return Blocks.STONE.defaultBlockState();
    }

    /** Strates des pays secs : bandes horizontales de 2 à 4 blocs, légèrement ondulées. */
    private static BlockState strate(int y, int x, int z) {
        int k = Mth.floor((y + BRUIT.noise(x / 60.0, 90, z / 60.0) * 3.0) / 3.0);
        return STRATES_SECHES[Math.floorMod(k * 5 + 3, STRATES_SECHES.length)];
    }
}

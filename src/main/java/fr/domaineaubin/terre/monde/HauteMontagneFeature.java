package fr.domaineaubin.terre.monde;

import com.mojang.serialization.Codec;
import fr.domaineaubin.terre.api.LieuxTerre;
import net.minecraft.core.BlockPos;
import net.minecraft.util.Mth;
import net.minecraft.world.level.WorldGenLevel;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.levelgen.Heightmap;
import net.minecraft.world.level.levelgen.feature.Feature;
import net.minecraft.world.level.levelgen.feature.FeaturePlaceContext;
import net.minecraft.world.level.levelgen.feature.configurations.NoneFeatureConfiguration;

import java.util.Set;

/**
 * Haute montagne (10/11/2026, monde agrandi et relief fin) : l'habillage du sol suit l'altitude réelle et la latitude,
 * plus seulement le biome (banc : herbe et arbres au sommet de l'Everest, Oberland tout en herbe).
 * - pente raide (3 blocs ou plus entre voisins) au-dessus de la limite des arbres : roche nue ;
 * - au-dessus de la limite des arbres : éboulis, gravier et roche, quelques plaques d'herbe rase (pelouses alpines) ;
 * - au-dessus de la limite des neiges : neige (roche sur les pentes raides).
 * Limites réelles selon la latitude (neiges : ~5 000 m sous les tropiques, ~5 600 m vers 30° (Himalaya, Andes sèches),
 * ~2 900 m vers 45° (Alpes), ~1 500 m vers 60°, ~600 m vers 70°). Posé avant la végétation (étape local_modifications) :
 * sans herbe ni terre, pas d'arbres. Les lieux gardent leur propre habillage.
 */
public class HauteMontagneFeature extends Feature<NoneFeatureConfiguration> {
    // latitude (°) -> limite des neiges, limite des arbres (m)
    private static final double[] LAT = {0, 20, 30, 40, 45, 50, 60, 70, 90};
    private static final double[] NEIGE = {4900, 5000, 5600, 3600, 2900, 2600, 1500, 600, 0};
    private static final double[] ARBRES = {3800, 3900, 3900, 2600, 2000, 1800, 800, 200, 0};
    private static final Set<Block> MEUBLE = Set.of(Blocks.GRASS_BLOCK, Blocks.DIRT, Blocks.PODZOL, Blocks.COARSE_DIRT,
            Blocks.MYCELIUM, Blocks.ROOTED_DIRT, Blocks.MOSS_BLOCK, Blocks.MUD);

    public HauteMontagneFeature(Codec<NoneFeatureConfiguration> codec) {
        super(codec);
    }

    static double limite(double[] t, double lat) {
        double a = Math.abs(lat);
        for (int i = 1; i < LAT.length; i++) {
            if (a <= LAT[i]) return Mth.lerp((a - LAT[i - 1]) / (LAT[i] - LAT[i - 1]), t[i - 1], t[i]);
        }
        return t[t.length - 1];
    }

    @Override
    public boolean place(FeaturePlaceContext<NoneFeatureConfiguration> ctx) {
        WorldGenLevel n = ctx.level();
        int x0 = ctx.origin().getX() & ~15, z0 = ctx.origin().getZ() & ~15;
        double lat = Terrain.lat(z0 + 8);
        double arbres = Terrain.blocsDepuisAltitude(limite(ARBRES, lat));
        double neige = Terrain.blocsDepuisAltitude(limite(NEIGE, lat));
        // chunk entièrement sous la limite des arbres : rien à faire
        int haut = n.getHeight(Heightmap.Types.OCEAN_FLOOR_WG, x0 + 8, z0 + 8);
        boolean vu = haut >= arbres - 24;
        for (int k = 0; k < 4 && !vu; k++) vu = n.getHeight(Heightmap.Types.OCEAN_FLOOR_WG, x0 + (k & 1) * 15, z0 + (k >> 1) * 15) >= arbres - 24;
        if (!vu) return false;
        BlockPos.MutableBlockPos p = new BlockPos.MutableBlockPos();
        boolean modifie = false;
        for (int dx = 0; dx < 16; dx++) {
            for (int dz = 0; dz < 16; dz++) {
                int x = x0 + dx, z = z0 + dz;
                int y = n.getHeight(Heightmap.Types.OCEAN_FLOOR_WG, x, z) - 1;
                // un peu de bruit sur les limites : pas de ligne droite sur les versants
                double b = Terrain.get().bruit(x / 23.0, 71, z / 23.0) * 6 + Terrain.get().bruit(x / 7.0, 72, z / 7.0) * 2;
                if (y + b < arbres || LieuxTerre.a(x, z) != null) continue;
                if (!n.getFluidState(p.set(x, y + 1, z)).isEmpty()) continue;
                int raide = 0;
                raide = Math.max(raide, Math.abs(y + 1 - n.getHeight(Heightmap.Types.OCEAN_FLOOR_WG, x + 1, z)));
                raide = Math.max(raide, Math.abs(y + 1 - n.getHeight(Heightmap.Types.OCEAN_FLOOR_WG, x - 1, z)));
                raide = Math.max(raide, Math.abs(y + 1 - n.getHeight(Heightmap.Types.OCEAN_FLOOR_WG, x, z + 1)));
                raide = Math.max(raide, Math.abs(y + 1 - n.getHeight(Heightmap.Types.OCEAN_FLOOR_WG, x, z - 1)));
                double v = Mth.clamp(0.5 + 0.7 * Terrain.get().bruit(x / 5.0, 73, z / 5.0), 0.0, 1.0);
                BlockState dessus;
                if (raide >= 3) {
                    dessus = (v > 0.45 ? Blocks.ANDESITE : Blocks.STONE).defaultBlockState();
                } else if (y + b >= neige) {
                    dessus = Blocks.SNOW_BLOCK.defaultBlockState();
                } else {
                    // pelouses alpines, éboulis et roche, de plus en plus minéral en montant vers les neiges
                    double t = Mth.clamp((y + b - arbres) / Math.max(neige - arbres, 1.0), 0.0, 1.0);
                    if (v < 0.35 - 0.9 * t) continue;                                    // herbe rase gardée
                    dessus = (v < 0.55 - 0.3 * t ? Blocks.GRAVEL : v < 0.8 ? Blocks.STONE : Blocks.COBBLESTONE).defaultBlockState();
                }
                for (int k = 0; k < 4; k++) {
                    BlockState s = n.getBlockState(p.set(x, y - k, z));
                    if (!MEUBLE.contains(s.getBlock()) && !(k == 0 && s.is(Blocks.SNOW_BLOCK))) break;
                    n.setBlock(p, k == 0 ? dessus : Blocks.STONE.defaultBlockState(), 2);
                    modifie = true;
                }
                BlockState au = n.getBlockState(p.set(x, y + 1, z));
                if (au.is(Blocks.SNOW) && raide >= 3) n.setBlock(p, Blocks.AIR.defaultBlockState(), 2);
            }
        }
        return modifie;
    }
}

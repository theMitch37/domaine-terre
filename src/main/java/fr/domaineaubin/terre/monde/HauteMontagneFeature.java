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

    /** Altitude réelle (m) : relief fin s'il est là, sinon la carte 3'. */
    private static double altitude(int x, int z) {
        double a = ReliefFin.altitude(x, z);
        return Double.isNaN(a) ? Terrain.get().altitudeReelle(x, z) : a;
    }

    @Override
    public boolean place(FeaturePlaceContext<NoneFeatureConfiguration> ctx) {
        WorldGenLevel n = ctx.level();
        int x0 = ctx.origin().getX() & ~15, z0 = ctx.origin().getZ() & ~15;
        double lat = Terrain.lat(z0 + 8);
        // limites en mètres réels (10/11/2026 : avec le relief fin, une hauteur en blocs ne dit pas l'altitude réelle ;
        // la règle se fait sur la vraie altitude du lieu)
        double arbres = limite(ARBRES, lat), neige = limite(NEIGE, lat);
        boolean vu = false;
        for (int k = 0; k < 5 && !vu; k++) {
            int x = k == 4 ? x0 + 8 : x0 + (k & 1) * 15, z = k == 4 ? z0 + 8 : z0 + (k >> 1) * 15;
            vu = altitude(x, z) >= arbres - 400;
        }
        if (!vu) return false;
        BlockPos.MutableBlockPos p = new BlockPos.MutableBlockPos();
        boolean modifie = false;
        for (int dx = 0; dx < 16; dx++) {
            for (int dz = 0; dz < 16; dz++) {
                int x = x0 + dx, z = z0 + dz;
                int y = n.getHeight(Heightmap.Types.OCEAN_FLOOR_WG, x, z) - 1;
                // un peu de bruit sur les limites (en mètres) : pas de ligne droite sur les versants
                double b = Terrain.get().bruit(x / 23.0, 71, z / 23.0) * 150 + Terrain.get().bruit(x / 7.0, 72, z / 7.0) * 50;
                double alt = altitude(x, z) + b;
                if (alt < arbres || LieuxTerre.a(x, z) != null) continue;
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
                } else if (alt >= neige) {
                    dessus = Blocks.SNOW_BLOCK.defaultBlockState();
                } else {
                    // pelouses alpines, éboulis et roche, de plus en plus minéral en montant vers les neiges (Alpes :
                    // surtout des alpages juste au-dessus des arbres, surtout de la roche sous les glaciers)
                    double t = Mth.clamp((alt - arbres) / Math.max(neige - arbres, 1.0), 0.0, 1.0);
                    if (v < 0.8 - 1.1 * t) continue;                                     // herbe rase gardée
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

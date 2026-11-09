package fr.domaineaubin.terre.monde;

import com.mojang.serialization.Codec;
import net.minecraft.core.BlockPos;
import net.minecraft.util.Mth;
import net.minecraft.util.RandomSource;
import net.minecraft.world.level.WorldGenLevel;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.levelgen.Heightmap;
import net.minecraft.world.level.levelgen.feature.Feature;
import net.minecraft.world.level.levelgen.feature.FeaturePlaceContext;
import net.minecraft.world.level.levelgen.feature.configurations.NoneFeatureConfiguration;
import net.minecraft.world.level.levelgen.synth.ImprovedNoise;

/**
 * Sol du monde 1:30 (09/11/2026) : les biomes viennent d'une carte grossière (Grand Canyon vert). Chaque colonne croise
 * <ul>
 * <li>la couverture réelle du sol (ESA WorldCover 10 m, ReliefFin.sol) : sol nu, neige et glace, broussailles,
 * mousses et lichens, zones humides ;</li>
 * <li>la vraie roche (Macrostrat) : grès en strates rouges et ocre, calcaire clair, basalte noir, granite… ;</li>
 * <li>la vraie pente (relief 30 m) : au-delà de ~48° la roche est à nu (la neige ne tient pas), éboulis en altitude.</li>
 * </ul>
 * Sans données de sol (paquet absent), seule la pente compte (roche grise). Posé avant la végétation ; les arbres
 * suivent la couverture du sol (mixin ArbresSolMixin). Bruit à graine fixe : le même sol dans tous les mondes.
 */
public class RocheFeature extends Feature<NoneFeatureConfiguration> {
    private static final ImprovedNoise BRUIT = new ImprovedNoise(RandomSource.create(20261109L));

    /** Pente (blocs par bloc) au-delà de laquelle la roche est à nu, et début des éboulis. */
    static final double PAROI = 1.1, EBOULIS = 0.7;
    /** y au-dessus duquel les pentes moyennes sont en éboulis (~1 300 m en 1:30). */
    static final int Y_EBOULIS = 130;

    // familles de roche : mêmes numéros que outils/sol30.py (ROCHES)
    static final int INCONNUE = 0, GRES = 1, ARGILE = 2, CALCAIRE = 3, DOLOMIE = 4, CRAIE = 5, CONGLOMERAT = 6,
            EVAPORITE = 7, BASALTE = 8, ANDESITE = 9, TUF = 10, GRANITE = 11, GABBRO = 12, GNEISS = 13, QUARTZITE = 14,
            MARBRE = 15, MEUBLE = 16, GLACIAIRE = 17, DUNE = 18;
    private static final BlockState[][] PALETTES = new BlockState[19][];
    /** Familles déposées en couches : strates horizontales. */
    private static final boolean[] STRATES = new boolean[19];

    private static BlockState[] p(Block... b) {
        BlockState[] r = new BlockState[b.length];
        for (int i = 0; i < b.length; i++) r[i] = b[i].defaultBlockState();
        return r;
    }

    static {
        PALETTES[INCONNUE] = p(Blocks.STONE, Blocks.ANDESITE, Blocks.STONE, Blocks.TUFF);
        PALETTES[GRES] = p(Blocks.RED_SANDSTONE, Blocks.ORANGE_TERRACOTTA, Blocks.SANDSTONE, Blocks.RED_TERRACOTTA,
                Blocks.TERRACOTTA, Blocks.SMOOTH_SANDSTONE, Blocks.ORANGE_TERRACOTTA);
        PALETTES[ARGILE] = p(Blocks.TERRACOTTA, Blocks.BROWN_TERRACOTTA, Blocks.LIGHT_GRAY_TERRACOTTA,
                Blocks.RED_TERRACOTTA, Blocks.TERRACOTTA);
        PALETTES[CALCAIRE] = p(Blocks.CALCITE, Blocks.DIORITE, Blocks.SMOOTH_STONE, Blocks.WHITE_TERRACOTTA, Blocks.DIORITE);
        PALETTES[DOLOMIE] = p(Blocks.DIORITE, Blocks.CALCITE, Blocks.LIGHT_GRAY_TERRACOTTA, Blocks.DIORITE);
        PALETTES[CRAIE] = p(Blocks.CALCITE, Blocks.WHITE_TERRACOTTA, Blocks.CALCITE);
        PALETTES[CONGLOMERAT] = p(Blocks.TUFF, Blocks.ANDESITE, Blocks.GRANITE, Blocks.TERRACOTTA);
        PALETTES[EVAPORITE] = p(Blocks.WHITE_TERRACOTTA, Blocks.CALCITE, Blocks.SMOOTH_SANDSTONE);
        PALETTES[BASALTE] = p(Blocks.BASALT, Blocks.SMOOTH_BASALT, Blocks.BLACKSTONE, Blocks.BASALT);
        PALETTES[ANDESITE] = p(Blocks.ANDESITE, Blocks.TUFF, Blocks.STONE, Blocks.ANDESITE);
        PALETTES[TUF] = p(Blocks.TUFF, Blocks.WHITE_TERRACOTTA, Blocks.ANDESITE, Blocks.TUFF);
        PALETTES[GRANITE] = p(Blocks.STONE, Blocks.GRANITE, Blocks.DIORITE, Blocks.STONE);
        PALETTES[GABBRO] = p(Blocks.DEEPSLATE, Blocks.TUFF, Blocks.ANDESITE, Blocks.DEEPSLATE);
        PALETTES[GNEISS] = p(Blocks.STONE, Blocks.DEEPSLATE, Blocks.ANDESITE, Blocks.TUFF, Blocks.STONE);
        PALETTES[QUARTZITE] = p(Blocks.CALCITE, Blocks.DIORITE, Blocks.WHITE_TERRACOTTA);
        PALETTES[MARBRE] = p(Blocks.CALCITE, Blocks.DIORITE, Blocks.QUARTZ_BLOCK);
        PALETTES[MEUBLE] = p(Blocks.GRAVEL, Blocks.COARSE_DIRT, Blocks.SAND, Blocks.GRAVEL);
        PALETTES[GLACIAIRE] = p(Blocks.GRAVEL, Blocks.COARSE_DIRT, Blocks.STONE, Blocks.GRAVEL);
        PALETTES[DUNE] = p(Blocks.SAND, Blocks.SAND, Blocks.SANDSTONE);
        for (int f : new int[]{GRES, ARGILE, CALCAIRE, DOLOMIE, CRAIE, CONGLOMERAT, EVAPORITE, TUF}) STRATES[f] = true;
    }

    /**
     * Aridité 0..1 autour d'un point, d'après la vraie couverture du sol (WorldCover) sur ~2 km : part des
     * broussailles et du sol nu parmi les terres. Le Grand Canyon (broussailles + roche) est sec, la Beauce
     * (cultures) ne l'est pas. En attendant une couche climatique (Köppen), c'est la meilleure mesure qu'on ait.
     */
    static double aridite(int cx, int cz) {
        int sec = 0, terre = 0;
        for (int i = -3; i <= 3; i++)
            for (int j = -3; j <= 3; j++) {
                int s = ReliefFin.sol(cx + i * 96, cz + j * 96);
                if (s < 0) continue;
                int c = s & 255;
                if (c == 80 || c == 70 || c == 0) continue;     // eau, glace, sans donnée
                terre++;
                if (c == 20 || c == 60) sec++;
            }
        if (terre < 10) return 0;
        return Mth.clamp((sec / (double) terre - 0.3) / 0.4, 0.0, 1.0);
    }

    /**
     * Aridité d'après le climat réel (Köppen-Geiger, Beck et al. 2023, déjà dans le mod) : désert 1, steppe 0,75,
     * méditerranéen à été sec 0,35. Le plateau du Grand Canyon (steppe froide BSk) est sec même sous les genévriers.
     */
    static double climatSec(Terrain t, int x, int z) {
        int k = t.carte().climat(Terrain.lon(x + 0.5), Terrain.lat(z + 0.5));
        return switch (k) {
            case 4, 5 -> 1.0;                                   // BWh, BWk : désert
            case 6, 7 -> 0.75;                                  // BSh, BSk : steppe
            case 8, 17 -> 0.35;                                 // Csa, Dsa : été chaud et sec
            default -> 0.0;
        };
    }

    /** Sol sec : terre grossière, sable rouge sur grès et argiles, ou le haut de la roche du lieu. */
    private static BlockState sec(int roche, double b, int x, int z) {
        if (b > 0.3 && roche != INCONNUE) return PALETTES[roche][0];
        if ((roche == GRES || roche == ARGILE || roche == CONGLOMERAT) && b > -0.2) return Blocks.RED_SAND.defaultBlockState();
        return Blocks.COARSE_DIRT.defaultBlockState();
    }

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
        double aride = Math.max(aridite(x0 + 8, z0 + 8), climatSec(t, x0 + 8, z0 + 8));
        double[] h = new double[18 * 18];
        for (int dz = -1; dz <= 16; dz++)
            for (int dx = -1; dx <= 16; dx++)
                h[(dz + 1) * 18 + dx + 1] = t.hauteur(x0 + dx, z0 + dz);
        for (int dz = 0; dz < 16; dz++) {
            for (int dx = 0; dx < 16; dx++) {
                int x = x0 + dx, z = z0 + dz, i = (dz + 1) * 18 + dx + 1;
                double gx = (h[i + 1] - h[i - 1]) * 0.5, gz = (h[i + 18] - h[i - 18]) * 0.5;
                double pente = Math.sqrt(gx * gx + gz * gz);
                int s = ReliefFin.sol(x, z);
                int cov = s < 0 ? -1 : s & 255, roche = s < 0 ? INCONNUE : Math.min(s >> 8, 18);
                int y = n.getHeight(Heightmap.Types.WORLD_SURFACE_WG, x, z) - 1;
                if (y <= Terrain.NIVEAU_MER) continue;
                if (!n.getBlockState(p.set(x, y, z)).getFluidState().isEmpty()) continue;
                double b = BRUIT.noise(x / 9.0, y / 7.0, z / 9.0);
                // berges des cours d'eau (couche d'eau 1:30) : rives meubles, pas de roche à nu le long des ruisseaux
                int e = ReliefFin.eau(x, z);
                if (e >= 0 && (e & 15) >= 8 && (e & 15) <= 11 && cov != 60) {
                    boolean haut = cov == 70 || cov == 100 || y >= Y_EBOULIS;
                    // pays sec : seul le bord immédiat de l'eau reste vert (ripisylve d'un bloc), le reste suit le sol
                    if (!haut && (aride < 0.5 || (e & 15) == 8)) continue;
                    if (!haut) e = -1;
                    // en haute montagne : un liseré de gravier au bord du torrent (1 à 2 blocs), puis le sol normal
                    // (glacier, toundra, éboulis) ; des rives larges faisaient des bandes droites dans les alpages
                    if ((e & 15) <= 9) {
                        pose |= remplacer(n, p, x, y, z, b > 0.2 ? Blocks.COBBLESTONE.defaultBlockState()
                                : Blocks.GRAVEL.defaultBlockState());
                        continue;
                    }
                }
                boolean paroi = pente >= PAROI + 0.15 * b;
                if (paroi || cov == 60 || (cov == 70 && pente > 0.8)) {
                    // roche à nu (ou sol nu) : la vraie roche ; sur le plat, les roches meubles donnent sable et gravier
                    pose |= recouvrir(n, p, x, y, z, roche, cov == 60 && !paroi ? 2 : 5);
                } else if (cov == 70) {
                    pose |= glace(n, p, x, y, z);
                } else if (cov == 20) {                         // broussailles : terre sèche entre les touffes
                    // pays sec : presque plus d'herbe, le sol et la roche affleurent
                    if (b > -0.05 - 0.5 * aride) pose |= remplacer(n, p, x, y, z, sec(roche, b, x, z));
                } else if (cov == 10 && aride >= 0.5) {         // bois clairs de pays sec : sol nu entre les arbres
                    if (b > 0.45 - 0.9 * aride) pose |= remplacer(n, p, x, y, z, b > 0.1 ? Blocks.PODZOL.defaultBlockState()
                            : sec(roche, b, x, z));
                } else if (cov == 30 && aride > 0) {            // prairie de pays sec : steppe rase
                    if (b > 0.35 - 0.75 * aride) pose |= remplacer(n, p, x, y, z, sec(roche, b, x, z));
                } else if (cov == 100) {                        // mousses et lichens (toundra)
                    pose |= remplacer(n, p, x, y, z, b > 0.15 ? Blocks.MOSS_BLOCK.defaultBlockState()
                            : b > -0.2 ? Blocks.COARSE_DIRT.defaultBlockState() : Blocks.GRAVEL.defaultBlockState());
                } else if (cov == 90) {                         // zone humide
                    if (b > 0.1) pose |= remplacer(n, p, x, y, z, Blocks.MUD.defaultBlockState());
                } else if (pente >= EBOULIS && y >= Y_EBOULIS - 8 * b && b > -0.1) {
                    pose |= remplacer(n, p, x, y, z, roche == INCONNUE || roche == GRANITE || roche == GNEISS
                            ? (b > 0.25 ? Blocks.GRAVEL.defaultBlockState() : Blocks.COARSE_DIRT.defaultBlockState())
                            : (b > 0.25 ? Blocks.GRAVEL.defaultBlockState() : PALETTES[roche][1]));
                }
            }
        }
        return pose;
    }

    /** Remplace la couche de sol du dessus (herbe, terre…) par un bloc ; enlève neige et herbes au-dessus. */
    private static boolean remplacer(WorldGenLevel n, BlockPos.MutableBlockPos p, int x, int y, int z, BlockState v) {
        BlockState s = n.getBlockState(p.set(x, y, z));
        if (s.is(Blocks.SNOW) || s.canBeReplaced()) {
            n.setBlock(p, Blocks.AIR.defaultBlockState(), 2);
            y--;
            s = n.getBlockState(p.set(x, y, z));
        }
        if (!sol(s)) return false;
        n.setBlock(p, v, 2);
        return true;
    }

    /** Roche de la famille sur `prof` blocs (neige et herbes du dessus enlevées). */
    private static boolean recouvrir(WorldGenLevel n, BlockPos.MutableBlockPos p, int x, int y, int z, int roche, int prof) {
        boolean pose = false;
        BlockState s = n.getBlockState(p.set(x, y, z));
        if (s.is(Blocks.SNOW) || s.canBeReplaced()) {
            n.setBlock(p, Blocks.AIR.defaultBlockState(), 2);
            y--;
        }
        for (int k = 0; k < prof; k++) {
            s = n.getBlockState(p.set(x, y - k, z));
            if (!sol(s) && !s.is(Blocks.STONE) && !s.is(Blocks.DEEPSLATE)) break;
            n.setBlock(p, bloc(roche, x, y - k, z), 2);
            pose = true;
        }
        return pose;
    }

    /** Glacier ou névé (couverture neige et glace sur le plat) : neige en surface, glace dessous. */
    private static boolean glace(WorldGenLevel n, BlockPos.MutableBlockPos p, int x, int y, int z) {
        BlockState s = n.getBlockState(p.set(x, y, z));
        if (s.is(Blocks.SNOW) || s.canBeReplaced()) {
            n.setBlock(p, Blocks.AIR.defaultBlockState(), 2);
            y--;
        }
        boolean pose = false;
        for (int k = 0; k < 4; k++) {
            s = n.getBlockState(p.set(x, y - k, z));
            if (!sol(s) && !s.is(Blocks.STONE)) break;
            n.setBlock(p, k == 0 ? Blocks.SNOW_BLOCK.defaultBlockState() : Blocks.PACKED_ICE.defaultBlockState(), 2);
            pose = true;
        }
        return pose;
    }

    /** Couche de sol que la roche, la glace ou les éboulis remplacent. */
    private static boolean sol(BlockState s) {
        Block b = s.getBlock();
        return b == Blocks.GRASS_BLOCK || b == Blocks.DIRT || b == Blocks.COARSE_DIRT || b == Blocks.PODZOL
                || b == Blocks.MYCELIUM || b == Blocks.SNOW_BLOCK || b == Blocks.POWDER_SNOW || b == Blocks.SAND
                || b == Blocks.RED_SAND || b == Blocks.GRAVEL || b == Blocks.MUD || b == Blocks.ROOTED_DIRT
                || b == Blocks.MOSS_BLOCK || b == Blocks.CLAY || b == Blocks.SANDSTONE || b == Blocks.TERRACOTTA;
    }

    /** Bloc de roche d'une famille : strates horizontales (2 à 4 blocs, ondulées) ou bancs irréguliers. */
    static BlockState bloc(int roche, int x, int y, int z) {
        BlockState[] pal = PALETTES[roche];
        if (STRATES[roche]) {
            int k = Mth.floor((y + BRUIT.noise(x / 60.0, 90, z / 60.0) * 3.0) / 3.0);
            return pal[Math.floorMod(k * 5 + 3, pal.length)];
        }
        double v = BRUIT.noise(x / 13.0, y / 6.0 + 50, z / 13.0);
        int i = Mth.clamp((int) ((v + 0.6) / 1.2 * pal.length), 0, pal.length - 1);
        return pal[i];
    }
}

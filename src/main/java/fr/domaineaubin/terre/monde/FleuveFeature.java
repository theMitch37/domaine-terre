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
                if (w != Terrain.SANS_LAC && DIAG.get() < 30) {
                    int v = t.eauLit(x + 1, z), u = t.eauLit(x, z + 1);
                    if ((v != Terrain.SANS_LAC && Math.abs(v - w) > 8) || (u != Terrain.SANS_LAC && Math.abs(u - w) > 8)) {
                        DIAG.incrementAndGet();
                        fr.domaineaubin.terre.DomaineTerre.LOGGER.info("DIAG eau {} {} : {} | x+1 : {} | z+1 : {}", x, z,
                                t.diagnosticRiviere(x, z), t.diagnosticRiviere(x + 1, z), t.diagnosticRiviere(x, z + 1));
                    }
                }
                // abords du lit : seulement les creux sous le niveau de la rivière (11/11/2026)
                if (w == Terrain.SANS_LAC) w = t.eauAbords(x, z);
                if (w == Terrain.SANS_LAC) continue;
                // de la surface de l'eau vers le bas, tant qu'il y a de l'air (la carte de hauteur du moteur n'est pas
                // fiable ici : un lieu vient peut-être de creuser son lit dans ce chunk, StratesFeature)
                boolean eauEnHaut = false, mouille = false;
                for (int y = w - 1; y >= w - 64; y--) {
                    BlockState b = niveau.getBlockState(pos.set(x, y, z));
                    // une plante (herbe, fleur) posée par la végétation d'un chunk voisin avant que ce lit ne soit
                    // rempli n'est pas le fond (11/11/2026, banc : herbe au fond du Danube sous 5 blocs d'eau)
                    if (b.isAir() || plante(b)) {
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
        modifie |= pentes(niveau, t, x0, z0, pos);
        // mer à sec (11/11/2026, banc : estuaires de l'Indus et de la Gambie, centaines de colonnes de vase ou de sable à
        // l'air sous le niveau de la mer) : l'aquifère tire l'eau de cellules espacées de 16 blocs ; quand la cellule
        // tombe dans le lit d'un cours d'eau (sans aquifère), les pixels de mer voisins restaient secs. La mer est
        // remplie ici jusqu'à son niveau.
        for (int dx = 0; dx < 16; dx++) {
            for (int dz = 0; dz < 16; dz++) {
                int x = x0 + dx, z = z0 + dz;
                if (t.eauLit(x, z) != Terrain.SANS_LAC) continue;
                // aussi les creux de la côte sous le niveau de la mer (11/11/2026, banc : vase à sec dans les deltas du
                // Mékong et du Niger, 1 à 3 blocs sous la mer à côté d'elle) ; seulement à moins de ~20 blocs de la côte
                if (!t.enMer(x, z) && t.distanceCote(x, z) > 2.5) continue;
                for (int y = Terrain.NIVEAU_MER - 1; y >= Terrain.NIVEAU_MER - 64; y--) {
                    BlockState b = niveau.getBlockState(pos.set(x, y, z));
                    if (!b.isAir() && !plante(b)) break;
                    niveau.setBlock(pos, eau, 2);
                    modifie = true;
                }
            }
        }
        // poches d'air sous l'eau (12/11/2026, test en jeu : « des zones sans eau dans la mer », Jökulsárlón, Skógafoss) :
        // les nappes d'eau du jeu laissent parfois de l'air sous une couche d'eau, sans bloc entre les deux ; de la
        // surface jusqu'au fond, un air coincé sous de l'eau devient de l'eau
        for (int dx = 0; dx < 16; dx++) {
            for (int dz = 0; dz < 16; dz++) {
                int x = x0 + dx, z = z0 + dz;
                int fond = niveau.getHeight(Heightmap.Types.OCEAN_FLOOR_WG, x, z);
                int haut = niveau.getHeight(Heightmap.Types.WORLD_SURFACE_WG, x, z) - 1;
                boolean sousEau = false;
                for (int y = haut; y >= fond; y--) {
                    BlockState b = niveau.getBlockState(pos.set(x, y, z));
                    if (b.is(Blocks.WATER)) {
                        sousEau = true;
                    } else if (sousEau && (b.isAir() || plante(b))) {
                        // une poche (12 blocs au plus, fermée par un fond) ; pas le vide sous une chute d'eau
                        int n = 0;
                        while (n < 13 && y - n >= fond && niveau.getBlockState(pos.set(x, y - n, z)).isAir()) n++;
                        if (n > 12) {
                            sousEau = false;
                            y -= n - 1;
                            continue;
                        }
                        for (int k = 0; k < n; k++) niveau.setBlock(pos.set(x, y - k, z), eau, 2);
                        if (n == 0) niveau.setBlock(pos.set(x, y, z), eau, 2);
                        y -= Math.max(n - 1, 0);
                        modifie = true;
                    } else if (!b.isAir() && b.getFluidState().isEmpty()) {
                        sousEau = false;
                    }
                }
            }
        }
        // herbe sous l'eau hors des lits (bord des lacs, plats de la côte, 11/11/2026, banc : 130 à 330 colonnes par
        // zone, sous 1 à 2 blocs d'eau surtout) : les règles de surface ne voient pas l'eau des aquifères du mod ; sous
        // l'eau, le fond du lit
        for (int dx = 0; dx < 16; dx++) {
            for (int dz = 0; dz < 16; dz++) {
                int x = x0 + dx, z = z0 + dz;
                int y = niveau.getHeight(Heightmap.Types.OCEAN_FLOOR_WG, x, z) - 1;
                BlockState b = niveau.getBlockState(pos.set(x, y, z));
                if (!(b.is(Blocks.GRASS_BLOCK) || b.is(Blocks.PODZOL) || b.is(Blocks.MYCELIUM) || b.is(Blocks.DIRT_PATH)))
                    continue;
                if (!niveau.getBlockState(pos.set(x, y + 1, z)).is(Blocks.WATER)) continue;
                niveau.setBlock(pos.set(x, y, z), fond(t, x, z), 2);
                modifie = true;
            }
        }
        return modifie;
    }

    /**
     * Pentes d'eau au pied des marches (11/11/2026, test en jeu sur le Danube : « que les niveaux d'eau restent en
     * diagonale plutôt que de s'égaliser en gros carrés ») : le niveau d'un cours d'eau baisse d'un bloc d'un coup, ce
     * qui fait deux grandes plaques plates séparées par une ligne droite. Sur le bief du dessous, une nappe d'eau qui coule
     * descend depuis la marche sur 7 blocs, exactement comme le jeu la ferait couler (quantité 7 contre la marche, puis
     * un de moins par bloc) : la surface descend en pente et reste stable quand l'eau est mise à jour.
     */
    private static boolean pentes(WorldGenLevel niveau, Terrain t, int x0, int z0, BlockPos.MutableBlockPos pos) {
        final int M = 7, N = 16 + 2 * M;
        int[] w = new int[N * N];
        boolean marche = false;
        for (int i = 0; i < N; i++) {
            for (int j = 0; j < N; j++) {
                int v = t.eauLit(x0 - M + i, z0 - M + j);
                w[i * N + j] = v;
                if (v != Terrain.SANS_LAC && !marche && i > 0) {
                    int u = w[(i - 1) * N + j];
                    if (u != Terrain.SANS_LAC && Math.abs(u - v) == 1) marche = true;
                }
                if (v != Terrain.SANS_LAC && !marche && j > 0) {
                    int u = w[i * N + j - 1];
                    if (u != Terrain.SANS_LAC && Math.abs(u - v) == 1) marche = true;
                }
            }
        }
        if (!marche) return false;
        // distance (pas de 4 voisins, comme l'eau qui coule) à une colonne du lit plus haute d'un bloc, sur le même bief
        int[] d = new int[N * N];
        java.util.Arrays.fill(d, Integer.MAX_VALUE);
        java.util.ArrayDeque<Integer> file = new java.util.ArrayDeque<>();
        for (int i = 0; i < N; i++) {
            for (int j = 0; j < N; j++) {
                int v = w[i * N + j];
                if (v == Terrain.SANS_LAC) continue;
                for (int k = 0; k < 4; k++) {
                    int ii = i + (k == 0 ? 1 : k == 1 ? -1 : 0), jj = j + (k == 2 ? 1 : k == 3 ? -1 : 0);
                    if (ii < 0 || jj < 0 || ii >= N || jj >= N) continue;
                    if (w[ii * N + jj] == v + 1) {
                        d[i * N + j] = 1;
                        file.add(i * N + j);
                        break;
                    }
                }
            }
        }
        while (!file.isEmpty()) {
            int c = file.poll(), i = c / N, j = c % N;
            if (d[c] >= M) continue;
            for (int k = 0; k < 4; k++) {
                int ii = i + (k == 0 ? 1 : k == 1 ? -1 : 0), jj = j + (k == 2 ? 1 : k == 3 ? -1 : 0);
                if (ii < 0 || jj < 0 || ii >= N || jj >= N) continue;
                int e = ii * N + jj;
                if (w[e] != w[c] || d[e] <= d[c] + 1) continue;
                d[e] = d[c] + 1;
                file.add(e);
            }
        }
        boolean modifie = false;
        for (int dx = 0; dx < 16; dx++) {
            for (int dz = 0; dz < 16; dz++) {
                int c = (dx + M) * N + dz + M;
                if (d[c] > M) continue;
                int v = w[c];
                // la nappe se pose sur l'eau du bief (surface en v - 1), dans l'air juste au-dessus
                if (!niveau.getBlockState(pos.set(x0 + dx, v - 1, z0 + dz)).is(Blocks.WATER)) continue;
                if (!niveau.getBlockState(pos.set(x0 + dx, v, z0 + dz)).isAir()) continue;
                niveau.setBlock(pos, Fluids.FLOWING_WATER.getFlowing(8 - d[c], false).createLegacyBlock(), 2);
                modifie = true;
            }
        }
        return modifie;
    }

    /** Plante terrestre que l'eau remplace (herbe, fougère, fleur, buisson). */
    private static boolean plante(BlockState b) {
        return b.getFluidState().isEmpty() && b.canBeReplaced() && !b.is(Blocks.SNOW) && !b.isAir()
                || b.is(net.minecraft.tags.BlockTags.SMALL_FLOWERS);
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

    private static final java.util.concurrent.atomic.AtomicInteger DIAG = new java.util.concurrent.atomic.AtomicInteger();

    private static boolean plusBas(Terrain t, int x, int z, int w) {
        int v = t.eauLit(x, z);
        return v != Terrain.SANS_LAC && v < w;
    }
}

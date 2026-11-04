package fr.domaineaubin.lieux;

import com.mojang.serialization.Codec;
import it.unimi.dsi.fastutil.ints.IntArrayList;
import it.unimi.dsi.fastutil.longs.Long2ObjectOpenHashMap;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.world.level.WorldGenLevel;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.PointedDripstoneBlock;
import net.minecraft.world.level.block.RotatedPillarBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.properties.DripstoneThickness;
import net.minecraft.world.level.levelgen.feature.Feature;
import net.minecraft.world.level.levelgen.feature.FeaturePlaceContext;
import net.minecraft.world.level.levelgen.feature.configurations.NoneFeatureConfiguration;

import java.io.DataInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.UncheckedIOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.zip.GZIPInputStream;

/**
 * Grottes célèbres (MAJ 1 : Padirac, Han, Postojna, Eisriesenwelt, Fingal, grotte bleue de Capri), calculées hors du
 * jeu (outils/grottes.py) et posées bloc par bloc, chunk par chunk, à l'étape « décoration souterraine » de tous les
 * biomes de l'Overworld (après les grottes vanilla, avant la végétation). Une coque rebouche les grottes et les lacs
 * vanilla qui les traverseraient. Rien n'est posé ailleurs que dans le chunk en cours.
 */
public class GrottesFeature extends Feature<NoneFeatureConfiguration> {
    static final int AIR = 200, EAU = 201, PLEIN = 202, CALCITE = 203, DRIPSTONE = 204, GRAVIER = 205, ARGILE = 206,
            SABLE = 207, GLACE_TASSEE = 208, GLACE_BLEUE = 209, GLACE = 210, NEIGE = 211, LANTERNE = 212,
            BASALTE = 213, BASALTE_POLI = 214, BASALTE_LISSE = 215, MOUSSE = 216;

    /** Blocs de chaque chunk : (x & 15) | (z & 15) << 4 | (y + 64) << 8 | classe << 17. */
    private static volatile Long2ObjectOpenHashMap<int[]> blocs;

    public GrottesFeature(Codec<NoneFeatureConfiguration> codec) {
        super(codec);
    }

    private static long cle(int cx, int cz) {
        return ((long) cx << 32) ^ (cz & 0xFFFFFFFFL);
    }

    private static Long2ObjectOpenHashMap<int[]> blocs() {
        Long2ObjectOpenHashMap<int[]> b = blocs;
        if (b != null) return b;
        synchronized (GrottesFeature.class) {
            if (blocs != null) return blocs;
            Long2ObjectOpenHashMap<IntArrayList> tmp = new Long2ObjectOpenHashMap<>();
            try (InputStream in = GrottesFeature.class.getResourceAsStream("/domaine_terre_lieux/grottes.bin")) {
                if (in != null) {
                    ByteBuffer buf = ByteBuffer.wrap(new GZIPInputStream(in).readAllBytes()).order(ByteOrder.LITTLE_ENDIAN);
                    int n = buf.getInt();
                    for (int i = 0; i < n; i++) {
                        int x = buf.getInt(), y = buf.getInt(), z = buf.getInt(), c = buf.get() & 0xFF;
                        if (y < -64 || y > 319) continue;
                        int v = (x & 15) | (z & 15) << 4 | (y + 64) << 8 | c << 17;
                        tmp.computeIfAbsent(cle(x >> 4, z >> 4), k -> new IntArrayList()).add(v);
                    }
                }
            } catch (IOException e) {
                throw new UncheckedIOException("Impossible de charger grottes.bin", e);
            }
            b = new Long2ObjectOpenHashMap<>(tmp.size());
            for (var e : tmp.long2ObjectEntrySet()) b.put(e.getLongKey(), e.getValue().toIntArray());
            DomaineLieux.LOGGER.info("Grottes : {} chunks", b.size());
            blocs = b;
            return b;
        }
    }

    /** Colonne dans l'emprise d'une grotte célèbre (son chunk ou un chunk voisin) ? */
    public static boolean dansGrotte(int x, int z) {
        Long2ObjectOpenHashMap<int[]> b = blocs();
        int cx = x >> 4, cz = z >> 4;
        for (int dx = -1; dx <= 1; dx++) {
            for (int dz = -1; dz <= 1; dz++) {
                if (b.containsKey(cle(cx + dx, cz + dz))) return true;
            }
        }
        return false;
    }

    @Override
    public boolean place(FeaturePlaceContext<NoneFeatureConfiguration> ctx) {
        WorldGenLevel niveau = ctx.level();
        int cx = ctx.origin().getX() >> 4, cz = ctx.origin().getZ() >> 4;
        int[] l = blocs().get(cle(cx, cz));
        if (l == null) return false;
        BlockPos.MutableBlockPos pos = new BlockPos.MutableBlockPos();
        int x0 = cx << 4, z0 = cz << 4;
        for (int v : l) {
            int x = x0 + (v & 15), z = z0 + ((v >> 4) & 15), y = ((v >> 8) & 511) - 64, c = (v >> 17) & 255;
            pos.set(x, y, z);
            if (c == PLEIN) {
                BlockState b = niveau.getBlockState(pos);
                if (b.isAir() || !b.getFluidState().isEmpty())
                    niveau.setBlock(pos, (y < 0 ? Blocks.DEEPSLATE : Blocks.STONE).defaultBlockState(), 2);
                continue;
            }
            BlockState b = etat(c, x, y, z);
            if (b != null) niveau.setBlock(pos, b, 2);
        }
        return true;
    }

    private static BlockState pointe(Direction d, DripstoneThickness t) {
        return Blocks.POINTED_DRIPSTONE.defaultBlockState().setValue(PointedDripstoneBlock.TIP_DIRECTION, d)
                .setValue(PointedDripstoneBlock.THICKNESS, t);
    }

    private static BlockState etat(int c, int x, int y, int z) {
        return switch (c) {
            case AIR -> Blocks.CAVE_AIR.defaultBlockState();
            case EAU -> Blocks.WATER.defaultBlockState();
            case CALCITE -> Blocks.CALCITE.defaultBlockState();
            case DRIPSTONE -> Blocks.DRIPSTONE_BLOCK.defaultBlockState();
            case GRAVIER -> Blocks.GRAVEL.defaultBlockState();
            case ARGILE -> Blocks.CLAY.defaultBlockState();
            case SABLE -> Blocks.SAND.defaultBlockState();
            case GLACE_TASSEE -> Blocks.PACKED_ICE.defaultBlockState();
            case GLACE_BLEUE -> Blocks.BLUE_ICE.defaultBlockState();
            case GLACE -> Blocks.ICE.defaultBlockState();
            case NEIGE -> Blocks.SNOW_BLOCK.defaultBlockState();
            case LANTERNE -> Blocks.SEA_LANTERN.defaultBlockState();
            case BASALTE -> Blocks.BASALT.defaultBlockState().setValue(RotatedPillarBlock.AXIS, Direction.Axis.Y);
            case BASALTE_POLI -> Blocks.POLISHED_BASALT.defaultBlockState().setValue(RotatedPillarBlock.AXIS, Direction.Axis.Y);
            case BASALTE_LISSE -> Blocks.SMOOTH_BASALT.defaultBlockState();
            case MOUSSE -> Blocks.MOSS_BLOCK.defaultBlockState();
            case 220 -> pointe(Direction.UP, DripstoneThickness.BASE);
            case 221 -> pointe(Direction.UP, DripstoneThickness.MIDDLE);
            case 222 -> pointe(Direction.UP, DripstoneThickness.FRUSTUM);
            case 223 -> pointe(Direction.UP, DripstoneThickness.TIP);
            case 225 -> pointe(Direction.DOWN, DripstoneThickness.BASE);
            case 226 -> pointe(Direction.DOWN, DripstoneThickness.MIDDLE);
            case 227 -> pointe(Direction.DOWN, DripstoneThickness.FRUSTUM);
            case 228 -> pointe(Direction.DOWN, DripstoneThickness.TIP);
            default -> null;
        };
    }
}

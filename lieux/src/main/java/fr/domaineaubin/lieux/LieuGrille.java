package fr.domaineaubin.lieux;

import fr.domaineaubin.terre.monde.Terrain;
import it.unimi.dsi.fastutil.longs.Long2ObjectOpenHashMap;
import net.minecraft.core.BlockPos;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.level.WorldGenLevel;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;

import java.io.DataInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.UncheckedIOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.ArrayList;
import java.util.List;
import java.util.zip.GZIPInputStream;

/**
 * Lieu « en grille » : toute la forme est calculée hors du jeu (outils/lieux_cotiers.py), au bloc près en 1:250,
 * sur le trait de côte exact du mod. Ce code ne fait que relire les grilles (ReliefLieu) :
 * 0 = écart de hauteur avec le terrain du mod (x 16), 1 = dessus des couches (x 16), 2 = classe + drapeaux,
 * 3 = emprise du lieu (x 1000, voir {@link fr.domaineaubin.terre.api.Lieu#poids}).
 * Les arches (surplombs) sont dans un fichier .vox à part. Le rendu outils/rendu_grille.py relit les mêmes données.
 */
public final class LieuGrille implements LieuSculpte {
    /** Classes de matériau (bits 0-3 de la grille 2), comme dans lieux_cotiers.py. */
    static final int CREUSE = 0, PLATEAU = 1, PLAGE = 2, FOND = 3, ROC = 4, AIGUILLE = 5, DUNE = 6, VASE = 7, CHENAL = 8, PRE = 9, SABLE = 10;
    static final int TAILLEE = 16, REMBLAI = 32, BIOME = 64, INONDE = 128;

    /** Palettes de roches. */
    public enum Palette { CRAIE, CRAIE_PURE, MOHER, DUNE, BAIE }

    private final String id;
    private final Palette palette;
    /** Grille lon/lat (ancien format), ou null pour un lieu en tuiles ({@link Tuiles}). */
    private final ReliefLieu relief;
    private volatile Long2ObjectOpenHashMap<List<int[]>> surplombs;

    public LieuGrille(String id, Palette palette) {
        this(id, palette, false);
    }

    /** @param enTuiles le lieu est sculpté dans les tuiles (hauteurs exactes, bords recollés au terrain calculé) */
    public LieuGrille(String id, Palette palette, boolean enTuiles) {
        this.id = id;
        this.palette = palette;
        this.relief = enTuiles ? null : new ReliefLieu(id + ".bin");
    }

    @Override
    public String id() {
        return id;
    }

    @Override
    public ResourceLocation biome() {
        return new ResourceLocation(DomaineLieux.MOD_ID, id);
    }

    private int type(int x, int z) {
        if (relief == null) return Tuiles.type(x, z);
        return relief.valeur(2, Terrain.lon(x), Terrain.lat(z)) & 0xFF;
    }

    private double dessusCouches(int x, int z) {
        if (relief == null) return Tuiles.sommet(x, z);
        return relief.echant(1, Terrain.lon(x), Terrain.lat(z)) / 16.0;
    }

    // ---------------------------------------------------------------- Lieu

    @Override
    public boolean concerne(int x, int z) {
        if (relief == null) return id.equals(Tuiles.lieu(x, z));
        return relief.contient(x, z);
    }

    @Override
    public double hauteur(int x, int z, double h) {
        if (relief == null) {
            double t = Tuiles.hauteur(x, z);
            return Double.isNaN(t) ? h : t;
        }
        return h + relief.echant(0, Terrain.lon(x), Terrain.lat(z)) / 16.0;
    }

    @Override
    public double poids(int x, int z) {
        if (!concerne(x, z)) return 0.0;
        if (relief == null) return 1.0;      // tuile : la colonne sculptée suit exactement sa hauteur
        return relief.echant(3, Terrain.lon(x), Terrain.lat(z)) / 1000.0;
    }

    @Override
    public boolean dansBiome(int x, int z) {
        return concerne(x, z) && (type(x, z) & BIOME) != 0;
    }

    @Override
    public boolean inonde(int x, int z, double hauteur) {
        // seulement l'eau voulue (mer au pied des falaises, baie) : inonder tout ce qui est bas dessinait le rectangle
        return (type(x, z) & INONDE) != 0;
    }

    /** Le biome couvre toute la hauteur des falaises. */
    @Override
    public double basBiome(int x, int z, double hauteur) {
        return 45.0;
    }

    @Override
    public double rebordSiParoi(int x, int z) {
        if (!concerne(x, z)) return Double.NaN;
        int t = type(x, z);
        return (t & 15) != 0 ? dessusCouches(x, z) : Double.NaN;
    }

    @Override
    public double hauteurNette(int x, int z) {
        if (!concerne(x, z) || (type(x, z) & TAILLEE) == 0) return Double.NaN;
        return Terrain.get().hauteur(x, z);
    }

    @Override
    public double remblai(int x, int z) {
        if (!concerne(x, z) || (type(x, z) & REMBLAI) == 0) return Double.NaN;
        return Terrain.get().hauteur(x, z);
    }

    @Override
    public int sculpteMin() {
        return 55;
    }

    @Override
    public int fondStrates() {
        return 50;
    }

    /** Le sol naturel (herbe, terre) n'est gardé que sur les colonnes non taillées. */
    @Override
    public boolean garderSol(int y, double rebord, int sommet, boolean taillee) {
        return !taillee && y >= sommet - 3;
    }

    // ---------------------------------------------------------------- roches

    private static int h2(int x, int z, int s) {
        return ((x * 73856093) ^ (z * 19349663) ^ (s * 83492791)) & 1023;
    }

    @Override
    public BlockState strate(int x, int y, int z, double rebord) {
        return bloc(type(x, z) & 15, x, y, z, rebord, false).defaultBlockState();
    }

    @Override
    public BlockState sommet(int x, int y, int z, double rebord) {
        return bloc(type(x, z) & 15, x, y, z, rebord, true).defaultBlockState();
    }

    /** Petite ondulation verticale des lits de roche (-1, 0 ou 1), lente le long de la paroi. */
    private static int vague(int x, int z) {
        return (int) Math.round(0.8 * Math.sin(x * 0.11 + z * 0.07) + 0.45 * Math.sin(x * 0.031 - z * 0.053));
    }

    private static final int[] LITS_CRAIE = {4, 8, 13, 17, 22, 26, 31, 35};
    private static final int[] LITS_CRAIE_PURE = {6, 14, 22, 30};
    private static final int[] BANCS_MOHER = {3, 9, 14, 21, 27, 32, 38};

    private Block bloc(int cl, int x, int y, int z, double top, boolean dessus) {
        switch (palette) {
            case CRAIE, CRAIE_PURE -> {
                if (cl == PLAGE) return h2(x, z, 0) % 6 == 0 ? Blocks.CALCITE : Blocks.GRAVEL;     // galets, blocs de craie
                if (cl == FOND) return h2(x, z, 1) % 3 == 0 ? Blocks.CALCITE : Blocks.GRAVEL;      // platier
                if (cl == PLATEAU && dessus && y > 63) return Blocks.GRASS_BLOCK;
                if (cl == PLATEAU && y >= top - 2 && y > 64) return Blocks.DIRT;
                if (y <= 64) return h2(x, z, y) % 3 == 0 ? Blocks.MOSSY_COBBLESTONE : Blocks.DIORITE; // pied verdi
                int r = y - 63 + vague(x, z);
                int[] lits = palette == Palette.CRAIE ? LITS_CRAIE : LITS_CRAIE_PURE;
                int couverture = palette == Palette.CRAIE ? 6 : 4;
                for (int k : lits) {
                    // lits de silex : fins, en pointillés
                    if (r == k && h2(Math.floorDiv(x, 3), Math.floorDiv(z, 3), k) % 10 < couverture) return Blocks.TUFF;
                }
                // coulures verticales grises, discrètes
                if (h2(Math.floorDiv(x, 2), Math.floorDiv(z, 2), 77) % 13 == 0 && y < top - 3) return Blocks.DIORITE;
                return Blocks.CALCITE;
            }
            case MOHER -> {
                if (cl == PLAGE || cl == FOND) return h2(x, z, 2) % 3 == 0 ? Blocks.COBBLESTONE : Blocks.STONE;
                if (cl == PLATEAU && dessus && y > 63) return Blocks.GRASS_BLOCK;
                if (cl == PLATEAU && y >= top - 2 && y > 64) return Blocks.DIRT;
                int r = y - 60 + vague(x, z);
                for (int k : BANCS_MOHER) if (r == k) return Blocks.DRIPSTONE_BLOCK;              // bancs de grès
                int m = h2(Math.floorDiv(x, 2), Math.floorDiv(z, 2), Math.floorDiv(y, 3));
                if (m % 4 == 0) return Blocks.COBBLED_DEEPSLATE;                                  // schistes
                return m % 7 == 0 ? Blocks.TUFF : Blocks.DEEPSLATE;
            }
            case DUNE -> {
                return y >= top - 6 ? Blocks.SAND : Blocks.SANDSTONE;
            }
            case BAIE -> {
                if (cl == ROC) {
                    if (dessus && h2(x, z, 0) % 3 == 0) return Blocks.GRASS_BLOCK;
                    int m = h2(Math.floorDiv(x, 2), Math.floorDiv(z, 2), Math.floorDiv(y, 3));
                    return m % 3 == 0 ? Blocks.ANDESITE : (m % 5 == 0 ? Blocks.TUFF : Blocks.STONE);   // granite gris
                }
                if (cl == PRE) return dessus ? Blocks.GRASS_BLOCK : Blocks.DIRT;                  // herbus
                if (cl == VASE && dessus) return Blocks.CLAY;                                     // tangue mouillée
                return y >= 57 ? Blocks.SAND : Blocks.STONE;
            }
        }
        return Blocks.STONE;
    }

    // ---------------------------------------------------------------- surplombs (arches)

    private static long cle(int cx, int cz) {
        return ((long) cx << 32) ^ (cz & 0xFFFFFFFFL);
    }

    private Long2ObjectOpenHashMap<List<int[]>> surplombs() {
        Long2ObjectOpenHashMap<List<int[]>> s = surplombs;
        if (s != null) return s;
        synchronized (this) {
            if (surplombs != null) return surplombs;
            s = new Long2ObjectOpenHashMap<>();
            try (InputStream in = LieuGrille.class.getResourceAsStream("/domaine_terre_lieux/" + id + ".vox")) {
                if (in != null) {
                    ByteBuffer b = ByteBuffer.wrap(new GZIPInputStream(in).readAllBytes()).order(ByteOrder.LITTLE_ENDIAN);
                    int n = b.getInt();
                    for (int i = 0; i < n; i++) {
                        int x = b.getInt(), y = b.getInt(), z = b.getInt(), c = b.get();
                        s.computeIfAbsent(cle(x >> 4, z >> 4), k -> new ArrayList<>()).add(new int[]{x, y, z, c});
                    }
                }
            } catch (IOException e) {
                throw new UncheckedIOException("Impossible de charger " + id + ".vox", e);
            }
            surplombs = s;
            return s;
        }
    }

    /** Les arches sont placées en coordonnées de blocs du 1:250 (les lieux sont réglés pour cette échelle). */
    @Override
    public void poser(WorldGenLevel niveau, int x0, int z0) {
        if (Terrain.echelle() != GrandCanyon.ECHELLE_REFERENCE) return;
        List<int[]> l = surplombs().get(cle(x0 >> 4, z0 >> 4));
        if (l == null) return;
        BlockPos.MutableBlockPos pos = new BlockPos.MutableBlockPos();
        for (int[] v : l) {
            BlockState b = v[3] == CREUSE ? (v[1] <= 62 ? Blocks.WATER : Blocks.AIR).defaultBlockState()   // arches
                    : bloc(v[3], v[0], v[1], v[2], 999, false).defaultBlockState();
            niveau.setBlock(pos.set(v[0], v[1], v[2]), b, 2);
        }
    }
}

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
    /** Lot 2 (montagne) : neige, glace, éboulis, mousse, lit d'un torrent ou d'un lac. */
    static final int NEIGE = 11, GLACE = 12, EBOULIS = 13, MOUSSE = 14, LIT = 15;
    static final int TAILLEE = 16, REMBLAI = 32, BIOME = 64, INONDE = 128;

    /** Palettes de roches. */
    public enum Palette { CRAIE, CRAIE_PURE, MOHER, DUNE, BAIE,
        /** Lot 2 : calcaire des Pyrénées (Gavarnie), basalte d'Islande, travertin (Plitvice), gneiss de Norvège,
         *  gneiss sombre du Cervin, dolomie claire (Tre Cime). */
        CALCAIRE, BASALTE, TRAVERTIN, GNEISS, CERVIN, DOLOMIE,
        /** Lot 3 : granite clair du Mont-Blanc (Mer de Glace, glace nue et névés), Islande glaciaire (Jökulsárlón :
         *  sable noir, icebergs et glacier tout en glace). */
        GRANITE, ISLANDE,
        /** Lot 3 (suite) : basalte en colonnes (Chaussée des Géants), conglomérat (Météores), volcan (Etna, Vésuve :
         *  coulées noires, cendres, soufre). */
        CHAUSSEE, CONGLOMERAT, VOLCAN }

    /** Blocs particuliers des fichiers .vox (classe >= 100) : lave, fumerolle, geyser, magma. */
    static final int VOX_LAVE = 100, VOX_FUMEROLLE = 101, VOX_GEYSER = 102, VOX_MAGMA = 103;

    private final String id;
    private final Palette palette;
    /** Grille lon/lat (ancien format), ou null pour un lieu en tuiles ({@link Tuiles}). */
    private final ReliefLieu relief;
    private volatile Long2ObjectOpenHashMap<List<int[]>> surplombs;
    /** y le plus bas recoloré en couches (les lieux de montagne s'arrêtent plus haut). */
    private final int fond;

    public LieuGrille(String id, Palette palette) {
        this(id, palette, false);
    }

    /** @param enTuiles le lieu est sculpté dans les tuiles (hauteurs exactes, bords recollés au terrain calculé) */
    public LieuGrille(String id, Palette palette, boolean enTuiles) {
        this(id, palette, enTuiles, 50);
    }

    /** @param fond y le plus bas recoloré (lieux de montagne : sous le pied de leurs parois, pas jusqu'à y 50) */
    public LieuGrille(String id, Palette palette, boolean enTuiles, int fond) {
        this.id = id;
        this.palette = palette;
        this.relief = enTuiles ? null : new ReliefLieu(id + ".bin");
        this.fond = fond;
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
        return Math.min(45.0, fond - 5.0);
    }

    /** Eau propre au lieu (lot 2) : torrents, lacs, cascades en altitude, lue dans les tuiles. */
    @Override
    public int eau(int x, int z) {
        if (relief != null || !concerne(x, z)) return Integer.MIN_VALUE;
        return Tuiles.eau(x, z);
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
        return Math.min(55, fond);
    }

    @Override
    public int fondStrates() {
        return fond;
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
            case CALCAIRE -> {
                // calcaire en gros bancs gris, vires d'herbe et de neige, éboulis au pied (Gavarnie)
                if (cl == NEIGE) return dessus ? Blocks.SNOW_BLOCK : Blocks.STONE;
                if (cl == EBOULIS) return h2(x, z, y) % 3 == 0 ? Blocks.COBBLESTONE : Blocks.GRAVEL;
                if (cl == LIT) return h2(x, z, y) % 4 == 0 ? Blocks.MOSSY_COBBLESTONE : Blocks.GRAVEL;
                if ((cl == PLATEAU || cl == PRE) && dessus) return Blocks.GRASS_BLOCK;
                if ((cl == PLATEAU || cl == PRE) && y >= top - 2) return Blocks.DIRT;
                int r = Math.floorMod(y + vague(x, z), 11);
                if (r == 0) return Blocks.TUFF;                                                   // joints de bancs
                if (r <= 3) return Blocks.ANDESITE;
                if (r == 7) return Blocks.CALCITE;
                return h2(Math.floorDiv(x, 3), Math.floorDiv(z, 3), Math.floorDiv(y, 4)) % 9 == 0 ? Blocks.DIORITE : Blocks.STONE;
            }
            case BASALTE -> {
                // orgues de basalte, mousse sur le dessus (Gullfoss, Skógafoss)
                if (cl == LIT) return h2(x, z, y) % 3 == 0 ? Blocks.COBBLED_DEEPSLATE : Blocks.GRAVEL;
                if (cl == MOUSSE && dessus) return h2(x, z, 0) % 4 == 0 ? Blocks.GRASS_BLOCK : Blocks.MOSS_BLOCK;
                if ((cl == PLATEAU || cl == PRE) && dessus) return h2(x, z, 0) % 3 == 0 ? Blocks.MOSS_BLOCK : Blocks.GRASS_BLOCK;
                if ((cl == PLATEAU || cl == PRE || cl == MOUSSE) && y >= top - 1) return Blocks.DIRT;
                if (cl == EBOULIS) return Blocks.GRAVEL;
                if (cl == PLAGE) return dessus ? (h2(x, z, 1) % 4 == 0 ? Blocks.DIORITE : Blocks.CALCITE) : Blocks.CALCITE;   // geysérite
                int r = Math.floorMod(y - 60 + vague(x, z), 9);
                if (r == 0) return Blocks.TUFF;                                                   // lits de cendres
                return h2(x, z, Math.floorDiv(y, 5)) % 5 == 0 ? Blocks.SMOOTH_BASALT : Blocks.BASALT;
            }
            case TRAVERTIN -> {
                // barrages de travertin moussus, lacs au fond clair, canyon calcaire (Plitvice)
                if (cl == LIT) return h2(x, z, y) % 3 == 0 ? Blocks.CLAY : Blocks.CALCITE;
                if (cl == MOUSSE) return dessus ? Blocks.MOSS_BLOCK : (h2(x, z, y) % 3 == 0 ? Blocks.DRIPSTONE_BLOCK : Blocks.CALCITE);
                if ((cl == PLATEAU || cl == PRE) && dessus) return Blocks.GRASS_BLOCK;
                if ((cl == PLATEAU || cl == PRE) && y >= top - 2) return Blocks.DIRT;
                if (cl == EBOULIS) return Blocks.GRAVEL;
                int r = Math.floorMod(y + vague(x, z), 7);
                if (r == 0) return Blocks.DIORITE;
                return h2(Math.floorDiv(x, 2), Math.floorDiv(z, 2), Math.floorDiv(y, 3)) % 6 == 0 ? Blocks.ANDESITE : Blocks.STONE;
            }
            case GNEISS -> {
                // gneiss gris rayé, mousse et herbe sur les replats (Geiranger, Preikestolen)
                if (cl == LIT || cl == FOND) return h2(x, z, y) % 3 == 0 ? Blocks.GRAVEL : Blocks.STONE;
                if (cl == NEIGE) return dessus ? Blocks.SNOW_BLOCK : Blocks.STONE;
                if ((cl == PLATEAU || cl == PRE || cl == MOUSSE) && dessus)
                    return cl == MOUSSE || h2(x, z, 0) % 4 == 0 ? Blocks.MOSS_BLOCK : Blocks.GRASS_BLOCK;
                if ((cl == PLATEAU || cl == PRE || cl == MOUSSE) && y >= top - 1) return Blocks.DIRT;
                if (cl == EBOULIS) return h2(x, z, y) % 2 == 0 ? Blocks.COBBLESTONE : Blocks.GRAVEL;
                int r = Math.floorMod(y + 2 * vague(x, z) + Math.floorDiv(x + z, 9), 8);
                if (r == 0) return Blocks.DEEPSLATE;                                              // veines sombres
                if (r == 3) return Blocks.DIORITE;
                return h2(Math.floorDiv(x, 2), Math.floorDiv(z, 2), Math.floorDiv(y, 3)) % 4 == 0 ? Blocks.ANDESITE : Blocks.STONE;
            }
            case CERVIN -> {
                // gneiss sombre, neige sur les replats, glace des glaciers, éboulis gris
                // glacier : neige dessus, 4 blocs de glace dessous, puis la roche (pas une montagne de glace)
                if (cl == GLACE && dessus) return Blocks.SNOW_BLOCK;
                if (cl == GLACE && y >= top - 4) return h2(x, z, y) % 5 == 0 ? Blocks.BLUE_ICE : Blocks.PACKED_ICE;
                if (cl == NEIGE) return dessus ? Blocks.SNOW_BLOCK : Blocks.STONE;
                if (cl == EBOULIS) return h2(x, z, y) % 3 == 0 ? Blocks.ANDESITE : Blocks.GRAVEL;
                if ((cl == PLATEAU || cl == PRE) && dessus) return Blocks.GRASS_BLOCK;
                if ((cl == PLATEAU || cl == PRE) && y >= top - 1) return Blocks.DIRT;
                int r = Math.floorMod(y + vague(x, z), 6);
                if (r == 0) return Blocks.COBBLED_DEEPSLATE;
                if (r == 3) return Blocks.TUFF;
                return h2(Math.floorDiv(x, 2), Math.floorDiv(z, 2), Math.floorDiv(y, 3)) % 3 == 0 ? Blocks.DEEPSLATE : Blocks.STONE;
            }
            case DOLOMIE -> {
                // dolomie claire en fines strates, pierriers au pied (Tre Cime)
                if (cl == NEIGE) return dessus ? Blocks.SNOW_BLOCK : Blocks.DIORITE;
                if (cl == EBOULIS) return h2(x, z, y) % 3 == 0 ? Blocks.DIORITE : Blocks.GRAVEL;
                if ((cl == PLATEAU || cl == PRE) && dessus) return Blocks.GRASS_BLOCK;
                if ((cl == PLATEAU || cl == PRE) && y >= top - 1) return Blocks.DIRT;
                int r = Math.floorMod(y + vague(x, z), 5);
                if (r == 0) return Blocks.STONE;
                if (r == 2) return Blocks.DIORITE;
                return h2(Math.floorDiv(x, 3), Math.floorDiv(z, 3), Math.floorDiv(y, 4)) % 7 == 0 ? Blocks.TUFF : Blocks.CALCITE;
            }
            case GRANITE -> {
                // protogine claire du Mont-Blanc ; glacier : glace nue (6 blocs) ; névé : neige sur 3 blocs de glace
                if (cl == GLACE && dessus) return h2(x, z, 3) % 5 == 0 ? Blocks.BLUE_ICE : Blocks.PACKED_ICE;
                if (cl == GLACE && y >= top - 6) return h2(x, z, y) % 7 == 0 ? Blocks.BLUE_ICE : Blocks.PACKED_ICE;
                if (cl == NEIGE && dessus) return Blocks.SNOW_BLOCK;
                if (cl == NEIGE && y >= top - 3) return Blocks.PACKED_ICE;
                if (cl == EBOULIS) return h2(x, z, y) % 3 == 0 ? Blocks.ANDESITE : (h2(x, z, y) % 3 == 1 ? Blocks.COBBLESTONE : Blocks.GRAVEL);
                if (cl == LIT) return h2(x, z, y) % 3 == 0 ? Blocks.COBBLESTONE : Blocks.GRAVEL;
                if ((cl == PLATEAU || cl == PRE) && dessus) return Blocks.GRASS_BLOCK;
                if ((cl == PLATEAU || cl == PRE) && y >= top - 2) return Blocks.DIRT;
                int m = h2(Math.floorDiv(x, 2), Math.floorDiv(z, 2), Math.floorDiv(y, 3));
                if (m % 11 == 0) return Blocks.GRANITE;                                           // feldspaths roses
                if (Math.floorMod(y + vague(x, z) + Math.floorDiv(x - z, 7), 9) == 0) return Blocks.DIORITE;   // filons
                return m % 4 == 0 ? Blocks.ANDESITE : Blocks.STONE;
            }
            case ISLANDE -> {
                // icebergs et glacier : tout en glace ; sable noir ; mousse ; basalte et cendres
                if (cl == GLACE) return h2(x, z, dessus ? 5 : y) % 4 == 0 ? Blocks.BLUE_ICE : Blocks.PACKED_ICE;
                if (cl == PLAGE) {
                    if (dessus || y >= top - 2) return h2(x, z, y) % 6 == 0 ? Blocks.GRAVEL : Blocks.BLACK_CONCRETE_POWDER;
                    return Blocks.COBBLED_DEEPSLATE;
                }
                if (cl == FOND || cl == LIT) return h2(x, z, y) % 3 == 0 ? Blocks.GRAVEL : Blocks.COBBLED_DEEPSLATE;
                if (cl == EBOULIS) return h2(x, z, y) % 3 == 0 ? Blocks.TUFF : (h2(x, z, y) % 3 == 1 ? Blocks.COBBLED_DEEPSLATE : Blocks.GRAVEL);
                if (cl == MOUSSE && dessus) return h2(x, z, 0) % 5 == 0 ? Blocks.GRASS_BLOCK : Blocks.MOSS_BLOCK;
                if ((cl == PLATEAU || cl == PRE) && dessus) return h2(x, z, 0) % 3 == 0 ? Blocks.MOSS_BLOCK : Blocks.GRASS_BLOCK;
                if ((cl == PLATEAU || cl == PRE || cl == MOUSSE) && y >= top - 1) return Blocks.DIRT;
                if (cl == NEIGE) return dessus ? Blocks.SNOW_BLOCK : Blocks.BASALT;
                int r = Math.floorMod(y - 60 + vague(x, z), 7);
                if (r == 0) return Blocks.TUFF;
                return h2(x, z, Math.floorDiv(y, 5)) % 4 == 0 ? Blocks.SMOOTH_BASALT : Blocks.BASALT;
            }
            case CHAUSSEE -> {
                // basalte en colonnes (prismes verticaux), galets noirs, prés au-dessus des falaises
                if (cl == PLAGE) return h2(x, z, y) % 3 == 0 ? Blocks.COBBLED_DEEPSLATE : Blocks.GRAVEL;
                if (cl == FOND) return h2(x, z, y) % 3 == 0 ? Blocks.GRAVEL : Blocks.SMOOTH_BASALT;
                if ((cl == PLATEAU || cl == PRE || cl == MOUSSE) && dessus) return Blocks.GRASS_BLOCK;
                if ((cl == PLATEAU || cl == PRE || cl == MOUSSE) && y >= top - 2) return Blocks.DIRT;
                if (cl == EBOULIS) return h2(x, z, y) % 2 == 0 ? Blocks.COBBLED_DEEPSLATE : Blocks.GRAVEL;
                // colonnes : chaque colonne de 2 x 2 blocs a sa teinte ; lits de latérite rouge entre deux coulées
                if (Math.floorMod(y - 60 + vague(x, z), 13) == 0) return Blocks.TERRACOTTA;
                int c = h2(Math.floorDiv(x, 2), Math.floorDiv(z, 2), 7) % 4;
                return c == 0 ? Blocks.POLISHED_BASALT : (c == 1 ? Blocks.SMOOTH_BASALT : Blocks.BASALT);
            }
            case CONGLOMERAT -> {
                // conglomérat brun-gris en gros bancs (galets pris dans le grès), touffes d'herbe sur les dômes
                if ((cl == PLATEAU || cl == PRE) && dessus) return Blocks.GRASS_BLOCK;
                if ((cl == PLATEAU || cl == PRE) && y >= top - 2) return Blocks.DIRT;
                if (cl == EBOULIS) return h2(x, z, y) % 3 == 0 ? Blocks.COBBLESTONE : Blocks.GRAVEL;
                int r = Math.floorMod(y + vague(x, z), 9);
                if (r == 0) return Blocks.PACKED_MUD;                                              // joints de grès
                int m = h2(x, z, y) % 7;
                if (m == 0) return Blocks.COBBLESTONE;                                            // galets
                if (m == 1) return Blocks.ANDESITE;
                return r < 4 ? Blocks.TUFF : Blocks.STONE;
            }
            case VOLCAN -> {
                // coulées de lave noires, cendres et scories, soufre autour des fumerolles
                if (cl == FOND) return h2(x, z, y) % 4 == 0 ? Blocks.BLACKSTONE : Blocks.BASALT;
                if (cl == EBOULIS) {
                    int m = h2(x, z, y) % 6;
                    return m < 2 ? Blocks.TUFF : (m < 4 ? Blocks.GRAVEL : (m == 4 ? Blocks.BLACKSTONE : Blocks.COBBLED_DEEPSLATE));
                }
                if (cl == MOUSSE) return dessus ? (h2(x, z, 0) % 3 == 0 ? Blocks.TUFF : Blocks.YELLOW_TERRACOTTA) : Blocks.TUFF;
                if ((cl == PLATEAU || cl == PRE) && dessus) return Blocks.GRASS_BLOCK;
                if ((cl == PLATEAU || cl == PRE) && y >= top - 2) return Blocks.DIRT;
                int r = Math.floorMod(y + vague(x, z), 7);
                if (r == 0) return Blocks.TUFF;                                                   // lits de cendres
                return h2(x, z, Math.floorDiv(y, 3)) % 3 == 0 ? Blocks.BLACKSTONE : Blocks.BASALT;
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
                        int x = b.getInt(), y = b.getInt(), z = b.getInt(), c = b.get() & 0xFF;
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
            // les blocs du .vox sont rangés par chunk : on ne pose que ceux du chunk en cours
            if ((v[0] >> 4) != (x0 >> 4) || (v[2] >> 4) != (z0 >> 4)) continue;
            BlockState b = switch (v[3]) {
                case VOX_LAVE -> Blocks.LAVA.defaultBlockState();
                case VOX_MAGMA -> Blocks.MAGMA_BLOCK.defaultBlockState();
                case VOX_FUMEROLLE -> fr.domaineaubin.lieux.bloc.BlocsLieux.FUMEROLLE.get().defaultBlockState();
                case VOX_GEYSER -> fr.domaineaubin.lieux.bloc.BlocsLieux.GEYSER.get().defaultBlockState();
                case CREUSE -> (v[1] <= 62 ? Blocks.WATER : Blocks.AIR).defaultBlockState();          // arches
                default -> bloc(v[3], v[0], v[1], v[2], 999, false).defaultBlockState();
            };
            niveau.setBlock(pos.set(v[0], v[1], v[2]), b, 2);
        }
    }
}

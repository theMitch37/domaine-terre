package fr.domaineaubin.lieux;

import fr.domaineaubin.terre.monde.Terrain;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.util.Mth;
import net.minecraft.util.RandomSource;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.levelgen.synth.ImprovedNoise;

import static fr.domaineaubin.lieux.ReliefLieu.lisse;

/**
 * Grand Canyon (Arizona). Le tracé vient du réel : talweg du Colorado retrouvé dans le relief ETOPO 2022,
 * niveau des plateaux, lacs Mead, Mohave et Powell à leur vraie forme. La coupe, elle, est dessinée : la hauteur
 * du monde étant fixe, le relief réel serait ~15 fois trop raide en 1:250 (aiguilles, lames).
 * Profil d'après les vraies couches, du rebord au fleuve : Kaibab (falaise), Toroweap, Coconino (falaise claire),
 * Hermit, Supai en gradins, grande falaise Redwall-Muav, plateau de Tonto, Tapeats, gorge de Vishnu.
 * Du bruit découpe les parois (amphithéâtres, éperons) et dresse des buttes en gradins (temples).
 * Réglé pour l'échelle 1:250. Données préparées par outils/grand_canyon_dem.py.
 */
public final class GrandCanyon implements LieuSculpte {
    public static final GrandCanyon INSTANCE = new GrandCanyon();

    /** Échelle de référence : tous les réglages sont faits pour elle. */
    public static final int ECHELLE_REFERENCE = 250;
    /** Fond du lit (y) : l'eau monte d'elle-même jusqu'à y 62. */
    public static final double FOND = 56.0;
    /** Pied des parois, juste au-dessus de l'eau. */
    private static final double PIED = 62.5;
    /** Largeur (degrés) du fondu vers le terrain du mod Terre sur les bords de la zone. */
    private static final double FONDU = 0.12;
    /** Grand Wash Cliffs (fin du Grand Canyon à l'ouest) et Lees Ferry (début de Marble Canyon à l'est). */
    private static final double LON_GRAND_WASH = -114.10, LON_LEES_FERRY = -111.62;

    /** Épaisseurs réelles (m) des couches, du rebord au fleuve, et forme de la paroi (falaise ou pente). */
    private static final double[] EPAISSEUR = {90, 70, 100, 100, 70, 70, 70, 70, 150, 120, 100, 60, 300};
    public static final int NB_COUCHES = EPAISSEUR.length;
    /** Fraction de profondeur au sommet de chaque couche (0 = rebord, 1 = fleuve). */
    private static final double[] SOMMET_COUCHE = new double[NB_COUCHES + 1];
    static {
        double tot = 0;
        for (double e : EPAISSEUR) tot += e;
        double a = 0;
        for (int i = 0; i < NB_COUCHES; i++) {
            SOMMET_COUCHE[i] = a / tot;
            a += EPAISSEUR[i];
        }
        SOMMET_COUCHE[NB_COUCHES] = 1.0;
    }
    /**
     * Coupe du canyon : distance relative au fleuve t (1 = rebord) -> fraction de profondeur.
     * Les couches dures occupent une bande étroite (falaise), les tendres une bande large (pente, replat).
     */
    private static final double[] PROFIL_T = {1.00, 0.97, 0.90, 0.87, 0.76, 0.74, 0.66, 0.64, 0.56, 0.52, 0.50, 0.22, 0.20, 0.05, 0.0};
    private static final double[] PROFIL_G = new double[PROFIL_T.length];
    static {
        for (int i = 0; i <= NB_COUCHES; i++) PROFIL_G[i] = SOMMET_COUCHE[i];
        PROFIL_G[NB_COUCHES + 1] = 1.0;
    }

    /** Grilles : 0 altitude réelle, 1 plateau (rebord), 2 niveau du Colorado, 3 distance au talweg (hm). */
    private final ReliefLieu relief = new ReliefLieu("grand_canyon.bin");
    private final ImprovedNoise bruit;
    private final ImprovedNoise bruitButtes;

    private GrandCanyon() {
        RandomSource r = RandomSource.create(36_1066_112L);
        bruit = new ImprovedNoise(r);
        bruitButtes = new ImprovedNoise(r);
    }

    @Override
    public String id() {
        return "grand_canyon";
    }

    @Override
    public ResourceLocation biome() {
        return new ResourceLocation(DomaineLieux.MOD_ID, "grand_canyon");
    }

    // ---------------------------------------------------------------- géométrie

    /** Demi-largeur du canyon en blocs (~75 en 1:250), un peu plus large aux petites échelles. */
    public static double demiLargeur() {
        return 75.0 * Math.pow((double) ECHELLE_REFERENCE / Terrain.echelle(), 0.26);
    }

    /** Valeurs d'une colonne. */
    private record Point(double e, double p, double r, double distBlocs, double t, double fraction,
                         double intensite, double fondu, double v) {
    }

    private Point point(int x, int z) {
        double lon = Terrain.lon(x), lat = Terrain.lat(z);
        double e = relief.echant(0, lon, lat), p = relief.echant(1, lon, lat), r = relief.echant(2, lon, lat);
        double db = relief.echant(3, lon, lat) * 100.0 * Terrain.BLOCS_PAR_DEGRE / 111_320.0;
        // le canyon naît à Lees Ferry et finit aux Grand Wash Cliffs : il s'y rétrécit jusqu'au lit du fleuve
        double intensite = lisse((lon - LON_GRAND_WASH) / 0.25) * (1.0 - lisse((lon - LON_LEES_FERRY + 0.25) / 0.25));
        // aux extrémités, plus de fente étroite (lames d'un bloc) : une vallée en V d'au moins ~80 blocs de large
        double w = demiLargeur() * Math.max(intensite, 0.55);
        double v = 1.0 - lisse(intensite / 0.6);
        // parois découpées : amphithéâtres, éperons et canyons latéraux
        double d = db, plancher = Math.min(6.0, w * 0.3);
        if (db >= plancher) {
            double wf = demiLargeur();
            d = Math.max(plancher, db + bruit.noise(x / (wf * 0.9), 0.0, z / (wf * 0.9)) * w * 0.35
                    + bruit.noise(x / 23.0, 1.0, z / 23.0) * w * 0.07);
        }
        double t = d / w;
        double g = Mth.clamp(profil(Mth.clamp(t, 0.0, 1.0)), 0.0, 1.0);
        g = Mth.lerp(v, g, Mth.clamp((1.0 - t) / 0.85, 0.0, 1.0));
        // buttes isolées (temples de Vishnu, Zoroaster…) : sommet vers le Supai, flancs en gradins
        if (t > 0.28 && t < 0.92 && v < 0.5) {
            double wb = demiLargeur();
            double b = bruitButtes.noise(x / (wb * 0.45), 7.0, z / (wb * 0.45));
            if (b > 0.25) {
                // 11/11/2026 (banc : aiguilles d'un bloc de large, hautes comme les buttes, au sommet des petites taches
                // du bruit) : seules les grandes taches montent jusqu'au Supai ; les petites restent des tertres
                double sb = Mth.clamp((b - 0.25) / 0.35, 0.0, 1.0);
                double gt = SOMMET_COUCHE[3] + (1.0 - sb) * (g - SOMMET_COUCHE[3]);
                g = Math.min(g, gradin(gt));
            }
        }
        return new Point(e, p, r, db, t, g, intensite, lisse(relief.distanceBord(lon, lat) / FONDU), v);
    }

    private static double profil(double t) {
        for (int i = 0; i < PROFIL_T.length - 1; i++) {
            double t0 = PROFIL_T[i], t1 = PROFIL_T[i + 1];
            if (t <= t0 && t >= t1) return Mth.lerp((t0 - t) / (t0 - t1), PROFIL_G[i], PROFIL_G[i + 1]);
        }
        return t > 1.0 ? 0.0 : 1.0;
    }

    /** Arrondit une fraction de profondeur au sommet de couche suivant (vers le bas) : gradins. */
    private static double gradin(double g) {
        for (int i = 0; i <= NB_COUCHES; i++) if (SOMMET_COUCHE[i] >= g) return SOMMET_COUCHE[i];
        return 1.0;
    }

    /** Couche géologique (0 = Kaibab … 12 = Vishnu) à une fraction de profondeur sous le rebord. */
    public static int couche(double fraction) {
        int c = 0;
        for (int i = 0; i < NB_COUCHES; i++) if (fraction >= SOMMET_COUCHE[i]) c = i;
        return c;
    }

    private static double yRebord(Point pt) {
        return Terrain.blocsDepuisAltitude(pt.p());
    }

    private static boolean dansCanyon(Point pt) {
        return pt.t() < 1.1 && pt.fondu() > 0.3;
    }

    // ---------------------------------------------------------------- Lieu

    @Override
    public boolean concerne(int x, int z) {
        return relief.contient(x, z);
    }

    /** Emprise : 1 dans la zone, 0 sur ses bords (même fondu que le relief). */
    @Override
    public double poids(int x, int z) {
        if (!concerne(x, z)) return 0.0;
        return lisse(relief.distanceBord(Terrain.lon(x), Terrain.lat(z)) / FONDU);
    }

    @Override
    public double hauteur(int x, int z, double h) {
        return calcul(point(x, z), h);
    }

    /**
     * Hauteur exacte du sol (y) pour la sculpture bloc par bloc, ou NaN si la colonne n'est pas taillée.
     * Seules les colonnes vraiment taillées par la coupe (ou le lit) sont sculptées. Ailleurs, le sol naturel
     * (arrondi tous les 4 blocs par Minecraft) reste tel quel : sinon une marche de 1-2 blocs, un muret,
     * apparaissait le long du rebord.
     */
    @Override
    public double hauteurNette(int x, int z) {
        if (!concerne(x, z)) return Double.NaN;
        Point pt = point(x, z);
        if (!dansCanyon(pt) || pt.t() > 1.0) return Double.NaN;
        double finale = Terrain.get().hauteur(x, z);
        if (pt.t() > 0.9 && finale < coupe(pt) - 0.5) return Double.NaN;   // terrain plus bas que la coupe : pas taillé
        return finale;
    }

    private static double coupe(Point pt) {
        double rebord = yRebord(pt);
        return rebord - pt.fraction() * (rebord - PIED);
    }

    /**
     * Le canyon est CREUSÉ dans le paysage : la coupe part du niveau du plateau réel. Près du rebord, le sol ne monte
     * jamais au-dessus du terrain du mod (h), sinon des murailles. À l'intérieur, la coupe décide, jusqu'à 16 blocs
     * au-dessus de h : un petit creux du terrain du mod ne perce plus le sommet d'une butte.
     * Hors du canyon, le terrain n'est pas touché.
     */
    private double calcul(Point pt, double h) {
        double y = h;
        if (pt.t() <= 1.0) {
            double rebord = yRebord(pt);
            double k = lisse((pt.t() - 0.80) / 0.15);
            double plafond = h + (1.0 - k) * Mth.clamp(rebord - h, 0.0, 16.0);
            y = Math.min(plafond, coupe(pt));
        }
        // le Colorado (~6 blocs de large) et les lacs (Mead, Mohave, Powell) au niveau du fleuve
        // lacs : là où le relief réel est à leur niveau (11/11/2026 : jusqu'à 26 m au-dessus, la plaine de la rivière
        // était noyée aussi, « rivière trop large » à la sortie du canyon)
        double lit = Math.max(1.0 - lisse((pt.distBlocs() - 2.5) / 1.5), 1.0 - lisse((pt.e() - pt.r() - 3.0) / 8.0));
        y = Mth.lerp(lit, y, FOND);
        return Mth.lerp(pt.fondu(), h, y);
    }

    @Override
    public boolean dansBiome(int x, int z) {
        return concerne(x, z) && dansCanyon(point(x, z));
    }

    /** Tout le canyon et les abords des lacs : l'aquifère y prend le niveau de la mer (le fleuve ne s'assèche plus). */
    @Override
    public boolean inonde(int x, int z, double hauteur) {
        Point pt = point(x, z);
        return dansCanyon(pt) || pt.t() < 1.5 || pt.e() - pt.r() < 60.0;
    }

    /** Dans le canyon, son biome descend jusqu'au fond (sinon les replats et parois prennent le biome froid du plateau). */
    @Override
    public double basBiome(int x, int z, double hauteur) {
        return FOND - 10.0;
    }

    /** Pour les strates : y du rebord si la colonne est dans le canyon, sinon NaN. */
    @Override
    public double rebordSiParoi(int x, int z) {
        if (!concerne(x, z)) return Double.NaN;
        Point pt = point(x, z);
        return dansCanyon(pt) ? yRebord(pt) : Double.NaN;
    }

    /** Fraction de profondeur (0 = rebord, 1 = fleuve) d'un bloc à la hauteur y. */
    public static double fraction(double y, double rebord) {
        return Mth.clamp((rebord - y) / (rebord - PIED), 0.0, 1.0);
    }

    // ---------------------------------------------------------------- couches

    /** Couches réelles du Grand Canyon, du rebord au fleuve. */
    private static final Block[] COUCHES = {
            Blocks.WHITE_TERRACOTTA,       // calcaire de Kaibab (rebord, crème)
            Blocks.TERRACOTTA,             // formation de Toroweap
            Blocks.SMOOTH_SANDSTONE,       // grès de Coconino (bande claire)
            Blocks.RED_TERRACOTTA,         // schistes de Hermit (pente rouge)
            Blocks.ORANGE_TERRACOTTA,      // groupe de Supai : gradins rouges et orangés
            Blocks.RED_TERRACOTTA,
            Blocks.ORANGE_TERRACOTTA,
            Blocks.RED_TERRACOTTA,
            Blocks.TERRACOTTA,             // calcaire de Redwall (grande falaise)
            Blocks.LIGHT_GRAY_TERRACOTTA,  // calcaire de Muav
            Blocks.LIGHT_GRAY_TERRACOTTA,  // schistes de Bright Angel (plateau de Tonto)
            Blocks.BROWN_TERRACOTTA,       // grès de Tapeats
            Blocks.DEEPSLATE,              // schiste de Vishnu (gorge intérieure)
    };

    @Override
    public BlockState strate(int x, int y, int z, double rebord) {
        if (y <= 61) return Blocks.SAND.defaultBlockState();          // berges et lit du Colorado
        double f = fraction(y, rebord) + StratesFeature.ondulation(x, z);
        return COUCHES[couche(f)].defaultBlockState();
    }

    @Override
    public int fondStrates() {
        return (int) FOND - 6;
    }
}

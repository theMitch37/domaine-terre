package fr.domaineaubin.lieux;

import fr.domaineaubin.terre.monde.Terrain;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.util.Mth;
import net.minecraft.util.RandomSource;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.levelgen.synth.ImprovedNoise;

import static fr.domaineaubin.lieux.ReliefLieu.lisse;

/**
 * Gorges du Verdon (Alpes-de-Haute-Provence / Var), du pont du Galetas à Castellane, et lac de Sainte-Croix.
 * Tracé réel du Verdon et de l'Artuby retrouvé dans le relief Copernicus GLO-30, lac à sa vraie forme.
 * La coupe est dessinée : grandes falaises de calcaire presque verticales, vires herbeuses, falaises basses,
 * rivière turquoise au fond. En 1:250 la gorge réelle ferait 4 blocs de large : elle est élargie à ~26 blocs.
 * Le lac est au niveau de la mer (y 62) au lieu de sa vraie hauteur (~y 79) : la cuvette autour reprend le relief
 * réel abaissé d'autant, sinon il serait au fond d'une tranchée.
 * Réglé pour l'échelle 1:250. Données : outils/verdon_dem.py ; rendu de contrôle : outils/rendu_verdon.py
 * (copie Python de cette classe, à garder synchronisée).
 */
public final class Verdon implements LieuSculpte {
    public static final Verdon INSTANCE = new Verdon();

    /** Fond du lit (y) : l'eau monte d'elle-même jusqu'à y 62. */
    private static final double FOND = 57.0;
    /** Pied des parois, juste au-dessus de l'eau. */
    private static final double PIED = 62.5;
    /** Demi-largeurs (blocs) des gorges du Verdon et de l'Artuby. */
    private static final double W_V = 13.0, W_A = 8.0;
    /** Largeur (degrés) du fondu vers le terrain du mod Terre sur les bords de la zone. */
    private static final double FONDU = 0.03;
    /** Niveau réel du lac de Sainte-Croix (m) et rayon (blocs) de la cuvette autour. */
    private static final double NIV_LAC = 473.0, BASSIN = 30.0;
    /**
     * Coupe : distance relative à la rivière t (1 = rebord) -> fraction de profondeur sous le rebord.
     * Grande falaise (la moitié de la hauteur), vires, falaise basse, puis berges et rivière.
     * Les falaises sont des marches de largeur nulle (t répété) : une colonne est soit en haut, soit en bas.
     * Une falaise « presque » verticale laisserait des colonnes à mi-hauteur, qui font des lames dans le jeu.
     */
    private static final double[] PROFIL_T = {1.00, 1.00, 0.74, 0.62, 0.54, 0.54, 0.30, 0.0};
    private static final double[] PROFIL_G = {0.00, 0.50, 0.62, 0.66, 0.66, 0.95, 1.00, 1.0};

    /** Grilles : 0 altitude, 1 plateau, 2 distance au Verdon, 3 abscisse le long du Verdon, 4 distance à l'Artuby, 5 lac. */
    private final ReliefLieu relief = new ReliefLieu("verdon.bin");
    private final ImprovedNoise bruitV, bruitV2, bruitA, bruitA2, coulures, taches;

    private Verdon() {
        RandomSource r = RandomSource.create(43_77_06_30L);
        bruitV = new ImprovedNoise(r);
        bruitV2 = new ImprovedNoise(r);
        bruitA = new ImprovedNoise(r);
        bruitA2 = new ImprovedNoise(r);
        coulures = new ImprovedNoise(r);
        taches = new ImprovedNoise(r);
    }

    @Override
    public String id() {
        return "verdon";
    }

    @Override
    public ResourceLocation biome() {
        return new ResourceLocation(DomaineLieux.MOD_ID, "verdon");
    }

    // ---------------------------------------------------------------- géométrie

    /**
     * Une gorge (Verdon ou Artuby) dans une colonne : distance relative t, fraction de profondeur g, présence,
     * et profondeur relative prof (1 = gorge entière ; vers 0, le fond remonte jusqu'au plateau : tête de gorge).
     */
    private record Branche(double dist, double t, double g, double pres, double prof) {
    }

    private record Point(double e, double rebord, double lac, Branche v, Branche a, double fondu) {
        Branche proche() {
            return v.t() <= a.t() ? v : a;
        }
    }

    private Point point(int x, int z) {
        double lon = Terrain.lon(x), lat = Terrain.lat(z);
        double bpd = Terrain.BLOCS_PAR_DEGRE;
        double e = relief.echant(0, lon, lat);
        double rebord = Terrain.blocsDepuisAltitude(relief.echant(1, lon, lat));
        double dv = relief.echant(2, lon, lat) * 1e-5 * bpd;
        double sb = relief.echant(3, lon, lat) * 1e-4 * bpd;
        double da = relief.echant(4, lon, lat) * 1e-5 * bpd;
        double lac = relief.echant(5, lon, lat) * 1e-5 * bpd;
        // en amont du Point Sublime, le fond remonte peu à peu jusqu'au plateau : la gorge finit en tête de gorge
        // (avant : vallée en V qui s'effaçait, d'où une rampe d'herbe ; et un puits fermé au bout de l'Artuby)
        double inten = 1.0 - lisse((sb - 112.0) / 48.0);
        double presV = 1.0 - lisse((sb - 155.0) / 25.0);
        double intenA = lisse((lat - 43.704) / 0.026);
        double presA = lisse((lat - 43.697) / 0.008);
        Branche v = branche(x, z, dv, W_V, inten, presV, bruitV, bruitV2);
        Branche a = branche(x, z, da, W_A, intenA, presA, bruitA, bruitA2);
        return new Point(e, rebord, lac, v, a, lisse(relief.distanceBord(lon, lat) / FONDU));
    }

    private static Branche branche(int x, int z, double dist, double w0, double inten, double pres,
                                   ImprovedNoise b1, ImprovedNoise b2) {
        double prof = lisse(inten);
        // la tête de gorge se resserre un peu en remontant ; les parois restent verticales
        double w = w0 * (0.65 + 0.35 * prof);
        // bruit à grande échelle seulement : les parois sont presque verticales, un bruit fin y ferait des aiguilles
        double plancher = Math.min(4.0, w * 0.3), d = dist;
        if (dist >= plancher) {
            double e1 = w0 * 0.8;
            d = Math.max(plancher, dist + b1.noise(x / e1, 0.0, z / e1) * w * 0.20
                    + b2.noise(x / 25.0, 3.0, z / 25.0) * w * 0.12);
        }
        double t = d / w;
        double g = Mth.clamp(profil(Mth.clamp(t, 0.0, 1.0)), 0.0, 1.0);
        return new Branche(dist, t, g, pres, prof);
    }

    private static double profil(double t) {
        for (int i = 0; i < PROFIL_T.length - 1; i++) {
            double t0 = PROFIL_T[i], t1 = PROFIL_T[i + 1];
            if (t0 == t1) continue;                         // falaise : marche verticale
            if (t <= t0 && t >= t1) return Mth.lerp((t0 - t) / (t0 - t1), PROFIL_G[i], PROFIL_G[i + 1]);
        }
        return t > 1.0 ? 0.0 : 1.0;
    }

    /** Pied des parois de cette branche : au-dessus de l'eau dans la gorge, puis il remonte vers le plateau. */
    private static double pied(Point pt, Branche b) {
        return Mth.lerp(b.prof(), pt.rebord() - 2.5, PIED);
    }

    private static double coupe(Point pt, Branche b) {
        return pt.rebord() - b.g() * (pt.rebord() - pied(pt, b));
    }

    /**
     * Gorge CREUSÉE dans le paysage : près du rebord, le sol ne monte jamais au-dessus du terrain du mod (h) ;
     * à l'intérieur, la coupe décide jusqu'à 12 blocs au-dessus de h. Hors de la gorge, h n'est pas touché.
     */
    private static double hauteurBranche(Point pt, Branche b, double h) {
        double y = h;
        if (b.t() <= 1.0) {
            double k = lisse((b.t() - 0.80) / 0.15);
            double plafond = h + (1.0 - k) * Mth.clamp(pt.rebord() - h, 0.0, 12.0);
            y = Math.min(plafond, coupe(pt, b));
        }
        // lit de la rivière : en eau dans la gorge, puis lit sec qui remonte avec le fond (la rivière y prend sa source)
        double lit = 1.0 - lisse((b.dist() - 2.4) / 1.2);
        double fondLit = Mth.lerp(lisse((b.prof() - 0.55) / 0.4), pied(pt, b) - 1.0, FOND);
        y = Mth.lerp(lit, y, Math.min(y, fondLit));
        return Mth.lerp(b.pres(), h, y);
    }

    private double calcul(Point pt, double h) {
        double y = Math.min(hauteurBranche(pt, pt.v(), h), hauteurBranche(pt, pt.a(), h));
        // lac de Sainte-Croix et sa cuvette
        double lac;
        if (pt.lac() < 0) {
            lac = 62.0 - Math.min(7.0, 1.5 - pt.lac() * 0.6);
        } else {
            double cuvette = Math.max(Terrain.blocsDepuisAltitude(pt.e()) - (Terrain.blocsDepuisAltitude(NIV_LAC) - 63.5), 63.5);
            lac = Mth.lerp(lisse(pt.lac() / BASSIN), cuvette, h);
        }
        y = Math.min(y, Math.min(lac, h));
        return Mth.lerp(pt.fondu(), h, y);
    }

    /** Colonnes traitées par la sculpture : la gorge et une bande de plateau au-delà du rebord (remblai). */
    private static boolean dansGorge(Point pt) {
        // ~8 blocs au-delà du rebord : Minecraft y arrondit le plateau vers le bas (interpolation tous les 4 blocs
        // + bruit des parois). Une bande plus étroite laissait un muret comblé et une tranchée derrière.
        return pt.fondu() > 0.3 && ((pt.v().t() < 1.6 && pt.v().pres() > 0.3) || (pt.a().t() < 1.6 && pt.a().pres() > 0.3));
    }

    // ---------------------------------------------------------------- Lieu

    @Override
    public boolean concerne(int x, int z) {
        return relief.contient(x, z);
    }

    @Override
    public double hauteur(int x, int z, double h) {
        return calcul(point(x, z), h);
    }

    /**
     * Le biome déborde de ~13 blocs au-delà du rebord (plus que la bande de remblai) : Minecraft ne lance la sculpture (StratesFeature) que dans
     * les chunks qui contiennent le biome du lieu. Sans cette marge, des chunks du rebord restaient bruts.
     */
    /** Emprise : 1 dans la gorge et la cuvette du lac, puis passage progressif au terrain libre du mod. */
    @Override
    public double poids(int x, int z) {
        if (!concerne(x, z)) return 0.0;
        Point pt = point(x, z);
        double v = (1.0 - lisse((pt.v().t() - 1.6) / 0.6)) * pt.v().pres();
        double a = (1.0 - lisse((pt.a().t() - 1.6) / 0.6)) * pt.a().pres();
        double l = 1.0 - lisse((pt.lac() - BASSIN) / 20.0);
        return pt.fondu() * Math.max(Math.max(v, a), l);
    }

    @Override
    public boolean dansBiome(int x, int z) {
        if (!concerne(x, z)) return false;
        Point pt = point(x, z);
        if (pt.fondu() <= 0.3) return false;
        return (pt.v().t() < 2.0 && pt.v().pres() > 0.3) || (pt.a().t() < 2.0 && pt.a().pres() > 0.3) || pt.lac() < 1.5;
    }

    /** Toute la gorge et le lac : l'aquifère y prend le niveau de la mer (la rivière ne s'assèche pas). */
    @Override
    public boolean inonde(int x, int z, double hauteur) {
        Point pt = point(x, z);
        return dansGorge(pt) || pt.v().t() < 1.5 || pt.lac() < 4.0;
    }

    /** Le biome descend jusqu'au fond (sinon les vires prennent le biome du plateau). */
    @Override
    public double basBiome(int x, int z, double hauteur) {
        return FOND - 10.0;
    }

    @Override
    public double rebordSiParoi(int x, int z) {
        if (!concerne(x, z)) return Double.NaN;
        Point pt = point(x, z);
        return dansGorge(pt) ? pt.rebord() : Double.NaN;
    }

    @Override
    public double hauteurNette(int x, int z) {
        if (!concerne(x, z)) return Double.NaN;
        Point pt = point(x, z);
        Branche b = pt.proche();
        if (!dansGorge(pt) || b.t() > 1.0) return Double.NaN;
        double finale = Terrain.get().hauteur(x, z);
        if (b.t() > 0.9 && finale < coupe(pt, b) - 0.5) return Double.NaN;   // terrain plus bas que la coupe : pas taillé
        return finale;
    }

    /** Bande de plateau juste au-delà du rebord : comblée jusqu'au terrain visé si Minecraft l'a arrondie. */
    @Override
    public double remblai(int x, int z) {
        if (!concerne(x, z)) return Double.NaN;
        Point pt = point(x, z);
        Branche b = pt.proche();
        if (!dansGorge(pt) || b.t() <= 1.0) return Double.NaN;
        return Terrain.get().hauteur(x, z);
    }

    // ---------------------------------------------------------------- roche

    private static double fraction(double y, double rebord) {
        return Mth.clamp((rebord - y) / (rebord - PIED), 0.0, 1.0);
    }

    /**
     * Calcaire du Tithonique : grandes parois blanches (calcite, diorite) striées de coulures verticales ocre
     * (terre cuite blanche) et grises (andésite, tuf) ; vires de pierre ; falaises basses grises polies par l'eau.
     */
    @Override
    public BlockState strate(int x, int y, int z, double rebord) {
        if (y <= 61) return (y >= 57 ? Blocks.GRAVEL : Blocks.STONE).defaultBlockState();   // lit de galets
        double f = fraction(y, rebord);
        double n = coulures.noise(x / 2.5, y / 14.0, z / 2.5);
        double m = taches.noise(x / 9.0, y / 6.0, z / 9.0);
        if (n > 0.29) return Blocks.WHITE_TERRACOTTA.defaultBlockState();
        if (n < -0.36) return (f < 0.5 ? Blocks.ANDESITE : Blocks.TUFF).defaultBlockState();
        if (f >= 0.50 && f < 0.70) return (m > 0.06 ? Blocks.STONE : Blocks.ANDESITE).defaultBlockState();
        if (f >= 0.70) return (m > -0.06 ? Blocks.DIORITE : Blocks.STONE).defaultBlockState();
        return (m < 0.12 ? Blocks.CALCITE : Blocks.DIORITE).defaultBlockState();
    }

    /** Les vires (replats à mi-hauteur) sont herbeuses : arbres et buissons peuvent y pousser. */
    @Override
    public BlockState sommet(int x, int y, int z, double rebord) {
        if (point(x, z).proche().t() > 1.0) return Blocks.GRASS_BLOCK.defaultBlockState();   // plateau remblayé
        if (y > 63 && y >= rebord - 7) return Blocks.GRASS_BLOCK.defaultBlockState();       // tête de gorge peu profonde
        double f = fraction(y, rebord);
        if (f >= 0.50 && f < 0.72 && y > 63) return Blocks.GRASS_BLOCK.defaultBlockState();
        return strate(x, y, z, rebord);
    }

    /** Le plateau garde son sol, y compris au bord quand le terrain du mod est plus bas que le rebord réel. */
    @Override
    public boolean garderSol(int y, double rebord, int sommet, boolean taillee) {
        return y >= rebord - 2 || (!taillee && y >= sommet - 3);
    }

    @Override
    public int fondStrates() {
        return (int) FOND - 4;
    }

    @Override
    public boolean gereSesCoursDEau() {
        return true;
    }
}

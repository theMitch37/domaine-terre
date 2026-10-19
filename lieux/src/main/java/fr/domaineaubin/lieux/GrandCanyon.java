package fr.domaineaubin.lieux;

import fr.domaineaubin.terre.api.Lieu;
import fr.domaineaubin.terre.monde.Terrain;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.util.Mth;
import net.minecraft.util.RandomSource;
import net.minecraft.world.level.levelgen.synth.ImprovedNoise;

import java.io.DataInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.UncheckedIOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.zip.GZIPInputStream;

/**
 * Grand Canyon (Arizona). Le tracé vient du réel : talweg du Colorado retrouvé dans le relief ETOPO 2022,
 * niveau des plateaux, lacs Mead, Mohave et Powell à leur vraie forme. La coupe, elle, est dessinée : la hauteur
 * du monde étant fixe, le relief réel serait ~15 fois trop raide en 1:250 (aiguilles, lames).
 * Profil d'après les vraies couches, du rebord au fleuve : Kaibab (falaise), Toroweap, Coconino (falaise claire),
 * Hermit, Supai en gradins, grande falaise Redwall-Muav, plateau de Tonto, Tapeats, gorge de Vishnu.
 * Du bruit découpe les parois (amphithéâtres, éperons) et dresse des buttes en gradins (temples).
 * Réglé pour l'échelle 1:250. Données préparées par outils/grand_canyon_dem.py.
 */
public final class GrandCanyon implements Lieu {
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

    private double lon0, lat0, pasLon, pasLat;
    private int largeur, hauteurGrille;
    private short[] alt, plateau, fleuve, distance;
    private volatile boolean charge;
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

    // ---------------------------------------------------------------- données

    private void charger() {
        if (charge) return;
        synchronized (this) {
            if (charge) return;
            try (InputStream in = GrandCanyon.class.getResourceAsStream("/domaine_terre_lieux/grand_canyon.bin")) {
                if (in == null) throw new IOException("grand_canyon.bin introuvable");
                byte[] tout = new GZIPInputStream(in).readAllBytes();
                ByteBuffer b = ByteBuffer.wrap(tout).order(ByteOrder.LITTLE_ENDIAN);
                lon0 = b.getDouble();
                lat0 = b.getDouble();
                pasLon = b.getDouble();
                pasLat = b.getDouble();
                largeur = b.getInt();
                hauteurGrille = b.getInt();
                int n = largeur * hauteurGrille;
                alt = lireGrille(b, n);
                plateau = lireGrille(b, n);
                fleuve = lireGrille(b, n);
                distance = lireGrille(b, n);
            } catch (IOException e) {
                throw new UncheckedIOException("Impossible de charger le relief du Grand Canyon", e);
            }
            charge = true;
        }
    }

    private static short[] lireGrille(ByteBuffer b, int n) {
        short[] g = new short[n];
        b.asShortBuffer().get(g);
        b.position(b.position() + 2 * n);
        return g;
    }

    private double lonMax() { return lon0 + largeur * pasLon; }
    private double latMin() { return lat0 - hauteurGrille * pasLat; }

    /** Interpolation bilinéaire d'une grille au point (lon, lat). */
    private double echant(short[] g, double lon, double lat) {
        double fx = (lon - lon0) / pasLon - 0.5, fy = (lat0 - lat) / pasLat - 0.5;
        int ix = Mth.floor(fx), iy = Mth.floor(fy);
        double tx = fx - ix, ty = fy - iy;
        return Mth.lerp(ty, Mth.lerp(tx, v(g, ix, iy), v(g, ix + 1, iy)), Mth.lerp(tx, v(g, ix, iy + 1), v(g, ix + 1, iy + 1)));
    }

    private double v(short[] g, int x, int y) {
        return g[Mth.clamp(y, 0, hauteurGrille - 1) * largeur + Mth.clamp(x, 0, largeur - 1)];
    }

    // ---------------------------------------------------------------- géométrie

    /** Demi-largeur du canyon en blocs (~75 en 1:250), un peu plus large aux petites échelles. */
    public static double demiLargeur() {
        return 75.0 * Math.pow((double) ECHELLE_REFERENCE / Terrain.echelle(), 0.26);
    }

    /** Valeurs d'une colonne. */
    private record Point(double e, double p, double r, double distBlocs, double t, double fraction,
                         double intensite, double fondu) {
    }

    private Point point(int x, int z) {
        charger();
        double lon = Terrain.lon(x), lat = Terrain.lat(z);
        double e = echant(alt, lon, lat), p = echant(plateau, lon, lat), r = echant(fleuve, lon, lat);
        double db = echant(distance, lon, lat) * 100.0 * Terrain.BLOCS_PAR_DEGRE / 111_320.0;
        // le canyon naît à Lees Ferry et finit aux Grand Wash Cliffs : il s'y rétrécit jusqu'au lit du fleuve
        double intensite = lisse((lon - LON_GRAND_WASH) / 0.25) * (1.0 - lisse((lon - LON_LEES_FERRY + 0.25) / 0.25));
        double w = demiLargeur() * Math.max(intensite, 0.06);
        // parois découpées : amphithéâtres, éperons et canyons latéraux
        double d = db, plancher = Math.min(6.0, w * 0.3);
        if (db >= plancher) {
            double wf = demiLargeur();
            d = Math.max(plancher, db + bruit.noise(x / (wf * 0.9), 0.0, z / (wf * 0.9)) * w * 0.35
                    + bruit.noise(x / 23.0, 1.0, z / 23.0) * w * 0.07);
        }
        double t = d / w;
        double g = Mth.clamp(profil(Mth.clamp(t, 0.0, 1.0)), 0.0, 1.0);
        // buttes isolées (temples de Vishnu, Zoroaster…) : sommet vers le Supai, flancs en gradins
        if (t > 0.28 && t < 0.92) {
            double wb = demiLargeur();
            double b = bruitButtes.noise(x / (wb * 0.45), 7.0, z / (wb * 0.45));
            if (b > 0.25) {
                double sb = Mth.clamp((b - 0.25) / 0.15, 0.0, 1.0);
                double gt = SOMMET_COUCHE[3] + (1.0 - sb) * (g - SOMMET_COUCHE[3]);
                g = Math.min(g, gradin(gt));
            }
        }
        double bord = Math.min(Math.min(lon - lon0, lonMax() - lon), Math.min(lat0 - lat, lat - latMin()));
        return new Point(e, p, r, db, t, g, intensite, lisse(bord / FONDU));
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
        charger();
        double lon = Terrain.lon(x), lat = Terrain.lat(z);
        return lon > lon0 && lon < lonMax() && lat < lat0 && lat > latMin();
    }

    @Override
    public double hauteur(int x, int z, double h) {
        return calcul(point(x, z), h);
    }

    /** Hauteur exacte du sol (y) pour la sculpture bloc par bloc, ou NaN hors du canyon. */
    public double hauteurNette(int x, int z) {
        if (!concerne(x, z)) return Double.NaN;
        Point pt = point(x, z);
        if (!dansCanyon(pt)) return Double.NaN;
        return calcul(pt, Terrain.get().hauteur(x, z));
    }

    private double calcul(Point pt, double h) {
        double base = Terrain.blocsDepuisAltitude(pt.e());
        double rebord = yRebord(pt);
        double y;
        if (pt.t() <= 1.0) {
            y = rebord - pt.fraction() * (rebord - PIED);
        } else {
            // autour du canyon : rejoint le plateau réel sur une bande courte
            y = Mth.lerp(lisse((pt.t() - 1.0) / 0.45), rebord, base);
        }
        // le Colorado (~6 blocs de large) et les lacs (Mead, Mohave, Powell) au niveau du fleuve
        double lit = Math.max(1.0 - lisse((pt.distBlocs() - 2.5) / 1.5), 1.0 - lisse((pt.e() - pt.r() - 6.0) / 20.0));
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
    public double rebordSiCanyon(int x, int z) {
        if (!concerne(x, z)) return Double.NaN;
        Point pt = point(x, z);
        return dansCanyon(pt) ? yRebord(pt) : Double.NaN;
    }

    /** Fraction de profondeur (0 = rebord, 1 = fleuve) d'un bloc à la hauteur y. */
    public static double fraction(double y, double rebord) {
        return Mth.clamp((rebord - y) / (rebord - PIED), 0.0, 1.0);
    }

    private static double lisse(double t) {
        t = Mth.clamp(t, 0.0, 1.0);
        return t * t * (3 - 2 * t);
    }
}

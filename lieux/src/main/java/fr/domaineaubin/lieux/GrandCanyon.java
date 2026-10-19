package fr.domaineaubin.lieux;

import fr.domaineaubin.terre.api.Lieu;
import fr.domaineaubin.terre.monde.Terrain;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.util.Mth;

import java.io.DataInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.UncheckedIOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.zip.GZIPInputStream;

/**
 * Grand Canyon (Arizona), d'après le relief réel (ETOPO 2022, un point tous les 450 m) : tracé du Colorado,
 * Marble Canyon, canyons latéraux, buttes et plateaux à leur vraie place, du lac Powell au lac Mohave.
 * <p>
 * La hauteur du monde étant fixe, le canyon réel serait ~15 fois trop raide en 1:250 : les données sont
 * élargies 3 fois autour du talweg (le fleuve et les environs lointains restent à leur place).
 * Le relief est remis à l'échelle verticale du mod : le rebord garde sa hauteur (plateau réel), le fleuve
 * descend sous le niveau de la mer (l'aquifère le remplit), et la paroi suit les vraies couches géologiques
 * (Kaibab, Coconino, Supai, Redwall, Tonto, schiste de Vishnu…) : falaise raide pour les couches dures,
 * pente pour les tendres. Les lacs Mead et Mohave sont remplis au niveau du fleuve.
 * Réglé pour l'échelle 1:250 (les largeurs sont réelles à toutes les échelles, la hauteur est fixe).
 * Données préparées par outils/grand_canyon_dem.py.
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

    /** Couches réelles sous le rebord : épaisseur (m) et falaise (dure) ou pente (tendre). */
    private static final double[] EPAISSEUR = {90, 70, 100, 100, 70, 70, 70, 70, 150, 120, 100, 60};
    private static final boolean[] FALAISE = {true, false, true, false, true, false, true, false, true, true, false, true};
    private static final double SOMME;
    static {
        double s = 0;
        for (double e : EPAISSEUR) s += e;
        SOMME = s;
    }
    /** Nombre de couches : les 12 ci-dessus + le schiste de Vishnu (gorge intérieure, au plus 300 m). */
    public static final int NB_COUCHES = EPAISSEUR.length + 1;

    private double lon0, lat0, pasLon, pasLat;
    private int largeur, hauteurGrille;
    private short[] alt, plateau, fleuve, distance;
    private volatile boolean charge;

    private GrandCanyon() {
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

    /** Valeurs d'une colonne : altitude, rebord, fleuve (m), distance au fleuve (m), poids du canyon et du lieu. */
    private record Point(double lon, double lat, double e, double p, double r, double dist, double canyon, double fondu) {
        double profondeur() { return p - e; }
        double span() { return Math.max(p - r, 1.0); }
    }

    private Point point(int x, int z) {
        charger();
        double lon = Terrain.lon(x), lat = Terrain.lat(z);
        double e = echant(alt, lon, lat), p = echant(plateau, lon, lat), r = echant(fleuve, lon, lat);
        double dist = echant(distance, lon, lat) * 100.0;
        // canyon : creusé sous le plateau, près du Colorado, entre Lees Ferry et les Grand Wash Cliffs
        double canyon = lisse((p - e - 15.0) / 60.0)
                * lisse((lon - LON_GRAND_WASH) / 0.12) * (1.0 - lisse((lon - LON_LEES_FERRY) / 0.08))
                * (1.0 - lisse((dist - 32000.0) / 10000.0));
        double bord = Math.min(Math.min(lon - lon0, lonMax() - lon), Math.min(lat0 - lat, lat - latMin()));
        return new Point(lon, lat, e, p, r, dist, canyon, lisse(bord / FONDU));
    }

    /**
     * Épaisseurs des couches pour un canyon de profondeur span (m) : la gorge de Vishnu fait au plus 300 m,
     * les autres couches s'étirent ensemble pour remplir le reste (Marble Canyon, moins profond, s'arrête plus haut).
     */
    private static double epaisseur(int i, double span) {
        double vishnu = Math.min(Math.max(span - SOMME, 0.0), 300.0);
        if (i == EPAISSEUR.length) return vishnu;
        return EPAISSEUR[i] * Math.max(1.0, (span - vishnu) / SOMME);
    }

    /**
     * Profondeur « sculptée ». Version nette (bloc par bloc, pour la feature) : chaque couche dure devient une
     * falaise verticale suivie d'un replat. Version douce (pour le bruit du terrain, interpolé tous les 4 blocs) :
     * simple suivi du relief, sinon l'interpolation vanilla fabrique des pics et des surplombs.
     */
    private static double sculpte(double dm, double span, boolean net) {
        if (!net) return dm;
        double out = 0.0, a = 0.0;
        for (int i = 0; i < NB_COUCHES; i++) {
            double ep = epaisseur(i, span);
            if (ep <= 0) continue;
            double u = Mth.clamp((dm - a) / ep, 0.0, 1.0);
            boolean falaise = i == EPAISSEUR.length || FALAISE[i];
            out += ep * (falaise ? Mth.clamp((u - 0.5) * 8.0 + 0.5, 0.0, 1.0) : u);
            a += ep;
        }
        return out;
    }

    /** Couche géologique (0 = Kaibab … 12 = Vishnu) à une profondeur dm (m) sous le rebord. */
    public static int couche(double dm, double span) {
        double a = 0.0;
        int c = 0;
        for (int i = 0; i < NB_COUCHES; i++) {
            if (dm >= a) c = i;
            a += epaisseur(i, span);
        }
        return c;
    }

    private static double yRebord(Point pt) {
        return Terrain.blocsDepuisAltitude(pt.p());
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
        return calcul(point(x, z), h, false);
    }

    /** Hauteur exacte du sol (y) avec les falaises nettes, ou NaN si la colonne n'est pas dans le canyon. */
    public double hauteurNette(int x, int z) {
        if (!concerne(x, z)) return Double.NaN;
        Point pt = point(x, z);
        if (pt.canyon() * pt.fondu() <= 0.3) return Double.NaN;
        return calcul(pt, Terrain.get().hauteur(x, z), true);
    }

    private double calcul(Point pt, double h, boolean net) {
        double base = Terrain.blocsDepuisAltitude(pt.e());
        double rebord = yRebord(pt);
        double paroi = rebord - Math.min(sculpte(pt.profondeur(), pt.span(), net) / pt.span(), 1.0) * (rebord - PIED);
        double y = Mth.lerp(pt.canyon(), base, paroi);
        // le Colorado (~5 blocs de large en 1:250) et les lacs (Mead, Mohave, Powell) au niveau du fleuve
        double lit = Math.max(1.0 - lisse((pt.dist() - 350.0) / 250.0), 1.0 - lisse((pt.e() - pt.r() - 6.0) / 20.0));
        y = Mth.lerp(lit, y, FOND);
        return Mth.lerp(pt.fondu(), h, y);
    }

    @Override
    public boolean dansBiome(int x, int z) {
        if (!concerne(x, z)) return false;
        Point pt = point(x, z);
        return pt.canyon() * pt.fondu() > 0.3;
    }

    /** Tout le canyon et les abords des lacs : l'aquifère y prend le niveau de la mer (le fleuve ne s'assèche plus). */
    @Override
    public boolean inonde(int x, int z, double hauteur) {
        Point pt = point(x, z);
        return pt.canyon() * pt.fondu() > 0.05 || pt.dist() < 3000.0 || pt.e() - pt.r() < 60.0;
    }

    /** Dans le canyon, son biome descend jusqu'au fond (sinon les replats et parois prennent le biome froid du plateau). */
    @Override
    public double basBiome(int x, int z, double hauteur) {
        return FOND - 10.0;
    }

    /**
     * Pour les strates : {y du rebord, profondeur réelle du canyon en m} si la colonne est dans le canyon, sinon null.
     */
    public double[] strates(int x, int z) {
        if (!concerne(x, z)) return null;
        Point pt = point(x, z);
        if (pt.canyon() * pt.fondu() <= 0.3) return null;
        return new double[]{yRebord(pt), pt.span()};
    }

    /** Profondeur réelle (m) sous le rebord d'un bloc à la hauteur y. */
    public static double profondeurReelle(double y, double rebord, double span) {
        return Mth.clamp((rebord - y) / (rebord - PIED), 0.0, 1.0) * span;
    }

    private static double lisse(double t) {
        t = Mth.clamp(t, 0.0, 1.0);
        return t * t * (3 - 2 * t);
    }
}

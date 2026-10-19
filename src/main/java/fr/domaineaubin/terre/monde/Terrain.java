package fr.domaineaubin.terre.monde;

import fr.domaineaubin.terre.api.Lieu;
import fr.domaineaubin.terre.api.LieuxTerre;
import net.minecraft.util.Mth;
import net.minecraft.util.RandomSource;
import net.minecraft.world.level.levelgen.synth.ImprovedNoise;

/**
 * Transforme la carte de la Terre en terrain Minecraft.
 * Prototype : échelle 1:1000 fixe (1 bloc ≈ 1 km), x = longitude, z = -latitude.
 */
public final class Terrain {
    /** 1:1000 : un degré de longitude ou de latitude = 111,32 blocs. */
    /** Blocs par degré : 1:1000 = 111,32 ; 1:500 = 222,64 (défaut) ; 1:250 = 445,28. Fixé au démarrage du monde. */
    public static volatile double BLOCS_PAR_DEGRE = 222.64;
    private static volatile int echelle = 500;

    /** Active l'échelle du monde chargé (250, 500 ou 1000). */
    public static synchronized void activer(int nouvelle) {
        if (nouvelle != echelle) {
            echelle = nouvelle;
            BLOCS_PAR_DEGRE = 111.32 * 1000.0 / nouvelle;
            Terrain t = instance;
            if (t != null) t.fleuves = null;   // les fleuves dépendent de l'échelle
            generation++;                       // invalide les caches de colonnes
        }
    }

    public static int echelle() {
        return echelle;
    }
    public static final int NIVEAU_MER = 63;

    private static volatile Terrain instance;

    public static Terrain get() {
        Terrain t = instance;
        if (t == null) {
            synchronized (Terrain.class) {
                t = instance;
                if (t == null) {
                    t = new Terrain(CarteTerre.charger());
                    instance = t;
                }
            }
        }
        return t;
    }

    private final CarteTerre carte;
    private final ImprovedNoise bruitCote;
    private final ImprovedNoise bruitDetail;

    private Terrain(CarteTerre carte) {
        this.carte = carte;
        RandomSource r = RandomSource.create(20261014L);
        this.bruitCote = new ImprovedNoise(r);
        this.bruitDetail = new ImprovedNoise(r);
    }

    public CarteTerre carte() { return carte; }

    // ---------------------------------------------------------------- cache par colonne

    /** Valeurs partagées d'une colonne : calculées une fois, réutilisées par toutes les sorties et les biomes. */
    private record Colonne(int x, int z, int generation, double sd, double alt, double pente, Riviere r, double h, boolean lieu) {
    }

    private static volatile int generation = 0;
    private static final int TAILLE_CACHE = 256;
    private final ThreadLocal<Colonne[]> cache = ThreadLocal.withInitial(() -> new Colonne[TAILLE_CACHE]);

    private Colonne colonne(int x, int z) {
        int i = ((x >> 2) * 31 + (z >> 2) * 17 + (x & 3) * 7 + (z & 3)) & (TAILLE_CACHE - 1);
        Colonne[] tab = cache.get();
        Colonne c = tab[i];
        int g = generation;
        if (c != null && c.x == x && c.z == z && c.generation == g) return c;
        double sd = distanceCote(x, z);
        double alt = altitudeReelle(x, z);
        double pente = sd >= 0 ? pente(x, z) : 0.0;
        Riviere r = sd >= 0 ? riviereBrute(x, z) : null;
        double h = calculerHauteur(x, z, sd, alt, pente, r);
        // lieux uniques (addons) : ils reprennent la main sur le relief de leur zone
        Lieu lieu = LieuxTerre.liste().isEmpty() ? null : LieuxTerre.a(x, z);
        if (lieu != null) h = lieu.hauteur(x, z, h);
        c = new Colonne(x, z, g, sd, alt, pente, r, h, lieu != null);
        tab[i] = c;
        return c;
    }

    public static double lon(double x) { return x / BLOCS_PAR_DEGRE; }
    public static double lat(double z) { return -z / BLOCS_PAR_DEGRE; }
    public static double x(double lon) { return lon * BLOCS_PAR_DEGRE; }
    public static double z(double lat) { return -lat * BLOCS_PAR_DEGRE; }

    /** Distance signée à la côte (minutes d'arc), avec un bruit qui découpe le trait de côte. */
    public double distanceCote(int x, int z) {
        double sd = carte.cote(lon(x), lat(z));
        double n = bruitCote.noise(x / 37.0, 0, z / 37.0) * 0.8 + bruitCote.noise(x / 11.0, 10, z / 11.0) * 0.35;
        return sd + n;
    }

    public double altitudeReelle(int x, int z) {
        return carte.relief(lon(x), lat(z));
    }

    /** Pente réelle approximative en mètres par kilomètre. */
    public double pente(int x, int z) {
        double lo = lon(x), la = lat(z), d = 0.05;
        double gx = carte.relief(lo + d, la) - carte.relief(lo - d, la);
        double gz = carte.relief(lo, la + d) - carte.relief(lo, la - d);
        return Math.sqrt(gx * gx + gz * gz) / (2 * d * 111.32);
    }

    /** Correspondance altitude réelle (m) -> hauteur Minecraft (y), voir le plan v1. */
    public static double blocsDepuisAltitude(double alt) {
        if (alt < 0) {
            if (alt > -200) return 62 + alt / 200.0 * 17;                       // plateau continental : y 45 à 62
            return 45 - Math.min((-alt - 200) / 5800.0, 1.0) * 15;              // grands fonds : y 30 à 45
        }
        if (alt <= 500) return 64 + alt / 500.0 * 16;                            // plaines : y 64 à 80
        if (alt <= 2000) return 80 + (alt - 500) / 1500.0 * 60;                  // collines et plateaux : y 80 à 140
        return 140 + Math.min((alt - 2000) / 6800.0, 1.0) * 160;                 // montagnes : y 140 à 300
    }

    private static double lisse(double t) {
        return t * t * (3 - 2 * t);
    }

    /** Fond de vallée (y lissé) en dessous duquel le fleuve est en eau ; au-dessus de VALLEE_SECHE, plus de vallée. */
    public static final double VALLEE_EAU = 80.0, VALLEE_SECHE = 86.0;
    /** Largeur maximale de la pente douce entre la rive et le terrain naturel, en blocs. */
    public static final double VALLEE_MAX = 64.0;

    /** Largeur de la pente de vallée : plus le fleuve est encaissé, plus elle est large (pas de falaises). */
    public static double largeurVallee(Riviere r) {
        return Mth.clamp((r.niveau() - NIVEAU_MER) * 4.0, 2.0 * r.demiLargeur(), VALLEE_MAX);
    }

    /**
     * Hauteur visée du sol en y, vallées des fleuves comprises.
     * Les fleuves sont creusés jusque sous le niveau de la mer : c'est le moteur (aquifère) qui y met l'eau,
     * comme pour les rivières vanilla, avant les arbres, plantes et villages.
     */
    public double hauteur(int x, int z) {
        return colonne(x, z).h();
    }

    private double calculerHauteur(int x, int z, double sd, double alt, double pente, Riviere r) {
        double h = hauteurBase(x, z, sd, alt, pente);
        if (r == null) return h;
        double k = Mth.clamp((VALLEE_SECHE - r.niveau()) / (VALLEE_SECHE - VALLEE_EAU), 0.0, 1.0);
        if (k <= 0.0) return h;
        double cible;
        if (r.distance() <= r.demiLargeur()) {
            // lit : profil en creux sous la surface de l'eau (y 62)
            double u = r.distance() / r.demiLargeur();
            cible = (NIVEAU_MER - 1) - Math.max(1.0, r.profondeur() * (1.0 - u * u)) + 0.5;
        } else {
            // rive à un bloc au-dessus de l'eau, puis pente douce jusqu'au terrain naturel
            double t = lisse(Mth.clamp((r.distance() - r.demiLargeur()) / largeurVallee(r), 0.0, 1.0));
            cible = Mth.lerp(t, NIVEAU_MER + 0.5, h);
        }
        return Math.min(h, Mth.lerp(k, h, cible));
    }

    // ---------------------------------------------------------------- fleuves

    /** Infos d'un cours d'eau au voisinage d'une colonne. */
    public record Riviere(double distance, double demiLargeur, double niveau, int profondeur, int classe, int cx, int cz) {
    }

    private volatile Fleuves fleuves;

    private Fleuves fleuves() {
        if (fleuves == null) {
            synchronized (this) {
                if (fleuves == null) fleuves = Fleuves.charger(BLOCS_PAR_DEGRE, this::niveauEau);
            }
        }
        return fleuves;
    }

    public static double demiLargeur(int classe) {
        return switch (classe) { case 1 -> 30.0; case 2 -> 12.0; default -> 4.5; };
    }

    public static int profondeur(int classe) {
        return switch (classe) { case 1 -> 6; case 2 -> 4; default -> 2; };
    }

    /** Cours d'eau le plus proche s'il influence cette colonne (vallée comprise), sinon null. */
    public Riviere riviere(int x, int z) {
        Colonne c = colonne(x, z);
        return c.r();
    }

    /**
     * Distance (blocs) à l'axe du cours d'eau le plus proche et sa classe (1 fleuve, 2 rivière, 3 ruisseau),
     * jusqu'à {@link Fleuves#RAYON_INDEX} blocs ; null au-delà. Pour les addons de lieux.
     */
    public double[] coursEau(int x, int z) {
        Fleuves.Proche p = fleuves().proche(x, z);
        if (p == null) return null;
        return new double[]{p.distance(), p.classe()};
    }

    private Riviere riviereBrute(int x, int z) {
        Fleuves.Proche p = fleuves().proche(x, z);
        if (p == null) return null;
        double hw = demiLargeur(p.classe());
        if (p.distance() > hw + VALLEE_MAX) return null;
        // fond de vallée pris sur l'axe du cours d'eau : le même d'une rive à l'autre
        double niveau = niveauVallee(Mth.floor(p.cx()), Mth.floor(p.cz()));
        return new Riviere(p.distance(), hw, niveau, profondeur(p.classe()), p.classe(), Mth.floor(p.cx()), Mth.floor(p.cz()));
    }

    /**
     * Fond de vallée : relief très lissé (minimum de 5 points espacés d'environ 6 km), en y.
     * Sert à décider si le fleuve est en eau (fond bas) ou une vallée sèche (montagne), et la largeur de la vallée.
     */
    public double niveauVallee(int x, int z) {
        double lo = lon(x), la = lat(z), d = 0.055, m = Double.MAX_VALUE;
        double[][] pts = {{0, 0}, {d, 0}, {-d, 0}, {0, d}, {0, -d}};
        for (double[] o : pts) m = Math.min(m, carte.relief(lo + o[0], la + o[1]));
        return blocsDepuisAltitude(Math.max(m, 1.0));
    }

    /** Niveau de l'eau d'un tronçon : suit le relief réel lissé, jamais sous la mer. */
    private int niveauEau(double x, double z) {
        double alt = carte.relief(lon(x), lat(z));
        return Math.max(NIVEAU_MER, Mth.floor(blocsDepuisAltitude(Math.max(alt, 1.0))) - 1);
    }

    /** Hauteur visée du sol sans les fleuves. */
    private double hauteurBase(int x, int z, double sd, double alt, double pente) {
        if (sd >= 0) {
            double p = Mth.clamp(pente / 80.0, 0.0, 1.0);
            double detail = bruitDetail.noise(x / 48.0, 0, z / 48.0) * (1.2 + 6.0 * p)
                    + bruitDetail.noise(x / 13.0, 5, z / 13.0) * 0.6;
            double hTerre = blocsDepuisAltitude(Math.max(alt, 1.0)) + detail;
            return Mth.lerp(lisse(Mth.clamp(sd / 2.0, 0.0, 1.0)), NIVEAU_MER + 0.6, Math.max(hTerre, NIVEAU_MER + 0.6));
        }
        double hMer = blocsDepuisAltitude(Math.min(alt, -1.0));
        return Mth.lerp(lisse(Mth.clamp(-sd / 2.0, 0.0, 1.0)), NIVEAU_MER - 1.0, Math.min(hMer, NIVEAU_MER - 1.0));
    }

    // ---------------------------------------------------------------- sorties pour le routeur de bruit vanilla

    /** depth vanilla = gradient(y) + offset ; gradient(y) = 1,5 - (y + 64) / 128, donc offset = (H - 128) / 128. */
    public double offset(int x, int z) {
        return (hauteur(x, z) - 128.0) / 128.0;
    }

    /** Grand facteur = terrain collé à la hauteur visée (plat) ; petit facteur = relief plus libre. */
    public double facteur(int x, int z) {
        Colonne c = colonne(x, z);
        if (c.lieu()) return 30.0;          // lieu sculpté : le terrain suit exactement sa forme
        if (c.sd() < 0) return 6.0;
        double p = Mth.clamp(c.pente() / 80.0, 0.0, 1.0);
        double f = Mth.lerp(p, 8.0, 5.0);
        // près des cours d'eau, le terrain colle au profil de la vallée (pas de bosses dans le lit ni de creux sur la rive)
        Riviere r = c.r();
        if (r != null) {
            double t = Mth.clamp(1.0 - (r.distance() - r.demiLargeur()) / largeurVallee(r), 0.0, 1.0);
            f = Mth.lerp(t, f, 30.0);
        }
        return f;
    }

    /** Pics déchiquetés seulement dans les vraies montagnes raides. */
    public double dentelure(int x, int z) {
        Colonne c = colonne(x, z);
        if (c.sd() < 0 || c.r() != null || c.lieu()) return 0.0;
        double alt = c.alt();
        return Mth.clamp((c.pente() - 40.0) / 120.0, 0.0, 1.0) * Mth.clamp((alt - 1200.0) / 1500.0, 0.0, 1.0) * 0.2;
    }

    /**
     * Ajout au bruit d'« inondation » des aquifères vanilla : dans le lit et les vallées des fleuves en eau
     * (et au fond des lieux creusés sous la mer), l'aquifère prend toujours le niveau de la mer.
     * Sans ça, le moteur laisse au hasard les lits étroits à sec.
     */
    public double inondation(int x, int z) {
        Colonne c = colonne(x, z);
        if (c.lieu()) {
            Lieu l = LieuxTerre.a(x, z);
            if (l != null && l.inonde(x, z, c.h())) return 2.0;
        }
        Riviere r = c.r();
        if (r == null || r.distance() > r.demiLargeur() + 40.0) return 0.0;
        double k = Mth.clamp((VALLEE_SECHE - r.niveau()) / (VALLEE_SECHE - VALLEE_EAU), 0.0, 1.0);
        return k > 0.5 ? 2.0 : 0.0;
    }

    /** Continentalité vanilla (sert au choix des biomes : océan, côte, intérieur). */
    public double continents(int x, int z) {
        Colonne c = colonne(x, z);
        double sd = c.sd();
        if (sd >= 0) {
            double blocs = sd * BLOCS_PAR_DEGRE / 60.0;
            return -0.11 + Mth.clamp(blocs / 150.0, 0.0, 1.0) * 0.6;
        }
        if (sd > -3) return -0.11 + sd / 3.0 * 0.08;
        double alt = c.alt();
        if (alt > -1000) return Mth.lerp(Mth.clamp(-alt / 1000.0, 0.0, 1.0), -0.19, -0.455);
        return Mth.lerp(Mth.clamp((-alt - 1000) / 3000.0, 0.0, 1.0), -0.46, -1.05);
    }

    /**
     * Érosion vanilla (sert au choix des biomes) tirée du vrai relief :
     * basse sur les vraies montagnes raides (pics, pentes), haute dans les plaines (biomes plats).
     */
    public double erosion(int x, int z) {
        Colonne c = colonne(x, z);
        if (c.sd() < 0) return 0.0;
        double alt = c.alt();
        double mont = Mth.clamp((alt - 1500.0) / 2000.0, 0.0, 1.0) * Mth.clamp(c.pente() / 60.0, 0.0, 1.0);
        double e = 0.45 - 0.6 * Mth.clamp((alt - 300.0) / 1500.0, 0.0, 1.0) - 0.7 * mont
                + bruitDetail.noise(x / 300.0, 50, z / 300.0) * 0.15;
        return Mth.clamp(e, -1.0, 1.0);
    }
}

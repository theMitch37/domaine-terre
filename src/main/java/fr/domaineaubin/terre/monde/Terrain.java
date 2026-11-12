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
    /** Blocs par degré : 1:1000 = 111,32 ; 1:500 = 222,64 ; 1:250 = 445,28 (défaut). Fixé au démarrage du monde. */
    public static volatile double BLOCS_PAR_DEGRE = 445.28;
    private static volatile int echelle = 250;

    /** Active l'échelle du monde chargé (250, 500 ou 1000). */
    public static synchronized void activer(int nouvelle) {
        double bpd = 111.32 * 1000.0 / nouvelle;
        // on compare aussi les blocs par degré : l'échelle et BLOCS_PAR_DEGRE doivent toujours aller ensemble
        if (nouvelle != echelle || bpd != BLOCS_PAR_DEGRE) {
            echelle = nouvelle;
            BLOCS_PAR_DEGRE = bpd;
            Terrain t = instance;
            if (t != null) t.fleuves = null;   // les fleuves dépendent de l'échelle
            generation++;                       // invalide les caches de colonnes
        }
    }

    public static int echelle() {
        return echelle;
    }
    public static final int NIVEAU_MER = 63;
    /** Hauteur du monde (10/11/2026, décision de Maxime) : y -512 à 1023 ; le fond des fosses reste au-dessus de la bedrock. */
    public static final int Y_MIN = -512, Y_MAX = 1024;
    static final double PLANCHER_FOSSES = -505.0;

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
    private final CotesFines cotes;
    private final Lacs lacs;

    private Terrain(CarteTerre carte) {
        this.carte = carte;
        RandomSource r = RandomSource.create(20261014L);
        this.bruitCote = new ImprovedNoise(r);       // gardé (même hasard pour bruitDetail) ; inutile avec les côtes fines
        this.bruitDetail = new ImprovedNoise(r);
        this.cotes = CotesFines.charger();
        this.lacs = Lacs.charger();
    }

    public CarteTerre carte() { return carte; }

    // ---------------------------------------------------------------- cache par colonne

    /** Valeurs partagées d'une colonne : calculées une fois, réutilisées par toutes les sorties et les biomes. */
    private record Colonne(int x, int z, int generation, double sd, double alt, double pente, Riviere r, double h, double poids,
                           int niveauLac, int bergeLac, int eauLac, int eauRiv, int bergeRiv, int litRiv) {
        boolean lieu() {
            return poids > 0.0;
        }

        /** Dans un lac (eau de lac à niveauLac) ? */
        boolean lac() {
            return niveauLac != SANS_LAC;
        }
    }

    /** Pas de lac dans cette colonne. */
    public static final int SANS_LAC = Integer.MIN_VALUE;

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
        Lacs.Proche lp = sd >= 0 && lacs != null ? lacs.proche(lon(x + 0.5), lat(z + 0.5)) : null;
        int nivLac = lp == null ? SANS_LAC : (int) Math.min(niveauLac(lacs.altitude(lp.lac())), lacs.plafond(lp.lac()));
        // relief fin (10/11/2026, rivières « en escalier entre deux murs ») : le niveau d'un cours d'eau venait de la
        // carte 3' (fond de vallée lissé, plus haut que le vrai) ; sur le relief fin, le vrai fond de vallée est plus
        // bas et la berge, tenue au-dessus de l'eau, faisait un canal perché. L'eau descend au vrai fond de vallée,
        // pris sur l'axe du cours d'eau (le même des deux rives) ; elle ne monte jamais plus haut qu'avant.
        // (le niveau est calculé par Fleuves sur le vrai fond de vallée, sommet par sommet : niveauFin)
        // près d'un lac (et dedans), un cours d'eau prend au moins le niveau du lac : il y entre et en sort à niveau
        boolean presLac = lp != null && (lp.distance() > 0 || -lp.distance() <= BERGE);
        // 11/11/2026 (test en jeu, Valais : « une immense cascade ») : un lac de montagne près du Rhône relevait le fleuve
        // à son niveau, 95 blocs plus haut, sur les colonnes proches du lac seulement : une marche de 95 blocs en
        // travers du fleuve. Un cours d'eau bien plus bas qu'un lac voisin ne le traverse pas : il garde son niveau
        // 12/11/2026 (test en jeu, lac près du Léman à y 99 dont la rive est était à 92-95) : le niveau d'avant compte
        // pour la berge du lac ; un cours d'eau relevé au niveau du lac n'a pas de berges assez hautes pour le tenir
        int eauAvantLac = r == null ? SANS_LAC : r.eau();
        if (r != null && presLac && r.eau() < nivLac && nivLac - r.eau() <= 4) r = r.avecEau(nivLac);
        // près de l'eau, le relief réel en entier (10/11/2026) : l'eau est à sa vraie altitude, les rives aussi (avec
        // une part seulement du détail fin, la rive restait au-dessus ou au-dessous de l'eau : murs, lacs perchés)
        double procheRiv = 0.0, procheLac = 0.0;
        if (r != null) procheRiv = 1.0 - lisse(Mth.clamp((r.distance() - r.demiLargeur() - BERGE_RIVIERE) / 24.0, 0.0, 1.0));
        if (lp != null) procheLac = lp.distance() > 0 ? 1.0 : 1.0 - lisse(Mth.clamp((-lp.distance() - 6.0) / 30.0, 0.0, 1.0));
        double h = calculerHauteur(x, z, sd, alt, pente, r, true, procheRiv, procheLac);
        // lacs (étape C1) : cuvette dans le lac, berges qui descendent jusqu'à son niveau autour
        int niveauLac = SANS_LAC, bergeLac = SANS_LAC, eauLac = SANS_LAC;
        int eauRiv = SANS_LAC, bergeRiv = SANS_LAC, litRiv = SANS_LAC;
        if (r != null && r.distance() <= r.demiLargeur() + EAU_RIVIERE) eauRiv = r.eau();
        if (r != null && r.distance() > r.demiLargeur() && r.distance() <= r.demiLargeur() + BERGE_RIVIERE) bergeRiv = r.eau();
        if (r != null && r.distance() <= r.demiLargeur()) litRiv = r.eau();
        if (lp != null) {
            int niv = nivLac;
            if (lp.distance() > 0) {
                h = fondLac(niv, lp.distance(), lacs.superficie(lp.lac()));
                niveauLac = niv;
                eauLac = niv;
            } else {
                // le lit et la berge d'un cours d'eau gardent leur forme (à niveau du lac) : la berge du lac ne les comble pas
                // 11/11/2026 (test en jeu, Valais : lac de montagne à y 174 au bord de la vallée du Rhône à y 80, son eau
                // pendait en mur de 70 blocs) : la berge d'un cours d'eau bien plus bas que le lac ne remplace pas le
                // rebord du lac, qui retient son eau
                // (12/11/2026) la berge d'un cours d'eau relevé au niveau du lac est tenue au-dessus du lac comme sa rive,
                // sinon l'eau du lac s'échappait par-dessus en nappes sur la pente
                boolean litOuBerge = r != null && r.distance() <= r.demiLargeur() + BERGE_RIVIERE
                        && (eauAvantLac >= niv - 2 || r.distance() <= r.demiLargeur());
                if (!litOuBerge) h = bergeLac(h, niv, -lp.distance());
                if (-lp.distance() < BERGE && !litOuBerge) bergeLac = niv;
                if (-lp.distance() <= BERGE) eauLac = niv;
            }
        }
        // lieux uniques (addons) : ils reprennent la main sur le relief de leur zone
        Lieu lieu = LieuxTerre.liste().isEmpty() ? null : LieuxTerre.a(x, z);
        // lit et berge d'un cours d'eau du mod : à lui, sauf dans un lieu qui le gère lui-même (voir Lieu.gereSesCoursDEau)
        if (lieu != null && !lieu.gereSesCoursDEau() && r != null && r.distance() <= r.demiLargeur() + BERGE_RIVIERE)
            lieu = null;
        double poids = 0.0;
        if (lieu != null) {
            // relief fin (09/11/2026) : les lieux ont été sculptés et raccordés sur le terrain d'avant (carte 3') ; ils
            // reçoivent ce terrain-là, et l'écart avec le relief fin est ajouté à leurs colonnes sculptées, en entier au
            // bord de la zone du lieu et plus du tout à RACCORD_FIN blocs à l'intérieur : plus de marche au bord
            double hAvant = calculerHauteur(x, z, sd, alt, pente, r, false, 0.0, 0.0);
            if (lp != null) {
                if (lp.distance() > 0) hAvant = fondLac(nivLac, lp.distance(), lacs.superficie(lp.lac()));
                else if (!(r != null && r.distance() <= r.demiLargeur() + BERGE_RIVIERE
                        && (eauAvantLac >= nivLac - 2 || r.distance() <= r.demiLargeur()))) hAvant = bergeLac(hAvant, nivLac, -lp.distance());
            }
            double hl = lieu.hauteur(x, z, hAvant);
            // toutes les colonnes de la zone, sculptées ou non, gardent le terrain d'avant à l'intérieur (10/11/2026,
            // Gullfoss : le plateau non sculpté suivait le relief fin, qui y voit la vallée de la Hvítá en V large, et
            // descendait de 12 blocs au pied des parois de la gorge, sculptées sur le terrain d'avant : murs debout)
            // (12/11/2026) aussi en s'approchant d'un cours d'eau du mod, qui garde son lit et sa berge dans le lieu
            double inter = interieurLieu(x, z);
            if (r != null && !lieu.gereSesCoursDEau())
                inter = Math.min(inter, Math.max(0.0, r.distance() - r.demiLargeur() - BERGE_RIVIERE));
            if (h != hAvant) hl += (h - hAvant) * (1.0 - Mth.clamp(inter / RACCORD_FIN, 0.0, 1.0));
            h = hl;
            // (12/11/2026, banc Mer de Glace : le Rhône à Martigny et la Doire baltée passaient dans la loupe du
            // Mont-Blanc en tranchée de 100 blocs de haut, droite) : en s'approchant d'un cours d'eau du mod, le terrain
            // du lieu descend en vallée vers lui (pente 2 au bord de la berge, plus raide en s'éloignant)
            boolean creusee = false;
            if (r != null && !lieu.gereSesCoursDEau()) {
                double dv = Math.max(0.0, r.distance() - r.demiLargeur() - BERGE_RIVIERE);
                double plafond = r.eau() + 1.0 + 2.0 * dv + 0.05 * dv * dv;
                if (h > plafond) {
                    // s'efface de 16 à 48 blocs du lit : à mi-chemin entre deux cours d'eau de niveaux différents, le
                    // plus proche change d'un coup (banc : mur droit de 15 blocs à la source de la Doire baltée)
                    double k = 1.0 - lisse(Mth.clamp((dv - 16.0) / 32.0, 0.0, 1.0));
                    h = Mth.lerp(k, h, plafond);
                    creusee = k > 0.5;
                }
            }
            poids = Mth.clamp(lieu.poids(x, z), 0.0, 1.0);
            // un lieu sculpté (Grand Canyon, Verdon) gère l'eau de son cours d'eau lui-même (niveau de la mer)
            eauRiv = SANS_LAC;
            bergeRiv = SANS_LAC;
            litRiv = SANS_LAC;
            // les lacs du mod n'existent pas dans un lieu (son relief réel a ses propres lacs, ou n'en a pas)
            niveauLac = SANS_LAC;
            bergeLac = SANS_LAC;
            eauLac = SANS_LAC;
            // lot 2 : eau propre au lieu (torrents, lacs, cascades en altitude), posée comme un lit par FleuveFeature
            int el = lieu.eau(x, z);
            // l'eau du lieu ne reste pas suspendue au-dessus de la vallée creusée
            if (creusee && el != SANS_LAC && el > h + 1.0) el = SANS_LAC;
            if (el != SANS_LAC) {
                eauRiv = el;
                litRiv = el;
            }
        }
        if (niveauLac != SANS_LAC) litRiv = SANS_LAC;          // dans un lac, c'est l'eau du lac
        c = new Colonne(x, z, g, sd, alt, pente, r, h, poids, niveauLac, bergeLac, eauLac, eauRiv, bergeRiv, litRiv);
        tab[i] = c;
        return c;
    }

    public static double lon(double x) { return x / BLOCS_PAR_DEGRE; }
    public static double lat(double z) { return -z / BLOCS_PAR_DEGRE; }
    public static double x(double lon) { return lon * BLOCS_PAR_DEGRE; }
    public static double z(double lat) { return -lat * BLOCS_PAR_DEGRE; }

    /** Minutes d'arc par case de la carte des côtes fines. */
    private static final double MIN_PAR_CASE = 60.0 / CotesFines.CASES_PAR_DEGRE;

    /**
     * Distance signée à la côte (minutes d'arc, positive dans les terres).
     * 0.3.2 : le vrai trait de côte au bloc près (GSHHG full) près des côtes, sans bruit inventé ; plus loin,
     * la carte 3' donne l'ordre de grandeur, avec le signe de la carte fine.
     */
    public double distanceCote(int x, int z) {
        double grossiere = carte.cote(lon(x), lat(z));
        if (cotes == null) {
            return grossiere + bruitCote.noise(x / 37.0, 0, z / 37.0) * 0.8 + bruitCote.noise(x / 11.0, 10, z / 11.0) * 0.35;
        }
        double fine = cotes.distance(lon(x + 0.5), lat(z + 0.5));
        if (Math.abs(fine) < CotesFines.RAYON) return fine * MIN_PAR_CASE;
        double bord = CotesFines.RAYON * MIN_PAR_CASE;
        return fine > 0 ? Math.max(grossiere, bord) : Math.min(grossiere, -bord);
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
        // 10/11/2026 (décision de Maxime) : monde de y -512 à 1024. Plaines, collines et plateau continental gardent
        // leur hauteur ; seules les hautes montagnes (toit du monde) et les grands fonds sont étirés.
        if (alt < 0) {
            if (alt > -200) return 62 + alt / 200.0 * 20;                       // plateau continental : y 42 à 62 (10 m/bloc)
            if (alt > -6000) return 42 + (alt + 200) / 5800.0 * 292;            // talus, glacis, plaines abyssales : y 42 à -250
            // fosses : y -250 à -420 jusqu'à 9 800 m, puis une faille au fond des plus profondes (Mariannes, Tonga,
            // Philippines, Kermadec) : parois presque verticales de 9 800 à 10 300 m, jusqu'à y -500 (80 blocs)
            double t1 = Math.min((-alt - 6000) / 3800.0, 1.0);
            double t2 = Mth.clamp((-alt - 9800) / 500.0, 0.0, 1.0);
            return -250 - 170 * t1 - 80 * (1 - Math.pow(1 - t2, 2.5));
        }
        if (alt <= 500) return 64 + alt / 500.0 * 16;                            // plaines : y 64 à 80
        if (alt <= 2000) return 80 + (alt - 500) / 1500.0 * 60;                  // collines et plateaux : y 80 à 140
        if (alt <= 4000) return 140 + (alt - 2000) / 2000.0 * 100;               // montagnes : y 140 à 240
        return 240 + Math.min((alt - 4000) / 4849.0, 1.0) * 380;                 // hautes montagnes : y 240 à 620 (Everest)
    }

    private static double lisse(double t) {
        return t * t * (3 - 2 * t);
    }

    // ---------------------------------------------------------------- lacs (étape C1)

    /**
     * Niveau de l'eau d'un lac (y de la première couche d'air au-dessus de l'eau : l'eau remplit y < niveau), depuis
     * l'altitude réelle de sa surface, avec la même courbe que la terre (sous 0 m, la pente des plaines continue).
     */
    public static int niveauLac(double altitude) {
        double y = altitude < 0 ? 64 + altitude / 500.0 * 16 : blocsDepuisAltitude(altitude);
        return Mth.floor(y);
    }

    /**
     * Fond du lac à `d` cases du rivage : une petite marche sous l'eau au bord (sinon le jeu, qui interpole le terrain
     * sur des cellules de 4 blocs, relève le bord du lac au-dessus de l'eau et les lacs étroits perdent un tiers de
     * leur largeur), puis le fond descend en pente douce jusqu'à une
     * profondeur qui grandit avec la superficie (pas de données de profondeur : 3 blocs pour 1 km², 8 pour le Léman,
     * 12 pour le Baïkal), comme le reste exagérée.
     */
    static double fondLac(int niveau, double d, double superficie) {
        double pmax = Mth.clamp(2.0 + 2.2 * Math.log10(superficie + 1.0), 2.0, 14.0);
        double largeur = Mth.clamp(pmax * 3.0, 4.0, 40.0);
        return niveau - 2.9 - (pmax - 1.0) * lisse(Mth.clamp(d / largeur, 0.0, 1.0));
    }

    /**
     * Berge à `d` cases du lac : le terrain descend jusqu'au niveau de l'eau en pente douce (0,6 bloc par bloc) ;
     * sur les 3 premières cases, jamais plus bas que l'eau (la cuvette doit tenir l'eau du lac) ; plus loin, il ne
     * descend sous l'eau que peu à peu (0,3 bloc par bloc).
     */
    static double bergeLac(double h, int niveau, double d) {
        double haut = niveau + 0.6, brut = h;
        // ETOPO met une valeur vide (≈ 0 m) sous les lacs, qui déborde sur la rive (cases de 5 km) : près d'un lac, le
        // terrain ne descend pas sous son niveau (marge qui se relâche de 0,3 bloc par bloc en s'éloignant)
        // 12/11/2026 (banc, lac de Joux : une nappe à son niveau à 34 blocs de la rive, qui se vidait sur la pente) : une
        // cellule d'aquifère dont le point tombe à BERGE cases du lac couvre encore ~16 blocs plus loin ; la rive reste
        // au niveau du lac jusque-là
        h = Math.max(h, haut - 0.3 * Math.max(d - BERGE - 16.0, 0.0));
        // la berge monte de plus en plus raide (vallée glaciaire) puis rejoint le relief entre 36 et 48 cases
        double x = Math.max(d - 2.0, 0.0);
        h = Math.min(h, haut + 0.6 * x + 0.02 * x * x);
        if (d < 3.0) h = Math.max(h, haut);
        return Mth.lerp(lisse(Mth.clamp((d - 40.0) / 8.0, 0.0, 1.0)), h, brut);
    }

    /**
     * Largeur (cases) de la berge tenue au-dessus de l'eau du lac (terrain et plancher de densité). Les aquifères du jeu
     * décident de l'eau par cellules d'environ 16 blocs, à partir d'un point qui peut tomber sur la rive : jusqu'à
     * BERGE cases du lac, l'aquifère reçoit donc le niveau du lac (FluidesMixin), et le sol y reste au-dessus de l'eau.
     */
    static final double BERGE = 20.0;

    /** Niveau d'eau que les aquifères prennent ici : celui du lac (dans le lac et sur sa berge), sinon SANS_LAC. */
    public int niveauLac(int x, int z) {
        return colonne(x, z).eauLac();
    }

    /**
     * Lit et abords d'un cours d'eau (hors lac) : les aquifères n'y mettent pas d'eau (FluidesMixin), c'est FleuveFeature
     * qui remplit le lit, colonne par colonne, à son niveau. Les aquifères décident par cellules de ~16 blocs : là où le
     * niveau descend d'un bloc tous les quelques blocs, ils noyaient l'aval au niveau de l'amont et posaient des
     * barrières de pierre dans le lit.
     */
    public boolean sansAquifere(int x, int z) {
        Colonne c = colonne(x, z);
        return c.eauLac() == SANS_LAC && c.eauRiv() != SANS_LAC;
    }

    /** Niveau de l'eau (l'eau remplit y < niveau) du lit d'un cours d'eau dans cette colonne, ou SANS_LAC. */
    /** Diagnostic (banc) du niveau d'un cours d'eau en ce point. */
    /**
     * Distance (blocs) au bord du lit du cours d'eau du mod le plus proche, ou une grande valeur (12/11/2026, faune :
     * estuaires).
     */
    public double distanceCoursDEau(int x, int z) {
        Fleuves.Proche p = fleuves().proche(x, z);
        return p == null ? Double.MAX_VALUE : Math.max(0.0, p.distance() - demiLargeur(p.classe()));
    }

    /**
     * Niveau du lac du mod le plus proche (à moins de Lacs.RAYON cases), sans tenir compte des lieux, ou SANS_LAC ; avec
     * dedans = vrai, seulement à l'intérieur du lac (12/11/2026 : Grand Canyon, lac Powell dans le fondu du lieu).
     */
    public int niveauLacSansLieu(int x, int z, boolean dedans) {
        if (lacs == null || distanceCote(x, z) < 0) return SANS_LAC;
        Lacs.Proche lp = lacs.proche(lon(x + 0.5), lat(z + 0.5));
        if (lp == null || (dedans && lp.distance() <= 0)) return SANS_LAC;
        return (int) Math.min(niveauLac(lacs.altitude(lp.lac())), lacs.plafond(lp.lac()));
    }

    /** Diagnostic temporaire (12/11/2026, lac de Joux au banc). */
    public String diagnosticColonne(int x, int z) {
        Colonne c = colonne(x, z);
        Lacs.Proche lp = lacs != null ? lacs.proche(lon(x + 0.5), lat(z + 0.5)) : null;
        String l = lp == null ? "aucun lac" : String.format(java.util.Locale.ROOT, "lac %d d=%.1f alt=%.0f niv=%d plafond=%.1f",
                lp.lac(), lp.distance(), lacs.altitude(lp.lac()), niveauLac(lacs.altitude(lp.lac())), lacs.plafond(lp.lac()));
        Lieu li = LieuxTerre.liste().isEmpty() ? null : LieuxTerre.a(x, z);
        if (li != null) l += " lieu " + li.id() + " eau=" + li.eau(x, z) + " hauteur=" + String.format(java.util.Locale.ROOT, "%.1f", li.hauteur(x, z, c.h()));
        return String.format(java.util.Locale.ROOT, "h=%.2f nivLac=%d bergeLac=%d eauLac=%d eauRiv=%d litRiv=%d lieu=%b riv=%s %s",
                c.h(), c.niveauLac(), c.bergeLac(), c.eauLac(), c.eauRiv(), c.litRiv(), c.lieu(),
                c.r() == null ? "-" : String.format(java.util.Locale.ROOT, "d%.1f hw%.1f eau%d", c.r().distance(), c.r().demiLargeur(), c.r().eau()), l);
    }

    public String diagnosticRiviere(int x, int z) {
        Colonne c = colonne(x, z);
        return "lit " + c.litRiv() + " eauRiv " + c.eauRiv() + " eauLac " + c.eauLac() + " lieu " + (LieuxTerre.a(x, z) != null)
                + " h " + String.format(java.util.Locale.ROOT, "%.1f", c.h()) + fleuves().diagnostic(x, z);
    }

    public int eauLit(int x, int z) {
        return colonne(x, z).litRiv();
    }

    /**
     * Niveau du cours d'eau aux abords du lit (jusqu'à EAU_RIVIERE blocs), ou SANS_LAC (11/11/2026). Les aquifères n'y
     * mettent pas d'eau ; un creux plus bas que la rivière y restait à sec (Gambie : vase à sec sous le niveau de la
     * mer à côté de l'eau).
     */
    public int eauAbords(int x, int z) {
        Colonne c = colonne(x, z);
        // seulement au niveau de la mer (estuaires, deltas) : plus haut, une pente qui descend à côté du lit recevait
        // l'eau de la rivière en pans debout (11/11/2026, banc Oberland : 300 trous et murs d'eau, Grimsel)
        if (c.eauLac() != SANS_LAC || c.eauRiv() == SANS_LAC || c.eauRiv() > NIVEAU_MER + 1) return SANS_LAC;
        return c.eauRiv();
    }

    /** Ancien seuil (avant l'étape C2, toute l'eau au niveau de la mer) : plus utilisé, gardé pour les addons. */
    public static final double VALLEE_EAU = 80.0, VALLEE_SECHE = 86.0;
    /** Largeur maximale de la pente douce entre la rive et le terrain naturel, en blocs. */
    public static final double VALLEE_MAX = 64.0;

    /**
     * Largeur de la pente de vallée à une colonne de hauteur h : plus le cours d'eau est encaissé, plus elle est large
     * (pente ~1 pour 2, pas de falaises), au moins deux demi-largeurs du lit.
     */
    public static double largeurVallee(Riviere r, double h) {
        return Mth.clamp((h - r.eau()) * 2.0, 2.0 * r.demiLargeur(), VALLEE_MAX);
    }

    /**
     * Hauteur visée du sol en y, vallées des fleuves comprises.
     * Les fleuves sont creusés jusque sous le niveau de la mer : c'est le moteur (aquifère) qui y met l'eau,
     * comme pour les rivières vanilla, avant les arbres, plantes et villages.
     */
    public double hauteur(int x, int z) {
        return colonne(x, z).h();
    }

    /** Colonne sous l'eau du lit d'un fleuve ou d'une rivière (biome « fleuve » du terroir). */
    public boolean eauDeFleuve(int x, int z) {
        Colonne c = colonne(x, z);
        return c.litRiv() != SANS_LAC && c.h() < c.litRiv();
    }

    /** Colonne sous l'eau d'un lac du mod (le fond est sous le niveau du lac) : biome « lac » du terroir. */
    public boolean eauDeLac(int x, int z) {
        Colonne c = colonne(x, z);
        return c.lac() && c.h() < c.niveauLac();
    }

    private double calculerHauteur(int x, int z, double sd, double alt, double pente, Riviere r) {
        return calculerHauteur(x, z, sd, alt, pente, r, true, 0.0, 0.0);
    }

    private double calculerHauteur(int x, int z, double sd, double alt, double pente, Riviere r, boolean fin, double presRiv,
                                   double presLac) {
        double h = hauteurBase(x, z, sd, alt, pente, fin, presRiv, presLac);
        if (r == null) return h;
        // étape C2 : chaque cours d'eau a son niveau (r.eau(), qui descend vers l'aval), en altitude comme en plaine
        int w = r.eau();
        if (r.distance() <= r.demiLargeur()) {
            // lit : profil en creux sous la surface de l'eau
            double u = r.distance() / r.demiLargeur();
            return Math.min(h, (w - 1) - Math.max(1.0, r.profondeur() * (1.0 - u * u)) + 0.5);
        }
        // rive un demi-bloc au-dessus de l'eau, puis pente douce jusqu'au terrain naturel
        double t = lisse(Mth.clamp((r.distance() - r.demiLargeur()) / largeurVallee(r, h), 0.0, 1.0));
        double v = Math.min(h, Mth.lerp(t, w + 0.5, h));
        // la berge tient l'eau : jamais sous le niveau du cours d'eau près du lit
        return r.distance() <= r.demiLargeur() + BERGE_RIVIERE ? Math.max(v, w + 0.6) : v;
    }

    // ---------------------------------------------------------------- fleuves

    /** Infos d'un cours d'eau au voisinage d'une colonne. */
    public record Riviere(double distance, double demiLargeur, double niveau, int profondeur, int classe, int cx, int cz,
                          int eau) {
        /** Le même cours d'eau avec un autre niveau d'eau (près d'un lac). */
        Riviere avecEau(int e) {
            return new Riviere(distance, demiLargeur, niveau, profondeur, classe, cx, cz, e);
        }
    }

    /** Berge (cases au-delà du lit) tenue au-dessus de l'eau ; et largeur où l'aquifère prend le niveau du cours d'eau. */
    static final double BERGE_RIVIERE = 4.0, EAU_RIVIERE = 20.0;

    private volatile Fleuves fleuves;

    private Fleuves fleuves() {
        if (fleuves == null) {
            synchronized (this) {
                if (fleuves == null) {
                    Fleuves f = Fleuves.charger(BLOCS_PAR_DEGRE, this::niveauEau);
                    f.reliefFin(this::niveauFin);
                    fleuves = f;
                }
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
        return new Riviere(p.distance(), hw, niveau, profondeur(p.classe()), p.classe(), Mth.floor(p.cx()), Mth.floor(p.cz()),
                p.niveau());
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

    /**
     * Niveau de l'eau (y de la première couche d'air : l'eau remplit y < niveau) à un sommet de cours d'eau (étape C2) :
     * deux blocs sous le fond de vallée réel lissé, jamais sous la mer. Fleuves.charger le fait ensuite descendre de
     * l'amont vers l'aval sans jamais remonter.
     */
    private int niveauEau(double x, double z) {
        int n = Math.max(NIVEAU_MER, Mth.floor(niveauVallee(Mth.floor(x), Mth.floor(z))) - 2);
        // près d'un lac, ETOPO met une valeur vide (≈ 0 m) : le cours d'eau ne descend pas sous le niveau du lac
        int xi = Mth.floor(x), zi = Mth.floor(z);
        Lacs.Proche lp = lacs != null ? lacs.proche(lon(xi + 0.5), lat(zi + 0.5)) : null;
        if (lp != null) n = Math.max(n, (int) Math.min(niveauLac(lacs.altitude(lp.lac())), lacs.plafond(lp.lac())));
        return n;
    }

    /** Niveau de l'eau d'un sommet de cours d'eau au relief fin (vrai fond de vallée), ou Integer.MIN_VALUE sans relief fin. */
    private int niveauFin(double x, double z) {
        double f = ReliefFin.altitudeFond(Mth.floor(x), Mth.floor(z));
        if (Double.isNaN(f)) return Integer.MIN_VALUE;
        // l'eau un bloc sous le sol du fond de vallée (11/11/2026, test en jeu, delta de l'Indus : un fond à 0 m donnait
        // une eau un bloc au-dessus de la mer, mêlée à elle par taches à deux niveaux)
        return Math.max(NIVEAU_MER, Mth.floor(blocsDepuisAltitude(Math.max(f, 1.0))) - 1);
    }

    /** Hauteur visée du sol sans les fleuves. */
    private double hauteurBase(int x, int z, double sd, double alt, double pente, boolean fin) {
        return hauteurBase(x, z, sd, alt, pente, fin, 0.0, 0.0);
    }

    /**
     * presRiv, presLac : proximité d'un cours d'eau, d'un lac (0 à 1). Près d'un cours d'eau, le vrai fond de vallée
     * (jamais plus haut que le terrain) ; près d'un lac, la vraie altitude des rives (celle du lac).
     */
    private double hauteurBase(int x, int z, double sd, double alt, double pente, boolean fin, double presRiv,
                               double presLac) {
        if (sd >= 0) {
            double p = Mth.clamp(pente / 80.0, 0.0, 1.0);
            double detail = bruitDetail.noise(x / 48.0, 0, z / 48.0) * (1.2 + 6.0 * p)
                    + bruitDetail.noise(x / 13.0, 5, z / 13.0) * 0.6;
            double hTerre = blocsDepuisAltitude(Math.max(alt, 1.0)) + detail;
            // relief fin (08/11/2026) : le vrai relief à 250 m remplace le bruit de détail ; la carte 3' garde le niveau
            // moyen, seule une part du détail fin est gardée (les hauteurs sont exagérées ×6 à ×10)
            double af = fin ? ReliefFin.altitudeTerrain(x, z) : Double.NaN;      // pente limitée (10/11/2026)
            if (!Double.isNaN(af)) {
                double base = blocsDepuisAltitude(Math.max(alt, 1.0));
                hTerre = base + (blocsDepuisAltitude(Math.max(af, 1.0)) - base) * ReliefFin.detail();
                // 11/11/2026 (test en jeu, Sahara : longues marches de sable droites d'un bloc) : sur un terrain presque
                // plat, chaque bloc de hauteur traçait une courbe de niveau lisse ; un léger bruit (moins d'un bloc) la
                // fait onduler
                hTerre += bruitDetail.noise(x / 11.0, 9, z / 11.0) * 0.55 + bruitDetail.noise(x / 4.5, 11, z / 4.5) * 0.3;
                if (presRiv > 0.0 || presLac > 0.0) {
                    double ar = ReliefFin.altitude(x, z);
                    if (!Double.isNaN(ar)) {
                        double hr = blocsDepuisAltitude(Math.max(ar, 1.0));
                        hTerre += (Math.min(hr, hTerre) - hTerre) * presRiv;
                        hTerre += (hr - hTerre) * presLac;
                    }
                }
            }
            return Mth.lerp(lisse(Mth.clamp(sd / 2.0, 0.0, 1.0)), NIVEAU_MER + 0.6, Math.max(hTerre, NIVEAU_MER + 0.6));
        }
        double hMer = alt < -9300 ? fosse(x, z, alt) : blocsDepuisAltitude(Math.min(alt, -1.0));
        return Mth.lerp(lisse(Mth.clamp(-sd / 2.0, 0.0, 1.0)), NIVEAU_MER - 1.0, Math.min(hMer, NIVEAU_MER - 1.0));
    }

    /**
     * Faille des grandes fosses (08/11/2026 : tranchée droite aux parois lisses et au fond plat). Les parois serpentent
     * (la profondeur réelle décalée par un bruit fixe, ±350 m), forment des corniches tous les 6 blocs, et le fond se
     * creuse en cuvettes séparées par des buttes. Bruit à graine fixe : la même fosse dans tous les mondes.
     */
    private double fosse(int x, int z, double alt) {
        double w = Mth.clamp((-alt - 9300) / 600.0, 0.0, 1.0);
        double a = alt + w * (bruitDetail.noise(x / 56.0, 40, z / 56.0) * 260 + bruitDetail.noise(x / 17.0, 41, z / 17.0) * 90);
        double h = blocsDepuisAltitude(Math.min(a, -1.0));
        // 10/11/2026 : mêmes formes, à la nouvelle profondeur (faille de y -420 à -500)
        if (h < -428 && h > -495) {                              // corniches : paliers de 8 blocs, contremarches raides
            double q = 8.0, b = Math.floor(h / q) * q, f = (h - b) / q;
            h = Mth.lerp(0.55, h, b + q * f * f * f);
        }
        if (h < -490) {                                          // fond : cuvettes et buttes (jusqu'à 9 blocs)
            double m = bruitDetail.noise(x / 38.0, 42, z / 38.0) + 0.35 * bruitDetail.noise(x / 11.0, 43, z / 11.0);
            h += Math.max(0.0, m) * 9.0 * Mth.clamp((-490.0 - h) / 7.0, 0.0, 1.0);
        }
        return Math.max(h, PLANCHER_FOSSES);
    }

    // ---------------------------------------------------------------- sorties pour le routeur de bruit vanilla

    /** depth vanilla = gradient(y) + offset ; gradient(y) = 1,5 - (y + 64) / 128, donc offset = (H - 128) / 128. */
    public double offset(int x, int z) {
        return (hauteur(x, z) - 128.0) / 128.0;
    }

    /** Grand facteur = terrain collé à la hauteur visée (plat) ; petit facteur = relief plus libre. */
    public double facteur(int x, int z) {
        Colonne c = colonne(x, z);
        double f;
        if (c.sd() < 0) {
            // mer fidèle (0.3.2) : le fond suit la profondeur réelle ; plus il est haut, moins il a de liberté
            f = Mth.lerp(Mth.clamp((c.h() - 40.0) / 18.0, 0.0, 1.0), 8.0, 18.0);
        } else {
            // relief 100 % Terre (0.3.2) : le terrain colle à la hauteur visée (relief réel + bruitDetail à graine fixe),
            // sans la liberté du relief vanilla ; connu au bloc près (terre_py) et identique dans tous les mondes
            f = 30.0;
        }
        // près des cours d'eau, le terrain colle au profil de la vallée (pas de bosses dans le lit ni de creux sur la rive)
        Riviere r = c.r();
        if (r != null) {
            double t = Mth.clamp(1.0 - (r.distance() - r.demiLargeur()) / VALLEE_MAX, 0.0, 1.0);
            f = Mth.lerp(t, f, 30.0);
        }
        // lieu sculpté : le terrain suit exactement sa forme, avec un passage progressif vers le relief libre
        return c.lieu() ? Mth.lerp(c.poids(), f, 30.0) : f;
    }

    /** Pics déchiquetés seulement dans les vraies montagnes raides. */
    public double dentelure(int x, int z) {
        Colonne c = colonne(x, z);
        if (true) return 0.0;                 // relief 100 % Terre : pas de pics vanilla (à réimplanter à notre façon)
        double alt = c.alt();
        return Mth.clamp((c.pente() - 40.0) / 120.0, 0.0, 1.0) * Mth.clamp((alt - 1200.0) / 1500.0, 0.0, 1.0) * 0.2
                * (1.0 - c.poids());
    }

    /** En mer d'après la carte (pour l'eau des fosses sous y -54, où le jeu mettrait de la lave). */
    public boolean enMer(int x, int z) {
        return colonne(x, z).sd() < 0;
    }

    /** Profondeur sous le sol où les grottes peuvent commencer (sous l'eau : plus bas, pour ne jamais percer un fond). */
    static final double GROTTES_SOUS_SOL = 18.0, GROTTES_SOUS_EAU = 32.0;
    /** Bas des grottes (10/11/2026) : l'ancien fond du monde, + 8 blocs pour le fond arrondi (vide jusqu'à y -60). */
    static final double FOND_GROTTES = -52.0;
    /**
     * Autour des lieux (07/11/2026) : sur cette distance, la limite des grottes descend progressivement, jusqu'à
     * GROTTES_LIEU blocs de plus sous le sol au bord et sous le lieu (aucune grotte à portée de vue). Avant, la limite tombait d'un
     * coup au bord de l'emprise et laissait un grand mur plat dans les grottes voisines (Vésuve).
     */
    static final int GROTTES_APPROCHE = 64;
    static final double GROTTES_LIEU = 140.0;
    private static final int[] RAYONS = {6, 12, 20, 32, 48, 64};
    private final ThreadLocal<long[]> cacheLieux = ThreadLocal.withInitial(() -> new long[512]);

    /**
     * Masque des grottes (04/11/2026, décision de Maxime : « grottes fermées ») : max avec la densité des grottes
     * vanilla. Négatif (-1, sans effet) là où elles peuvent creuser ; positif (bouche la grotte) à moins de 18 blocs
     * sous le sol (32 sous la mer, les lacs et les cours d'eau), bien plus bas sous les lieux et en approchant d'un lieu.
     * La pente de 8 blocs arrondit les voûtes : pas de plafond plat à la limite.
     */
    public double grottes(int x, int y, int z) {
        // 10/11/2026 : monde agrandi vers le bas ; vers l'ancien fond du monde (y -64), les grottes se referment
        // (pente de 8 blocs, fond arrondi) et tout reste plein en dessous
        double bas = Mth.clamp((FOND_GROTTES - y) / 8.0, -1.0, 1.0);
        if (bas >= 1.0) return 1.0;
        Colonne c = colonne(x, z);
        boolean eau = c.sd() < 0 || c.eauLac() != SANS_LAC || c.eauRiv() != SANS_LAC;
        double marge = eau ? GROTTES_SOUS_EAU : GROTTES_SOUS_SOL;
        if (!LieuxTerre.liste().isEmpty()) {
            // sous un lieu, les grottes restent très profondes (GROTTES_LIEU blocs sous son sol) : invisibles depuis le
            // lieu, et la limite continue de part et d'autre de son bord (plus de mur)
            double p = c.lieu() ? 1.0 : procheLieu(x, z);
            marge += p * GROTTES_LIEU;
        }
        double limite = c.h() - marge;
        return Math.max(bas, Mth.clamp((y - limite) / 8.0, -1.0, 1.0));
    }

    /** Bruit à graine fixe du terrain (même dans tous les mondes), environ -1 à 1, pour les habillages. */
    public double bruit(double x, double y, double z) {
        return bruitDetail.noise(x, y, z);
    }

    /** Pas de plancher dans cette colonne (bornes vides). */
    public static final double SANS_PLANCHER = -1.0e6;

    /**
     * Masques d'une colonne en un seul calcul (10/11/2026, génération plus rapide : MasquesFunction) :
     * {limite des grottes, haut du plancher, bas du plancher, plafond de la colonne (1 ou -20)}. Mêmes règles que
     * grottes(), plancher() et plafond(), qui restent pour les outils.
     */
    public void masques(int x, int z, double[] dans) {
        Colonne c = colonne(x, z);
        boolean eau = c.sd() < 0 || c.eauLac() != SANS_LAC || c.eauRiv() != SANS_LAC;
        double marge = eau ? GROTTES_SOUS_EAU : GROTTES_SOUS_SOL;
        if (!LieuxTerre.liste().isEmpty()) marge += (c.lieu() ? 1.0 : procheLieu(x, z)) * GROTTES_LIEU;
        dans[0] = c.h() - marge;
        if (c.bergeLac() != SANS_LAC) {
            dans[1] = c.bergeLac(); dans[2] = c.bergeLac() - 6;
        } else if (c.bergeRiv() != SANS_LAC && c.eauLac() == SANS_LAC) {
            dans[1] = c.bergeRiv(); dans[2] = c.bergeRiv() - 6;
        } else if (c.sd() < 0 || c.r() != null || c.h() < NIVEAU_MER) {
            dans[1] = SANS_PLANCHER; dans[2] = -SANS_PLANCHER;
        } else {
            dans[1] = NIVEAU_MER - 1; dans[2] = NIVEAU_MER - 5;
        }
        dans[3] = c.sd() >= 0 || c.h() >= PLAFOND_MER + 1.0 ? 1.0 : -20.0;
    }

    /** Distance (blocs) sur laquelle l'écart relief fin / terrain d'avant s'efface à l'intérieur d'un lieu. */
    static final double RACCORD_FIN = 56.0;
    private static final int[] RAYONS_IN = {6, 12, 20, 28, 36, 44, 52, 60};

    /** Distance approchée au bord de la zone du lieu, depuis l'intérieur (au-delà de 60 : 64). */
    private double interieurLieu(int x, int z) {
        for (int r : RAYONS_IN) {
            for (int k = 0; k < 16; k++) {
                double a = k * Math.PI / 8.0;
                if (LieuxTerre.a(x + (int) Math.round(r * Math.cos(a)), z + (int) Math.round(r * Math.sin(a))) == null)
                    return r - 3.0;
            }
        }
        return 64.0;
    }

    /** 1 dans un lieu, puis de 1 à 0 en s'en éloignant (0 à GROTTES_APPROCHE blocs et au-delà). Mis en cache par colonne. */
    private double procheLieu(int x, int z) {
        long[] tab = cacheLieux.get();
        int i = ((x * 31 + z * 17) & 255) * 2;
        long cle = ((((long) x << 32) ^ (z & 0xFFFFFFFFL)) * 31L) + generation;   // une autre échelle invalide le cache
        if (tab[i] == cle && tab[i + 1] != 0) return Double.longBitsToDouble(tab[i + 1] - 1);
        double p;
        if (LieuxTerre.a(x, z) != null) {
            p = 1.0;
        } else {
            p = 0.0;
            boucle:
            for (int r : RAYONS) {
                for (int k = 0; k < 16; k++) {
                    double a = k * Math.PI / 8.0;
                    if (LieuxTerre.a(x + (int) Math.round(r * Math.cos(a)), z + (int) Math.round(r * Math.sin(a))) != null) {
                        double v = 1.0 - (r - RAYONS[0] / 2.0) / GROTTES_APPROCHE;
                        p = Mth.clamp(v, 0.0, 1.0);
                        break boucle;
                    }
                }
            }
        }
        tab[i] = cle;
        tab[i + 1] = Double.doubleToRawLongBits(p) + 1;
        return p;
    }

    /** Haut du fond marin : jamais au-dessus de y 61 (l'eau à 62), pour qu'aucune île inventée ne sorte de l'eau. */
    public static final int PLAFOND_MER = NIVEAU_MER - 2;

    /**
     * Plafond de densité (min avec la densité finale) : en mer, sauf là où un lieu veut de la terre, tout bloc au-dessus de y 61 est vide.
     * Seules les vraies îles (terres de la carte) dépassent de l'eau. Ailleurs, sans effet (1 garde le signe).
     */
    public double plafond(int x, int y, int z) {
        Colonne c = colonne(x, z);
        // un lieu qui veut de la terre en mer (aiguille, arche, Mont-Saint-Michel) la garde ; partout ailleurs, plafond
        if (c.sd() >= 0 || c.h() >= PLAFOND_MER + 1.0) return 1.0;
        // franchement négatif : les « barrières » des aquifères vanilla ajoutent de la densité près des niveaux d'eau
        // et refaisaient des îlots d'un bloc à y 62 avec un plafond trop doux (-0,5)
        return y <= PLAFOND_MER ? 1.0 : -20.0;
    }

    /**
     * Plancher de densité (max avec la densité finale) : sur la terre ferme au bord de la mer, le sol ne descend pas
     * sous la mer (pas de mares ni de lagunes inventées). Seulement de y 58 à 62, hors fleuves et creux voulus par un lieu.
     */
    public double plancher(int x, int y, int z) {
        Colonne c = colonne(x, z);
        // berge d'un lac : le terrain, interpolé par le jeu sur des cellules de 4 blocs, ne doit pas descendre sous
        // l'eau du lac voisin (sinon l'eau s'échappe de la cuvette)
        if (c.bergeLac() != SANS_LAC) return y <= c.bergeLac() && y >= c.bergeLac() - 6 ? 0.5 : -1.0;
        // berge d'un cours d'eau (étape C2) : pareil, l'eau reste dans le lit
        if (c.bergeRiv() != SANS_LAC && c.eauLac() == SANS_LAC) return y <= c.bergeRiv() && y >= c.bergeRiv() - 6 ? 0.5 : -1.0;
        if (y < NIVEAU_MER - 5 || y > NIVEAU_MER - 1) return -1.0;
        if (c.sd() < 0 || c.r() != null || c.h() < NIVEAU_MER) return -1.0;
        return 0.5;
    }

    /**
     * Ajout au bruit d'« inondation » des aquifères vanilla : dans le lit et les vallées des fleuves en eau
     * (et au fond des lieux creusés sous la mer), l'aquifère prend toujours le niveau de la mer.
     * Sans ça, le moteur laisse au hasard les lits étroits à sec.
     */
    public double inondation(int x, int z) {
        Colonne c = colonne(x, z);
        if (c.eauLac() != SANS_LAC) return 2.0;  // lac et sa berge : l'aquifère prend le niveau du lac (FluidesMixin)
        if (c.lieu()) {
            Lieu l = LieuxTerre.a(x, z);
            if (l != null && l.inonde(x, z, c.h())) return 2.0;
        }
        return c.eauRiv() != SANS_LAC ? 2.0 : 0.0;   // lit et abords d'un cours d'eau : niveau du cours d'eau
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

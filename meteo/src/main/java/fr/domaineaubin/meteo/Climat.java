package fr.domaineaubin.meteo;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import fr.domaineaubin.terre.monde.Terrain;
import net.minecraft.world.level.Level;
import net.minecraftforge.fml.loading.FMLPaths;
import sereneseasons.api.season.Season;

import java.io.Reader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

/**
 * Le climat réel au service de la météo (Domaine Weather 0.1, 13/11/2026) : classe Köppen-Geiger de la carte du mod
 * Terre (Beck et al. 2023 : 1 Af, 2 Am, 3 Aw, 4 BWh, 5 BWk, 6 BSh, 7 BSk, 8-10 Cs, 11-13 Cw, 14-16 Cf, 17-20 Ds,
 * 21-24 Dw, 25-28 Df, 29 ET, 30 EF ; 0 = mer).
 *
 * - Pluie : part des nuages de Weather2 qui pleuvent selon le climat et la saison locale (déserts presque secs, été
 *   sec méditerranéen, hiver sec des moussons).
 * - Catastrophes : seulement là où elles existent (tornades dans leurs vraies zones, tempêtes de sable dans les
 *   déserts chauds et froids, tempêtes de neige dans les climats froids). Zones réglables dans
 *   config/domaine_weather_zones.json.
 */
public final class Climat {
    private Climat() {
    }

    /** Classe Köppen au bloc (x, z) ; 0 = mer ou inconnue. */
    public static int koppen(double x, double z) {
        return Terrain.get().carte().climat(Terrain.lon(x), Terrain.lat(z));
    }

    public static String nomKoppen(int k) {
        String[] n = {"mer", "Af", "Am", "Aw", "BWh", "BWk", "BSh", "BSk", "Csa", "Csb", "Csc", "Cwa", "Cwb", "Cwc",
                "Cfa", "Cfb", "Cfc", "Dsa", "Dsb", "Dsc", "Dsd", "Dwa", "Dwb", "Dwc", "Dwd", "Dfa", "Dfb", "Dfc", "Dfd",
                "ET", "EF"};
        return k >= 0 && k < n.length ? n[k] : "?";
    }

    // ---------------------------------------------------------------- pluie

    /** Chance (%) qu'un nuage pleuve dans ce climat, à cette saison locale. */
    public static int pluie(int k, Season saison) {
        boolean ete = saison == Season.SUMMER, hiver = saison == Season.WINTER;
        if (k == 0) return 100;                       // mer
        if (k == 1) return 100;                       // équatorial : toujours humide
        if (k == 2) return hiver ? 30 : 100;          // mousson : courte saison sèche
        if (k == 3) return hiver ? 10 : 100;          // savane : hiver sec
        if (k == 4 || k == 5) return 5;               // déserts
        if (k == 6 || k == 7) return 35;              // steppes semi-arides
        if (k >= 8 && k <= 10) return ete ? 10 : 100; // méditerranéen : été sec
        if (k >= 11 && k <= 13) return hiver ? 15 : 100; // hiver sec (Chine du Sud, Inde du Nord, hauts plateaux)
        if (k >= 14 && k <= 16) return 100;           // tempéré humide (Bretagne, Japon…)
        if (k >= 17 && k <= 20) return ete ? 15 : 100; // continental à été sec
        if (k >= 21 && k <= 24) return hiver ? 15 : 100; // continental à hiver sec (Mandchourie, Sibérie orientale)
        if (k >= 25 && k <= 28) return 100;           // continental humide
        if (k == 29) return 70;                       // toundra
        return 20;                                    // calotte glaciaire : désert froid
    }

    /** Vrai si le nuage {@code id} pleut au bloc (x, z) : tirage fixe par nuage et par sous-saison (pas de clignotement). */
    public static boolean nuagePleut(Level level, long id, double x, double z) {
        if (!Saisons.terre(level)) return true;
        var saison = Saisons.locale(level, z);
        int p = pluie(koppen(x, z), saison.getSeason());
        if (p >= 100) return true;
        long h = (id * 0x9E3779B97F4A7C15L) ^ (saison.getSubSeason().ordinal() * 0xC2B2AE3D27D4EB4FL);
        h ^= h >>> 31;
        return Math.floorMod(h, 100) < p;
    }

    // ---------------------------------------------------------------- catastrophes

    /** Zone de latitude / longitude (degrés). */
    public static final class Zone {
        public String nom;
        public double[] lat;
        public double[] lon;

        Zone(String nom, double lat0, double lat1, double lon0, double lon1) {
            this.nom = nom;
            this.lat = new double[]{lat0, lat1};
            this.lon = new double[]{lon0, lon1};
        }

        boolean contient(double la, double lo) {
            return la >= Math.min(lat[0], lat[1]) && la <= Math.max(lat[0], lat[1])
                    && lo >= Math.min(lon[0], lon[1]) && lo <= Math.max(lon[0], lon[1]);
        }
    }

    /** Réglages des catastrophes (config/domaine_weather_zones.json). */
    public static final class Zones {
        public String _note = "Domaine Weather : zones ou les catastrophes peuvent naitre (lat/lon en degres). "
                + "Tempetes de sable et de neige : classes Koppen autorisees (4 BWh, 5 BWk ; 17-30 = D et E).";
        public List<Zone> tornades = new ArrayList<>(List.of(
                new Zone("Grandes Plaines et Sud-Est des Etats-Unis", 26, 50, -105, -76),
                new Zone("Prairies canadiennes", 49, 56, -115, -95),
                new Zone("Pampa (Argentine, Uruguay, sud du Bresil)", -38, -24, -65, -48),
                new Zone("Bangladesh et est de l'Inde", 20, 27, 84, 93),
                new Zone("Sud-Est de l'Australie", -38, -26, 138, 153),
                new Zone("Highveld (Afrique du Sud)", -30, -24, 25, 31)));
        public int[] sable = {4, 5};
        public int[] neige = {10, 13, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30};
    }

    private static volatile Zones zones;

    public static Zones zones() {
        Zones z = zones;
        if (z != null) return z;
        synchronized (Climat.class) {
            if (zones != null) return zones;
            Path f = FMLPaths.CONFIGDIR.get().resolve("domaine_weather_zones.json");
            Gson g = new GsonBuilder().setPrettyPrinting().create();
            Zones lu = null;
            try {
                if (Files.exists(f)) {
                    try (Reader r = Files.newBufferedReader(f, StandardCharsets.UTF_8)) {
                        lu = g.fromJson(r, Zones.class);
                    }
                } else {
                    Files.createDirectories(f.getParent());
                    Files.writeString(f, g.toJson(new Zones()), StandardCharsets.UTF_8);
                }
            } catch (Exception e) {
                DomaineWeather.LOGGER.error("Domaine Weather : {} illisible, réglages par défaut", f, e);
            }
            zones = lu != null ? lu : new Zones();
            return zones;
        }
    }

    /** Zone de tornades au bloc (x, z), ou null. */
    public static Zone zoneTornade(double x, double z) {
        double la = Terrain.lat(z), lo = Terrain.lon(x);
        for (Zone zn : zones().tornades) if (zn.contient(la, lo)) return zn;
        return null;
    }

    private static boolean dans(int[] l, int k) {
        for (int v : l) if (v == k) return true;
        return false;
    }

    public static boolean sablePossible(double x, double z) {
        return dans(zones().sable, koppen(x, z));
    }

    public static boolean neigePossible(double x, double z) {
        return dans(zones().neige, koppen(x, z));
    }
}

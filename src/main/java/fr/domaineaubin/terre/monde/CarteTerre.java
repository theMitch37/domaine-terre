package fr.domaineaubin.terre.monde;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonParser;
import fr.domaineaubin.terre.DomaineTerre;
import net.minecraft.util.Mth;

import javax.imageio.ImageIO;
import java.awt.image.BufferedImage;
import java.awt.image.Raster;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;

/**
 * Les cartes de la Terre embarquées dans le mod (grille de 3 minutes d'arc, 7200 x 3600).
 * Longitude -180 -> 180 de gauche à droite, latitude 90 -> -90 de haut en bas.
 */
public final class CarteTerre {
    public static final int W = 7200;
    public static final int H = 3600;

    private final short[] relief;      // altitude en mètres
    private final byte[] cote;         // 128 + 4 x distance signée à la côte (minutes d'arc, + vers l'intérieur)
    private final byte[] terroir;      // 0 = mer, 1..29 ; bit 128 = lac intérieur de ce terroir
    private final byte[] climat;       // 0 = mer, 1..30 = classe Köppen-Geiger (Beck et al. 2023)
    private final byte[] biomes;       // 0 = pas de biome fixe, sinon index dans biomes.json (null si carte absente)
    private final String[] nomsTerroirs;
    private final String[] continents = new String[256];

    private CarteTerre(short[] relief, byte[] cote, byte[] terroir, byte[] climat, byte[] biomes, String[] noms) {
        this.relief = relief;
        this.cote = cote;
        this.terroir = terroir;
        this.climat = climat;
        this.biomes = biomes;
        this.nomsTerroirs = noms;
    }

    public static CarteTerre charger() {
        long t0 = System.currentTimeMillis();
        try {
            int[] ligne = new int[W];
            short[] rel = new short[W * H];
            Raster r = lire("relief.png").getRaster();
            for (int y = 0; y < H; y++) {
                r.getSamples(0, y, W, 1, 0, ligne);
                for (int x = 0; x < W; x++) rel[y * W + x] = (short) (ligne[x] - 11000);
            }
            byte[] cot = lireOctets("cotes.png", ligne);
            byte[] ter = lireOctets("terroirs.png", ligne);
            byte[] cli = lireOctets("climat.png", ligne);
            byte[] bio = CarteTerre.class.getResource("/domaine_terre/carte/biomes.png") != null
                    ? lireOctets("biomes.png", ligne) : null;
            String[] noms = new String[256];
            try (InputStream in = ouvrir("terroirs.json")) {
                JsonArray tab = JsonParser.parseReader(new InputStreamReader(in, StandardCharsets.UTF_8)).getAsJsonArray();
                for (JsonElement e : tab) {
                    noms[e.getAsJsonObject().get("index").getAsInt()] = e.getAsJsonObject().get("nom").getAsString()
                            + "|" + e.getAsJsonObject().get("continent").getAsString();
                }
            }
            noms[0] = "Mer|mer";
            DomaineTerre.LOGGER.info("Cartes de la Terre chargées en {} ms", System.currentTimeMillis() - t0);
            return new CarteTerre(rel, cot, ter, cli, bio, noms);
        } catch (IOException e) {
            throw new UncheckedIOException("Impossible de charger les cartes de la Terre", e);
        }
    }

    private static InputStream ouvrir(String nom) throws IOException {
        InputStream in = CarteTerre.class.getResourceAsStream("/domaine_terre/carte/" + nom);
        if (in == null) throw new IOException("Carte introuvable : " + nom);
        return in;
    }

    private static BufferedImage lire(String nom) throws IOException {
        try (InputStream in = ouvrir(nom)) {
            BufferedImage img = ImageIO.read(in);
            if (img == null || img.getWidth() != W || img.getHeight() != H) {
                throw new IOException("Carte invalide : " + nom);
            }
            return img;
        }
    }

    private static byte[] lireOctets(String nom, int[] ligne) throws IOException {
        byte[] out = new byte[W * H];
        Raster r = lire(nom).getRaster();
        for (int y = 0; y < H; y++) {
            r.getSamples(0, y, W, 1, 0, ligne);
            for (int x = 0; x < W; x++) out[y * W + x] = (byte) ligne[x];
        }
        return out;
    }

    // ---------------------------------------------------------------- échantillonnage

    private static double gx(double lon) { return (lon + 180.0) / 360.0 * W - 0.5; }
    private static double gy(double lat) { return (90.0 - lat) / 180.0 * H - 0.5; }

    private int idx(int x, int y) {
        return Mth.clamp(y, 0, H - 1) * W + Math.floorMod(x, W);
    }

    private static double cubique(double p0, double p1, double p2, double p3, double t) {
        return p1 + 0.5 * t * (p2 - p0 + t * (2 * p0 - 5 * p1 + 4 * p2 - p3 + t * (3 * (p1 - p2) + p3 - p0)));
    }

    /** Altitude réelle en mètres (interpolation bicubique). */
    public double relief(double lon, double lat) {
        double fx = gx(lon), fy = gy(lat);
        int ix = Mth.floor(fx), iy = Mth.floor(fy);
        double tx = fx - ix, ty = fy - iy;
        double[] l = new double[4];
        for (int j = 0; j < 4; j++) {
            int y = iy - 1 + j;
            l[j] = cubique(relief[idx(ix - 1, y)], relief[idx(ix, y)], relief[idx(ix + 1, y)], relief[idx(ix + 2, y)], tx);
        }
        return cubique(l[0], l[1], l[2], l[3], ty);
    }

    /** Distance signée à la côte en minutes d'arc, positive à l'intérieur des terres (bilinéaire). */
    public double cote(double lon, double lat) {
        double fx = gx(lon), fy = gy(lat);
        int ix = Mth.floor(fx), iy = Mth.floor(fy);
        double tx = fx - ix, ty = fy - iy;
        double a = c(ix, iy), b = c(ix + 1, iy), cc = c(ix, iy + 1), d = c(ix + 1, iy + 1);
        return Mth.lerp(ty, Mth.lerp(tx, a, b), Mth.lerp(tx, cc, d));
    }

    private double c(int x, int y) {
        return ((cote[idx(x, y)] & 0xFF) - 128) / 4.0;
    }

    public int terroir(double lon, double lat) {
        return terroir[idx(Mth.floor(gx(lon) + 0.5), Mth.floor(gy(lat) + 0.5))] & 0x7F;
    }

    /** Lac intérieur (eau qui ne touche pas l'océan) : il porte le terroir de ses rives. */
    public boolean lac(double lon, double lat) {
        return (terroir[idx(Mth.floor(gx(lon) + 0.5), Mth.floor(gy(lat) + 0.5))] & 0x80) != 0;
    }

    /** Classe de climat Köppen-Geiger (0 = mer ou inconnue). */
    public int climat(double lon, double lat) {
        return climat[idx(Mth.floor(gx(lon) + 0.5), Mth.floor(gy(lat) + 0.5))] & 0xFF;
    }

    /** Biome fixe de la carte des biomes (index dans biomes.json, 0 = aucun). */
    public int biome(double lon, double lat) {
        if (biomes == null) return 0;
        return biomes[idx(Mth.floor(gx(lon) + 0.5), Mth.floor(gy(lat) + 0.5))] & 0xFF;
    }

    public String nomTerroir(int index) {
        String n = nomsTerroirs[index];
        return n == null ? "?" : n.split("\\|")[0];
    }

    public String continent(int index) {
        String n = nomsTerroirs[index];
        return n == null || !n.contains("|") ? "" : n.split("\\|")[1];
    }
}

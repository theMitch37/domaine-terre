package fr.domaineaubin.lieux;

import fr.domaineaubin.terre.monde.Terrain;
import net.minecraft.util.Mth;

import java.io.IOException;
import java.io.InputStream;
import java.io.UncheckedIOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.zip.GZIPInputStream;

/**
 * Relief réel préparé pour un lieu (outils/*_dem.py) : grilles int16 sur une zone lon/lat, chargées à la demande.
 * Format (gzip, petit-boutiste) : lon0, lat0, pasLon, pasLat (double), largeur, hauteur (int), puis N grilles
 * de largeur x hauteur valeurs int16, ligne par ligne du nord au sud. Le sens de chaque grille dépend du lieu
 * (altitude réelle, niveau du plateau, niveau du fleuve, distance au talweg…).
 * Thread-safe : chargé une fois, ensuite en lecture seule.
 */
public final class ReliefLieu {
    private final String ressource;
    private double lon0, lat0, pasLon, pasLat;
    private int largeur, hauteur;
    private short[][] grilles;
    private volatile boolean charge;

    /** @param fichier nom du fichier dans /domaine_terre_lieux/ (ex. « verdon.bin ») */
    public ReliefLieu(String fichier) {
        this.ressource = "/domaine_terre_lieux/" + fichier;
    }

    private void charger() {
        if (charge) return;
        synchronized (this) {
            if (charge) return;
            try (InputStream in = ReliefLieu.class.getResourceAsStream(ressource)) {
                if (in == null) throw new IOException(ressource + " introuvable");
                ByteBuffer b = ByteBuffer.wrap(new GZIPInputStream(in).readAllBytes()).order(ByteOrder.LITTLE_ENDIAN);
                lon0 = b.getDouble();
                lat0 = b.getDouble();
                pasLon = b.getDouble();
                pasLat = b.getDouble();
                largeur = b.getInt();
                hauteur = b.getInt();
                int n = largeur * hauteur;
                int nb = b.remaining() / (2 * n);
                grilles = new short[nb][];
                for (int i = 0; i < nb; i++) {
                    short[] g = new short[n];
                    b.asShortBuffer().get(g);
                    b.position(b.position() + 2 * n);
                    grilles[i] = g;
                }
            } catch (IOException e) {
                throw new UncheckedIOException("Impossible de charger " + ressource, e);
            }
            charge = true;
        }
    }

    public double lonMin() { charger(); return lon0; }
    public double lonMax() { charger(); return lon0 + largeur * pasLon; }
    public double latMax() { charger(); return lat0; }
    public double latMin() { charger(); return lat0 - hauteur * pasLat; }

    /** La position (lon, lat) est-elle dans la zone des données ? */
    public boolean contient(double lon, double lat) {
        charger();
        return lon > lon0 && lon < lon0 + largeur * pasLon && lat < lat0 && lat > lat0 - hauteur * pasLat;
    }

    /** La colonne (x, z) en blocs est-elle dans la zone ? */
    public boolean contient(int x, int z) {
        return contient(Terrain.lon(x), Terrain.lat(z));
    }

    /** Distance (degrés) au bord le plus proche de la zone : sert au fondu vers le terrain du mod Terre. */
    public double distanceBord(double lon, double lat) {
        charger();
        return Math.min(Math.min(lon - lon0, lon0 + largeur * pasLon - lon), Math.min(lat0 - lat, lat - (lat0 - hauteur * pasLat)));
    }

    /** Interpolation bilinéaire de la grille i au point (lon, lat). */
    public double echant(int i, double lon, double lat) {
        charger();
        short[] g = grilles[i];
        double fx = (lon - lon0) / pasLon - 0.5, fy = (lat0 - lat) / pasLat - 0.5;
        int ix = Mth.floor(fx), iy = Mth.floor(fy);
        double tx = fx - ix, ty = fy - iy;
        return Mth.lerp(ty, Mth.lerp(tx, v(g, ix, iy), v(g, ix + 1, iy)), Mth.lerp(tx, v(g, ix, iy + 1), v(g, ix + 1, iy + 1)));
    }

    private double v(short[] g, int x, int y) {
        return g[Mth.clamp(y, 0, hauteur - 1) * largeur + Mth.clamp(x, 0, largeur - 1)];
    }

    /** Courbe en S entre 0 et 1. */
    public static double lisse(double t) {
        t = Mth.clamp(t, 0.0, 1.0);
        return t * t * (3 - 2 * t);
    }
}

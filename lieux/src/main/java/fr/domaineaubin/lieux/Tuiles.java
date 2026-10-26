package fr.domaineaubin.lieux;

import fr.domaineaubin.terre.monde.Terrain;
import it.unimi.dsi.fastutil.longs.Long2ObjectOpenHashMap;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.UncheckedIOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.StandardCharsets;
import java.util.zip.GZIPInputStream;

/**
 * Tuiles sculptées (26/10) : la carte est un damier de tuiles de 512 x 512 blocs (une région Minecraft), en 1:250.
 * Une tuile sans fichier garde le terrain calculé par le mod Terre. Une tuile sculptée donne, colonne par colonne,
 * soit « terrain calculé », soit la hauteur exacte voulue par un lieu ; ses colonnes sculptées rejoignent le terrain
 * calculé à leur bord (calculé hors du jeu au bloc près, outils/tuiles.py) : ni poids ni fondu.
 * Version 2 (lot 2) : niveau d'eau du lieu par colonne (torrents, lacs, bassins en altitude, cascades).
 * Format : voir outils/tuiles.py. Chargées à la demande, ensuite en lecture seule (thread-safe).
 */
public final class Tuiles {
    public static final int TAILLE = 512, VIDE = -32768;
    private static final int MAGIE = 0x454C5554;
    private static final String DOSSIER = "/domaine_terre_lieux/tuiles/";

    /** Une tuile chargée. */
    public static final class Tuile {
        final String[] lieux;
        final short[] haut, sommet;
        final byte[] type, lieu;
        /** Niveau de l'eau du lieu (version 2), ou null (version 1 : aucune eau propre au lieu). */
        final short[] eau;

        private Tuile(String[] lieux, short[] haut, short[] sommet, byte[] type, byte[] lieu, short[] eau) {
            this.lieux = lieux; this.haut = haut; this.sommet = sommet; this.type = type; this.lieu = lieu; this.eau = eau;
        }
    }

    /** Tuiles déjà chargées : copie remplacée à chaque chargement (rare), lue sans verrou. */
    private static volatile Long2ObjectOpenHashMap<Tuile> chargees = new Long2ObjectOpenHashMap<>();
    /** Tuiles présentes (index.txt), triées. */
    private static volatile long[] presentes;

    private Tuiles() {
    }

    private static long cle(int tx, int tz) {
        return ((long) tx << 32) ^ (tz & 0xFFFFFFFFL);
    }

    private static long[] presentes() {
        long[] p = presentes;
        if (p != null) return p;
        synchronized (Tuiles.class) {
            if (presentes != null) return presentes;
            java.util.List<Long> l = new java.util.ArrayList<>();
            try (InputStream in = Tuiles.class.getResourceAsStream(DOSSIER + "index.txt")) {
                if (in != null) {
                    BufferedReader r = new BufferedReader(new InputStreamReader(in, StandardCharsets.UTF_8));
                    for (String ligne; (ligne = r.readLine()) != null; ) {
                        String[] m = ligne.trim().split("\\s+");
                        if (m.length == 2) l.add(cle(Integer.parseInt(m[0]), Integer.parseInt(m[1])));
                    }
                }
            } catch (IOException e) {
                throw new UncheckedIOException("Impossible de lire l'index des tuiles", e);
            }
            p = l.stream().mapToLong(Long::longValue).sorted().toArray();
            presentes = p;
            return p;
        }
    }

    /** Tuile sculptée qui contient la colonne, ou null (terrain calculé). Les tuiles ne valent qu'en 1:250. */
    public static Tuile a(int x, int z) {
        if (Terrain.echelle() != GrandCanyon.ECHELLE_REFERENCE) return null;
        int tx = Math.floorDiv(x, TAILLE), tz = Math.floorDiv(z, TAILLE);
        long c = cle(tx, tz);
        if (java.util.Arrays.binarySearch(presentes(), c) < 0) return null;
        Tuile t = chargees.get(c);
        if (t != null) return t;
        synchronized (Tuiles.class) {
            t = chargees.get(c);
            if (t != null) return t;
            t = charger(tx, tz);
            Long2ObjectOpenHashMap<Tuile> copie = new Long2ObjectOpenHashMap<>(chargees);
            copie.put(c, t);
            chargees = copie;
            return t;
        }
    }

    private static Tuile charger(int tx, int tz) {
        String res = DOSSIER + tx + "_" + tz + ".bin";
        try (InputStream in = Tuiles.class.getResourceAsStream(res)) {
            if (in == null) throw new IOException(res + " introuvable");
            ByteBuffer b = ByteBuffer.wrap(new GZIPInputStream(in).readAllBytes()).order(ByteOrder.LITTLE_ENDIAN);
            if (b.getInt() != MAGIE) throw new IOException(res + " : en-tête invalide");
            int version = b.getInt();
            if ((version != 1 && version != 2) || b.getInt() != tx || b.getInt() != tz)
                throw new IOException(res + " : en-tête invalide");
            String[] lieux = new String[b.getInt()];
            for (int i = 0; i < lieux.length; i++) {
                byte[] nom = new byte[b.getShort()];
                b.get(nom);
                lieux[i] = new String(nom, StandardCharsets.UTF_8);
            }
            int n = TAILLE * TAILLE;
            short[] haut = new short[n], sommet = new short[n];
            byte[] type = new byte[n], lieu = new byte[n];
            b.asShortBuffer().get(haut); b.position(b.position() + 2 * n);
            b.asShortBuffer().get(sommet); b.position(b.position() + 2 * n);
            b.get(type);
            b.get(lieu);
            short[] eau = null;
            if (version >= 2) {
                eau = new short[n];
                b.asShortBuffer().get(eau);
            }
            return new Tuile(lieux, haut, sommet, type, lieu, eau);
        } catch (IOException e) {
            throw new UncheckedIOException("Impossible de charger la tuile " + res, e);
        }
    }

    private static int indice(int x, int z) {
        return Math.floorMod(z, TAILLE) * TAILLE + Math.floorMod(x, TAILLE);
    }

    /** Identifiant du lieu sculpté dans cette colonne, ou null. */
    public static String lieu(int x, int z) {
        Tuile t = a(x, z);
        if (t == null) return null;
        int k = t.lieu[indice(x, z)] & 0xFF;
        return k == 0 ? null : t.lieux[k - 1];
    }

    /** Hauteur visée (y) de la colonne sculptée, ou NaN (terrain calculé). */
    public static double hauteur(int x, int z) {
        Tuile t = a(x, z);
        if (t == null) return Double.NaN;
        short h = t.haut[indice(x, z)];
        return h == VIDE ? Double.NaN : h / 16.0;
    }

    /** Repère des couches (y). */
    public static double sommet(int x, int z) {
        Tuile t = a(x, z);
        return t == null ? Double.NaN : t.sommet[indice(x, z)] / 16.0;
    }

    /** Niveau de l'eau du lieu dans cette colonne (l'eau remplit y &lt; niveau), ou Integer.MIN_VALUE. */
    public static int eau(int x, int z) {
        Tuile t = a(x, z);
        if (t == null || t.eau == null) return Integer.MIN_VALUE;
        short e = t.eau[indice(x, z)];
        return e == VIDE ? Integer.MIN_VALUE : e;
    }

    /** Classe + drapeaux (comme LieuGrille), 0 hors lieu. */
    public static int type(int x, int z) {
        Tuile t = a(x, z);
        return t == null ? 0 : t.type[indice(x, z)] & 0xFF;
    }
}

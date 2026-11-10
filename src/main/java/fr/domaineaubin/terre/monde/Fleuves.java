package fr.domaineaubin.terre.monde;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import fr.domaineaubin.terre.DomaineTerre;
import it.unimi.dsi.fastutil.ints.IntArrayList;
import it.unimi.dsi.fastutil.longs.Long2ObjectOpenHashMap;

import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;

/**
 * Tracés réels des fleuves (Natural Earth), convertis en segments en coordonnées de blocs,
 * avec une grille d'index pour trouver vite le segment le plus proche.
 */
public final class Fleuves {
    private static final int CELLULE = 128;
    /** Rayon (blocs) dans lequel le segment le plus proche est garanti trouvé. */
    public static final double RAYON_INDEX = 256.0;

    /** Résultat d'une recherche : distance au lit, classe, point le plus proche sur l'axe du lit, niveau de l'eau (y). */
    public record Proche(double distance, int classe, double cx, double cz, int niveau) {
    }

    /** Calcule le niveau d'eau d'un segment à partir d'un point (coordonnées de blocs). */
    public interface CalculNiveau {
        int niveau(double x, double z);
    }

    /** Point de mer (blocs) le plus proche d'une embouchure restée à terre, ou null (10/11/2026). */
    public interface VersMer {
        double[] mer(double x, double z);
    }

    private final float[] ax, az, bx, bz;
    private final byte[] classe;
    private final short[] niveauA, niveauB;
    /** Bit 1 : le sommet A est la source du cours d'eau ; bit 2 : le sommet B (le lit ne déborde pas au-delà). */
    private final byte[] source;
    private final Long2ObjectOpenHashMap<int[]> grille;
    /** Par segment : premier segment de son cours d'eau, nombre de segments, et sens (amont au début ?). */
    private final int[] debut, nombre;
    private final boolean[] amontDebut;
    /** Niveau d'eau au relief fin aux sommets A et B (calculé à la demande ; INCONNU = pas encore, SANS = pas de relief). */
    private final short[] finA, finB;
    private static final short INCONNU = Short.MIN_VALUE, SANS = Short.MIN_VALUE + 1;
    private volatile CalculNiveau calculFin;

    private Fleuves(float[] ax, float[] az, float[] bx, float[] bz, byte[] classe, short[] niveauA, short[] niveauB, byte[] source,
                    Long2ObjectOpenHashMap<int[]> grille, int[] debut, int[] nombre, boolean[] amontDebut) {
        this.debut = debut;
        this.nombre = nombre;
        this.amontDebut = amontDebut;
        this.finA = new short[ax.length];
        this.finB = new short[ax.length];
        java.util.Arrays.fill(finA, INCONNU);
        java.util.Arrays.fill(finB, INCONNU);
        this.source = source;
        this.ax = ax; this.az = az; this.bx = bx; this.bz = bz;
        this.classe = classe;
        this.niveauA = niveauA;
        this.niveauB = niveauB;
        this.grille = grille;
    }

    private static long cle(int cx, int cz) {
        return ((long) cx << 32) ^ (cz & 0xFFFFFFFFL);
    }

    public static Fleuves charger(double blocsParDegre, CalculNiveau calcul) {
        return charger(blocsParDegre, calcul, null);
    }

    /**
     * versMer (10/11/2026, test : « les fleuves ne rejoignent pas toujours la mer ») : le tracé Natural Earth s'arrête
     * souvent quelques dizaines de blocs avant le trait de côte (deltas du Gange, de l'Indus, du Niger…) et le lit
     * finissait en cul-de-sac dans les terres. Une embouchure restée à terre est prolongée tout droit jusqu'à la mer.
     */
    public static Fleuves charger(double blocsParDegre, CalculNiveau calcul, VersMer versMer) {
        long t0 = System.currentTimeMillis();
        JsonArray tab;
        try (InputStream in = Fleuves.class.getResourceAsStream("/domaine_terre/carte/fleuves.json")) {
            if (in == null) throw new IOException("fleuves.json introuvable");
            tab = JsonParser.parseReader(new InputStreamReader(in, StandardCharsets.UTF_8)).getAsJsonArray();
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
        java.util.List<double[]> traces = new java.util.ArrayList<>(tab.size());
        int prolonges = 0;
        for (JsonElement e : tab) {
            JsonArray ja = e.getAsJsonObject().getAsJsonArray("p");
            double[] d = new double[ja.size()];
            for (int k = 0; k < d.length; k++) d[k] = ja.get(k).getAsDouble();
            int m = d.length / 2;
            if (versMer != null && m >= 2) {
                // embouchure : le bout le plus bas
                double xa = d[0] * blocsParDegre, za = -d[1] * blocsParDegre;
                double xb = d[2 * m - 2] * blocsParDegre, zb = -d[2 * m - 1] * blocsParDegre;
                boolean finEnAval = calcul.niveau(xb, zb) <= calcul.niveau(xa, za);
                double[] mer = finEnAval ? versMer.mer(xb, zb) : versMer.mer(xa, za);
                if (mer != null) {
                    double[] d2 = new double[d.length + 2];
                    double lo = mer[0] / blocsParDegre, la = -mer[1] / blocsParDegre;
                    if (finEnAval) {
                        System.arraycopy(d, 0, d2, 0, d.length);
                        d2[d.length] = lo;
                        d2[d.length + 1] = la;
                    } else {
                        d2[0] = lo;
                        d2[1] = la;
                        System.arraycopy(d, 0, d2, 2, d.length);
                    }
                    d = d2;
                    prolonges++;
                }
            }
            traces.add(d);
        }
        int n = 0;
        for (double[] d : traces) n += Math.max(0, d.length / 2 - 1);
        float[] ax = new float[n], az = new float[n], bx = new float[n], bz = new float[n];
        byte[] cl = new byte[n];
        short[] nva = new short[n], nvb = new short[n];
        byte[] src = new byte[n];
        int[] deb = new int[n], nbr = new int[n];
        boolean[] amd = new boolean[n];
        Long2ObjectOpenHashMap<IntArrayList> tmp = new Long2ObjectOpenHashMap<>();
        int i = 0;
        for (int r = 0; r < tab.size(); r++) {
            JsonObject o = tab.get(r).getAsJsonObject();
            int c = o.get("c").getAsInt();
            double[] p = traces.get(r);
            double marge = Math.max(Terrain.demiLargeur(c) + Terrain.VALLEE_MAX, RAYON_INDEX);
            // niveau de l'eau à chaque sommet (étape C2) : depuis le fond de vallée réel, puis il ne fait que descendre
            // de l'amont (le bout le plus haut) vers l'aval : jamais d'eau qui remonte le long d'un cours d'eau
            int nb = p.length / 2;
            int[] nivS = new int[nb];
            for (int s = 0; s < nb; s++)
                nivS[s] = calcul.niveau(p[2 * s] * blocsParDegre, -p[2 * s + 1] * blocsParDegre);
            boolean amontAuDebut = nb > 1 && nivS[0] >= nivS[nb - 1];
            if (amontAuDebut) {
                for (int s = 1; s < nb; s++) nivS[s] = Math.min(nivS[s], nivS[s - 1]);
            } else {
                for (int s = nb - 2; s >= 0; s--) nivS[s] = Math.min(nivS[s], nivS[s + 1]);
            }
            int premier = i;
            for (int k = 0; k + 3 < p.length; k += 2) {
                deb[i] = premier;
                nbr[i] = nb - 1;
                amd[i] = amontAuDebut;
                double x1 = p[k] * blocsParDegre, z1 = -p[k + 1] * blocsParDegre;
                double x2 = p[k + 2] * blocsParDegre, z2 = -p[k + 3] * blocsParDegre;
                ax[i] = (float) x1; az[i] = (float) z1; bx[i] = (float) x2; bz[i] = (float) z2; cl[i] = (byte) c;
                nva[i] = (short) nivS[k / 2];
                nvb[i] = (short) nivS[k / 2 + 1];
                if (amontAuDebut && k == 0) src[i] |= 1;
                if (!amontAuDebut && k + 4 >= p.length) src[i] |= 2;
                int c0x = (int) Math.floor((Math.min(x1, x2) - marge) / CELLULE), c1x = (int) Math.floor((Math.max(x1, x2) + marge) / CELLULE);
                int c0z = (int) Math.floor((Math.min(z1, z2) - marge) / CELLULE), c1z = (int) Math.floor((Math.max(z1, z2) + marge) / CELLULE);
                for (int gx = c0x; gx <= c1x; gx++)
                    for (int gz = c0z; gz <= c1z; gz++)
                    {
                        long cg = cle(gx, gz);
                        IntArrayList liste = tmp.get(cg);
                        if (liste == null) {
                            liste = new IntArrayList();
                            tmp.put(cg, liste);
                        }
                        liste.add(i);
                    }
                i++;
            }
        }
        Long2ObjectOpenHashMap<int[]> grille = new Long2ObjectOpenHashMap<>(tmp.size());
        tmp.long2ObjectEntrySet().forEach(en -> grille.put(en.getLongKey(), en.getValue().toIntArray()));
        DomaineTerre.LOGGER.info("Fleuves chargés : {} segments ({} embouchures prolongées jusqu'à la mer) en {} ms", n,
                prolonges, System.currentTimeMillis() - t0);
        return new Fleuves(ax, az, bx, bz, cl, nva, nvb, src, grille, deb, nbr, amd);
    }

    /**
     * Relief fin (10/11/2026) : le niveau de l'eau suit le vrai fond de vallée. Sans lui, il venait de la carte 3'
     * (fond lissé, plus haut que le vrai) et la rivière coulait perchée entre deux murs. Niveau d'un sommet : le plus
     * bas des fonds de vallée de ce sommet et des 3 sommets en amont (~90 blocs), si bien qu'il ne remonte pas d'une
     * bosse du relief à l'autre ; jamais plus haut que le niveau d'avant (qui ne fait que descendre).
     */
    public void reliefFin(CalculNiveau calcul) {
        this.calculFin = calcul;
    }

    private int fin(int id, boolean a, CalculNiveau cf) {
        short[] tab = a ? finA : finB;
        short v = tab[id];
        if (v != INCONNU) return v;
        int s = id - debut[id] + (a ? 0 : 1);                   // sommet dans son cours d'eau (0 .. nombre)
        int m = Integer.MAX_VALUE;
        boolean vu = false;
        for (int k = 0; k <= 3; k++) {
            int t = amontDebut[id] ? s - k : s + k;
            if (t < 0 || t > nombre[id]) break;
            int seg = debut[id] + Math.min(t, nombre[id] - 1);
            double x = t < nombre[id] ? ax[seg] : bx[seg], z = t < nombre[id] ? az[seg] : bz[seg];
            int n = cf.niveau(x, z);
            if (n == Integer.MIN_VALUE) continue;
            vu = true;
            m = Math.min(m, n);
        }
        if (!vu) return SANS;                                    // mer, ou paquet pas encore là : pas gardé
        short r = (short) Math.max(Math.min(m, Short.MAX_VALUE), SANS + 1);
        tab[id] = r;
        return r;
    }

    /**
     * Segment qui « domine » ce point : celui dont le bord du lit est le plus proche
     * (un grand fleuve l'emporte sur une rivière voisine). null si aucun dans la cellule.
     */
    public Proche proche(double x, double z) {
        int[] ids = grille.get(cle((int) Math.floor(x / CELLULE), (int) Math.floor(z / CELLULE)));
        if (ids == null) return null;
        double meilleur = Double.MAX_VALUE;
        Proche res = null;
        for (int id : ids) {
            double x1 = ax[id], z1 = az[id], dx = bx[id] - x1, dz = bz[id] - z1;
            double l2 = dx * dx + dz * dz;
            double t = l2 > 0 ? ((x - x1) * dx + (z - z1) * dz) / l2 : 0;
            // au-delà de la source, pas de lit (sinon une mare ronde) : seulement la pente de la vallée
            boolean auDela = (t < 0 && (source[id] & 1) != 0) || (t > 1 && (source[id] & 2) != 0);
            t = Math.max(0, Math.min(1, t));
            double px = x1 + t * dx, pz = z1 + t * dz;
            double d = Math.sqrt((x - px) * (x - px) + (z - pz) * (z - pz));
            if (auDela) d += Terrain.demiLargeur(classe[id]);
            double score = d - Terrain.demiLargeur(classe[id]);
            if (score < meilleur) {
                meilleur = score;
                int na = niveauA[id], nb = niveauB[id];
                CalculNiveau cf = calculFin;
                if (cf != null) {
                    int fa = fin(id, true, cf), fb = fin(id, false, cf);
                    if (fa != SANS) na = Math.min(na, fa);
                    if (fb != SANS) nb = Math.min(nb, fb);
                }
                double nv = na + (nb - na) * t;
                // biefs plats : le niveau ne change que par marches d'un bloc (petites chutes, rapides)
                res = new Proche(d, classe[id], px, pz, (int) Math.floor(nv));
            }
        }
        return res;
    }
}

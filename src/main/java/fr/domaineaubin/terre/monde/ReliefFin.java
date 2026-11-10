package fr.domaineaubin.terre.monde;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import fr.domaineaubin.terre.DomaineTerre;
import net.minecraft.network.chat.Component;
import net.minecraft.server.MinecraftServer;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.fml.loading.FMLPaths;
import net.minecraftforge.server.ServerLifecycleHooks;

import java.io.IOException;
import java.io.Reader;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.zip.Inflater;

/**
 * Relief fin (chantier du 08/11/2026) : le vrai relief à un point par bloc (Copernicus DEM GLO-90 ramené à 250 m,
 * outils/relief_fin.py), par paquets de 4 x 4 régions de 512 blocs (relief_<bx>_<bz>.bin).
 *
 * Les paquets sont cherchés dans <jeu>/domaine_terre/relief/ (cache, et packs hors ligne posés à la main), sinon
 * téléchargés (une seule fois, gardés dans ce dossier). Sans paquet (hors ligne, serveur injoignable) : NaN, le
 * terrain reprend la génération d'avant (carte 3') et un message prévient les joueurs.
 * Réglages : config/domaine_terre_relief.json {"actif": true, "url": "...{bx}...{bz}...", "detail": 0.5}.
 */
@Mod.EventBusSubscriber(modid = DomaineTerre.MOD_ID, bus = Mod.EventBusSubscriber.Bus.FORGE)
public final class ReliefFin {
    static final int T = 512, Q = 5;
    static final short VIDE = Short.MIN_VALUE;
    private static final short[] SANS = new short[0];          // paquet ou région sans terre
    private static final int MAX_REGIONS = 96;                  // ~48 Mo en mémoire

    private static volatile boolean actif = true;
    private static volatile String url =
            "https://github.com/theMitch37/domaine-terre-relief/releases/download/v1-z{bz}/relief_{bx}_{bz}.bin";
    private static volatile double detail = 0.5;      // 10/11/2026 : 0,25 -> 0,5 (monde agrandi : vraies arêtes, banc Everest)
    private static volatile boolean charge = false;

    private static final Map<Long, short[]> regions = new LinkedHashMap<>(128, 0.75f, true);
    private static final Map<Long, Future<?>> enCours = new ConcurrentHashMap<>();
    private static final java.util.Set<Long> mers = ConcurrentHashMap.newKeySet();
    private static final Map<Long, Long> echecs = new ConcurrentHashMap<>();       // paquet -> instant de l'échec
    private static final ExecutorService telechargeur = Executors.newFixedThreadPool(2, r -> {
        Thread t = new Thread(r, "Domaine Terre - relief fin");
        t.setDaemon(true);
        return t;
    });
    private static final HttpClient http = HttpClient.newBuilder()
            .followRedirects(HttpClient.Redirect.NORMAL).connectTimeout(Duration.ofSeconds(10)).build();
    private static volatile boolean manque = false, prevenu = false;

    private ReliefFin() {
    }

    /** Part du détail fin gardée (le mod exagère les hauteurs ×6 à ×10 : tout le détail ferait des murs). */
    public static double detail() {
        reglages();
        return detail;
    }

    /** Altitude réelle (m) au bloc (x, z), ou NaN (pas de relief fin : mer, ou paquet indisponible). */
    public static double altitude(int x, int z) {
        reglages();
        if (!actif) return Double.NaN;
        int tx = x >> 9, tz = z >> 9;
        short[] r = region(tx, tz);
        if (r.length == 0) return Double.NaN;
        short v = r[(z & 511) * T + (x & 511)];
        return v == VIDE ? Double.NaN : v * (double) Q;
    }

    // ---------------------------------------------------------------- pente limitée (10/11/2026)

    /**
     * Pente maximale du terrain, en blocs par bloc (décision de Maxime, 10/11/2026 : « limiter la pente » plutôt que
     * baisser le toit du monde). Au-dessus de 4 000 m, un bloc vaut 12,8 m en hauteur pour 250 m à l'horizontale :
     * une pente réelle de 30° y devenait presque verticale (aiguilles). Le terrain est rabaissé là où il monte plus
     * vite que 65° depuis un point plus bas (enveloppe de pente, aussi dite « lipschitzienne ») : les fonds de vallée
     * ne bougent pas, les sommets deviennent des pyramides à arêtes (l'Everest perd environ 15 % de sa hauteur).
     */
    static final double PENTE_MAX = 2.14;
    /** Marge lue autour d'une région : un sommet est limité par les points bas jusqu'à ~100 blocs. */
    private static final int MARGE = 96;
    private static final Map<Long, short[]> limitees = new LinkedHashMap<>(128, 0.75f, true);

    /**
     * Altitude (m) que le terrain utilise au bloc (x, z) : celle du relief fin, rabaissée là où la pente du terrain
     * dépasserait {@link #PENTE_MAX} ; NaN sans relief fin. L'altitude réelle ({@link #altitude}) reste celle des
     * règles (neige, roche, arbres).
     */
    public static double altitudeTerrain(int x, int z) {
        reglages();
        if (!actif) return Double.NaN;
        int tx = x >> 9, tz = z >> 9;
        short[] r = limitee(tx, tz);
        if (r.length == 0) return Double.NaN;
        short v = r[(z & 511) * T + (x & 511)];
        return v == VIDE ? Double.NaN : v * (double) Q;
    }

    /** Régions gardées en relief brut faute de voisin disponible : instant du dernier essai. */
    private static final Map<Long, Long> provisoires = new ConcurrentHashMap<>();

    private static short[] limitee(int tx, int tz) {
        long k = cle(tx, tz);
        synchronized (limitees) {
            short[] r = limitees.get(k);
            if (r != null) {
                Long p = provisoires.get(k);
                if (p == null || System.currentTimeMillis() - p < 60_000) return r;
            }
        }
        short[] brut = region(tx, tz);
        if (brut.length == 0) return brut;
        short[] r = calculerLimitee(tx, tz, brut);
        if (r == null) {                                         // voisin pas encore là : relief brut, réessayé plus tard
            provisoires.put(k, System.currentTimeMillis());
            r = brut;
        } else {
            provisoires.remove(k);
        }
        synchronized (limitees) {
            limitees.put(k, r);
            while (limitees.size() > MAX_REGIONS) limitees.remove(limitees.keySet().iterator().next());
        }
        return r;
    }

    /** Région limitée en pente, ou null si une région voisine n'est pas encore disponible. */
    private static short[] calculerLimitee(int tx, int tz, short[] brut) {
        Terrain t = Terrain.get();
        double d = detail();
        int n = T + 2 * MARGE;
        int x0 = tx * T - MARGE, z0 = tz * T - MARGE;
        short[][] vois = new short[9][];
        for (int j = -1; j <= 1; j++) {
            for (int i = -1; i <= 1; i++) {
                short[] v = (i == 0 && j == 0) ? brut : region(tx + i, tz + j);
                if (v.length == 0) {
                    synchronized (regions) {
                        if (!regions.containsKey(cle(tx + i, tz + j))) return null;     // indisponible (pas la mer)
                    }
                }
                vois[(j + 1) * 3 + (i + 1)] = v;
            }
        }
        double[] h = new double[n * n], base = new double[n * n];
        for (int zz = 0; zz < n; zz++) {
            int z = z0 + zz;
            for (int xx = 0; xx < n; xx++) {
                int x = x0 + xx;
                short[] v = vois[(Math.floorDiv(z, T) - tz + 1) * 3 + (Math.floorDiv(x, T) - tx + 1)];
                int i = zz * n + xx;
                double b = Terrain.blocsDepuisAltitude(Math.max(t.altitudeReelle(x, z), 1.0));
                base[i] = b;
                short a = v.length == 0 ? VIDE : v[Math.floorMod(z, T) * T + Math.floorMod(x, T)];
                h[i] = a == VIDE ? Terrain.NIVEAU_MER : b + (Terrain.blocsDepuisAltitude(Math.max(a * (double) Q, 1.0)) - b) * d;
            }
        }
        double[] e = h.clone();
        double s = PENTE_MAX, s2 = PENTE_MAX * Math.sqrt(2.0);
        for (int zz = 0; zz < n; zz++) {                         // passe aller (haut-gauche vers bas-droite)
            for (int xx = 0; xx < n; xx++) {
                int i = zz * n + xx;
                double m = e[i];
                if (xx > 0) m = Math.min(m, e[i - 1] + s);
                if (zz > 0) {
                    m = Math.min(m, e[i - n] + s);
                    if (xx > 0) m = Math.min(m, e[i - n - 1] + s2);
                    if (xx < n - 1) m = Math.min(m, e[i - n + 1] + s2);
                }
                e[i] = m;
            }
        }
        for (int zz = n - 1; zz >= 0; zz--) {                    // passe retour
            for (int xx = n - 1; xx >= 0; xx--) {
                int i = zz * n + xx;
                double m = e[i];
                if (xx < n - 1) m = Math.min(m, e[i + 1] + s);
                if (zz < n - 1) {
                    m = Math.min(m, e[i + n] + s);
                    if (xx < n - 1) m = Math.min(m, e[i + n + 1] + s2);
                    if (xx > 0) m = Math.min(m, e[i + n - 1] + s2);
                }
                e[i] = m;
            }
        }
        short[] out = brut.clone();
        for (int zz = 0; zz < T; zz++) {
            for (int xx = 0; xx < T; xx++) {
                int i = (zz + MARGE) * n + (xx + MARGE), o = zz * T + xx;
                if (out[o] == VIDE || e[i] >= h[i] - 1e-6) continue;
                // altitude qui redonne, avec la même part de détail, la hauteur limitée
                double y = base[i] + (e[i] - base[i]) / Math.max(d, 1e-3);
                double a = altitudeDepuisBlocs(y);
                out[o] = (short) Math.max(Math.min(Math.round(a / Q), Short.MAX_VALUE), Short.MIN_VALUE + 1);
            }
        }
        return out;
    }

    /** Inverse de {@link Terrain#blocsDepuisAltitude} sur les terres (y 64 à 620). */
    static double altitudeDepuisBlocs(double y) {
        if (y <= 64) return 1.0;
        if (y <= 80) return (y - 64) * 500.0 / 16.0;
        if (y <= 140) return 500 + (y - 80) * 1500.0 / 60.0;
        if (y <= 240) return 2000 + (y - 140) * 2000.0 / 100.0;
        return 4000 + Math.min(y - 240, 380.0) * 4849.0 / 380.0;
    }

    /**
     * Fond de vallée au relief fin autour d'un point de l'axe d'un cours d'eau (10/11/2026) : la plus basse des
     * altitudes sur 3 x 3 points espacés de 2 blocs (le tracé du cours d'eau s'écarte d'un bloc ou deux du vrai
     * talweg), en m ; NaN sans relief fin.
     */
    public static double altitudeFond(int x, int z) {
        double m = Double.NaN;
        for (int dz = -2; dz <= 2; dz += 2) {
            for (int dx = -2; dx <= 2; dx += 2) {
                double a = altitude(x + dx, z + dz);
                if (!Double.isNaN(a) && (Double.isNaN(m) || a < m)) m = a;
            }
        }
        return m;
    }

    private static long cle(int a, int b) {
        return ((long) a << 32) ^ (b & 0xFFFFFFFFL);
    }

    private static short[] region(int tx, int tz) {
        long k = cle(tx, tz);
        synchronized (regions) {
            short[] r = regions.get(k);
            if (r != null) return r;
        }
        int bx = tx >> 2, bz = tz >> 2;
        Map<Integer, short[]> paquet = paquet(bx, bz);
        short[] r = SANS;
        synchronized (regions) {
            for (var e : paquet.entrySet()) {
                int i = e.getKey();
                regions.put(cle((bx << 2) + (i & 3), (bz << 2) + (i >> 2)), e.getValue());
            }
            // régions sans terre (paquet de mer, ou mer dans un paquet de terre) : connues, vides
            if (!paquet.containsKey(-1)) {
                for (int i = 0; i < 16; i++) regions.putIfAbsent(cle((bx << 2) + (i & 3), (bz << 2) + (i >> 2)), SANS);
            }
            r = regions.getOrDefault(k, SANS);
            if (paquet.containsKey(-1)) {                      // indisponible : ne pas garder, on réessaiera plus tard
                for (int i = 0; i < 16; i++) regions.remove(cle((bx << 2) + (i & 3), (bz << 2) + (i >> 2)));
                r = SANS;
            }
            while (regions.size() > MAX_REGIONS) regions.remove(regions.keySet().iterator().next());
        }
        return r;
    }

    private static Path dossier() {
        return FMLPaths.GAMEDIR.get().resolve("domaine_terre").resolve("relief");
    }

    /** Régions d'un paquet (index 0..15 -> altitudes / 5 m) ; {-1: ...} si indisponible pour l'instant. */
    private static Map<Integer, short[]> paquet(int bx, int bz) {
        Path f = dossier().resolve("relief_" + bx + "_" + bz + ".bin");
        Path vide = dossier().resolve("relief_" + bx + "_" + bz + ".vide");
        if (Files.exists(vide) || mers.contains(cle(bx, bz))) return Map.of();
        if (!Files.exists(f)) {
            long k = cle(bx, bz);
            Long e = echecs.get(k);
            if (e != null && System.currentTimeMillis() - e < 300_000) return indisponible();
            Future<?> tache = enCours.computeIfAbsent(k, kk -> telechargeur.submit(() -> telecharger(bx, bz, f, vide)));
            try {
                tache.get(60, TimeUnit.SECONDS);
            } catch (Exception ex) {
                DomaineTerre.LOGGER.warn("Relief fin : paquet {} {} pas encore là ({})", bx, bz, ex.toString());
            } finally {
                enCours.remove(k, tache);
            }
            if (Files.exists(vide) || mers.contains(k)) return Map.of();
            if (!Files.exists(f)) {
                echecs.put(k, System.currentTimeMillis());
                manque = true;
                return indisponible();
            }
        }
        try {
            return lire(Files.readAllBytes(f));
        } catch (Exception ex) {
            DomaineTerre.LOGGER.error("Relief fin : {} illisible, supprimé", f, ex);
            try {
                Files.deleteIfExists(f);
            } catch (IOException ignore) {
            }
            return indisponible();
        }
    }

    private static Map<Integer, short[]> indisponible() {
        return Map.of(-1, SANS);
    }

    private static void telecharger(int bx, int bz, Path f, Path vide) {
        String u = url.replace("{bx}", Integer.toString(bx)).replace("{bz}", Integer.toString(bz));
        try {
            Files.createDirectories(f.getParent());
            HttpRequest req = HttpRequest.newBuilder(URI.create(u)).timeout(Duration.ofSeconds(45))
                    .header("User-Agent", "DomaineTerre").GET().build();
            HttpResponse<byte[]> rep = http.send(req, HttpResponse.BodyHandlers.ofByteArray());
            if (rep.statusCode() == 404) {                    // pas de paquet : rien que de la mer (retenu le temps de la
                mers.add(cle(bx, bz));                         // session seulement : un dépôt absent répond aussi 404)
                return;
            }
            if (rep.statusCode() != 200) {
                DomaineTerre.LOGGER.warn("Relief fin : {} -> {}", u, rep.statusCode());
                return;
            }
            byte[] b = rep.body();
            lire(b);                                           // vérifie avant de garder
            Path tmp = f.resolveSibling(f.getFileName() + ".part");
            Files.write(tmp, b);
            Files.move(tmp, f, StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
            DomaineTerre.LOGGER.info("Relief fin : paquet {} {} téléchargé ({} Ko)", bx, bz, b.length / 1024);
        } catch (Exception ex) {
            DomaineTerre.LOGGER.warn("Relief fin : téléchargement de {} impossible ({})", u, ex.toString());
        }
    }

    static Map<Integer, short[]> lire(byte[] b) throws Exception {
        ByteBuffer bb = ByteBuffer.wrap(b).order(ByteOrder.LITTLE_ENDIAN);
        if (b.length < 16 + 128 || b[0] != 'R' || b[1] != 'E' || b[2] != 'L' || b[3] != 'B')
            throw new IOException("pas un paquet de relief");
        bb.position(4);
        int version = bb.getInt();
        if (version != 1) throw new IOException("version " + version);
        bb.getInt();
        bb.getInt();
        Map<Integer, short[]> m = new LinkedHashMap<>();
        for (int i = 0; i < 16; i++) {
            int o = bb.getInt(16 + 8 * i), l = bb.getInt(20 + 8 * i);
            if (l == 0) continue;
            m.put(i, region(b, o, l));
        }
        return m;
    }

    /** Une région : zlib(512 x 512 int16), écart avec le voisin de gauche, VIDE = pas de donnée. */
    private static short[] region(byte[] b, int o, int l) throws Exception {
        Inflater inf = new Inflater();
        inf.setInput(b, o, l);
        byte[] brut = new byte[T * T * 2];
        int n = 0;
        while (n < brut.length && !inf.finished()) {
            int k = inf.inflate(brut, n, brut.length - n);
            if (k == 0 && (inf.needsInput() || inf.needsDictionary())) break;
            n += k;
        }
        inf.end();
        if (n != brut.length) throw new IOException("région tronquée");
        ByteBuffer bb = ByteBuffer.wrap(brut).order(ByteOrder.LITTLE_ENDIAN);
        short[] q = new short[T * T];
        for (int z = 0; z < T; z++) {
            int prec = VIDE;
            for (int x = 0; x < T; x++) {
                int d = bb.getShort();
                int v = d == VIDE ? VIDE : (prec == VIDE ? d : prec + d);
                q[z * T + x] = (short) v;
                prec = v;
            }
        }
        return q;
    }

    private static void reglages() {
        if (charge) return;
        synchronized (ReliefFin.class) {
            if (charge) return;
            Path cfg = FMLPaths.CONFIGDIR.get().resolve("domaine_terre_relief.json");
            try {
                if (Files.exists(cfg)) {
                    try (Reader r = Files.newBufferedReader(cfg, StandardCharsets.UTF_8)) {
                        JsonObject o = JsonParser.parseReader(r).getAsJsonObject();
                        if (o.has("actif")) actif = o.get("actif").getAsBoolean();
                        if (o.has("url")) url = o.get("url").getAsString();
                        if (o.has("detail")) detail = o.get("detail").getAsDouble();
                    }
                } else {
                    Files.createDirectories(cfg.getParent());
                    Files.writeString(cfg, "{\n  \"actif\": true,\n  \"url\": \"" + url + "\",\n  \"detail\": " + detail
                            + "\n}\n", StandardCharsets.UTF_8);
                }
            } catch (Exception e) {
                DomaineTerre.LOGGER.error("Relief fin : {} illisible", cfg, e);
            }
            DomaineTerre.LOGGER.info("Relief fin : {} (détail {}, dossier {})", actif ? "actif" : "désactivé", detail, dossier());
            charge = true;
        }
    }

    /** Prévient une fois les joueurs quand une zone a dû être générée sans le relief fin. */
    @SubscribeEvent
    public static void tic(TickEvent.ServerTickEvent e) {
        if (e.phase != TickEvent.Phase.END || !manque || prevenu) return;
        MinecraftServer s = ServerLifecycleHooks.getCurrentServer();
        if (s == null || s.getPlayerList().getPlayerCount() == 0) return;
        prevenu = true;
        s.getPlayerList().broadcastSystemMessage(Component.literal(
                "§6[Domaine Terre]§r Relief détaillé indisponible (pas de connexion ?) : certaines zones sont générées avec "
                        + "le relief simplifié. Il reviendra pour les nouvelles zones dès que la connexion sera rétablie."), false);
    }
}

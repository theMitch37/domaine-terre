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
 * Réglages : config/domaine_terre_relief.json {"actif": true, "url": "...{bx}...{bz}...", "detail": 0.25}.
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
    private static volatile double detail = 0.25;
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
            if (paquet.isEmpty()) {
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

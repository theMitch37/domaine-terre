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
import java.io.RandomAccessFile;
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
 * Relief fin (chantier du 08/11/2026) : le vrai relief à un point par bloc, téléchargé pendant la génération.
 * <ul>
 * <li>1:250 : Copernicus DEM GLO-90 ramené à 250 m (outils/relief_fin.py), paquets v1 de 4 x 4 régions de 512 blocs
 * (relief_&lt;bx&gt;_&lt;bz&gt;.bin, releases v1-z&lt;bz&gt;), dossier &lt;jeu&gt;/domaine_terre/relief/.</li>
 * <li>1:30 (09/11/2026) : Copernicus DEM GLO-30 à 30 m (relief30.py du dépôt relief), paquets v2 de 16 x 16 régions
 * (relief30_&lt;bx&gt;_&lt;bz&gt;.bin, releases v30-z&lt;bz&gt;), dossier &lt;jeu&gt;/domaine_terre/relief30/. Là où ils
 * manquent encore, le relief à 250 m est interpolé entre ses points.</li>
 * <li>1:500 et 1:1000 : le relief à 250 m, interpolé à la position réelle de chaque bloc.</li>
 * </ul>
 * Les paquets sont cherchés dans leur dossier (cache, et packs hors ligne posés à la main), sinon téléchargés (une
 * seule fois, gardés). Une région n'est décodée qu'au besoin. Sans paquet (hors ligne, serveur injoignable) : NaN, le
 * terrain reprend la génération d'avant (carte 3') et un message prévient les joueurs.
 * Réglages : config/domaine_terre_relief.json {"actif", "url", "detail", "url_30", "detail_30"}.
 */
@Mod.EventBusSubscriber(modid = DomaineTerre.MOD_ID, bus = Mod.EventBusSubscriber.Bus.FORGE)
public final class ReliefFin {
    static final int T = 512, Q = 5;
    static final short VIDE = Short.MIN_VALUE;
    private static final short[] SANS = new short[0];          // paquet ou région sans terre

    private static volatile boolean actif = true;
    private static volatile double detail = 0.25, detail30 = 1.0;
    private static volatile boolean charge = false;
    private static volatile boolean manque = false, prevenu = false;

    private static final String URL_V1 =
            "https://github.com/theMitch37/domaine-terre-relief/releases/download/v1-z{bz}/relief_{bx}_{bz}.bin";
    private static final String URL_V30 =
            "https://github.com/theMitch37/domaine-terre-relief/releases/download/v30-z{bz}/relief30_{bx}_{bz}.bin";

    /** Relief à 250 m (un point par bloc en 1:250). */
    private static final Jeu V1 = new Jeu("relief", "relief_", 250, 4, URL_V1, 96, 45, 60);
    /** Relief à 30 m (un point par bloc en 1:30). */
    private static final Jeu V30 = new Jeu("relief30", "relief30_", 30, 16, URL_V30, 128, 300, 90);
    /**
     * Sol à 30 m (09/11/2026, outils/sol30.py) : roche × 256 + couverture du sol (ESA WorldCover), même format de
     * paquets que le relief 1:30.
     */
    private static final Jeu SOL30 = new Jeu("sol30", "sol30_", 30, 16,
            "https://github.com/theMitch37/domaine-terre-relief/releases/download/s30-z{bz}/sol30_{bx}_{bz}.bin", 128, 300, 90);

    /** Eau intérieure à 30 m (09/11/2026, outils/sol30.py) : niveau et distance signée à la berge. */
    private static final Jeu EAU30 = new Jeu("eau30", "eau30_", 30, 16,
            "https://github.com/theMitch37/domaine-terre-relief/releases/download/e30-z{bz}/eau30_{bx}_{bz}.bin", 128, 300, 90);

    /**
     * Fond des mers à 15" (09/11/2026, fond.py du dépôt relief) : ETOPO 2022 (NOAA, domaine public), ramené sur la
     * grille du relief 1:250 (un point tous les 250 m), seulement en mer et près des côtes ; lu en bilinéaire.
     */
    private static final Jeu FOND = new Jeu("fond", "fond_", 250, 4,
            "https://github.com/theMitch37/domaine-terre-relief/releases/download/f-z{bz}/fond_{bx}_{bz}.bin", 96, 120, 30);

    /** Altitude réelle du fond (m, négative en mer) au bloc (x, z), NaN sans donnée. Seulement en 1:30 pour l'instant. */
    public static double fond(int x, int z) {
        reglages();
        if (!actif || Terrain.echelle() >= 250) return Double.NaN;
        return interpole(FOND, Terrain.lon(x + 0.5), Terrain.lat(z + 0.5));
    }

    /**
     * Eau intérieure du bloc (x, z) d'un monde 1:30 : round((niveau en m + 500) / 3) × 16 + c (c de 0 à 7 : dans
     * l'eau, Terrain.DANS_EAU ; de 8 à 15 : terre proche, Terrain.PRES_EAU) ; -1 sans eau proche ou sans donnée.
     */
    public static int eau(int x, int z) {
        reglages();
        if (!actif || Terrain.echelle() != EAU30.echelle) return -1;
        int v = EAU30.brut(x, z);
        return v == VIDE ? -1 : v & 0xFFFF;
    }

    /**
     * Sol du bloc (x, z) d'un monde 1:30 : roche × 256 + couverture (classes WorldCover : 10 arbres, 20 broussailles,
     * 30 prairie, 40 cultures, 50 bâti, 60 sol nu, 70 neige et glace, 80 eau, 90 zone humide, 95 mangrove,
     * 100 mousses et lichens) ; -1 sans donnée (autre échelle, paquet absent).
     */
    public static int sol(int x, int z) {
        reglages();
        if (!actif || Terrain.echelle() != SOL30.echelle) return -1;
        int v = SOL30.brut(x, z);
        return v == VIDE ? -1 : v & 0xFFFF;
    }

    private static final ExecutorService telechargeur = Executors.newFixedThreadPool(2, r -> {
        Thread t = new Thread(r, "Domaine Terre - relief fin");
        t.setDaemon(true);
        return t;
    });
    private static final HttpClient http = HttpClient.newBuilder()
            .followRedirects(HttpClient.Redirect.NORMAL).connectTimeout(Duration.ofSeconds(10)).build();

    private ReliefFin() {
    }

    /** Part du détail fin gardée : 0,25 en 1:250 (hauteurs exagérées ×6 à ×10), tout en 1:30 (vraies proportions). */
    public static double detail() {
        reglages();
        return Terrain.echelle() < 250 ? detail30 : detail;
    }

    /** Altitude réelle (m) au bloc (x, z) du monde chargé, ou NaN (pas de relief fin : mer, ou paquet indisponible). */
    public static double altitude(int x, int z) {
        reglages();
        if (!actif) return Double.NaN;
        int e = Terrain.echelle();
        if (e == V1.echelle) return V1.valeur(x, z);
        if (e == V30.echelle) {
            double a = V30.valeur(x, z);
            if (!Double.isNaN(a)) return a;
        }
        return interpole(V1, Terrain.lon(x + 0.5), Terrain.lat(z + 0.5));
    }

    /** Relief d'un jeu de données à une position quelconque : bilinéaire entre les centres de ses blocs. */
    private static double interpole(Jeu j, double lon, double lat) {
        double gx = lon * j.bpd - 0.5, gz = -lat * j.bpd - 0.5;
        int ix = (int) Math.floor(gx), iz = (int) Math.floor(gz);
        double fx = gx - ix, fz = gz - iz;
        double a = j.valeur(ix, iz), b = j.valeur(ix + 1, iz), c = j.valeur(ix, iz + 1), d = j.valeur(ix + 1, iz + 1);
        if (Double.isNaN(a) || Double.isNaN(b) || Double.isNaN(c) || Double.isNaN(d)) {
            // près de la mer : le point le plus proche (pas de moyenne avec le vide)
            return j.valeur(fx < 0.5 ? ix : ix + 1, fz < 0.5 ? iz : iz + 1);
        }
        return (a * (1 - fx) + b * fx) * (1 - fz) + (c * (1 - fx) + d * fx) * fz;
    }

    private static long cle(int a, int b) {
        return ((long) a << 32) ^ (b & 0xFFFFFFFFL);
    }

    /** Table d'un paquet : où trouver chacune de ses régions dans le fichier. */
    private record Paquet(Path fichier, int[] decalage, int[] longueur) {
    }

    private static final Paquet VIDE_PAQUET = new Paquet(null, new int[0], new int[0]);   // pas de terre
    private static final Paquet ABSENT = new Paquet(null, null, null);                    // pas encore là

    /** Un jeu de données (une résolution) : ses paquets, leur téléchargement et le cache de régions décodées. */
    private static final class Jeu {
        final String dossier, prefixe;
        final int echelle, n, decalN, maxRegions, delaiTelechargement, attente;
        final double bpd;
        volatile String url;
        final Map<Long, short[]> regions = new LinkedHashMap<>(256, 0.75f, true);
        final Map<Long, Paquet> paquets = new ConcurrentHashMap<>();
        final Map<Long, Future<?>> enCours = new ConcurrentHashMap<>();
        final java.util.Set<Long> mers = ConcurrentHashMap.newKeySet();
        final Map<Long, Long> echecs = new ConcurrentHashMap<>();       // paquet -> instant de l'échec

        Jeu(String dossier, String prefixe, int echelle, int n, String url, int maxRegions, int delaiTelechargement,
            int attente) {
            this.dossier = dossier;
            this.prefixe = prefixe;
            this.echelle = echelle;
            this.bpd = 111.32 * 1000.0 / echelle;
            this.n = n;
            this.decalN = Integer.numberOfTrailingZeros(n);
            this.url = url;
            this.maxRegions = maxRegions;
            this.delaiTelechargement = delaiTelechargement;
            this.attente = attente;
        }

        Path dossier() {
            return FMLPaths.GAMEDIR.get().resolve("domaine_terre").resolve(dossier);
        }

        /** Valeur brute du bloc, VIDE sans donnée. */
        int brut(int x, int z) {
            short[] r = region(x >> 9, z >> 9);
            if (r.length == 0) return VIDE;
            return r[(z & 511) * T + (x & 511)];
        }

        double valeur(int x, int z) {
            short[] r = region(x >> 9, z >> 9);
            if (r.length == 0) return Double.NaN;
            short v = r[(z & 511) * T + (x & 511)];
            return v == VIDE ? Double.NaN : v * (double) Q;
        }

        short[] region(int tx, int tz) {
            long k = cle(tx, tz);
            synchronized (regions) {
                short[] r = regions.get(k);
                if (r != null) return r;
            }
            Paquet p = paquet(tx >> decalN, tz >> decalN);
            if (p == ABSENT) return SANS;                     // indisponible : pas gardé, on réessaiera plus tard
            short[] r = SANS;
            if (p != VIDE_PAQUET) {
                int i = (tx & (n - 1)) + n * (tz & (n - 1));
                if (p.longueur()[i] > 0) {
                    try {
                        r = lireRegion(p.fichier(), p.decalage()[i], p.longueur()[i]);
                    } catch (Exception ex) {
                        DomaineTerre.LOGGER.error("Relief fin : région {} {} illisible dans {}", tx, tz, p.fichier(), ex);
                        oublier(tx >> decalN, tz >> decalN, p.fichier());
                        return SANS;
                    }
                }
            }
            synchronized (regions) {
                regions.put(k, r);
                while (regions.size() > maxRegions) regions.remove(regions.keySet().iterator().next());
            }
            return r;
        }

        private void oublier(int bx, int bz, Path f) {
            paquets.remove(cle(bx, bz));
            try {
                Files.deleteIfExists(f);
            } catch (IOException ignore) {
            }
        }

        /** Table du paquet (bx, bz), VIDE_PAQUET s'il n'a pas de terre, ABSENT s'il n'est pas disponible pour l'instant. */
        Paquet paquet(int bx, int bz) {
            long k = cle(bx, bz);
            Paquet p = paquets.get(k);
            if (p != null) return p;
            Path f = dossier().resolve(prefixe + bx + "_" + bz + ".bin");
            Path vide = dossier().resolve(prefixe + bx + "_" + bz + ".vide");
            if (Files.exists(vide) || mers.contains(k)) return garder(k, VIDE_PAQUET);
            if (!Files.exists(f)) {
                Long e = echecs.get(k);
                if (e != null && System.currentTimeMillis() - e < 300_000) return ABSENT;
                Future<?> tache = enCours.computeIfAbsent(k, kk -> telechargeur.submit(() -> telecharger(bx, bz, f)));
                try {
                    tache.get(attente, TimeUnit.SECONDS);
                    enCours.remove(k, tache);
                } catch (Exception ex) {
                    // le téléchargement continue en arrière-plan ; le paquet servira dès qu'il sera là
                    DomaineTerre.LOGGER.warn("Relief fin : paquet {} {} {} pas encore là ({})", dossier, bx, bz, ex.toString());
                    if (tache.isDone()) enCours.remove(k, tache);
                }
                if (mers.contains(k)) return garder(k, VIDE_PAQUET);
                if (!Files.exists(f)) {
                    echecs.put(k, System.currentTimeMillis());
                    manque = true;
                    return ABSENT;
                }
            }
            try {
                return garder(k, table(f));
            } catch (Exception ex) {
                DomaineTerre.LOGGER.error("Relief fin : {} illisible, supprimé", f, ex);
                oublier(bx, bz, f);
                return ABSENT;
            }
        }

        /** Lance en arrière-plan le téléchargement du paquet (bx, bz) s'il manque (sans attendre). */
        void prevoir(int bx, int bz) {
            long k = cle(bx, bz);
            if (paquets.containsKey(k) || mers.contains(k) || enCours.containsKey(k)) return;
            Long e = echecs.get(k);
            if (e != null && System.currentTimeMillis() - e < 300_000) return;
            Path f = dossier().resolve(prefixe + bx + "_" + bz + ".bin");
            if (Files.exists(f) || Files.exists(dossier().resolve(prefixe + bx + "_" + bz + ".vide"))) return;
            enCours.computeIfAbsent(k, kk -> telechargeur.submit(() -> {
                telecharger(bx, bz, f);
                enCours.remove(kk);
            }));
        }

        private Paquet garder(long k, Paquet p) {
            paquets.put(k, p);
            return p;
        }

        /** Lit l'en-tête d'un paquet (v1 : 4 x 4 régions ; v2 : n x n). */
        Paquet table(Path f) throws IOException {
            try (RandomAccessFile raf = new RandomAccessFile(f.toFile(), "r")) {
                byte[] t = new byte[24];
                raf.readFully(t, 0, 16);
                ByteBuffer bb = ByteBuffer.wrap(t).order(ByteOrder.LITTLE_ENDIAN);
                if (t[0] != 'R' || t[1] != 'E' || t[2] != 'L' || t[3] != 'B') throw new IOException("pas un paquet de relief");
                int version = bb.getInt(4), debut, cote;
                if (version == 1) {
                    cote = 4;
                    debut = 16;
                } else if (version == 2) {
                    raf.readFully(t, 16, 8);
                    cote = bb.getInt(16);
                    debut = 24;
                } else {
                    throw new IOException("version " + version);
                }
                if (cote != n) throw new IOException(cote + " régions par côté au lieu de " + n);
                byte[] tab = new byte[n * n * 8];
                raf.seek(debut);
                raf.readFully(tab);
                ByteBuffer tb = ByteBuffer.wrap(tab).order(ByteOrder.LITTLE_ENDIAN);
                int[] dec = new int[n * n], lon = new int[n * n];
                long taille = raf.length();
                for (int i = 0; i < n * n; i++) {
                    dec[i] = tb.getInt();
                    lon[i] = tb.getInt();
                    if (lon[i] > 0 && (dec[i] < debut || (long) dec[i] + lon[i] > taille)) throw new IOException("paquet tronqué");
                }
                return new Paquet(f, dec, lon);
            }
        }

        private void telecharger(int bx, int bz, Path f) {
            String u = url.replace("{bx}", Integer.toString(bx)).replace("{bz}", Integer.toString(bz));
            try {
                Files.createDirectories(f.getParent());
                HttpRequest req = HttpRequest.newBuilder(URI.create(u)).timeout(Duration.ofSeconds(delaiTelechargement))
                        .header("User-Agent", "DomaineTerre").GET().build();
                Path tmp = f.resolveSibling(f.getFileName() + ".part");
                HttpResponse<Path> rep = http.send(req, HttpResponse.BodyHandlers.ofFile(tmp));
                if (rep.statusCode() == 404) {                    // pas de paquet : rien que de la mer (retenu le temps
                    Files.deleteIfExists(tmp);                     // de la session : une release absente répond aussi 404)
                    mers.add(cle(bx, bz));
                    return;
                }
                if (rep.statusCode() != 200) {
                    Files.deleteIfExists(tmp);
                    DomaineTerre.LOGGER.warn("Relief fin : {} -> {}", u, rep.statusCode());
                    return;
                }
                table(tmp);                                        // vérifie avant de garder
                long taille = Files.size(tmp);
                Files.move(tmp, f, StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
                DomaineTerre.LOGGER.info("Relief fin : paquet {} {} {} téléchargé ({} Ko)", dossier, bx, bz, taille / 1024);
            } catch (Exception ex) {
                DomaineTerre.LOGGER.warn("Relief fin : téléchargement de {} impossible ({})", u, ex.toString());
            }
        }
    }

    /** Une région : zlib(512 x 512 int16), écart avec le voisin de gauche, VIDE = pas de donnée. */
    private static short[] lireRegion(Path f, int o, int l) throws Exception {
        byte[] b = new byte[l];
        try (RandomAccessFile raf = new RandomAccessFile(f.toFile(), "r")) {
            raf.seek(o);
            raf.readFully(b);
        }
        Inflater inf = new Inflater();
        inf.setInput(b, 0, l);
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
                        if (o.has("url")) V1.url = o.get("url").getAsString();
                        if (o.has("detail")) detail = o.get("detail").getAsDouble();
                        if (o.has("url_30")) V30.url = o.get("url_30").getAsString();
                        if (o.has("detail_30")) detail30 = o.get("detail_30").getAsDouble();
                    }
                } else {
                    Files.createDirectories(cfg.getParent());
                    Files.writeString(cfg, "{\n  \"actif\": true,\n  \"url\": \"" + V1.url + "\",\n  \"detail\": " + detail
                            + ",\n  \"url_30\": \"" + V30.url + "\",\n  \"detail_30\": " + detail30 + "\n}\n",
                            StandardCharsets.UTF_8);
                }
            } catch (Exception e) {
                DomaineTerre.LOGGER.error("Relief fin : {} illisible", cfg, e);
            }
            DomaineTerre.LOGGER.info("Relief fin : {} (détail {} en 1:250, {} en 1:30, dossier {})", actif ? "actif" : "désactivé",
                    detail, detail30, V1.dossier().getParent());
            charge = true;
        }
    }

    private static int tics = 0;

    /**
     * Téléchargement à l'avance (09/11/2026) : toutes les 2 s, les paquets à moins de MARGE blocs de chaque joueur de
     * l'Overworld (plus loin s'il va vite : cheval, élytres) sont récupérés en arrière-plan. Quand le joueur arrive au
     * bord d'un nouveau paquet, celui-ci est déjà sur le disque : la génération n'attend jamais.
     */
    private static void prevoir(MinecraftServer s) {
        int e = Terrain.echelle();
        if (!actif) return;
        if (e == V30.echelle) {
            prevoir(s, V30);
            prevoir(s, SOL30);
            prevoir(s, EAU30);
            prevoir(s, FOND);
        } else if (e == V1.echelle) {
            prevoir(s, V1);
        }
    }

    private static void prevoir(MinecraftServer s, Jeu j) {
        int cote = T * j.n;
        for (var joueur : s.getPlayerList().getPlayers()) {
            if (joueur.level().dimension() != net.minecraft.world.level.Level.OVERWORLD) continue;
            double vitesse = joueur.getDeltaMovement().horizontalDistance() * 20.0;         // blocs par seconde
            double m = Math.min(MARGE + vitesse * 120.0, 3.0 * MARGE);                      // 2 min d'avance en plus
            // grille du jeu de données (le fond 1:250 sert aussi au monde 1:30)
            double f = j.bpd / Terrain.BLOCS_PAR_DEGRE;
            int x0 = (int) Math.floor((joueur.getX() - m) * f), x1 = (int) Math.floor((joueur.getX() + m) * f);
            int z0 = (int) Math.floor((joueur.getZ() - m) * f), z1 = (int) Math.floor((joueur.getZ() + m) * f);
            for (int bx = Math.floorDiv(x0, cote); bx <= Math.floorDiv(x1, cote); bx++)
                for (int bz = Math.floorDiv(z0, cote); bz <= Math.floorDiv(z1, cote); bz++)
                    j.prevoir(bx, bz);
        }
    }

    /** Distance (blocs) à laquelle un paquet voisin est téléchargé à l'avance. */
    static final double MARGE = 2000.0;

    /** Prévient une fois les joueurs quand une zone a dû être générée sans le relief fin. */
    @SubscribeEvent
    public static void tic(TickEvent.ServerTickEvent e) {
        if (e.phase != TickEvent.Phase.END) return;
        if (++tics % 40 == 0) {
            MinecraftServer srv = ServerLifecycleHooks.getCurrentServer();
            if (srv != null) {
                reglages();
                prevoir(srv);
            }
        }
        if (!manque || prevenu) return;
        MinecraftServer s = ServerLifecycleHooks.getCurrentServer();
        if (s == null || s.getPlayerList().getPlayerCount() == 0) return;
        prevenu = true;
        s.getPlayerList().broadcastSystemMessage(Component.literal(
                "§6[Domaine Terre]§r Relief détaillé indisponible (pas de connexion ?) : certaines zones sont générées avec "
                        + "le relief simplifié. Il reviendra pour les nouvelles zones dès que la connexion sera rétablie."), false);
    }
}

package fr.domaineaubin.terre.monde;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import fr.domaineaubin.terre.DomaineTerre;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Holder;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.tags.FluidTags;
import net.minecraft.util.Mth;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.MobCategory;
import net.minecraft.world.level.LevelAccessor;
import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.biome.MobSpawnSettings;
import net.minecraftforge.registries.ForgeRegistries;

import javax.imageio.ImageIO;
import java.awt.image.Raster;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Faune de la vraie Terre (décisions de Maxime, 04/11/2026) : chaque animal n'apparaît que dans ses terroirs ET
 * dans les écorégions RESOLVE de son milieu (forêt humide, savane, désert…), ou sur l'eau douce / le rivage pour
 * les animaux d'eau et de côte ; les poissons de mer suivent la température et la profondeur de la mer.
 * Données : /domaine_terre/faune/zones.png et especes.json (outils/faune/generer_faune.py).
 * Les entités absentes du pack (mod non installé) sont ignorées.
 */
public final class FauneTerre {
    private static final int W = 7200, H = 3600;
    private static final String[] TEMPS = {"chaude", "tiede", "temperee", "froide", "gelee"};
    private static final String[] BANDES = {"cote", "plateau", "large", "abysse"};

    /** Étages souterrains, du plus haut au plus profond. */
    public enum Etage { COUCHES_HAUTES, PROFONDEURS, ABIMES, GROTTES_INONDEES, FOSSES }

    /** Une ligne de la table, résolue. */
    public record Entree(String id, EntityType<?> type, MobCategory categorie, long terroirs, boolean tousTerroirs,
                         int biomes, int[][] precis, boolean eau, boolean cote, int temps, int bandes, boolean mer,
                         boolean nuit, Etage etage, MobSpawnSettings.SpawnerData donnees, boolean generationSeule) {
        boolean dansTerroir(int t) {
            return t > 0 && t < 64 && (terroirs & (1L << t)) != 0;
        }
    }

    private static volatile FauneTerre instance;

    public static FauneTerre get() {
        FauneTerre f = instance;
        if (f == null) {
            synchronized (FauneTerre.class) {
                f = instance;
                if (f == null) {
                    f = charger();
                    instance = f;
                }
            }
        }
        return f;
    }

    private final byte[] zones;
    private final int[] biomePrecis;
    private final List<Entree> surface;
    private final List<Entree> souterrain;
    private final Map<Long, List<MobSpawnSettings.SpawnerData>> cache = new ConcurrentHashMap<>();

    private FauneTerre(byte[] zones, int[] biomePrecis, List<Entree> surface, List<Entree> souterrain) {
        this.zones = zones;
        this.biomePrecis = biomePrecis;
        this.surface = surface;
        this.souterrain = souterrain;
    }

    private static FauneTerre charger() {
        long t0 = System.currentTimeMillis();
        byte[] z = new byte[W * H];
        int[] ligne = new int[W];
        try (InputStream in = FauneTerre.class.getResourceAsStream("/domaine_terre/faune/zones.png")) {
            if (in == null) throw new IllegalStateException("zones.png absent");
            Raster r = ImageIO.read(in).getRaster();
            for (int y = 0; y < H; y++) {
                r.getSamples(0, y, W, 1, 0, ligne);
                for (int x = 0; x < W; x++) z[y * W + x] = (byte) ligne[x];
            }
        } catch (Exception e) {
            DomaineTerre.LOGGER.error("Faune : carte des zones illisible, faune du jeu de base", e);
            return new FauneTerre(null, new int[0], List.of(), List.of());
        }
        JsonObject racine;
        try (InputStream in = FauneTerre.class.getResourceAsStream("/domaine_terre/faune/especes.json")) {
            racine = JsonParser.parseReader(new InputStreamReader(in, StandardCharsets.UTF_8)).getAsJsonObject();
        } catch (Exception e) {
            DomaineTerre.LOGGER.error("Faune : table des espèces illisible, faune du jeu de base", e);
            return new FauneTerre(null, new int[0], List.of(), List.of());
        }
        JsonArray pr = racine.getAsJsonArray("precises");
        int[] bp = new int[pr.size()];
        for (int i = 0; i < bp.length; i++) bp[i] = pr.get(i).getAsJsonObject().get("biome").getAsInt();
        List<Entree> surface = new ArrayList<>(), souterrain = new ArrayList<>();
        int absents = 0;
        for (JsonElement el : racine.getAsJsonArray("especes")) {
            JsonObject o = el.getAsJsonObject();
            ResourceLocation rl = new ResourceLocation(o.get("entite").getAsString());
            // registre du jeu (celui qui sert à enregistrer les entités dans les chunks) et vérification du nom : le
            // registre « par défaut » rend un cochon pour un nom inconnu, et une entité dont le type n'y est pas sous son
            // nom est enregistrée comme cochon (07/11/2026 : cochons partout à la place d'Untamed Wilds)
            EntityType<?> type = net.minecraft.core.registries.BuiltInRegistries.ENTITY_TYPE.getOptional(rl).orElse(null);
            if (type == null || !rl.equals(EntityType.getKey(type))) {
                if (absents++ < 40) {
                    EntityType<?> forge = ForgeRegistries.ENTITY_TYPES.getValue(rl);
                    DomaineTerre.LOGGER.warn("Faune : {} introuvable sous son nom (registre du jeu : {}, Forge : {})", rl,
                            type == null ? "absent" : EntityType.getKey(type),
                            forge == null ? "absent" : EntityType.getKey(forge));
                }
                continue;
            }
            long ts = 0;
            int nb = 0;
            for (JsonElement t : o.getAsJsonArray("terroirs")) {
                ts |= 1L << t.getAsInt();
                nb++;
            }
            int bio = 0;
            for (JsonElement b : o.getAsJsonArray("biomes")) bio |= 1 << b.getAsInt();
            int[][] precis = null;
            JsonObject p = o.getAsJsonObject("precis");
            if (p != null && p.size() > 0) {
                precis = new int[64][];
                for (Map.Entry<String, JsonElement> e : p.entrySet()) {
                    JsonArray a = e.getValue().getAsJsonArray();
                    int[] k = new int[a.size()];
                    for (int i = 0; i < k.length; i++) k[i] = a.get(i).getAsInt();
                    precis[Integer.parseInt(e.getKey())] = k;
                }
            }
            int temps = 0, bandes = 0;
            boolean mer = o.has("mer") && o.get("mer").isJsonObject();
            if (mer) {
                JsonObject m = o.getAsJsonObject("mer");
                for (JsonElement t : m.getAsJsonArray("temperatures")) temps |= 1 << indice(TEMPS, t.getAsString());
                for (JsonElement b : m.getAsJsonArray("bandes")) bandes |= 1 << indice(BANDES, b.getAsString());
            }
            Etage etage = null;
            if (o.has("etage") && !o.get("etage").isJsonNull()) {
                etage = Etage.valueOf(o.get("etage").getAsString().toUpperCase(java.util.Locale.ROOT));
            }
            int min = Math.max(1, o.get("min").getAsInt()), max = Math.max(min, o.get("max").getAsInt());
            MobSpawnSettings.SpawnerData d = new MobSpawnSettings.SpawnerData(type, Math.max(1, o.get("poids").getAsInt()), min, max);
            // Untamed Wilds range ses bêtes en MISC (le jeu ne les fait jamais naître lui-même) : la table les fait naître
            // avec les animaux (CREATURE), mais seulement à la génération des chunks (07/11/2026). Les apparitions
            // naturelles ne comptent pas les MISC dans le plafond d'animaux : elles en feraient naître sans fin.
            MobCategory cat = type.getCategory();
            boolean generationSeule = cat == MobCategory.MISC;
            if (generationSeule) cat = MobCategory.CREATURE;
            Entree en = new Entree(o.get("id").getAsString(), type, cat, ts, nb >= 29, bio, precis,
                    o.get("eau").getAsBoolean(), o.get("cote").getAsBoolean(), temps, bandes, mer,
                    o.get("nuit").getAsBoolean(), etage, d, generationSeule);
            (etage == null ? surface : souterrain).add(en);
        }
        DomaineTerre.LOGGER.info("Faune de la Terre : {} espèces en surface, {} sous terre ({} absentes du pack), {} ms",
                surface.size(), souterrain.size(), absents, System.currentTimeMillis() - t0);
        return new FauneTerre(z, bp, surface, souterrain);
    }

    private static int indice(String[] t, String s) {
        for (int i = 0; i < t.length; i++) if (t[i].equals(s)) return i;
        return 0;
    }

    public boolean active() {
        return zones != null;
    }

    public List<Entree> souterrain() {
        return souterrain;
    }

    private int pixel(int x, int z) {
        double lon = Terrain.lon(x + 0.5), lat = Terrain.lat(z + 0.5);
        int px = Math.floorMod(Mth.floor((lon + 180.0) / 0.05), W);
        int py = Mth.clamp(Mth.floor((90.0 - lat) / 0.05), 0, H - 1);
        return py * W + px;
    }

    /**
     * Liste des apparitions possibles en surface pour cette catégorie à cette position.
     * eauProche / coteProche : tests faits par l'appelant (null = ne pas les regarder, génération des chunks).
     */
    public List<MobSpawnSettings.SpawnerData> liste(LevelAccessor niveau, MobCategory cat, BlockPos pos, Holder<Biome> biome,
                                                    boolean eauProche, boolean coteProche, boolean nuit, boolean generation) {
        int pix = pixel(pos.getX(), pos.getZ());
        String chemin = biome.unwrapKey().map(k -> k.location().getPath()).orElse("");
        int temp = -1, bande = -1;
        if (biome.unwrapKey().map(k -> k.location().getNamespace().equals(DomaineTerre.MOD_ID)).orElse(false)
                && chemin.startsWith("mer/")) {
            String[] p = chemin.substring(4).split("_");
            if (p.length == 2) {
                temp = indice(TEMPS, p[0]);
                bande = indice(BANDES, p[1]);
            }
        }
        long cle = ((long) pix << 20) | ((long) cat.ordinal() << 12) | ((temp + 1L) << 8) | ((bande + 1L) << 4)
                | (eauProche ? 8 : 0) | (coteProche ? 4 : 0) | (nuit ? 2 : 0) | (generation ? 1 : 0);
        List<MobSpawnSettings.SpawnerData> l = cache.get(cle);
        if (l != null) return l;
        l = calculer(pix, cat, temp, bande, eauProche, coteProche, nuit, generation);
        if (cache.size() > 200_000) cache.clear();
        cache.put(cle, l);
        return l;
    }

    private List<MobSpawnSettings.SpawnerData> calculer(int pix, MobCategory cat, int temp, int bande, boolean eauProche,
                                                        boolean coteProche, boolean nuit, boolean generation) {
        int z = zones[pix] & 0xFF;
        boolean merBiome = temp >= 0;
        int terroir;
        int grand = 0, precis = -1;
        if (z >= 128) {
            terroir = z - 128;                         // mer : terroir de la terre la plus proche (0 = haute mer)
        } else {
            double lon = -180.0 + (pix % W + 0.5) * 0.05, lat = 90.0 - (pix / W + 0.5) * 0.05;
            terroir = Terrain.get().carte().terroir(lon, lat);
            if (z >= 1 && z <= 14) grand = z;
            else if (z >= 16 && z - 16 < biomePrecis.length) {
                precis = z - 16;
                grand = biomePrecis[precis];
            }
        }
        List<MobSpawnSettings.SpawnerData> out = new ArrayList<>();
        for (Entree e : surface) {
            if (e.categorie() != cat) continue;
            if (e.generationSeule() && !generation) continue;
            if (e.nuit() && !nuit) continue;
            if (merBiome) {
                if (!e.mer() || (e.temps() & (1 << temp)) == 0 || (e.bandes() & (1 << bande)) == 0) continue;
                if (!e.tousTerroirs() && !e.dansTerroir(terroir)) continue;
                out.add(e.donnees());
                continue;
            }
            if (!e.dansTerroir(terroir)) continue;
            if (e.precis() != null && e.precis()[terroir] != null && !contient(e.precis()[terroir], precis)) continue;
            boolean terre = (e.biomes() & (1 << grand)) != 0 && grand > 0;
            // à la génération, eauProche / coteProche disent si le chunk a un cours d'eau, un lac ou la côte (07/11/2026 :
            // sinon crocodiles, hippopotames… ne naissaient jamais, les apparitions naturelles étant trop rares)
            boolean eau = e.eau() && eauProche;
            boolean cote = e.cote() && coteProche;
            if (terre || eau || cote) out.add(e.donnees());
        }
        return List.copyOf(out);
    }

    private static boolean contient(int[] t, int v) {
        for (int x : t) if (x == v) return true;
        return false;
    }

    /** Eau à moins de 3 blocs (même niveau ou juste dessous). */
    public static boolean eauProche(LevelAccessor niveau, BlockPos pos) {
        BlockPos.MutableBlockPos m = new BlockPos.MutableBlockPos();
        for (int dy = -1; dy <= 0; dy++) {
            for (int dx = -3; dx <= 3; dx++) {
                for (int dz = -3; dz <= 3; dz++) {
                    m.set(pos.getX() + dx, pos.getY() + dy, pos.getZ() + dz);
                    if (niveau.getFluidState(m).is(FluidTags.WATER)) return true;
                }
            }
        }
        return false;
    }

    /**
     * Génération d'un chunk : un cours d'eau (lit) ou un lac du mod passe-t-il dans le chunk ? Grille de 4 x 4 points
     * (tous les 4 blocs) : un fleuve étroit (le Nil fait quelques blocs de large en 1:250) passait entre 5 points.
     */
    public static boolean eauDansChunk(int x0, int z0) {
        Terrain t = Terrain.get();
        for (int dx = 1; dx < 16; dx += 4) {
            for (int dz = 1; dz < 16; dz += 4) {
                int x = x0 + dx, z = z0 + dz;
                if (t.eauLit(x, z) != Terrain.SANS_LAC || t.eauDeLac(x, z)) return true;
            }
        }
        return false;
    }

    /** Génération d'un chunk : le trait de côte passe-t-il près du chunk (environ 15 blocs du centre) ? */
    public static boolean coteDansChunk(int x0, int z0) {
        return Math.abs(Terrain.get().distanceCote(x0 + 8, z0 + 8)) < 2.0;
    }

    /** Rivage de la vraie mer (moins d'environ 5 blocs du trait de côte). */
    public static boolean coteProche(BlockPos pos) {
        return Math.abs(Terrain.get().distanceCote(pos.getX(), pos.getZ())) < 0.7;
    }
}

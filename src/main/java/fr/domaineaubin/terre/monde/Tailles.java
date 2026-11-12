package fr.domaineaubin.terre.monde;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import fr.domaineaubin.terre.DomaineTerre;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.entity.EntityType;
import net.minecraftforge.event.entity.EntityEvent;
import net.minecraftforge.event.server.ServerStartedEvent;
import net.minecraftforge.eventbus.api.EventPriority;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.fml.loading.FMLPaths;
import net.minecraftforge.registries.ForgeRegistries;

import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.Reader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.Map;

/**
 * Taille des créatures (08/11/2026) : facteur par espèce, pour la taille réelle (1 bloc = 1 m), insectes réduits mais
 * visibles. Table dans le mod (domaine_terre/faune/tailles.json), remplaçable ligne à ligne par
 * config/domaine_terre_tailles.json. Côté serveur : la boîte de collision (EntityEvent.Size) ; côté client :
 * le modèle affiché (TaillesRendu). Untamed Wilds règle ses espèces lui-même (« scale », outils/generer_placement.py).
 * Au démarrage d'un serveur, la taille d'origine de toutes les créatures est écrite dans domaine_tailles.csv.
 */
@Mod.EventBusSubscriber(modid = DomaineTerre.MOD_ID, bus = Mod.EventBusSubscriber.Bus.FORGE)
public final class Tailles {
    private static volatile Map<EntityType<?>, Float> facteurs;

    private Tailles() {
    }

    public static float facteur(EntityType<?> type) {
        Map<EntityType<?>, Float> f = facteurs;
        if (f == null) f = charger();
        Float v = f.get(type);
        return v == null ? 1.0f : v;
    }

    private static synchronized Map<EntityType<?>, Float> charger() {
        if (facteurs != null) return facteurs;
        Map<String, Float> brut = new HashMap<>();
        try (InputStream in = Tailles.class.getResourceAsStream("/domaine_terre/faune/tailles.json")) {
            if (in != null) lire(new InputStreamReader(in, StandardCharsets.UTF_8), brut);
        } catch (Exception e) {
            DomaineTerre.LOGGER.error("Tailles : table du mod illisible", e);
        }
        Path cfg = FMLPaths.CONFIGDIR.get().resolve("domaine_terre_tailles.json");
        if (Files.exists(cfg)) {
            try (Reader r = Files.newBufferedReader(cfg, StandardCharsets.UTF_8)) {
                lire(r, brut);
            } catch (Exception e) {
                DomaineTerre.LOGGER.error("Tailles : {} illisible", cfg, e);
            }
        }
        Map<EntityType<?>, Float> m = new HashMap<>();
        for (var e : brut.entrySet()) {
            ResourceLocation rl = ResourceLocation.tryParse(e.getKey());
            if (rl == null || !ForgeRegistries.ENTITY_TYPES.containsKey(rl)) continue;
            float f = e.getValue();
            if (f > 0.01f && Math.abs(f - 1.0f) > 0.01f) m.put(ForgeRegistries.ENTITY_TYPES.getValue(rl), f);
        }
        DomaineTerre.LOGGER.info("Tailles : {} créatures redimensionnées", m.size());
        facteurs = m;
        return m;
    }

    private static void lire(Reader r, Map<String, Float> dans) {
        JsonObject o = JsonParser.parseReader(r).getAsJsonObject();
        JsonObject t = o.has("facteurs") ? o.getAsJsonObject("facteurs") : o;
        for (var e : t.entrySet()) {
            if (e.getValue().isJsonPrimitive() && e.getValue().getAsJsonPrimitive().isNumber()) {
                dans.put(e.getKey(), e.getValue().getAsFloat());
            }
        }
    }

    @SubscribeEvent(priority = EventPriority.LOW)
    public static void taille(EntityEvent.Size event) {
        float t = facteur(event.getEntity().getType());
        float s = echelleUW(event.getEntity());
        // 12/11/2026 (test en jeu : requin marteau et requin-baleine dans des cubes de 4 à 6 blocs) : une boîte de
        // collision est carrée vue de dessus ; pour une bête longue et plate (poissons, requins), l'échelle du modèle
        // agrandit la boîte moins vite (racine carrée) et la hauteur moitié moins que la largeur
        float l = t, h = t;
        if (s != 1.0f) {
            if (aquatique(event.getEntity())) {
                l *= (float) Math.sqrt(s);
                h *= (float) Math.sqrt(s) * 0.6f;
            } else {
                l *= s;
                h *= s;
            }
        }
        if (Math.abs(l - 1.0f) > 0.001f || Math.abs(h - 1.0f) > 0.001f)
            event.setNewSize(event.getNewSize().scale(l, h), true);
    }

    /*
     * 12/11/2026 (test en jeu : requins, poissons-scies d'Untamed Wilds, boîte bien plus petite ou plus grande que la
     * bête) : Untamed Wilds agrandit le modèle de chaque espèce (« scale » du datapack × taille de l'individu) mais pas
     * la boîte de collision, restée celle du type. Elle suit maintenant l'échelle du modèle, relue par réflexion.
     */
    private static final Map<Class<?>, java.lang.reflect.Method[]> UW = new java.util.concurrent.ConcurrentHashMap<>();
    private static final java.lang.reflect.Method[] AUCUNE = new java.lang.reflect.Method[0];

    static float echelleUW(net.minecraft.world.entity.Entity e) {
        java.lang.reflect.Method[] m = UW.computeIfAbsent(e.getClass(), c -> {
            if (!c.getName().startsWith("untamedwilds.")) return AUCUNE;
            try {
                return new java.lang.reflect.Method[]{c.getMethod("getModelScale"), c.getMethod("getMobSize")};
            } catch (NoSuchMethodException ex) {
                return AUCUNE;
            }
        });
        if (m.length == 0) return 1.0f;
        try {
            float s = (Float) m[0].invoke(e) * (Float) m[1].invoke(e);
            return s > 0.05f && s < 20.0f ? s : 1.0f;
        } catch (Throwable ex) {
            return 1.0f;  // pendant la construction de l'entité, avant ses données
        }
    }

    private static boolean aquatique(net.minecraft.world.entity.Entity e) {
        for (Class<?> c = e.getClass(); c != null; c = c.getSuperclass()) {
            if (c.getName().equals("untamedwilds.entity.ComplexMobAquatic")) return true;
        }
        return false;
    }

    /** L'espèce et la taille d'une bête d'Untamed Wilds arrivent après sa création (et du serveur au client). */
    @SubscribeEvent
    public static void suivreUW(net.minecraftforge.event.entity.living.LivingEvent.LivingTickEvent event) {
        net.minecraft.world.entity.LivingEntity e = event.getEntity();
        if ((e.tickCount % 20) != 1 || UW.get(e.getClass()) == AUCUNE) return;
        float s = echelleUW(e);
        if (aquatique(e)) s = (float) Math.sqrt(s);
        float voulue = e.getType().getWidth() * s * facteur(e.getType());
        if (Math.abs(e.getBbWidth() - voulue) > 0.02f) e.refreshDimensions();
    }

    /** Tailles d'origine (boîte de collision) de toutes les créatures, pour régler la table. */
    @SubscribeEvent
    public static void export(ServerStartedEvent event) {
        StringBuilder sb = new StringBuilder("id;categorie;largeur;hauteur;facteur\n");
        for (var e : ForgeRegistries.ENTITY_TYPES.getEntries()) {
            EntityType<?> t = e.getValue();
            sb.append(e.getKey().location()).append(';').append(t.getCategory().getName()).append(';')
                    .append(t.getWidth()).append(';').append(t.getHeight()).append(';').append(facteur(t)).append('\n');
        }
        try {
            Files.writeString(FMLPaths.GAMEDIR.get().resolve("domaine_tailles.csv"), sb.toString(), StandardCharsets.UTF_8);
        } catch (Exception ex) {
            DomaineTerre.LOGGER.warn("Tailles : export impossible", ex);
        }
    }
}

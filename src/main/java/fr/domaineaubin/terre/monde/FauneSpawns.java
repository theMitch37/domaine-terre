package fr.domaineaubin.terre.monde;

import fr.domaineaubin.terre.DomaineTerre;
import fr.domaineaubin.terre.api.Lieu;
import fr.domaineaubin.terre.api.LieuxTerre;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Holder;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.tags.FluidTags;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.entity.MobCategory;
import net.minecraft.world.entity.ai.attributes.AttributeInstance;
import net.minecraft.world.entity.ai.attributes.AttributeModifier;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.entity.monster.Enemy;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.LevelAccessor;
import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.biome.MobSpawnSettings;
import net.minecraftforge.event.entity.living.MobSpawnEvent;
import net.minecraftforge.event.entity.player.PlayerSpawnPhantomsEvent;
import net.minecraftforge.event.level.LevelEvent;
import net.minecraftforge.eventbus.api.Event;
import net.minecraftforge.eventbus.api.EventPriority;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.UUID;

/**
 * Apparitions dans un monde Terre (04/11/2026) :
 * - animaux, oiseaux, insectes et poissons : la table de {@link FauneTerre} remplace les listes des biomes
 *   (celles du jeu de base et celles ajoutées par les mods) ;
 * - monstres : seulement sous le sol d'origine, par étages (couches hautes, profondeurs, abîmes), plus forts en
 *   descendant ; sorcières en surface dans les marais ; rien dans les lieux uniques (grottes célèbres) ;
 * - phantoms : seulement en Roumanie et dans les Carpates.
 * Untamed Wilds garde son propre système (features par terroir).
 */
@Mod.EventBusSubscriber(modid = DomaineTerre.MOD_ID, bus = Mod.EventBusSubscriber.Bus.FORGE)
public final class FauneSpawns {
    private static final Set<MobCategory> GEREES = Set.of(MobCategory.CREATURE, MobCategory.AMBIENT,
            MobCategory.WATER_CREATURE, MobCategory.WATER_AMBIENT);
    /** Profondeur sous le sol d'origine où commencent les profondeurs ; y où commencent les abîmes. */
    private static final int PROFONDEURS = 40, ABIMES = -40;
    private static final Set<String> HAUTS = Set.of("zombie", "zombie_villager", "husk", "skeleton", "stray", "spider", "slime");
    private static final Set<String> MOYENS = Set.of("creeper", "enderman", "witch", "cave_spider");
    private static final UUID VIE = UUID.fromString("6f0d1c1e-3a52-4f8e-9d0a-1b2c3d4e5f61");
    private static final UUID ATTAQUE = UUID.fromString("6f0d1c1e-3a52-4f8e-9d0a-1b2c3d4e5f62");
    private static final UUID ARMURE = UUID.fromString("6f0d1c1e-3a52-4f8e-9d0a-1b2c3d4e5f63");

    private static final java.util.concurrent.atomic.AtomicInteger JOURNAL = new java.util.concurrent.atomic.AtomicInteger();

    private FauneSpawns() {
    }

    /** Monde Terre (source de biomes du mod) et Overworld. */
    static boolean terre(LevelAccessor niveau) {
        ServerLevel s = niveau instanceof ServerLevel sl ? sl
                : niveau instanceof net.minecraft.world.level.WorldGenLevel w ? w.getLevel() : null;
        return s != null && s.dimension() == Level.OVERWORLD
                && s.getChunkSource().getGenerator().getBiomeSource() instanceof TerroirBiomeSource;
    }

    @SubscribeEvent(priority = EventPriority.LOWEST)
    public static void apparitions(LevelEvent.PotentialSpawns event) {
        LevelAccessor niveau = event.getLevel();
        if (!terre(niveau)) return;
        FauneTerre faune = FauneTerre.get();
        if (!faune.active()) return;
        MobCategory cat = event.getMobCategory();
        BlockPos pos = event.getPos();
        if (cat == MobCategory.MONSTER) {
            monstres(event, niveau, pos, faune);
            return;
        }
        if (!GEREES.contains(cat)) return;
        Holder<Biome> biome = niveau.getBiome(pos);
        boolean nuit = niveau instanceof Level l && !l.isDay();
        List<MobSpawnSettings.SpawnerData> l = faune.liste(niveau, cat, pos, biome,
                FauneTerre.eauProche(niveau, pos), FauneTerre.coteProche(pos), nuit, false);
        remplacer(event, l);
    }

    private static void remplacer(LevelEvent.PotentialSpawns event, List<MobSpawnSettings.SpawnerData> l) {
        for (MobSpawnSettings.SpawnerData d : new ArrayList<>(event.getSpawnerDataList())) event.removeSpawnerData(d);
        for (MobSpawnSettings.SpawnerData d : l) event.addSpawnerData(d);
    }

    private static int etage(int x, int y, int z) {
        int sol = (int) Math.floor(Terrain.get().hauteur(x, z));
        if (y >= sol - 2) return -1;
        if (sol - y < PROFONDEURS) return 0;
        return y > ABIMES ? 1 : 2;
    }

    private static boolean dansLieu(int x, int z) {
        for (Lieu l : LieuxTerre.liste()) {
            if (l.concerne(x, z)) return true;   // toute l'emprise : les galeries (Padirac) dépassent le biome de surface
        }
        return false;
    }

    private static void monstres(LevelEvent.PotentialSpawns event, LevelAccessor niveau, BlockPos pos, FauneTerre faune) {
        int e = etage(pos.getX(), pos.getY(), pos.getZ());
        List<MobSpawnSettings.SpawnerData> garder = new ArrayList<>();
        if (e < 0) {
            // surface : seulement les sorcières des marais
            String chemin = niveau.getBiome(pos).unwrapKey().map(k -> k.location().getPath()).orElse("");
            if (chemin.endsWith("swamp")) {
                for (MobSpawnSettings.SpawnerData d : event.getSpawnerDataList()) {
                    if (d.type == EntityType.WITCH) garder.add(d);
                }
            }
            remplacer(event, garder);
            return;
        }
        if (dansLieu(pos.getX(), pos.getZ())) {
            remplacer(event, garder);                      // grottes célèbres et lieux uniques : pas de monstres
            return;
        }
        boolean dansEau = niveau.getFluidState(pos).is(FluidTags.WATER);
        for (MobSpawnSettings.SpawnerData d : event.getSpawnerDataList()) {
            var cle = EntityType.getKey(d.type);
            if (!cle.getNamespace().equals("minecraft")) continue;     // les monstres des mods passent par la table
            String n = cle.getPath();
            if (n.equals("drowned")) {
                if (dansEau) garder.add(d);                // noyés : grottes inondées seulement
            } else if (HAUTS.contains(n) || (e >= 1 && MOYENS.contains(n)) || e >= 2) {
                garder.add(d);
            }
        }
        for (FauneTerre.Entree en : faune.souterrain()) {
            boolean ok = switch (en.etage()) {
                case COUCHES_HAUTES -> true;
                case PROFONDEURS -> e >= 1;
                case ABIMES -> e >= 2;
                case GROTTES_INONDEES -> e >= 1 && dansEau;
                case FOSSES -> dansEau && (e >= 1 || pos.getY() < 0);
            };
            if (ok) garder.add(en.donnees());
        }
        remplacer(event, garder);
    }

    /**
     * Règles d'apparition des mods (08/11/2026). Untamed Wilds n'en a aucune et passe toujours ; Alex's Mobs, Naturalist…
     * refusent souvent sur la Terre (crocodile : jamais au-dessus de y 67, gazelle, jerboa… : tirages, lumière, blocs
     * précis). Résultat : dromadaires et varans partout, crocodiles du Nil presque absents. Pour les bêtes de la table,
     * c'est la table qui décide où et combien : on ne garde que la vérification physique du jeu (sol porteur, place libre,
     * eau pour les bêtes d'eau).
     */
    @SubscribeEvent
    public static void placement(MobSpawnEvent.SpawnPlacementCheck event) {
        if (event.getDefaultResult() || !terre(event.getLevel())) return;
        EntityType<?> type = event.getEntityType();
        if (type.getCategory() == MobCategory.MONSTER || !FauneTerre.get().dansLaTable(type)) return;
        if (event.getLevel() instanceof net.minecraft.world.level.LevelReader lecture
                && net.minecraft.world.level.NaturalSpawner.isSpawnPositionOk(
                        net.minecraft.world.entity.SpawnPlacements.getPlacementType(type), lecture, event.getPos(), type)) {
            event.setResult(Event.Result.ALLOW);
        }
    }

    /** Monstres plus forts en descendant : +50 % de vie, +2 dégâts, +2 armure par étage sous les couches hautes. */
    @SubscribeEvent
    public static void force(MobSpawnEvent.FinalizeSpawn event) {
        Mob m = event.getEntity();
        if (!(m instanceof Enemy) || !terre(event.getLevel())) return;
        int e = etage(m.getBlockX(), m.getBlockY(), m.getBlockZ());
        if (e < 1) return;
        ajouter(m.getAttribute(Attributes.MAX_HEALTH), VIE, "vie", 0.5 * e, AttributeModifier.Operation.MULTIPLY_TOTAL);
        ajouter(m.getAttribute(Attributes.ATTACK_DAMAGE), ATTAQUE, "attaque", 2.0 * e, AttributeModifier.Operation.ADDITION);
        ajouter(m.getAttribute(Attributes.ARMOR), ARMURE, "armure", 2.0 * e, AttributeModifier.Operation.ADDITION);
        m.setHealth(m.getMaxHealth());
    }

    private static void ajouter(AttributeInstance a, UUID id, String nom, double v, AttributeModifier.Operation op) {
        if (a != null && a.getModifier(id) == null) {
            a.addPermanentModifier(new AttributeModifier(id, "domaine_terre:profondeur_" + nom, v, op));
        }
    }

    /** Phantoms endémiques : seulement en Roumanie et en Moldavie (Transylvanie, Carpates). */
    @SubscribeEvent
    public static void phantoms(PlayerSpawnPhantomsEvent event) {
        if (!terre(event.getEntity().level())) return;
        double lon = Terrain.lon(event.getEntity().getX()), lat = Terrain.lat(event.getEntity().getZ());
        boolean roumanie = lat > 43.6 && lat < 48.3 && lon > 20.2 && lon < 29.7;
        if (!roumanie) event.setResult(Event.Result.DENY);
    }

    /** Génération des chunks (appelé par le mixin) : animaux de la table, ceux de l'eau et de la côte si le chunk en a. */
    public static net.minecraft.util.random.WeightedRandomList<MobSpawnSettings.SpawnerData> generation(
            net.minecraft.world.level.ServerLevelAccessor niveau, Holder<Biome> biome, net.minecraft.world.level.ChunkPos chunk,
            MobCategory cat, net.minecraft.util.random.WeightedRandomList<MobSpawnSettings.SpawnerData> base) {
        if (!GEREES.contains(cat) || !terre(niveau)) return base;
        FauneTerre faune = FauneTerre.get();
        if (!faune.active()) return base;
        BlockPos centre = new BlockPos(chunk.getMiddleBlockX(), 64, chunk.getMiddleBlockZ());
        int x0 = chunk.getMinBlockX(), z0 = chunk.getMinBlockZ();
        List<MobSpawnSettings.SpawnerData> l = faune.liste(niveau, cat, centre, biome,
                FauneTerre.eauDansChunk(x0, z0), FauneTerre.coteDansChunk(x0, z0), false, true);
        if (JOURNAL.getAndIncrement() < 3) {
            DomaineTerre.LOGGER.info("Faune (génération) {} {} : biome {}, {} espèces {}", chunk, cat,
                    biome.unwrapKey().map(k -> k.location().toString()).orElse("?"), l.size(),
                    l.stream().map(d -> EntityType.getKey(d.type).getPath()).toList());
        }
        return net.minecraft.util.random.WeightedRandomList.create(l);
    }
}

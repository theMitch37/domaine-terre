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
import net.minecraft.world.entity.MobSpawnType;
import net.minecraft.world.entity.ai.attributes.AttributeInstance;
import net.minecraft.world.entity.ai.attributes.AttributeModifier;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.entity.monster.Enemy;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.LevelAccessor;
import net.minecraft.world.level.ServerLevelAccessor;
import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.biome.MobSpawnSettings;
import net.minecraftforge.event.entity.EntityJoinLevelEvent;
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
        remplacer(event, faune.filtrer(l, pos, biome, niveau.getRandom()));
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
            // surface : seulement les sorcières des marais, et les monstres de la table autorisés en surface
            // (Rafalleur des grands ergs, 09/11/2026)
            Holder<Biome> biome = niveau.getBiome(pos);
            String chemin = biome.unwrapKey().map(k -> k.location().getPath()).orElse("");
            if (chemin.endsWith("swamp")) {
                for (MobSpawnSettings.SpawnerData d : event.getSpawnerDataList()) {
                    if (d.type == EntityType.WITCH) garder.add(d);
                }
            }
            if (!dansLieu(pos.getX(), pos.getZ())) {
                boolean nuit = niveau instanceof Level l && !l.isDay();
                garder.addAll(faune.monstresSurface(niveau, pos, biome, nuit, niveau.getRandom()));
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
     * Seules nos règles décident (10/11/2026, décision de Maxime : « que les spawns ne dépendent que de nos choix »).
     * Pour toute bête de la table (surface et étages, tous mods confondus), les règles propres des mods sont coupées :
     * prédicat de placement (crocodile d'Alex's Mobs : jamais au-dessus de y 67 ; sol précis, lumière, herbe…) et
     * checkSpawnRules / checkSpawnObstruction (tirages d'Alex's Mobs, règles de Naturalist…). À leur place,
     * {@link #nosRegles}. Ne touche que les apparitions naturelles et celles de la génération (pas les œufs, les
     * générateurs, l'élevage). Les bêtes hors table (monstres du jeu de base des étages) gardent les règles du jeu.
     */
    @SubscribeEvent(priority = EventPriority.HIGH)
    public static void placement(MobSpawnEvent.SpawnPlacementCheck event) {
        if (!naturelle(event.getSpawnType()) || !terre(event.getLevel())) return;
        if (FauneTerre.get().entree(event.getEntityType()) != null) event.setResult(Event.Result.ALLOW);
    }

    /** Priorité haute : le refus des grottes célèbres (addon Lieux, priorité normale) passe après et l'emporte. */
    @SubscribeEvent(priority = EventPriority.HIGH)
    public static void position(MobSpawnEvent.PositionCheck event) {
        if (!naturelle(event.getSpawnType()) || !terre(event.getLevel())) return;
        FauneTerre.Entree e = FauneTerre.get().entree(event.getEntity().getType());
        if (e == null) return;
        event.setResult(nosRegles(e, event.getEntity(), event.getLevel()) ? Event.Result.ALLOW : Event.Result.DENY);
    }

    private static boolean naturelle(MobSpawnType t) {
        return t == MobSpawnType.NATURAL || t == MobSpawnType.CHUNK_GENERATION;
    }

    /**
     * Nos règles, et seulement elles (le où et le combien sont déjà décidés par les listes de la table) :
     * - physique : la bête tient à cette place (pas d'autre entité, pas de bloc) ; une bête de terre pas dans un liquide ;
     * - surface : une bête de surface naît au-dessus du sol d'origine, sauf `sous_terre` (chauve-souris) ou un biome de
     *   grotte imposé (Papilloneur, grottes luxuriantes) ; les poissons ne sont pas concernés ;
     * - monstres de la table : dans le noir (comme ceux du jeu de base), sauf `monstre_surface` (Rafalleur) ;
     * - `noir` : dans le noir aussi (chauve-souris) ; `sol` : bloc dessous (« sable ») ; `pluie` : par pluie ou orage.
     */
    static boolean nosRegles(FauneTerre.Entree e, Mob m, ServerLevelAccessor n) {
        BlockPos pos = m.blockPosition();
        if (!n.isUnobstructed(m) || !n.noCollision(m)) return false;
        boolean eau = net.minecraft.world.entity.SpawnPlacements.getPlacementType(m.getType())
                == net.minecraft.world.entity.SpawnPlacements.Type.IN_WATER;
        if (!eau && !n.getFluidState(pos).isEmpty()) return false;
        if (!eau && e.etage() == null && !e.sousTerre() && e.biomeJeu() == null
                && etage(pos.getX(), pos.getY(), pos.getZ()) >= 0) return false;
        boolean monstre = e.categorie() == MobCategory.MONSTER;
        if (((monstre && !e.monstreSurface()) || e.noir())
                && !net.minecraft.world.entity.monster.Monster.isDarkEnoughToSpawn(n, pos, n.getRandom())) return false;
        if (eau && !profondeurOk(m, n)) return false;
        if ("sable".equals(e.sol()) && !n.getBlockState(pos.below()).is(net.minecraft.tags.BlockTags.SAND)) return false;
        return !e.pluie() || n.getLevelData().isRaining();
    }

    /**
     * Profondeur d'eau à la place de la bête (11/11/2026, test en jeu : grand requin dans 2 blocs d'eau d'un estuaire,
     * baleine près de la côte) : au moins 2 blocs, et une fois et demie la hauteur de la bête (un grand requin d'Untamed
     * Wilds : 4 blocs ; une baleine bleue : une quinzaine, la vraie mer du large).
     */
    static boolean profondeurOk(Mob m, LevelAccessor n) {
        int requis = Math.max(2, (int) Math.ceil(m.getBbHeight() * 1.5));
        BlockPos.MutableBlockPos p = m.blockPosition().mutable();
        int y0 = p.getY();
        int bas = y0, haut = y0;
        while (bas > n.getMinBuildHeight() && y0 - bas < 64 && n.getFluidState(p.setY(bas - 1)).is(FluidTags.WATER)) bas--;
        while (haut - y0 < 64 && n.getFluidState(p.setY(haut + 1)).is(FluidTags.WATER)) haut++;
        if (!n.getFluidState(p.setY(y0)).is(FluidTags.WATER)) return false;
        return haut - bas + 1 >= requis;
    }

    /** Marque des bêtes déjà passées par nos règles (ou nées d'un joueur : œuf, commande, élevage). */
    private static final String VERIFIEE = "domaine_terre_verifiee";

    /**
     * Bêtes nées par un autre système que les listes (11/11/2026, test en jeu : hippopotames d'Untamed Wilds en plein
     * Sahara, à 800 blocs du Nil ; grand requin dans un estuaire) : Untamed Wilds fait naître les siennes par ses propres
     * features, qui ne connaissent que les biomes. Quand une bête de la table arrive dans le monde depuis la génération ou
     * le disque pour la première fois, nos règles décident (FauneTerre.permis, profondeur d'eau) ; refusée, elle n'est
     * pas ajoutée. Les bêtes nées d'un joueur (œufs, commandes, élevage, /domaine zoo) arrivent « fraîches » : marquées,
     * jamais retirées ; les bêtes nommées ou apprivoisées non plus.
     */
    @SubscribeEvent(priority = EventPriority.HIGH)
    public static void arrivee(EntityJoinLevelEvent event) {
        if (!(event.getEntity() instanceof Mob m) || !(event.getLevel() instanceof ServerLevel n)) return;
        FauneTerre f = FauneTerre.get();
        if (!f.active() || !f.dansLaTable(m.getType())) return;
        net.minecraft.nbt.CompoundTag d = m.getPersistentData();
        if (d.getBoolean(VERIFIEE)) return;
        d.putBoolean(VERIFIEE, true);
        if (!event.loadedFromDisk() || !terre(n)) return;
        if (m.hasCustomName() || m.isLeashed()
                || (m instanceof net.minecraft.world.entity.TamableAnimal a && a.isTame())) return;
        BlockPos pos = m.blockPosition();
        boolean eau = net.minecraft.world.entity.SpawnPlacements.getPlacementType(m.getType())
                == net.minecraft.world.entity.SpawnPlacements.Type.IN_WATER;
        boolean ok = f.permis(m.getType(), pos.getX(), pos.getZ(), n.getBiome(pos)) && (!eau || profondeurOk(m, n));
        if (!ok) {
            event.setCanceled(true);
            if (JOURNAL.incrementAndGet() <= 20) DomaineTerre.LOGGER.info("Faune : {} retiré en {} (hors de son milieu réel)",
                    net.minecraftforge.registries.ForgeRegistries.ENTITY_TYPES.getKey(m.getType()), pos.toShortString());
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
        return net.minecraft.util.random.WeightedRandomList.create(faune.filtrer(l, centre, biome, niveau.getRandom()));
    }
}

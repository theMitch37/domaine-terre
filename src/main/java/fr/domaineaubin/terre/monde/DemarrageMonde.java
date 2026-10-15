package fr.domaineaubin.terre.monde;

import fr.domaineaubin.terre.DomaineTerre;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.Registries;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.chunk.LevelChunk;
import net.minecraft.world.level.dimension.LevelStem;
import net.minecraft.world.level.levelgen.Heightmap;
import net.minecraft.world.level.storage.ServerLevelData;
import net.minecraftforge.event.level.LevelEvent;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.level.border.WorldBorder;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.event.server.ServerAboutToStartEvent;
import net.minecraftforge.event.server.ServerStartedEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** Au chargement d'un monde : active son échelle ; à sa création : place le point d'apparition sur terre. */
@Mod.EventBusSubscriber(modid = DomaineTerre.MOD_ID, bus = Mod.EventBusSubscriber.Bus.FORGE)
public final class DemarrageMonde {
    /** Point d'apparition par défaut : Paris (le joueur choisit ensuite sa région avec la lettre de départ). */
    private static final double SPAWN_LAT = 48.857, SPAWN_LON = 2.352;

    private DemarrageMonde() {
    }

    @SubscribeEvent
    public static void avantDemarrage(ServerAboutToStartEvent event) {
        LevelStem stem = event.getServer().registryAccess().registryOrThrow(Registries.LEVEL_STEM).get(LevelStem.OVERWORLD);
        if (stem != null && stem.generator().getBiomeSource() instanceof TerroirBiomeSource src) {
            Terrain.activer(src.echelle());
            DomaineTerre.LOGGER.info("Monde Terre à l'échelle 1:{}", src.echelle());
        }
    }

    @SubscribeEvent
    public static void pointApparition(LevelEvent.CreateSpawnPosition event) {
        if (!(event.getLevel() instanceof ServerLevel niveau) || niveau.dimension() != Level.OVERWORLD) return;
        if (!(niveau.getChunkSource().getGenerator().getBiomeSource() instanceof TerroirBiomeSource)) return;
        int x = (int) Math.floor(Terrain.x(SPAWN_LON));
        int z = (int) Math.floor(Terrain.z(SPAWN_LAT));
        LevelChunk chunk = niveau.getChunk(x >> 4, z >> 4);
        int y = chunk.getHeight(Heightmap.Types.MOTION_BLOCKING, x & 15, z & 15) + 1;
        event.getSettings().setSpawn(new BlockPos(x, y, z), 0.0F);
        event.setCanceled(true);
    }

    // ---------------------------------------------------------------- couture du Pacifique

    /** Marge (blocs) au-delà de 180° avant de basculer de l'autre côté ; le terrain y est déjà identique. */
    private static final int MARGE_COUTURE = 48;
    private static boolean mondeTerre = false;

    @SubscribeEvent
    public static void apresDemarrage(ServerStartedEvent event) {
        ServerLevel ow = event.getServer().overworld();
        mondeTerre = ow.getChunkSource().getGenerator().getBiomeSource() instanceof TerroirBiomeSource;
        if (!mondeTerre) return;
        // bordure du monde juste au-delà de la couture (on ne peut pas s'éloigner de la Terre)
        double demi = 180.0 * Terrain.BLOCS_PAR_DEGRE + 2 * MARGE_COUTURE;
        WorldBorder b = ow.getWorldBorder();
        b.setCenter(0, 0);
        b.setSize(2 * demi);
    }

    @SubscribeEvent
    public static void couture(TickEvent.PlayerTickEvent event) {
        if (!mondeTerre || event.phase != TickEvent.Phase.END || event.side.isClient()) return;
        if (event.player.tickCount % 5 != 0 || event.player.level().dimension() != Level.OVERWORLD) return;
        double tour = 360.0 * Terrain.BLOCS_PAR_DEGRE;
        double limite = 180.0 * Terrain.BLOCS_PAR_DEGRE + MARGE_COUTURE;
        double x = event.player.getX();
        double dx = x > limite ? -tour : (x < -limite ? tour : 0);
        if (dx == 0) return;
        // si le joueur est dans un bateau ou un navire, on déplace le véhicule avec ses passagers
        Entity e = event.player.getRootVehicle();
        e.teleportTo(e.getX() + dx, e.getY(), e.getZ());
    }
}

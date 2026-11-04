package fr.domaineaubin.lieux;

import net.minecraft.world.entity.monster.Enemy;
import net.minecraftforge.event.entity.living.MobSpawnEvent;
import net.minecraftforge.eventbus.api.Event;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/**
 * Pas de monstres dans les grottes célèbres (Padirac, Han, Postojna, Eisriesenwelt, Fingal, Capri) : ce ne sont pas
 * des lieux du mod Terre (pas de biome propre), leur emprise est celle de grottes.bin (04/11/2026, test en jeu :
 * des zombies apparaissaient dans Padirac).
 */
@Mod.EventBusSubscriber(modid = DomaineLieux.MOD_ID, bus = Mod.EventBusSubscriber.Bus.FORGE)
public final class GrottesSansMonstres {
    private GrottesSansMonstres() {
    }

    @SubscribeEvent
    public static void position(MobSpawnEvent.PositionCheck event) {
        if (event.getEntity() instanceof Enemy && GrottesFeature.dansGrotte((int) Math.floor(event.getX()), (int) Math.floor(event.getZ()))) {
            event.setResult(Event.Result.DENY);
        }
    }
}

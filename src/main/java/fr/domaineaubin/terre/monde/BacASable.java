package fr.domaineaubin.terre.monde;

import fr.domaineaubin.terre.DomaineTerre;
import net.minecraft.world.entity.Mob;
import net.minecraftforge.event.entity.EntityJoinLevelEvent;
import net.minecraftforge.eventbus.api.EventPriority;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/**
 * Monde 1:30 en « bac à sable » (09/11/2026, décision de Maxime : le temps des tests, aucune structure et aucun mob ;
 * on réintroduira tout un par un, « comme si nous recréions un jeu »).
 * <ul>
 * <li>Mobs : aucun (animaux, monstres, villageois, mobs des mods), qu'ils naissent à la génération, au fil du temps,
 * par un mod ou un œuf. Les joueurs, objets, projectiles et véhicules ne sont pas touchés.</li>
 * <li>Structures : aucune, de tous les mods (StructuresMixin).</li>
 * </ul>
 * Le monde 1:250 n'est pas concerné.
 */
@Mod.EventBusSubscriber(modid = DomaineTerre.MOD_ID, bus = Mod.EventBusSubscriber.Bus.FORGE)
public final class BacASable {
    private BacASable() {
    }

    /** Vrai dans un monde 1:30 (bac à sable des tests). */
    public static boolean actif() {
        return Terrain.echelle() < 250;
    }

    @SubscribeEvent(priority = EventPriority.HIGHEST)
    public static void entree(EntityJoinLevelEvent event) {
        if (actif() && event.getEntity() instanceof Mob) event.setCanceled(true);
    }
}

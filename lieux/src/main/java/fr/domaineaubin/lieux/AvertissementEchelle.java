package fr.domaineaubin.lieux;

import fr.domaineaubin.terre.monde.Terrain;
import fr.domaineaubin.terre.monde.TerroirBiomeSource;
import net.minecraft.ChatFormatting;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerPlayer;
import net.minecraftforge.event.entity.player.PlayerEvent;
import net.minecraftforge.event.server.ServerStartedEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** Les lieux sont réglés pour l'échelle 1:250 : on prévient si le monde Terre est à une autre échelle. */
@Mod.EventBusSubscriber(modid = DomaineLieux.MOD_ID, bus = Mod.EventBusSubscriber.Bus.FORGE)
public final class AvertissementEchelle {
    private static volatile boolean prevenir = false;

    private AvertissementEchelle() {
    }

    @SubscribeEvent
    public static void apresDemarrage(ServerStartedEvent event) {
        boolean terre = event.getServer().overworld().getChunkSource().getGenerator().getBiomeSource()
                instanceof TerroirBiomeSource;
        prevenir = terre && Terrain.echelle() != GrandCanyon.ECHELLE_REFERENCE;
        if (prevenir) {
            DomaineLieux.LOGGER.warn("Lieux uniques réglés pour l'échelle 1:{} ; ce monde est en 1:{}.",
                    GrandCanyon.ECHELLE_REFERENCE, Terrain.echelle());
        }
    }

    @SubscribeEvent
    public static void connexion(PlayerEvent.PlayerLoggedInEvent event) {
        if (prevenir && event.getEntity() instanceof ServerPlayer joueur) {
            joueur.sendSystemMessage(Component.translatable("message.domaine_terre_lieux.echelle", Terrain.echelle())
                    .withStyle(ChatFormatting.YELLOW));
        }
    }
}

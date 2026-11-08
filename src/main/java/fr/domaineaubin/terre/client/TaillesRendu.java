package fr.domaineaubin.terre.client;

import fr.domaineaubin.terre.DomaineTerre;
import fr.domaineaubin.terre.monde.Tailles;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.RenderLivingEvent;
import net.minecraftforge.eventbus.api.EventPriority;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** Modèle affiché à la taille de la table (voir Tailles) : le rendu est agrandi ou réduit autour des pieds. */
@Mod.EventBusSubscriber(modid = DomaineTerre.MOD_ID, bus = Mod.EventBusSubscriber.Bus.FORGE, value = Dist.CLIENT)
public final class TaillesRendu {
    private TaillesRendu() {
    }

    @SubscribeEvent(priority = EventPriority.LOWEST, receiveCanceled = false)
    public static void avant(RenderLivingEvent.Pre<?, ?> event) {
        float f = Tailles.facteur(event.getEntity().getType());
        if (f == 1.0f) return;
        event.getPoseStack().pushPose();
        event.getPoseStack().scale(f, f, f);
    }

    @SubscribeEvent(priority = EventPriority.HIGHEST)
    public static void apres(RenderLivingEvent.Post<?, ?> event) {
        if (Tailles.facteur(event.getEntity().getType()) == 1.0f) return;
        event.getPoseStack().popPose();
    }
}

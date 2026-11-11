package fr.domaineaubin.terre.client;

import fr.domaineaubin.terre.DomaineTerre;
import fr.domaineaubin.terre.monde.Tailles;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.RenderLivingEvent;
import net.minecraftforge.eventbus.api.EventPriority;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.common.MinecraftForge;
import net.minecraftforge.eventbus.api.Event;
import net.minecraftforge.fml.ModList;
import com.mojang.blaze3d.vertex.PoseStack;
import net.minecraft.world.entity.Entity;

import java.lang.reflect.Method;
import java.util.function.Consumer;

/** Modèle affiché à la taille de la table (voir Tailles) : le rendu est agrandi ou réduit autour des pieds. */
@Mod.EventBusSubscriber(modid = DomaineTerre.MOD_ID, bus = Mod.EventBusSubscriber.Bus.FORGE, value = Dist.CLIENT)
public final class TaillesRendu {
    private TaillesRendu() {
    }

    static {
        geckolib();
    }

    /**
     * Modèles GeckoLib (11/11/2026, test en jeu : araignées sauteuses plus grandes que les mygales) : Naturalist et
     * Critters and Companions dessinent leurs bêtes avec GeckoLib, qui ne passe pas par RenderLivingEvent ; seule la
     * boîte de collision suivait la table. Ses propres événements (GeoRenderEvent.Entity.Pre / Post) sont écoutés par
     * réflexion : pas de dépendance à GeckoLib pour compiler, rien si le mod est absent.
     */
    @SuppressWarnings({"unchecked", "rawtypes"})
    private static void geckolib() {
        try {
            if (!ModList.get().isLoaded("geckolib")) return;
            Class pre = Class.forName("software.bernie.geckolib.event.GeoRenderEvent$Entity$Pre");
            Class post = Class.forName("software.bernie.geckolib.event.GeoRenderEvent$Entity$Post");
            Method poseA = pre.getMethod("getPoseStack"), entA = pre.getMethod("getEntity");
            Method poseB = post.getMethod("getPoseStack"), entB = post.getMethod("getEntity");
            MinecraftForge.EVENT_BUS.addListener(EventPriority.LOWEST, false, pre,
                    (Consumer<Event>) e -> geo(e, poseA, entA, true));
            MinecraftForge.EVENT_BUS.addListener(EventPriority.HIGHEST, false, post,
                    (Consumer<Event>) e -> geo(e, poseB, entB, false));
            DomaineTerre.LOGGER.info("Tailles : modèles GeckoLib suivis");
        } catch (ReflectiveOperationException | RuntimeException | LinkageError ex) {
            DomaineTerre.LOGGER.warn("Tailles : GeckoLib non suivi ({})", ex.toString());
        }
    }

    private static void geo(Event e, Method pose, Method ent, boolean avant) {
        try {
            Entity en = (Entity) ent.invoke(e);
            if (en == null) return;
            float f = Tailles.facteur(en.getType());
            if (f == 1.0f) return;
            PoseStack ps = (PoseStack) pose.invoke(e);
            if (avant) {
                ps.pushPose();
                ps.scale(f, f, f);
            } else {
                ps.popPose();
            }
        } catch (ReflectiveOperationException ex) {
            throw new IllegalStateException(ex);
        }
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

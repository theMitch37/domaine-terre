package fr.domaineaubin.terre.client;

import fr.domaineaubin.terre.DomaineTerre;
import net.minecraft.client.Camera;
import net.minecraft.client.Minecraft;
import net.minecraft.core.BlockPos;
import net.minecraft.resources.ResourceKey;
import net.minecraft.util.Mth;
import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.material.FogType;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.ViewportEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/**
 * Ambiances visuelles de certains endroits (côté affichage seulement). Premier cas (08/11/2026) : les grandes fosses.
 * Dans l'eau d'une fosse, 30 blocs de visibilité en surface, puis de moins en moins et de plus en plus sombre jusqu'au
 * fond (9 blocs) ; au-dessus d'une fosse, hors de l'eau, une brume du large cache le fond depuis la surface. D'autres endroits pourront avoir leur règle ici.
 */
@Mod.EventBusSubscriber(modid = DomaineTerre.MOD_ID, bus = Mod.EventBusSubscriber.Bus.FORGE, value = Dist.CLIENT)
public final class Ambiances {
    private Ambiances() {
    }

    private static boolean abysse(Minecraft mc, BlockPos p) {
        ResourceKey<Biome> b = mc.level.getBiome(p).unwrapKey().orElse(null);
        if (b == null || !b.location().getNamespace().equals(DomaineTerre.MOD_ID)) return false;
        String n = b.location().getPath();
        return n.startsWith("mer/") && n.endsWith("_abysse");
    }

    /** Dans l'eau d'une fosse : 0 en surface, 1 au plus profond ; -1 ailleurs. */
    private static double profondeur(Camera camera) {
        if (camera.getFluidInCamera() != FogType.WATER) return -1;
        Minecraft mc = Minecraft.getInstance();
        if (mc.level == null || !abysse(mc, camera.getBlockPosition())) return -1;
        return Mth.clamp((63.0 - camera.getPosition().y) / 124.0, 0.0, 1.0);
    }

    private static boolean merProfonde(Minecraft mc, BlockPos p) {
        ResourceKey<Biome> b = mc.level.getBiome(p).unwrapKey().orElse(null);
        if (b == null || !b.location().getNamespace().equals(DomaineTerre.MOD_ID)) return false;
        String n = b.location().getPath();
        return n.startsWith("mer/") && (n.endsWith("_abysse") || n.endsWith("_large"));
    }

    /**
     * Au-dessus de la mer profonde (large et fosses), hors de l'eau : brume qui commence à la surface et cache le fond
     * (08/11/2026 : depuis un bateau ou en vol, l'eau du jeu laisse voir le fond à 50 blocs). Portée = hauteur
     * au-dessus de l'eau + 30 blocs (48 au moins) ; rien à partir de y 200. NaN ailleurs.
     */
    private static double surplomb(Camera camera) {
        if (camera.getFluidInCamera() != FogType.NONE) return Double.NaN;
        Minecraft mc = Minecraft.getInstance();
        if (mc.level == null) return Double.NaN;
        double y = camera.getPosition().y;
        if (y > 200 || !merProfonde(mc, camera.getBlockPosition())) return Double.NaN;
        return Math.max(48.0, (y - 63.0) + 30.0);
    }

    @SubscribeEvent
    public static void brouillard(ViewportEvent.RenderFog event) {
        double t = profondeur(event.getCamera());
        if (t >= 0) {
            // eau du large : 30 blocs de visibilité en surface (on ne voit pas le fond), 9 au fond
            float loin = (float) Mth.lerp(t, 30.0, 9.0);
            event.setFarPlaneDistance(Math.min(event.getFarPlaneDistance(), loin));
            event.setNearPlaneDistance(-4.0f);
            event.setCanceled(true);
            return;
        }
        // eau opaque (09/11/2026) : distance de vue sous l'eau selon le type d'eau (boueuse 3,5 blocs, mer 28 à 16)
        if (event.getCamera().getFluidInCamera() == FogType.WATER) {
            Minecraft mc = Minecraft.getInstance();
            double v = mc.level == null ? Double.NaN : EauOpaque.visibilite(mc.level, event.getCamera().getBlockPosition());
            if (!Double.isNaN(v) && v < event.getFarPlaneDistance()) {
                event.setFarPlaneDistance((float) v);
                event.setNearPlaneDistance(-4.0f);
                event.setCanceled(true);
            }
            return;
        }
        double s = surplomb(event.getCamera());
        if (!Double.isNaN(s) && event.getMode() == net.minecraft.client.renderer.FogRenderer.FogMode.FOG_TERRAIN
                && s < event.getFarPlaneDistance()) {
            float loin = (float) s;
            event.setFarPlaneDistance(loin);
            event.setNearPlaneDistance(Math.min(event.getNearPlaneDistance(), loin * 0.3f));
            event.setCanceled(true);
        }
    }

    @SubscribeEvent
    public static void couleur(ViewportEvent.ComputeFogColor event) {
        double t = profondeur(event.getCamera());
        if (t < 0) return;
        float f = (float) Mth.lerp(Mth.clamp((t - 0.3) / 0.7, 0.0, 1.0), 1.0, 0.06);   // le noir vient sous y 25
        event.setRed(event.getRed() * f);
        event.setGreen(event.getGreen() * f);
        event.setBlue(event.getBlue() * f);
    }
}

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
 * Sous y 10 dans un biome d'abysses, le brouillard de l'eau se resserre et s'assombrit avec la profondeur : on perd
 * la surface de vue, puis on ne voit le fond qu'une fois dessus. D'autres endroits pourront avoir leur règle ici.
 */
@Mod.EventBusSubscriber(modid = DomaineTerre.MOD_ID, bus = Mod.EventBusSubscriber.Bus.FORGE, value = Dist.CLIENT)
public final class Ambiances {
    private Ambiances() {
    }

    /** 0 = ambiance normale, 1 = au plus profond de la fosse. */
    private static double profondeur(Camera camera) {
        if (camera.getFluidInCamera() != FogType.WATER) return 0;
        Minecraft mc = Minecraft.getInstance();
        if (mc.level == null) return 0;
        BlockPos p = camera.getBlockPosition();
        if (p.getY() > 10) return 0;
        ResourceKey<Biome> b = mc.level.getBiome(p).unwrapKey().orElse(null);
        if (b == null || !b.location().getNamespace().equals(DomaineTerre.MOD_ID)) return 0;
        String n = b.location().getPath();
        if (!n.startsWith("mer/") || !n.endsWith("_abysse")) return 0;
        return Mth.clamp((10.0 - camera.getPosition().y) / 65.0, 0.0, 1.0);
    }

    @SubscribeEvent
    public static void brouillard(ViewportEvent.RenderFog event) {
        double t = profondeur(event.getCamera());
        if (t <= 0) return;
        float loin = (float) Mth.lerp(t, event.getFarPlaneDistance(), 9.0);
        event.setFarPlaneDistance(Math.min(event.getFarPlaneDistance(), loin));
        event.setNearPlaneDistance(-4.0f);
        event.setCanceled(true);
    }

    @SubscribeEvent
    public static void couleur(ViewportEvent.ComputeFogColor event) {
        double t = profondeur(event.getCamera());
        if (t <= 0) return;
        float f = (float) Mth.lerp(t, 1.0, 0.06);
        event.setRed(event.getRed() * f);
        event.setGreen(event.getGreen() * f);
        event.setBlue(event.getBlue() * f);
    }
}

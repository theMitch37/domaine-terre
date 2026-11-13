package fr.domaineaubin.meteo.vagues;

import com.mojang.blaze3d.systems.RenderSystem;
import com.mojang.blaze3d.vertex.BufferBuilder;
import com.mojang.blaze3d.vertex.DefaultVertexFormat;
import com.mojang.blaze3d.vertex.Tesselator;
import com.mojang.blaze3d.vertex.VertexFormat;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.GameRenderer;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.client.event.RenderLevelStageEvent;
import org.joml.Matrix4f;

/**
 * Dessin de la houle (prototype) : une surface de mer animée, une case par bloc, dans un rayon autour de la caméra,
 * posée sur l'eau de la mer là où elle est assez profonde. Couleur bleu profond, plus claire face au soleil.
 * Prototype : l'eau du jeu reste dessinée dessous (les creux laissent voir la surface plate).
 */
public final class RenduVagues {
    private RenduVagues() {
    }

    public static void dessiner(RenderLevelStageEvent e) {
        if (e.getStage() != RenderLevelStageEvent.Stage.AFTER_TRANSLUCENT_BLOCKS || !Houle.actif()) return;
        Minecraft mc = Minecraft.getInstance();
        net.minecraft.client.multiplayer.ClientLevel level = mc.level;
        if (level == null || level.dimension() != Level.OVERWORLD) return;
        Vec3 c = e.getCamera().getPosition();
        double surface = level.getSeaLevel() - 0.1;
        if (c.y < surface - 6 || c.y > surface + 300) return;
        double t = Houle.temps(level, e.getPartialTick());
        float lumiere = 1.0f - level.getSkyDarken(e.getPartialTick()) * 0.85f;
        int r = Math.max(8, Math.min(128, Houle.reglages().rayon));
        int cx = (int) Math.floor(c.x), cz = (int) Math.floor(c.z);
        int n = 2 * r + 1;
        double[] h = new double[(n + 1) * (n + 1)];
        boolean[] mer = new boolean[(n + 1) * (n + 1)];
        boolean une = false;
        for (int j = 0; j <= n; j++) {
            for (int i = 0; i <= n; i++) {
                int x = cx - r + i, z = cz - r + j;
                double a = Houle.amplitude(level, x, z);
                int k = j * (n + 1) + i;
                mer[k] = a > 0.02;
                une |= mer[k];
                h[k] = mer[k] ? Houle.hauteur(x, z, t, a) : 0;
            }
        }
        if (!une) return;
        Matrix4f m = e.getPoseStack().last().pose();
        RenderSystem.enableBlend();
        RenderSystem.defaultBlendFunc();
        RenderSystem.disableCull();
        RenderSystem.enableDepthTest();
        RenderSystem.setShader(GameRenderer::getPositionColorShader);
        BufferBuilder b = Tesselator.getInstance().getBuilder();
        b.begin(VertexFormat.Mode.QUADS, DefaultVertexFormat.POSITION_COLOR);
        for (int j = 0; j < n; j++) {
            for (int i = 0; i < n; i++) {
                int k00 = j * (n + 1) + i, k10 = k00 + 1, k01 = k00 + n + 1, k11 = k01 + 1;
                if (!(mer[k00] && mer[k10] && mer[k01] && mer[k11])) continue;
                double x0 = cx - r + i - c.x, z0 = cz - r + j - c.z;
                // éclairage : pente de la case vers le soleil (ouest-sud-ouest à l'horizon : simple)
                double hx = (h[k10] - h[k00] + h[k11] - h[k01]) / 2, hz = (h[k01] - h[k00] + h[k11] - h[k10]) / 2;
                float clair = (float) Math.max(0.55, Math.min(1.15, 0.85 + 0.6 * (-hx * 0.5 + hz * 0.3) + 0.12 * h[k00]));
                float l = clair * lumiere;
                int rr = (int) (28 * l), gg = (int) (78 * l), bb = (int) (150 * l), aa = 190;
                sommet(b, m, x0, surface + h[k00] - c.y, z0, rr, gg, bb, aa);
                sommet(b, m, x0, surface + h[k01] - c.y, z0 + 1, rr, gg, bb, aa);
                sommet(b, m, x0 + 1, surface + h[k11] - c.y, z0 + 1, rr, gg, bb, aa);
                sommet(b, m, x0 + 1, surface + h[k10] - c.y, z0, rr, gg, bb, aa);
            }
        }
        Tesselator.getInstance().end();
        RenderSystem.enableCull();
        RenderSystem.disableBlend();
    }

    private static void sommet(BufferBuilder b, Matrix4f m, double x, double y, double z, int r, int g, int bl, int a) {
        b.vertex(m, (float) x, (float) y, (float) z).color(r, g, bl, a).endVertex();
    }
}

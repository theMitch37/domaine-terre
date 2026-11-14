package fr.domaineaubin.meteo.vagues;

import com.mojang.blaze3d.systems.RenderSystem;
import com.mojang.blaze3d.vertex.BufferBuilder;
import com.mojang.blaze3d.vertex.DefaultVertexFormat;
import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.Tesselator;
import com.mojang.blaze3d.vertex.VertexBuffer;
import com.mojang.blaze3d.vertex.VertexFormat;
import net.minecraft.client.Minecraft;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.client.renderer.BiomeColors;
import net.minecraft.client.renderer.GameRenderer;
import net.minecraft.client.renderer.LightTexture;
import net.minecraft.client.renderer.texture.TextureAtlas;
import net.minecraft.client.renderer.texture.TextureAtlasSprite;
import net.minecraft.core.BlockPos;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.client.event.RenderLevelStageEvent;
import org.joml.Matrix4f;

import java.util.HashMap;
import java.util.Iterator;
import java.util.Map;

/**
 * Dessin de la mer (0.3.0). Le jeu ne dessine plus le dessus de la mer ({@link MasqueEau}) ; on le dessine ici avec
 * la texture d'eau du pack de ressources actif (animée) et la couleur d'eau du biome, éclairée par la lumière du jeu
 * (jour, nuit, pluie) et noyée dans le brouillard comme le reste du monde :
 * 1. près du joueur (rayon réglable), la houle, une case par bloc, recalculée à chaque image ; crêtes plus claires
 *    avec un peu d'écume, pentes ombrées (relief lisible) ;
 * 2. partout ailleurs jusqu'à la distance de vue, une surface plate, préparée une fois par chunk (tampon graphique).
 * La houle est toujours au-dessus de la surface plate : la surface plate, dessinée après avec le test de profondeur,
 * disparaît d'elle-même sous les vagues (pas de double épaisseur).
 */
public final class RenduVagues {
    private RenduVagues() {
    }

    private static final ResourceLocation EAU = new ResourceLocation("minecraft", "block/water_still");
    private static final int LUMIERE = LightTexture.pack(0, 15);
    private static final int CHUNKS_PAR_IMAGE = 6;

    /** Surface plate d'un chunk : tampon graphique prêt (null : aucune mer dans ce chunk). */
    private static final Map<Long, VertexBuffer> PLATS = new HashMap<>();
    private static final Map<Long, Boolean> VIDES = new HashMap<>();
    private static ClientLevel niveau;
    private static final BufferBuilder CONSTRUCTEUR = new BufferBuilder(256 * 4 * DefaultVertexFormat.PARTICLE.getVertexSize());

    public static void oublier() {
        for (VertexBuffer v : PLATS.values()) v.close();
        PLATS.clear();
        VIDES.clear();
    }

    private static TextureAtlasSprite sprite() {
        return Minecraft.getInstance().getModelManager().getAtlas(TextureAtlas.LOCATION_BLOCKS).getSprite(EAU);
    }

    public static void dessiner(RenderLevelStageEvent e) {
        if (e.getStage() != RenderLevelStageEvent.Stage.AFTER_TRANSLUCENT_BLOCKS) return;
        Minecraft mc = Minecraft.getInstance();
        ClientLevel level = mc.level;
        if (level != niveau) {
            oublier();
            niveau = level;
        }
        if (!Houle.actif() || level == null || level.dimension() != Level.OVERWORLD) return;
        Vec3 c = e.getCamera().getPosition();
        double plate = Houle.eauPlate(level);
        if (c.y > plate + 400) return;
        TextureAtlasSprite sp = sprite();

        RenderSystem.enableBlend();
        RenderSystem.defaultBlendFunc();
        RenderSystem.disableCull();
        RenderSystem.enableDepthTest();
        RenderSystem.depthMask(true);
        RenderSystem.setShader(GameRenderer::getParticleShader);
        RenderSystem.setShaderTexture(0, TextureAtlas.LOCATION_BLOCKS);
        mc.gameRenderer.lightTexture().turnOnLightLayer();

        houle(e, level, c, plate, sp);
        plats(e, mc, level, c, plate, sp);

        mc.gameRenderer.lightTexture().turnOffLightLayer();
        RenderSystem.enableCull();
        RenderSystem.disableBlend();
    }

    // ------------------------------------------------------------------------------------------------ la houle

    private static void houle(RenderLevelStageEvent e, ClientLevel level, Vec3 c, double plate, TextureAtlasSprite sp) {
        double t = Houle.temps(level, e.getPartialTick());
        int r = Math.max(8, Math.min(128, Houle.reglages().rayon));
        double ampMax = Math.max(0.05, Houle.reglages().amplitude);
        int cx = (int) Math.floor(c.x), cz = (int) Math.floor(c.z);
        int n = 2 * r + 1;
        double[] h = new double[(n + 1) * (n + 1)];
        double[] a = new double[(n + 1) * (n + 1)];
        boolean une = false;
        for (int j = 0; j <= n; j++) {
            for (int i = 0; i <= n; i++) {
                int x = cx - r + i, z = cz - r + j;
                int k = j * (n + 1) + i;
                double am = Houle.amplitude(level, x, z);
                // fondu vers la surface plate au bord du rayon (dessin seulement : la barque et la nage n'en dépendent pas)
                double d = Math.sqrt((x - c.x) * (x - c.x) + (z - c.z) * (z - c.z));
                double f = Math.max(0, Math.min(1, (r - d) / 16.0));
                am *= f * f * (3 - 2 * f);
                a[k] = am;
                h[k] = am > 0.02 ? Houle.levee(x, z, t, am) : 0;
                une |= am > 0.02;
            }
        }
        if (!une) return;
        Matrix4f m = e.getPoseStack().last().pose();
        BufferBuilder b = Tesselator.getInstance().getBuilder();
        b.begin(VertexFormat.Mode.QUADS, DefaultVertexFormat.PARTICLE);
        BlockPos.MutableBlockPos p = new BlockPos.MutableBlockPos();
        float u0 = sp.getU0(), u1 = sp.getU1(), v0 = sp.getV0(), v1 = sp.getV1();
        for (int j = 0; j < n; j++) {
            for (int i = 0; i < n; i++) {
                int k00 = j * (n + 1) + i, k10 = k00 + 1, k01 = k00 + n + 1, k11 = k01 + 1;
                if (a[k00] <= 0.02 && a[k10] <= 0.02 && a[k01] <= 0.02 && a[k11] <= 0.02) continue;
                int x = cx - r + i, z = cz - r + j;
                if (Houle.profondeur(level, x, z) <= 0) continue;               // pas de mer sur cette case
                double x0 = x - c.x, z0 = z - c.z;
                int teinte = BiomeColors.getAverageWaterColor(level, p.set(x, (int) plate, z));
                double hx = (h[k10] - h[k00] + h[k11] - h[k01]) / 2, hz = (h[k01] - h[k00] + h[k11] - h[k10]) / 2;
                double y0 = plate + 0.01 - c.y;
                sommet(b, m, x0, y0 + h[k00], z0, u0, v0, teinte, relief(h[k00], ampMax, hx, hz));
                sommet(b, m, x0, y0 + h[k01], z0 + 1, u0, v1, teinte, relief(h[k01], ampMax, hx, hz));
                sommet(b, m, x0 + 1, y0 + h[k11], z0 + 1, u1, v1, teinte, relief(h[k11], ampMax, hx, hz));
                sommet(b, m, x0 + 1, y0 + h[k10], z0, u1, v0, teinte, relief(h[k10], ampMax, hx, hz));
            }
        }
        Tesselator.getInstance().end();
    }

    /**
     * Relief de la houle : [éclat, écume]. Pente tournée vers le soleil d'ouest-sud-ouest plus claire, creux plus sombres,
     * haut des crêtes éclairci et blanchi (écume légère) pour que les vagues se lisent.
     */
    private static float[] relief(double h, double ampMax, double hx, double hz) {
        double haut = Math.max(0, Math.min(1, h / (2 * ampMax)));               // 0 = creux, 1 = crête
        double eclat = 0.80 + 0.30 * haut + 0.45 * (-hx * 0.5 + hz * 0.3);
        double ecume = Math.max(0, (haut - 0.78) / 0.22);
        return new float[]{(float) Math.max(0.55, Math.min(1.25, eclat)), (float) (ecume * ecume * 0.55)};
    }

    private static void sommet(BufferBuilder b, Matrix4f m, double x, double y, double z, float u, float v, int teinte,
                               float[] rel) {
        float rr = ((teinte >> 16) & 255) / 255f, gg = ((teinte >> 8) & 255) / 255f, bb = (teinte & 255) / 255f;
        float k = rel[0], w = rel[1];
        rr = Math.min(1, rr * k * (1 - w) + w);
        gg = Math.min(1, gg * k * (1 - w) + w);
        bb = Math.min(1, bb * k * (1 - w) + w);
        b.vertex(m, (float) x, (float) y, (float) z).uv(u, v).color(rr, gg, bb, 1f).uv2(LUMIERE).endVertex();
    }

    // ------------------------------------------------------------------------------------- la surface plate

    private static void plats(RenderLevelStageEvent e, Minecraft mc, ClientLevel level, Vec3 c, double plate,
                              TextureAtlasSprite sp) {
        int rv = mc.options.getEffectiveRenderDistance();
        int pcx = (int) Math.floor(c.x) >> 4, pcz = (int) Math.floor(c.z) >> 4;
        // oublier les chunks trop loin
        Iterator<Map.Entry<Long, VertexBuffer>> it = PLATS.entrySet().iterator();
        while (it.hasNext()) {
            Map.Entry<Long, VertexBuffer> en = it.next();
            int x = (int) (en.getKey() >> 32), z = (int) (long) en.getKey();
            if (Math.abs(x - pcx) > rv + 2 || Math.abs(z - pcz) > rv + 2) {
                en.getValue().close();
                it.remove();
            }
        }
        VIDES.keySet().removeIf(k -> Math.abs((int) (k >> 32) - pcx) > rv + 2 || Math.abs((int) (long) k - pcz) > rv + 2);

        int budget = CHUNKS_PAR_IMAGE;
        Matrix4f proj = e.getProjectionMatrix();
        PoseStack ps = e.getPoseStack();
        var shader = RenderSystem.getShader();
        for (int dz = -rv; dz <= rv; dz++) {
            for (int dx = -rv; dx <= rv; dx++) {
                if (dx * dx + dz * dz > (rv + 1) * (rv + 1)) continue;
                int qx = pcx + dx, qz = pcz + dz;
                long cle = ((long) qx << 32) | (qz & 0xFFFFFFFFL);
                if (VIDES.containsKey(cle)) continue;
                VertexBuffer vb = PLATS.get(cle);
                if (vb == null) {
                    if (budget <= 0 || !level.hasChunk(qx, qz)) continue;
                    budget--;
                    vb = construire(level, qx, qz, sp);
                    if (vb == null) {
                        VIDES.put(cle, Boolean.TRUE);
                        continue;
                    }
                    PLATS.put(cle, vb);
                }
                ps.pushPose();
                ps.translate((qx << 4) - c.x, plate - c.y, (qz << 4) - c.z);
                vb.bind();
                vb.drawWithShader(ps.last().pose(), proj, shader);
                ps.popPose();
            }
        }
        VertexBuffer.unbind();
    }

    /** Surface plate d'un chunk (coordonnées locales au chunk, y = 0 à la surface de l'eau plate), null si pas de mer. */
    private static VertexBuffer construire(ClientLevel level, int qx, int qz, TextureAtlasSprite sp) {
        // tous les voisins utiles au calcul doivent être chargés, sinon on réessaiera plus tard
        BufferBuilder b = CONSTRUCTEUR;                                  // réutilisé : mémoire hors tas Java
        b.begin(VertexFormat.Mode.QUADS, DefaultVertexFormat.PARTICLE);
        float u0 = sp.getU0(), u1 = sp.getU1(), v0 = sp.getV0(), v1 = sp.getV1();
        BlockPos.MutableBlockPos p = new BlockPos.MutableBlockPos();
        int y = level.getSeaLevel() - 1;
        int nb = 0;
        for (int lz = 0; lz < 16; lz++) {
            for (int lx = 0; lx < 16; lx++) {
                int x = (qx << 4) + lx, z = (qz << 4) + lz;
                if (Houle.profondeur(level, x, z) <= 0) continue;
                int t = BiomeColors.getAverageWaterColor(level, p.set(x, y, z));
                float r = ((t >> 16) & 255) / 255f * 0.9f, g = ((t >> 8) & 255) / 255f * 0.9f, bl = (t & 255) / 255f * 0.9f;
                b.vertex(lx, 0, lz).uv(u0, v0).color(r, g, bl, 1f).uv2(LUMIERE).endVertex();
                b.vertex(lx, 0, lz + 1).uv(u0, v1).color(r, g, bl, 1f).uv2(LUMIERE).endVertex();
                b.vertex(lx + 1, 0, lz + 1).uv(u1, v1).color(r, g, bl, 1f).uv2(LUMIERE).endVertex();
                b.vertex(lx + 1, 0, lz).uv(u1, v0).color(r, g, bl, 1f).uv2(LUMIERE).endVertex();
                nb++;
            }
        }
        BufferBuilder.RenderedBuffer rendu = b.end();
        if (nb == 0) {
            rendu.release();
            return null;
        }
        VertexBuffer vb = new VertexBuffer(VertexBuffer.Usage.STATIC);
        vb.bind();
        vb.upload(rendu);
        VertexBuffer.unbind();
        return vb;
    }
}

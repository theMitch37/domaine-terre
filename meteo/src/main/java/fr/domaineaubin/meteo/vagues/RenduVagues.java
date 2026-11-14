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
 * Dessin de la mer près du joueur (0.3.1). Dans un carré de chunks autour du joueur, le jeu ne dessine plus le dessus
 * de la mer ({@link MasqueEau}) ; on y dessine, case par case, la houle avec la texture d'eau du pack de ressources
 * actif (animée) et la couleur d'eau du biome, éclairée par la lumière du jeu (jour, nuit, pluie) et noyée dans le
 * brouillard. Crêtes plus claires avec un peu d'écume, pentes ombrées (relief lisible). La houle s'aplatit au bord du
 * rayon ; au-delà, jusqu'au bord du carré, surface plate (même texture) ; hors du carré, l'eau du jeu.
 */
public final class RenduVagues {
    private RenduVagues() {
    }

    private static final ResourceLocation EAU = new ResourceLocation("minecraft", "block/water_still");
    private static final int LUMIERE = LightTexture.pack(0, 15);
    private static ClientLevel niveau;

    /** Demi-côté du carré masqué (chunks) : la houle s'éteint avant son bord, où que soit le joueur dans son chunk. */
    public static int demiCarre() {
        int r = Math.max(8, Math.min(128, Houle.reglages().rayon));
        return (r + 15) / 16 + 1;
    }

    private static TextureAtlasSprite sprite() {
        return Minecraft.getInstance().getModelManager().getAtlas(TextureAtlas.LOCATION_BLOCKS).getSprite(EAU);
    }

    public static void dessiner(RenderLevelStageEvent e) {
        if (e.getStage() != RenderLevelStageEvent.Stage.AFTER_TRANSLUCENT_BLOCKS) return;
        Minecraft mc = Minecraft.getInstance();
        ClientLevel level = mc.level;
        if (level != niveau) {
            MasqueEau.oublier();
            TEINTES.clear();
            niveau = level;
        }
        if (!Houle.actif() || level == null || level.dimension() != Level.OVERWORLD) return;
        Vec3 c = e.getCamera().getPosition();
        int demi = demiCarre();
        MasqueEau.suivre(level, (int) Math.floor(c.x) >> 4, (int) Math.floor(c.z) >> 4, demi);
        double plate = Houle.eauPlate(level);
        TextureAtlasSprite sp = sprite();

        RenderSystem.enableBlend();
        RenderSystem.defaultBlendFunc();
        RenderSystem.disableCull();
        RenderSystem.enableDepthTest();
        RenderSystem.depthMask(true);
        RenderSystem.setShader(GameRenderer::getParticleShader);
        RenderSystem.setShaderTexture(0, TextureAtlas.LOCATION_BLOCKS);
        mc.gameRenderer.lightTexture().turnOnLightLayer();

        houle(e, level, c, plate, sp, demi);

        mc.gameRenderer.lightTexture().turnOffLightLayer();
        RenderSystem.enableCull();
        RenderSystem.disableBlend();
    }

    // ------------------------------------------------------------------------------------------------ la houle

    private static void houle(RenderLevelStageEvent e, ClientLevel level, Vec3 c, double plate, TextureAtlasSprite sp,
                              int demi) {
        double t = Houle.temps(level, e.getPartialTick());
        int rayon = Math.max(8, Math.min(128, Houle.reglages().rayon));
        double ampMax = Math.max(0.05, Houle.reglages().amplitude);
        // le carré masqué, en blocs : de (centre - demi) à (centre + demi) chunks inclus
        int ccx = (int) Math.floor(c.x) >> 4, ccz = (int) Math.floor(c.z) >> 4;
        int r = (demi * 2 + 1) * 8;                                       // demi-côté en blocs
        int cx = (ccx << 4) + 8, cz = (ccz << 4) + 8;
        int n = 2 * r;
        double[] h = new double[(n + 1) * (n + 1)];
        double[] a = new double[(n + 1) * (n + 1)];
        int[] prof = new int[(n + 1) * (n + 1)];
        for (int j = 0; j <= n; j++) {
            for (int i = 0; i <= n; i++) {
                int x = cx - r + i, z = cz - r + j;
                int k = j * (n + 1) + i;
                int pr = Houle.profondeur(level, x, z);
                if (pr <= 0 && MasqueEau.masquer(level, x, level.getSeaLevel() - 1, z)) pr = trou(level, x, z, pr);
                prof[k] = pr;
                double am = pr > 0 ? Houle.amplitudeSelonProfondeur(level, pr) : 0;
                // fondu vers la surface plate au bord du rayon (dessin seulement : la barque et la nage n'en dépendent pas)
                double d = Math.sqrt((x - c.x) * (x - c.x) + (z - c.z) * (z - c.z));
                double f = Math.max(0, Math.min(1, (rayon - d) / 16.0));
                am *= f * f * (3 - 2 * f);
                a[k] = am;
                h[k] = am > 0.02 ? Houle.levee(x, z, t, am) : 0;
            }
        }
        Matrix4f m = e.getPoseStack().last().pose();
        BufferBuilder b = Tesselator.getInstance().getBuilder();
        b.begin(VertexFormat.Mode.QUADS, DefaultVertexFormat.PARTICLE);
        BlockPos.MutableBlockPos p = new BlockPos.MutableBlockPos();
        float u0 = sp.getU0(), u1 = sp.getU1(), v0 = sp.getV0(), v1 = sp.getV1();
        for (int j = 0; j < n; j++) {
            for (int i = 0; i < n; i++) {
                int k00 = j * (n + 1) + i, k10 = k00 + 1, k01 = k00 + n + 1, k11 = k01 + 1;
                int x = cx - r + i, z = cz - r + j;
                if (prof[k00] <= 0) continue;               // pas de mer sur cette case (ou masque :
                                                                                // mêmes conditions, voir MasqueEau)
                double x0 = x - c.x, z0 = z - c.z;
                int teinte = teinte(level, p, x, (int) plate, z);
                double hx = (h[k10] - h[k00] + h[k11] - h[k01]) / 2, hz = (h[k01] - h[k00] + h[k11] - h[k10]) / 2;
                double y0 = plate + 0.01 - c.y;
                sommet(b, m, x0, y0 + h[k00], z0, u0, v0, teinte, relief(h[k00], a[k00], ampMax, hx, hz));
                sommet(b, m, x0, y0 + h[k01], z0 + 1, u0, v1, teinte, relief(h[k01], a[k01], ampMax, hx, hz));
                sommet(b, m, x0 + 1, y0 + h[k11], z0 + 1, u1, v1, teinte, relief(h[k11], a[k11], ampMax, hx, hz));
                sommet(b, m, x0 + 1, y0 + h[k10], z0, u1, v0, teinte, relief(h[k10], a[k10], ampMax, hx, hz));
            }
        }
        Tesselator.getInstance().end();
    }

    /**
     * 0.3.4 : une colonne dont la surface du jeu est masquée doit être dessinée (sinon : trou dans la mer). Si la
     * mémoire dit « pas de mer », on recalcule sans elle, on corrige et on le note dans le journal (50 fois au plus).
     */
    private static int journalTrous;

    private static int trou(ClientLevel level, int x, int z, int pr) {
        int direct = Houle.profondeurDirecte(level, x, z);
        if (journalTrous < 50) {
            journalTrous++;
            fr.domaineaubin.meteo.DomaineWeather.LOGGER.warn("[Vagues] trou évité en {} {} : mémoire {} (gardée {}), recalcul {}, biome {}",
                    x, z, pr, Houle.profondeurGardee(level, x, z), direct,
                    level.getBiome(new BlockPos(x, level.getSeaLevel() - 1, z)).unwrapKey().map(Object::toString).orElse("?"));
        }
        if (direct > 0) Houle.retenir(level, x, z, direct);
        return Math.max(direct, 1);                        // masquée : on dessine quoi qu'il arrive
    }

    // couleur d'eau du biome, gardée par chunk (le mélange des biomes coûte cher et ne change pas)
    private static final java.util.HashMap<Long, int[]> TEINTES = new java.util.HashMap<>();

    private static int teinte(ClientLevel level, BlockPos.MutableBlockPos p, int x, int y, int z) {
        long cle = ((long) (x >> 4) << 32) ^ ((z >> 4) & 0xFFFFFFFFL);
        int[] t = TEINTES.get(cle);
        if (t == null) {
            if (TEINTES.size() > 4096) TEINTES.clear();
            t = new int[256];
            java.util.Arrays.fill(t, -1);
            TEINTES.put(cle, t);
        }
        int i = ((z & 15) << 4) | (x & 15);
        if (t[i] == -1) t[i] = BiomeColors.getAverageWaterColor(level, p.set(x, y, z)) & 0xFFFFFF;
        return t[i];
    }

    /**
     * Relief de la houle : [éclat, écume]. Pente tournée vers le soleil d'ouest-sud-ouest plus claire, creux plus sombres,
     * haut des crêtes éclairci et blanchi (écume légère) pour que les vagues se lisent.
     */
    private static float[] relief(double h, double am, double ampMax, double hx, double hz) {
        // poids du relief : nul sur l'eau plate (même couleur que l'eau du jeu au-delà du carré : pas de ligne)
        double w = Math.max(0, Math.min(1, am / ampMax));
        double haut = Math.max(0, Math.min(1, h / (2 * ampMax)));               // 0 = creux, 1 = crête
        double eclat = 1 + w * (0.30 * (haut - 0.5) + 0.45 * (-hx * 0.5 + hz * 0.3));
        double ecume = w * Math.max(0, (haut - 0.78) / 0.22);
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

}

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

    /** 0.3.7 : cases de mer en plus au bord de la mer (évite un fil de jour entre notre eau et la côte). */
    private static final double RECOUVRE = 0.03;
    /** 0.3.7 : opacité de l'eau épaisse (2e passage) au plus profond ; 0.3.8 : 0,6 -> 0,85 (on voyait encore le fond). */
    private static final double OPACITE = 0.85;
    /**
     * 0.3.7 : distance (cases) sur laquelle l'eau épaisse s'efface vers la côte ou le bord du carré ; 0.3.8 : 8 -> 24
     * (le carré plus sombre se voyait d'un coup, l'eau du jeu au-delà étant plus claire).
     */
    private static final int FONDU_FOND = 24;
    private static final int BORD_MAX = FONDU_FOND + 1;
    /** 0.3.7 : distance (cases) sur laquelle la houle s'efface vers la côte ou le bord du carré. */
    private static final int BORD = 4;
    /** 0.3.8 : rayon (cases) du lissage de l'épaisseur, contre les marches et le quadrillage. */
    private static final int LISSAGE = 3;

    private static double[] H, A, OP, LISSE;
    private static int[] PROF, BORDS;
    private static long cle = Long.MIN_VALUE;
    private static int images;

    /** Distance au bord et profondeur lissée (0.3.7, 0.3.8), recalculées avec la profondeur. */
    private static void preparer(int n, int[] prof) {
        int[] bord = BORDS;
        double[] lisse = LISSE;
        java.util.Arrays.fill(lisse, 0);
        // 0.3.7 : distance (en cases, BORD_MAX au plus) de chaque case de mer au bord le plus proche (côte, bord du carré)
        for (int j = 0; j < n; j++) {
            for (int i = 0; i < n; i++) {
                int k = j * n + i;
                if (prof[j * (n + 1) + i] <= 0) {
                    bord[k] = 0;
                    continue;
                }
                int d = Math.min(i, Math.min(j, Math.min(n - 1 - i, n - 1 - j))) + 1;
                if (i > 0) d = Math.min(d, bord[k - 1] + 1);
                if (j > 0) d = Math.min(d, bord[k - n] + 1);
                bord[k] = Math.min(d, BORD_MAX);
            }
        }
        for (int j = n - 1; j >= 0; j--) {
            for (int i = n - 1; i >= 0; i--) {
                int k = j * n + i;
                if (bord[k] == 0) continue;
                if (i < n - 1) bord[k] = Math.min(bord[k], bord[k + 1] + 1);
                if (j < n - 1) bord[k] = Math.min(bord[k], bord[k + n] + 1);
            }
        }
        // 0.3.8 : profondeur lissée (moyenne des cases de mer voisines) : une case de profondeur inconnue (trou évité,
        // chunk qui arrive) prend celle de ses voisines au lieu de faire une tache claire, et l'épaisseur ne fait plus
        // de marches d'une case à l'autre (quadrillage vu en jeu le 15/11/2026)
        for (int j = 0; j < n; j++) {
            for (int i = 0; i < n; i++) {
                if (prof[j * (n + 1) + i] <= 0) continue;
                double s = 0;
                int nb = 0;
                for (int dj = -LISSAGE; dj <= LISSAGE; dj++) {
                    for (int di = -LISSAGE; di <= LISSAGE; di++) {
                        int ci = i + di, cj = j + dj;
                        if (ci < 0 || cj < 0 || ci >= n || cj >= n) continue;
                        int pv = prof[cj * (n + 1) + ci];
                        if (pv > 1) {                          // 1 = profondeur inconnue (trou évité) : ignorée
                            s += pv;
                            nb++;
                        }
                    }
                }
                lisse[j * n + i] = nb > 0 ? s / nb : prof[j * (n + 1) + i];
            }
        }
    }

    private static void houle(RenderLevelStageEvent e, ClientLevel level, Vec3 c, double plate, TextureAtlasSprite sp,
                              int demi) {
        double t = Houle.temps(level, e.getPartialTick());
        int rayon = Math.max(8, Math.min(128, Houle.reglages().rayon));
        double ampMax = Math.max(0.05, Houle.amplitudeRegion(level, c.x, c.z));
        // le carré masqué, en blocs : de (centre - demi) à (centre + demi) chunks inclus
        int ccx = (int) Math.floor(c.x) >> 4, ccz = (int) Math.floor(c.z) >> 4;
        int r = (demi * 2 + 1) * 8;                                       // demi-côté en blocs
        int cx = (ccx << 4) + 8, cz = (ccz << 4) + 8;
        int n = 2 * r;
        // 0.4.1 (optimisation) : tableaux gardés d'une image à l'autre (avant : ~1 Mo alloué à chaque image) ; la
        // profondeur, la distance au bord et le lissage ne sont recalculés que si le carré bouge, et sinon toutes les
        // 10 images (chunks qui arrivent, masque qui change)
        int nn = (n + 1) * (n + 1);
        if (H == null || H.length != nn) {
            H = new double[nn];
            A = new double[nn];
            PROF = new int[nn];
            OP = new double[nn];
            BORDS = new int[n * n];
            LISSE = new double[n * n];
            cle = Long.MIN_VALUE;
        }
        double[] h = H, a = A, op = OP;
        int[] prof = PROF;
        long nouvelle = ((long) cx << 32) ^ (cz & 0xFFFFFFFFL);
        boolean refaire = nouvelle != cle || ++images >= 10;
        if (refaire) {
            cle = nouvelle;
            images = 0;
            for (int j = 0; j <= n; j++) {
                for (int i = 0; i <= n; i++) {
                    int x = cx - r + i, z = cz - r + j;
                    int pr = Houle.profondeur(level, x, z);
                    if (pr <= 0 && MasqueEau.masquer(level, x, level.getSeaLevel() - 1, z)) pr = trou(level, x, z, pr);
                    prof[j * (n + 1) + i] = MasqueEau.dansCarre(x, z) ? pr : 0;
                }
            }
            preparer(n, prof);
        }
        int[] bord = BORDS;
        double[] lisse = LISSE;
        // amplitude de la région aux nœuds de 16 blocs (les mêmes que Houle.amplitudeRegion), une fois par image
        int nx0 = Math.floorDiv(cx - r, Houle.PAS_NOEUD), nz0 = Math.floorDiv(cz - r, Houle.PAS_NOEUD);
        int nnx = Math.floorDiv(cx + r, Houle.PAS_NOEUD) - nx0 + 2, nnz = Math.floorDiv(cz + r, Houle.PAS_NOEUD) - nz0 + 2;
        double[] noeuds = new double[nnx * nnz];
        boolean regionale = Houle.regionale(level);
        double fixe = Houle.reglages().amplitude;
        for (int j = 0; j < nnz; j++)
            for (int i = 0; i < nnx; i++)
                noeuds[j * nnx + i] = regionale ? Houle.amplitudeNoeud(level, nx0 + i, nz0 + j) : fixe;
        for (int j = 0; j <= n; j++) {
            for (int i = 0; i <= n; i++) {
                int x = cx - r + i, z = cz - r + j;
                int k = j * (n + 1) + i;
                // sommet : distance au bord et profondeur, la plus petite / la moyenne des 4 cases qui le touchent
                int dv = BORD_MAX;
                double ps = 0;
                int pn = 0;
                for (int dj = -1; dj <= 0; dj++) {
                    for (int di = -1; di <= 0; di++) {
                        int ci = i + di, cj = j + dj;
                        boolean dedans = ci >= 0 && cj >= 0 && ci < n && cj < n;
                        dv = Math.min(dv, dedans ? bord[cj * n + ci] : 0);
                        if (dedans && lisse[cj * n + ci] > 0) {
                            ps += lisse[cj * n + ci];
                            pn++;
                        }
                    }
                }
                int pr = prof[k];
                double pl = pn > 0 ? ps / pn : 0;
                double o = Math.min(1, dv / (double) FONDU_FOND);
                op[k] = pl > 0 ? Math.max(0, Math.min(1, (pl - 1) / 9.0)) * OPACITE * o * o * (3 - 2 * o) : 0;
                double am = 0;
                if (pr > 0 && dv > 0) {
                    double fx = (double) x / Houle.PAS_NOEUD - nx0, fz = (double) z / Houle.PAS_NOEUD - nz0;
                    int ix = (int) Math.floor(fx), iz = (int) Math.floor(fz);
                    double tx = fx - ix, tz = fz - iz;
                    int q = iz * nnx + ix;
                    am = (noeuds[q] * (1 - tx) * (1 - tz) + noeuds[q + 1] * tx * (1 - tz) + noeuds[q + nnx] * (1 - tx) * tz
                            + noeuds[q + nnx + 1] * tx * tz) * Houle.calmeCote(pr);
                }
                double g = Math.min(1, dv / (double) BORD);
                am *= g * g * (3 - 2 * g);
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
                // 0.3.7 : au bord de la mer, la case déborde un peu (pas de fil de jour contre la côte)
                double xa = x0 - (i > 0 && prof[k00 - 1] > 0 ? 0 : RECOUVRE);
                double xb = x0 + 1 + (prof[k10] > 0 ? 0 : RECOUVRE);
                double za = z0 - (j > 0 && prof[k00 - n - 1] > 0 ? 0 : RECOUVRE);
                double zb = z0 + 1 + (prof[k01] > 0 ? 0 : RECOUVRE);
                sommet(b, m, xa, y0 + h[k00], za, u0, v0, teinte, relief(h[k00], a[k00], ampMax, hx, hz));
                sommet(b, m, xa, y0 + h[k01], zb, u0, v1, teinte, relief(h[k01], a[k01], ampMax, hx, hz));
                sommet(b, m, xb, y0 + h[k11], zb, u1, v1, teinte, relief(h[k11], a[k11], ampMax, hx, hz));
                sommet(b, m, xb, y0 + h[k10], za, u1, v0, teinte, relief(h[k10], a[k10], ampMax, hx, hz));
                // 0.3.7 : l'eau épaisse : la même surface redessinée au même endroit, plus sombre, opacité selon la
                // profondeur (pas de 2e couche décalée sous la houle)
                if (op[k00] + op[k01] + op[k10] + op[k11] > 0.01) {
                    epais(b, m, xa, y0 + h[k00], za, u0, v0, teinte, relief(h[k00], a[k00], ampMax, hx, hz), op[k00]);
                    epais(b, m, xa, y0 + h[k01], zb, u0, v1, teinte, relief(h[k01], a[k01], ampMax, hx, hz), op[k01]);
                    epais(b, m, xb, y0 + h[k11], zb, u1, v1, teinte, relief(h[k11], a[k11], ampMax, hx, hz), op[k11]);
                    epais(b, m, xb, y0 + h[k10], za, u1, v0, teinte, relief(h[k10], a[k10], ampMax, hx, hz), op[k10]);
                }
            }
        }
        Tesselator.getInstance().end();
    }

    /** 0.3.7 : sommet de l'eau épaisse : couleur du biome assombrie (0,8 de l'éclat), opacité alpha. */
    private static void epais(BufferBuilder b, Matrix4f m, double x, double y, double z, float u, float v, int teinte,
                              float[] rel, double alpha) {
        float rr = ((teinte >> 16) & 255) / 255f, gg = ((teinte >> 8) & 255) / 255f, bb = (teinte & 255) / 255f;
        float k = rel[0] * 0.8f, w = rel[1];
        rr = Math.min(1, rr * k * (1 - w) + w);
        gg = Math.min(1, gg * k * (1 - w) + w);
        bb = Math.min(1, bb * k * (1 - w) + w);
        b.vertex(m, (float) x, (float) y, (float) z).uv(u, v).color(rr, gg, bb, (float) alpha).uv2(LUMIERE).endVertex();
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
    private static final float[] RELIEF = new float[2];

    private static float[] relief(double h, double am, double ampMax, double hx, double hz) {
        // poids du relief : nul sur l'eau plate (même couleur que l'eau du jeu au-delà du carré : pas de ligne)
        double w = Math.max(0, Math.min(1, am / ampMax));
        double haut = Math.max(0, Math.min(1, h / (2 * ampMax)));               // 0 = creux, 1 = crête
        double eclat = 1 + w * (0.30 * (haut - 0.5) + 0.45 * (-hx * 0.5 + hz * 0.3));
        double ecume = w * Math.max(0, (haut - 0.78) / 0.22);
        RELIEF[0] = (float) Math.max(0.55, Math.min(1.25, eclat));       // 0.4.1 : sans allocation (dessin seulement)
        RELIEF[1] = (float) (ecume * ecume * 0.55);
        return RELIEF;
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

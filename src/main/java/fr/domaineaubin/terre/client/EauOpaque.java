package fr.domaineaubin.terre.client;

import com.mojang.blaze3d.platform.NativeImage;
import com.mojang.serialization.Codec;
import fr.domaineaubin.terre.DomaineTerre;
import fr.domaineaubin.terre.mixin.client.SpriteSourcesAcces;
import net.minecraft.client.Minecraft;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.client.renderer.texture.SpriteContents;
import net.minecraft.client.renderer.texture.SpriteLoader;
import net.minecraft.client.renderer.texture.atlas.SpriteSource;
import net.minecraft.client.renderer.texture.atlas.SpriteSourceType;
import net.minecraft.core.BlockPos;
import net.minecraft.resources.ResourceKey;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.packs.resources.Resource;
import net.minecraft.server.packs.resources.ResourceManager;
import net.minecraft.tags.FluidTags;
import net.minecraft.util.Mth;
import net.minecraft.world.level.BlockAndTintGetter;
import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.material.FluidState;
import net.minecraftforge.client.extensions.common.IClientFluidTypeExtensions;

import java.util.Optional;
import java.util.Set;

/**
 * Eau plus ou moins opaque selon son type et sa profondeur (09/11/2026, demande de Maxime : les eaux boueuses cachent
 * leurs bêtes, l'océan est bleu profond et on n'en voit pas le fond depuis la surface).
 * <p>
 * Le jeu (Forge) et Embeddium demandent la texture de l'eau bloc par bloc, avec sa position (mixins SpritesEau*) :
 * on répond par une variante plus opaque de la texture d'eau du jeu. Les variantes sont fabriquées au chargement des
 * textures (source d'atlas « domaine_terre:eau_opaque ») depuis la texture d'eau active, pack de ressources compris :
 * aucune image n'est livrée avec le mod. Comme c'est l'eau elle-même qui devient opaque, elle cache tout ce qui est
 * dessous de la même façon : le fond, les poissons, les crocodiles.
 */
public final class EauOpaque {
    /** Niveaux d'opacité : 0 = texture du jeu, NIVEAUX = opaque. */
    static final int NIVEAUX = 7;
    private static final ResourceLocation[] IMMOBILE = new ResourceLocation[NIVEAUX + 1];
    private static final ResourceLocation[] COURANTE = new ResourceLocation[NIVEAUX + 1];
    private static final ResourceLocation EAU_IMMOBILE = new ResourceLocation("minecraft", "textures/block/water_still.png");
    private static final ResourceLocation EAU_COURANTE = new ResourceLocation("minecraft", "textures/block/water_flow.png");

    static {
        for (int k = 1; k <= NIVEAUX; k++) {
            IMMOBILE[k] = new ResourceLocation(DomaineTerre.MOD_ID, "block/eau/immobile_" + k);
            COURANTE[k] = new ResourceLocation(DomaineTerre.MOD_ID, "block/eau/courante_" + k);
        }
    }

    /** Terroirs aux grands fleuves boueux (mêmes que FleuveFeature et outils/couleurs_eau.py). */
    private static final Set<String> BOUEUX = Set.of("amazonie", "afrique_tropicale", "asie_sud_est", "chine", "inde",
            "sahara_sahel");

    private EauOpaque() {
    }

    private static boolean inscrit = false;

    /** Inscrit la source d'atlas (constructeur du mod, côté client, avant le premier chargement des textures). */
    public static synchronized void inscrire() {
        if (inscrit) return;
        inscrit = true;
        Source.type = SpriteSourcesAcces.inscrire(DomaineTerre.MOD_ID + ":eau_opaque", Source.CODEC);
    }

    // ---------------------------------------------------------------- les variantes de texture

    /** Source d'atlas : les variantes opaques des textures d'eau (assets/minecraft/atlases/blocks.json). */
    public static final class Source implements SpriteSource {
        static final Source INSTANCE = new Source();
        static final Codec<Source> CODEC = Codec.unit(INSTANCE);
        private static SpriteSourceType type;

        @Override
        public void run(ResourceManager rm, Output sortie) {
            ajouter(rm, sortie, EAU_IMMOBILE, IMMOBILE);
            ajouter(rm, sortie, EAU_COURANTE, COURANTE);
        }

        private static void ajouter(ResourceManager rm, Output sortie, ResourceLocation fichier, ResourceLocation[] noms) {
            Optional<Resource> r = rm.getResource(fichier);
            if (r.isEmpty()) {
                DomaineTerre.LOGGER.warn("Eau opaque : {} introuvable", fichier);
                return;
            }
            Resource res = r.get();
            for (int k = 1; k <= NIVEAUX; k++) {
                ResourceLocation nom = noms[k];
                float t = (float) k / NIVEAUX;
                sortie.add(nom, () -> {
                    SpriteContents c = SpriteLoader.loadSprite(nom, res);
                    if (c != null) opacifier(c.getOriginalImage(), t);
                    return c;
                });
            }
        }

        @Override
        public SpriteSourceType type() {
            return type;
        }
    }

    /** Rapproche l'opacité de chaque pixel de 1 : a' = a + (1 - a) × t (toutes les images de l'animation). */
    static void opacifier(NativeImage im, float t) {
        for (int y = 0; y < im.getHeight(); y++) {
            for (int x = 0; x < im.getWidth(); x++) {
                int c = im.getPixelRGBA(x, y);                   // ABGR
                int a = c >>> 24;
                int b = Math.round(a + (255 - a) * t);
                im.setPixelRGBA(x, y, (c & 0x00FFFFFF) | (Mth.clamp(b, 0, 255) << 24));
            }
        }
    }

    // ---------------------------------------------------------------- le choix, bloc par bloc

    /** Type d'eau d'un biome du mod : 2 boueuse (fleuve des terroirs boueux), 1 mer, 0 claire (lacs, rivières, autres). */
    static int type(ResourceKey<Biome> b) {
        if (b == null || !b.location().getNamespace().equals(DomaineTerre.MOD_ID)) return 0;
        String n = b.location().getPath();
        if (n.startsWith("mer/")) return 1;
        int i = n.indexOf('/');
        if (i > 0 && n.endsWith("/fleuve") && BOUEUX.contains(n.substring(0, i))) return 2;
        return 0;
    }

    /** Niveau d'opacité (0 à NIVEAUX) du bloc d'eau en pos. */
    static int niveau(FluidState s, BlockAndTintGetter l, BlockPos p) {
        if (!s.is(FluidTags.WATER)) return 0;
        return calculer(l, p);
    }

    private static int calculer(BlockAndTintGetter l, BlockPos p) {
        ClientLevel monde = Minecraft.getInstance().level;
        if (monde == null) return 0;
        int type = type(monde.getBiome(p).unwrapKey().orElse(null));
        // profondeur : blocs d'eau sous la surface de ce bloc, lui compris (jusqu'à 16)
        BlockPos.MutableBlockPos q = p.mutable();
        int prof = 0;
        while (prof < 16 && l.getFluidState(q).is(FluidTags.WATER)) {
            prof++;
            q.move(0, -1, 0);
        }
        double t = switch (type) {
            case 2 -> Mth.clamp(0.55 + 0.25 * prof, 0.0, 1.0);    // boueuse : presque opaque dès 1 bloc, opaque à 2
            case 1 -> Mth.clamp((prof - 1) / 9.0, 0.0, 1.0);      // mer : opaque à 10 blocs, bleu profond au large
            default -> Mth.clamp((prof - 2) / 18.0, 0.0, 0.85);   // claire : on voit loin, jamais tout à fait opaque
        };
        return (int) Math.round(t * NIVEAUX);
    }

    /** Texture immobile de l'eau en pos (appelé à la place de getStillTexture par Forge et Embeddium). */
    public static ResourceLocation immobile(IClientFluidTypeExtensions ext, FluidState s, BlockAndTintGetter l, BlockPos p) {
        ResourceLocation r = ext.getStillTexture(s, l, p);
        int k = niveau(s, l, p);
        return k == 0 ? r : IMMOBILE[k];
    }

    /** Texture courante de l'eau en pos (appelé à la place de getFlowingTexture). */
    public static ResourceLocation courante(IClientFluidTypeExtensions ext, FluidState s, BlockAndTintGetter l, BlockPos p) {
        ResourceLocation r = ext.getFlowingTexture(s, l, p);
        int k = niveau(s, l, p);
        return k == 0 ? r : COURANTE[k];
    }

    // ---------------------------------------------------------------- sous l'eau : distance de vue par type d'eau

    /** Distance de vue sous l'eau (blocs) selon le type d'eau où est la caméra, ou NaN (pas de règle). */
    static double visibilite(ClientLevel monde, BlockPos p) {
        return switch (type(monde.getBiome(p).unwrapKey().orElse(null))) {
            case 2 -> 3.5;                                        // boueuse : on voit à peine ses mains
            case 1 -> Mth.lerp(Mth.clamp((63.0 - p.getY()) / 40.0, 0.0, 1.0), 28.0, 16.0);   // mer
            default -> Double.NaN;                                // claire : le jeu décide
        };
    }
}

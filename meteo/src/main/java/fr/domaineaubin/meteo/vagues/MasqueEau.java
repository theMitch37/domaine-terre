package fr.domaineaubin.meteo.vagues;

import net.minecraft.client.Minecraft;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.core.BlockPos;
import net.minecraft.tags.FluidTags;
import net.minecraft.world.level.BlockAndTintGetter;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.material.FluidState;

/**
 * Surface plate du jeu masquée en mer (0.3.0) : le dessus des blocs d'eau au niveau de la mer, dans un biome de mer,
 * avec de l'air au-dessus, n'est plus dessiné par le jeu ; Domaine Weather dessine la mer à sa place (vagues près du
 * joueur, surface plate texturée plus loin). Appelé pendant la construction des chunks (jeu de base et Embeddium).
 * Mêmes conditions que {@link Houle#profondeur} : ce qui est masqué est exactement ce que l'on dessine.
 */
public final class MasqueEau {
    private MasqueEau() {
    }

    public static boolean masquer(BlockAndTintGetter region, int x, int y, int z) {
        if (!Houle.actif()) return false;
        ClientLevel level = Minecraft.getInstance().level;
        if (level == null || level.dimension() != Level.OVERWORLD || y != level.getSeaLevel() - 1) return false;
        try {
            FluidState f = region.getFluidState(new BlockPos(x, y, z));
            if (!f.is(FluidTags.WATER) || !f.isSource()) return false;
            if (!region.getBlockState(new BlockPos(x, y + 1, z)).isAir()) return false;
            return Houle.mer(level, x, y, z);
        } catch (RuntimeException e) {
            return false;
        }
    }

    /** Reconstruire tous les chunks (vagues coupées ou rallumées). */
    public static void rafraichir() {
        Minecraft mc = Minecraft.getInstance();
        mc.execute(() -> {
            if (mc.levelRenderer != null) mc.levelRenderer.allChanged();
            RenduVagues.oublier();
        });
    }
}

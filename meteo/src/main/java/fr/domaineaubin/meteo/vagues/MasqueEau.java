package fr.domaineaubin.meteo.vagues;

import net.minecraft.client.Minecraft;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.core.BlockPos;
import net.minecraft.tags.FluidTags;
import net.minecraft.world.level.BlockAndTintGetter;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.material.FluidState;

/**
 * Surface plate du jeu masquée en mer (0.3.1) : près du joueur, le dessus des blocs d'eau au niveau de la mer, dans un
 * biome de mer, avec de l'air au-dessus, n'est plus dessiné par le jeu ; Domaine Weather y dessine la houle. Plus loin,
 * l'eau du jeu reste (0.3.0 dessinait une surface plate à nous jusqu'à la distance de vue : elle ne s'affichait pas). Appelé pendant la construction des chunks (jeu de base et Embeddium).
 * Mêmes conditions que {@link Houle#profondeur} : ce qui est masqué est exactement ce que l'on dessine.
 */
public final class MasqueEau {
    private MasqueEau() {
    }

    /** Carré de chunks masqués autour du joueur (centre, demi-côté) ; « pret » faux : rien de masqué. */
    private static volatile int centreX, centreZ, demi;
    private static volatile boolean pret;

    /**
     * Le masque suit le joueur : seuls les chunks proches (où l'on dessine la mer) perdent leur surface plate ; plus
     * loin, l'eau du jeu (ou du shader) reste. Quand le joueur change de chunk, on fait reconstruire la bande de chunks
     * qui entre ou sort du carré (une seule tranche de 16 blocs de haut par chunk : celle du niveau de la mer).
     */
    public static void suivre(ClientLevel level, int cx, int cz, int nouveauDemi) {
        if (pret && cx == centreX && cz == centreZ && nouveauDemi == demi) return;
        boolean avant = pret;
        int ax = centreX, az = centreZ, ad = demi;
        centreX = cx;
        centreZ = cz;
        demi = nouveauDemi;
        pret = true;
        Minecraft mc = Minecraft.getInstance();
        int sy = (level.getSeaLevel() - 1) >> 4;
        int m = Math.max(ad, nouveauDemi);
        int x0 = Math.min(avant ? ax : cx, cx) - m, x1 = Math.max(avant ? ax : cx, cx) + m;
        int z0 = Math.min(avant ? az : cz, cz) - m, z1 = Math.max(avant ? az : cz, cz) + m;
        for (int x = x0; x <= x1; x++) {
            for (int z = z0; z <= z1; z++) {
                boolean dansAvant = avant && Math.abs(x - ax) <= ad && Math.abs(z - az) <= ad;
                boolean dansApres = Math.abs(x - cx) <= nouveauDemi && Math.abs(z - cz) <= nouveauDemi;
                if (dansAvant != dansApres) mc.levelRenderer.setSectionDirty(x, sy, z);
            }
        }
    }

    public static void oublier() {
        pret = false;
    }

    public static boolean dansCarre(int x, int z) {
        return pret && Math.abs((x >> 4) - centreX) <= demi && Math.abs((z >> 4) - centreZ) <= demi;
    }

    public static boolean masquer(BlockAndTintGetter region, int x, int y, int z) {
        if (!Houle.actif() || !dansCarre(x, z)) return false;
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
            pret = false;                                  // le carré sera remis (et reconstruit) à la prochaine image
            if (mc.levelRenderer != null) mc.levelRenderer.allChanged();
        });
    }
}

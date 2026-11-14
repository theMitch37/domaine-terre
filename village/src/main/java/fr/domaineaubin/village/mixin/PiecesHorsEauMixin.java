package fr.domaineaubin.village.mixin;

import fr.domaineaubin.terre.monde.Terrain;
import fr.domaineaubin.village.Points;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.shapes.BooleanOp;
import net.minecraft.world.phys.shapes.Shapes;
import net.minecraft.world.phys.shapes.VoxelShape;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Redirect;

/**
 * Aucune pièce de surface sur l'eau (Domaine Village 0.1.1, 14/11/2026) : dans un monde Terre, quand une structure en
 * pièces (village, avant-poste…) essaie de poser une pièce, l'eau d'un fleuve, d'un lac ou de la mer sous son emprise
 * compte comme un obstacle : le jeu essaie une autre pièce ou ferme la rue. Le village reste à la place de la vraie
 * ville (Paris garde son centre) et se construit sur les rives ; les ponts viendront plus tard.
 *
 * L'eau est lue sur la carte du mod Terre (pas de calcul du terrain : rapide). Les pièces enterrées (cités antiques,
 * plus de 8 blocs sous le sol) ne sont pas concernées.
 */
@Mixin(targets = "net.minecraft.world.level.levelgen.structure.pools.JigsawPlacement$Placer")
public abstract class PiecesHorsEauMixin {
    /** Pour le banc : -DdomaineVillage.eau=non rend le comportement d'avant (comparaison avant / après). */
    private static final boolean ACTIF = !"non".equals(System.getProperty("domaineVillage.eau"));

    @Redirect(method = "tryPlacingChildren", at = @At(value = "INVOKE",
            target = "Lnet/minecraft/world/phys/shapes/Shapes;joinIsNotEmpty(Lnet/minecraft/world/phys/shapes/VoxelShape;Lnet/minecraft/world/phys/shapes/VoxelShape;Lnet/minecraft/world/phys/shapes/BooleanOp;)Z"))
    private boolean domaineVillage$eauObstacle(VoxelShape libre, VoxelShape piece, BooleanOp op) {
        if (Shapes.joinIsNotEmpty(libre, piece, op)) return true;            // obstacle du jeu : inchangé
        if (!ACTIF || !Points.terre || piece.isEmpty()) return false;
        AABB b = piece.bounds();
        return surEau((int) Math.floor(b.minX), (int) Math.floor(b.minY), (int) Math.floor(b.minZ),
                (int) Math.ceil(b.maxX) - 1, (int) Math.ceil(b.maxZ) - 1);
    }

    /** Vrai si un point de l'emprise (grille de 3 blocs, bords compris) est sur l'eau, pour une pièce de surface. */
    private static boolean surEau(int x0, int y0, int z0, int x1, int z1) {
        Terrain t = Terrain.get();
        double solMilieu = t.hauteur((x0 + x1) >> 1, (z0 + z1) >> 1);
        if (y0 < solMilieu - 8) return false;                                 // pièce enterrée
        for (int x = x0; ; x = Math.min(x + 3, x1)) {
            for (int z = z0; ; z = Math.min(z + 3, z1)) {
                if (eau(t, x, z)) return true;
                if (z >= z1) break;
            }
            if (x >= x1) break;
        }
        return false;
    }

    private static boolean eau(Terrain t, int x, int z) {
        if (t.eauDeFleuve(x, z) || t.eauDeLac(x, z)) return true;
        return t.enMer(x, z) && t.hauteur(x, z) < Terrain.NIVEAU_MER - 1;
    }
}

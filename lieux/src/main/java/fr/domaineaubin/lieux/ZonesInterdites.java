package fr.domaineaubin.lieux;

import fr.domaineaubin.terre.api.Lieu;
import fr.domaineaubin.terre.api.LieuxTerre;
import net.minecraft.core.BlockPos;
import net.minecraft.world.level.levelgen.structure.Structure;
import net.minecraft.world.level.levelgen.structure.structures.JigsawStructure;

/**
 * Structures interdites sur les lieux (décision du 25/10, à revoir avec la mise à jour des structures).
 * Le point de départ d'une structure doit être à plus de MARGE blocs de la zone d'un lieu : les villages
 * (structures « jigsaw ») s'étalent loin de leur point de départ, d'où une marge plus grande.
 */
public final class ZonesInterdites {
    private static final int MARGE_JIGSAW = 96, MARGE = 40;

    private ZonesInterdites() {
    }

    public static boolean interdit(Structure structure, BlockPos depart) {
        if (LieuxTerre.liste().isEmpty()) return false;
        int m = structure instanceof JigsawStructure ? MARGE_JIGSAW : MARGE;
        int x = depart.getX(), z = depart.getZ();
        for (Lieu l : LieuxTerre.liste()) {
            for (int dx = -m; dx <= m; dx += m) {
                for (int dz = -m; dz <= m; dz += m) {
                    if (l.concerne(x + dx, z + dz) && l.poids(x + dx, z + dz) > 0.05) return true;
                }
            }
            // entre les points de test, pour les lieux étroits
            for (int dx = -m / 2; dx <= m / 2; dx += m / 2) {
                for (int dz = -m / 2; dz <= m / 2; dz += m / 2) {
                    if (l.concerne(x + dx, z + dz) && l.poids(x + dx, z + dz) > 0.05) return true;
                }
            }
        }
        return false;
    }
}

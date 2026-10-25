package fr.domaineaubin.lieux;

import fr.domaineaubin.terre.api.Lieu;
import net.minecraft.world.level.block.state.BlockState;

/**
 * Lieu dont les parois sont sculptées bloc par bloc et colorées en couches par {@link StratesFeature}.
 * Le bruit vanilla étant interpolé tous les 4 blocs, les falaises nettes ne s'obtiennent qu'ainsi.
 */
public interface LieuSculpte extends Lieu {

    /** y du rebord (sommet des couches) si la colonne fait partie des parois ou du fond, sinon NaN. */
    double rebordSiParoi(int x, int z);

    /**
     * Hauteur exacte du sol (y) pour la sculpture, ou NaN si la colonne n'est pas taillée.
     * Ne répondre que pour les colonnes vraiment taillées : ailleurs, le sol arrondi par Minecraft fait des murets.
     */
    double hauteurNette(int x, int z);

    /** Bloc de la paroi à la hauteur y (sous le rebord). */
    BlockState strate(int x, int y, int z, double rebord);

    /**
     * Bloc du dessus d'une colonne taillée (vires herbeuses…). Par défaut, le même que {@link #strate}.
     */
    default BlockState sommet(int x, int y, int z, double rebord) {
        return strate(x, y, z, rebord);
    }

    /**
     * Garder ce bloc de terre (herbe, terre) au lieu de le recolorer ?
     * @param taillee la colonne a-t-elle été taillée par la sculpture
     * @param sommet  y du dessus de la colonne
     * Par défaut : la terre des 2 blocs sous le rebord (le plateau garde son sol).
     */
    default boolean garderSol(int y, double rebord, int sommet, boolean taillee) {
        return y >= rebord - 2;
    }

    /** y le plus bas recoloré. */
    int fondStrates();

    /** y le plus bas sculpté (en dessous, le lit et les lacs restent ceux du terrain, remplis par l'aquifère). */
    default int sculpteMin() {
        return 64;
    }
}

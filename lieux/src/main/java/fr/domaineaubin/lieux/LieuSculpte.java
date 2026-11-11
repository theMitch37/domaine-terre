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

    /**
     * Hauteur (y) jusqu'à laquelle combler une colonne NON taillée, sans jamais la creuser, ou NaN.
     * Minecraft calcule le terrain tous les 4 blocs puis interpole : au bord d'une falaise verticale, le plateau
     * est arrondi vers le bas sur 2-3 blocs et la roche brute apparaît. On ne comble qu'au-delà d'un bloc d'écart
     * (sinon des murets d'un bloc).
     */
    default double remblai(int x, int z) {
        return Double.NaN;
    }

    /**
     * Zone protégée du hasard vanilla : aucun vide (grotte, ravin, poche d'eau) n'y est laissé sous la surface visée.
     * Par défaut : le biome du lieu, là où le lieu tient entièrement le terrain.
     */
    default boolean protege(int x, int z) {
        return dansBiome(x, z) && poids(x, z) > 0.9;
    }

    /** Bloc de la paroi à la hauteur y (sous le rebord). */
    BlockState strate(int x, int y, int z, double rebord);

    /**
     * Bloc du dessus d'une colonne taillée (vires herbeuses…). Par défaut, le même que {@link #strate}.
     */
    default BlockState sommet(int x, int y, int z, double rebord) {
        return strate(x, y, z, rebord);
    }

    /**
     * Abords (hors des parois) : bloc de surface de cette colonne à la hauteur y, pour une transition vers le terrain
     * autour (Grand Canyon : taches de terre cuite et de sable rouge vers le désert), ou null pour garder le sol.
     */
    default BlockState abords(int x, int y, int z) {
        return null;
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

    /**
     * Blocs en surplomb (arches…) que le relief, une hauteur par colonne, ne peut pas décrire.
     * Appelé une fois par chunk qui touche le lieu, après la sculpture ; ne poser que dans ce chunk.
     */
    default void poser(net.minecraft.world.level.WorldGenLevel niveau, int x0, int z0) {
    }

    /** y le plus bas recoloré. */
    int fondStrates();

    /** y le plus bas sculpté (en dessous, le lit et les lacs restent ceux du terrain, remplis par l'aquifère). */
    default int sculpteMin() {
        return 64;
    }
}

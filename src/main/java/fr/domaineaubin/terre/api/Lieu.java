package fr.domaineaubin.terre.api;

import net.minecraft.resources.ResourceLocation;

/**
 * Un lieu unique (Grand Canyon, Niagara…) fourni par un addon.
 * Les coordonnées sont en blocs ; utiliser {@link fr.domaineaubin.terre.monde.Terrain#x(double)} et
 * {@link fr.domaineaubin.terre.monde.Terrain#z(double)} pour passer des longitudes/latitudes aux blocs.
 * Toutes les méthodes sont appelées par plusieurs threads de génération en même temps : pas d'état modifiable.
 */
public interface Lieu {
    /** Identifiant court, ex. « grand_canyon ». */
    String id();

    /** Biome unique du lieu (doit exister dans le registre des biomes, fourni par l'addon). */
    ResourceLocation biome();

    /** Test rapide : la colonne est-elle dans la zone d'influence du lieu (relief compris) ? */
    boolean concerne(int x, int z);

    /**
     * Hauteur visée du sol (en y) une fois le lieu sculpté.
     * @param h hauteur calculée par le mod Terre (relief réel et fleuves compris)
     */
    double hauteur(int x, int z, double h);

    /** La colonne porte-t-elle le biome du lieu en surface ? */
    boolean dansBiome(int x, int z);

    /**
     * Hauteur (y) au-dessus de laquelle le biome du lieu s'applique dans une colonne {@link #dansBiome}.
     * Par défaut 16 blocs sous le sol (les grottes gardent leurs biomes). Un lieu très en relief (canyon)
     * peut descendre plus bas pour couvrir toutes ses parois.
     * @param hauteur hauteur visée du sol dans cette colonne
     */
    default double basBiome(int x, int z, double hauteur) {
        return hauteur - 16.0;
    }

    /**
     * L'aquifère doit-il prendre le niveau de la mer dans cette colonne (fleuve, lac du lieu) ?
     * L'aquifère vanilla décide par cases de 16 blocs : un lieu dont l'eau est étroite (fleuve au fond d'un
     * canyon) doit répondre oui sur une bande large autour, sinon le lit reste à sec par endroits.
     * Par défaut : seulement là où le sol est sous le niveau de la mer.
     */
    default boolean inonde(int x, int z, double hauteur) {
        return hauteur < 67.0;
    }
}

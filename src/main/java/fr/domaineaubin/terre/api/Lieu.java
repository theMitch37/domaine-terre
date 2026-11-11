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

    /**
     * Emprise du lieu dans cette colonne, de 0 (terrain du mod intact) à 1 (le terrain suit exactement {@link #hauteur}).
     * Doit passer progressivement de 1 à 0 vers les bords : sinon le relief libre du mod reprend d'un coup et on voit
     * le rectangle des données du lieu. Par défaut 1 sur toute la zone {@link #concerne}.
     */
    default double poids(int x, int z) {
        return 1.0;
    }

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

    /**
     * Eau propre au lieu dans cette colonne (lot 2 : torrents, lacs et bassins en altitude) : niveau de l'eau (elle
     * remplit y &lt; niveau), ou {@link Integer#MIN_VALUE} pour aucune. Posée comme le lit d'un cours d'eau
     * (FleuveFeature, sans aquifère) : là où une colonne d'eau touche une colonne d'eau plus basse, l'eau déborde et
     * tombe (cascade). Par défaut : aucune.
     */
    default int eau(int x, int z) {
        return Integer.MIN_VALUE;
    }

    /**
     * Le lieu gère lui-même le cours d'eau du mod qui le traverse (Grand Canyon, Verdon : son lit et son niveau). Sinon
     * (12/11/2026, test en jeu : « une immense cascade » en Valais, la zone du Cervin gardait le Rhône à son niveau
     * d'avant le relief fin, 95 blocs au-dessus du Rhône du mod juste à côté), là où le lieu pose de l'eau dans le lit
     * d'un cours d'eau du mod à un autre niveau, la colonne revient au mod. Par défaut : non.
     */
    default boolean gereSesCoursDEau() {
        return false;
    }
}

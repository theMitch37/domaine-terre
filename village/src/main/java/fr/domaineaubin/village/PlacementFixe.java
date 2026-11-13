package fr.domaineaubin.village;

import com.mojang.serialization.Codec;
import com.mojang.serialization.codecs.RecordCodecBuilder;
import fr.domaineaubin.terre.api.LieuxTerre;
import net.minecraft.core.Vec3i;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.chunk.ChunkGeneratorStructureState;
import net.minecraft.world.level.levelgen.structure.placement.RandomSpreadStructurePlacement;
import net.minecraft.world.level.levelgen.structure.placement.RandomSpreadType;
import net.minecraft.world.level.levelgen.structure.placement.StructurePlacement;
import net.minecraft.world.level.levelgen.structure.placement.StructurePlacementType;

import java.util.Optional;

/**
 * Placement à emplacements fixes (Domaine Village 0.1, 13/11/2026).
 *
 * Dans un monde Terre, une structure ne peut naître qu'aux points d'une liste fixe (ex. les villages tirés des vraies
 * villes) : la carte est découpée en cases de 32 chunks (512 blocs), au plus un point par case. Deux mondes ont donc les
 * mêmes villages. /locate fonctionne (il parcourt les cases). Jamais dans un lieu unique.
 *
 * Hors monde Terre, c'est le placement vanilla (même espacement, même sel) : rien ne change.
 *
 * Liste « *hasard » : placement vanilla au hasard, mais seulement dans un monde Terre (ex. quelques épaves le long des
 * côtes, en plus des cimetières de navires).
 */
public class PlacementFixe extends RandomSpreadStructurePlacement {
    /** Champs du placement vanilla (sans spread_type : toujours linéaire) + « liste » ; cases de {@link #CASE} chunks. */
    public static final Codec<PlacementFixe> CODEC = RecordCodecBuilder.create(i -> placementCodec(i).and(i.group(
            Codec.intRange(0, 4096).fieldOf("spacing").forGetter(PlacementFixe::spacingVanilla),
            Codec.intRange(0, 4096).fieldOf("separation").forGetter(RandomSpreadStructurePlacement::separation),
            Codec.STRING.fieldOf("liste").forGetter(p -> p.liste)
    )).apply(i, PlacementFixe::new));

    /** Taille d'une case (chunks) : 32 = 512 blocs, le maillage des villages validé par Maxime. */
    public static final int CASE = 32;

    private final String liste;
    private final int taille = CASE;
    private final int spacingVanilla;

    public PlacementFixe(Vec3i decalage, StructurePlacement.FrequencyReductionMethod methode, float frequence, int sel,
                         Optional<StructurePlacement.ExclusionZone> exclusion, int espacement, int separation,
                         String liste) {
        super(decalage, methode, frequence, sel, exclusion, espacement, separation, RandomSpreadType.LINEAR);
        this.spacingVanilla = espacement;
        this.liste = liste;
    }

    int spacingVanilla() {
        return spacingVanilla;
    }

    private boolean hasard() {
        return liste.startsWith("*");
    }

    @Override
    public int spacing() {
        return Points.terre && !hasard() ? taille : spacingVanilla;
    }

    @Override
    public ChunkPos getPotentialStructureChunk(long graine, int x, int z) {
        if (!Points.terre || hasard()) return super.getPotentialStructureChunk(graine, x, z);
        int cx = Math.floorDiv(x, taille), cz = Math.floorDiv(z, taille);
        ChunkPos p = Points.liste(liste, taille).get(Points.cle(cx, cz));
        return p != null ? p : new ChunkPos(cx * taille, cz * taille);     // case vide : coin de la case (refusé plus bas)
    }

    @Override
    protected boolean isPlacementChunk(ChunkGeneratorStructureState etat, int x, int z) {
        if (hasard()) return Points.terre && super.isPlacementChunk(etat, x, z);
        if (!Points.terre) return super.isPlacementChunk(etat, x, z);
        ChunkPos p = Points.liste(liste, taille).get(Points.cle(Math.floorDiv(x, taille), Math.floorDiv(z, taille)));
        if (p == null || p.x != x || p.z != z) return false;
        int bx = (x << 4) + 8, bz = (z << 4) + 8;
        for (int dx = -64; dx <= 64; dx += 64)
            for (int dz = -64; dz <= 64; dz += 64)
                if (LieuxTerre.a(bx + dx, bz + dz) != null) return false;      // jamais dans un lieu unique
        return true;
    }

    @Override
    public StructurePlacementType<?> type() {
        return DomaineVillage.FIXE.get();
    }
}

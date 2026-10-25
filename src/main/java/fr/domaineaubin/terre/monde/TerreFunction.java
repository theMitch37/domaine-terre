package fr.domaineaubin.terre.monde;

import com.mojang.serialization.Codec;
import com.mojang.serialization.codecs.RecordCodecBuilder;
import net.minecraft.util.KeyDispatchDataCodec;
import net.minecraft.util.StringRepresentable;
import net.minecraft.world.level.levelgen.DensityFunction;

/**
 * Fonction de densité « domaine_terre:terre » utilisable dans les fichiers JSON de génération.
 * Exemple : {"type": "domaine_terre:terre", "sortie": "offset"}
 */
public record TerreFunction(Sortie sortie) implements DensityFunction.SimpleFunction {

    public static final KeyDispatchDataCodec<TerreFunction> CODEC = KeyDispatchDataCodec.of(
            RecordCodecBuilder.mapCodec(i -> i.group(
                    Sortie.CODEC.fieldOf("sortie").forGetter(TerreFunction::sortie)
            ).apply(i, TerreFunction::new)));

    @Override
    public double compute(DensityFunction.FunctionContext ctx) {
        Terrain t = Terrain.get();
        int x = ctx.blockX();
        int z = ctx.blockZ();
        return switch (sortie) {
            case OFFSET -> t.offset(x, z);
            case FACTOR -> t.facteur(x, z);
            case JAGGEDNESS -> t.dentelure(x, z);
            case CONTINENTS -> t.continents(x, z);
            case EROSION -> t.erosion(x, z);
            case INONDATION -> t.inondation(x, z);
            case PLAFOND -> t.plafond(x, ctx.blockY(), z);
            case PLANCHER -> t.plancher(x, ctx.blockY(), z);
        };
    }

    @Override
    public double minValue() {
        return sortie.min;
    }

    @Override
    public double maxValue() {
        return sortie.max;
    }

    @Override
    public KeyDispatchDataCodec<? extends DensityFunction> codec() {
        return CODEC;
    }

    public enum Sortie implements StringRepresentable {
        OFFSET("offset", -1.0, 1.5),
        FACTOR("factor", 0.0, 30.0),
        JAGGEDNESS("jaggedness", 0.0, 1.0),
        CONTINENTS("continents", -1.1, 0.5),
        EROSION("erosion", -1.0, 1.0),
        INONDATION("inondation", 0.0, 2.0),
        PLAFOND("plafond", -1.0, 1.0),
        PLANCHER("plancher", -1.0, 0.5);

        public static final Codec<Sortie> CODEC = StringRepresentable.fromEnum(Sortie::values);

        private final String nom;
        final double min;
        final double max;

        Sortie(String nom, double min, double max) {
            this.nom = nom;
            this.min = min;
            this.max = max;
        }

        @Override
        public String getSerializedName() {
            return nom;
        }
    }
}

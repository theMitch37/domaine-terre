package fr.domaineaubin.terre.monde;

import com.mojang.serialization.codecs.RecordCodecBuilder;
import net.minecraft.util.KeyDispatchDataCodec;
import net.minecraft.util.Mth;
import net.minecraft.world.level.levelgen.DensityFunction;

/**
 * Fin de la densité du monde Terre en une seule fonction (10/11/2026, génération plus rapide) :
 * min(max(min(terrain, max(grottes vanilla, masque des grottes)), plancher), plafond).
 * Avant : trois fonctions domaine_terre:terre (grottes, plancher, plafond) appelées pour chaque bloc, chacune avec sa
 * recherche de colonne (profil du banc, monde agrandi : ~10 % du temps). Ici : les masques d'une colonne sont calculés
 * une fois (Terrain.masques) et gardés dans une petite mémoire propre à cette copie de la fonction ; le jeu en refait
 * une copie pour chaque chunk généré (mapAll), utilisée par un seul fil. Les grottes vanilla ne sont pas calculées là
 * où le masque est plein. Mêmes blocs qu'avant.
 * JSON : {"type": "domaine_terre:masques", "terrain": ..., "grottes": ...}
 */
public final class MasquesFunction implements DensityFunction {
    public static final KeyDispatchDataCodec<MasquesFunction> CODEC = KeyDispatchDataCodec.of(
            RecordCodecBuilder.mapCodec(i -> i.group(
                    DensityFunction.HOLDER_HELPER_CODEC.fieldOf("terrain").forGetter(MasquesFunction::terrain),
                    DensityFunction.HOLDER_HELPER_CODEC.fieldOf("grottes").forGetter(MasquesFunction::grottes)
            ).apply(i, MasquesFunction::new)));

    /** Bas des grottes : comme Terrain.grottes (fond arrondi de y -60 à -44). */
    private static final double FOND = -52.0;

    private final DensityFunction terrain, grottes;
    // mémoire par colonne (16 x 16), propre à cette copie
    private final int[] cx = new int[256], cz = new int[256];
    private final boolean[] plein = new boolean[256];
    private final double[] val = new double[256 * 4];
    private final double[] tmp = new double[4];
    /** Fil qui a fait cette copie : la mémoire ne sert qu'à lui (une copie partagée calcule sans mémoire). */
    private final Thread fil = Thread.currentThread();

    public MasquesFunction(DensityFunction terrain, DensityFunction grottes) {
        this.terrain = terrain;
        this.grottes = grottes;
    }

    public DensityFunction terrain() {
        return terrain;
    }

    public DensityFunction grottes() {
        return grottes;
    }

    private int colonne(int x, int z) {
        int i = ((z & 15) << 4) | (x & 15);
        if (!plein[i] || cx[i] != x || cz[i] != z) {
            Terrain.get().masques(x, z, tmp);
            System.arraycopy(tmp, 0, val, i * 4, 4);
            cx[i] = x;
            cz[i] = z;
            plein[i] = true;
        }
        return i * 4;
    }

    @Override
    public double compute(FunctionContext ctx) {
        double[] val = this.val;
        int k;
        if (Thread.currentThread() == fil) {
            k = colonne(ctx.blockX(), ctx.blockZ());
        } else {
            val = new double[4];
            Terrain.get().masques(ctx.blockX(), ctx.blockZ(), val);
            k = 0;
        }
        int y = ctx.blockY();
        double g = Math.max(Mth.clamp((FOND - y) / 8.0, -1.0, 1.0), Mth.clamp((y - val[k]) / 8.0, -1.0, 1.0));
        double t = terrain.compute(ctx);
        double m = g >= 1.0 ? Math.min(t, 1.0) : Math.min(t, Math.max(grottes.compute(ctx), g));
        double plancher = y <= val[k + 1] && y >= val[k + 2] ? 0.5 : -1.0;
        double plafond = val[k + 3] >= 1.0 || y <= Terrain.PLAFOND_MER ? 1.0 : -20.0;
        return Math.min(Math.max(m, plancher), plafond);
    }

    @Override
    public void fillArray(double[] tab, ContextProvider ctx) {
        ctx.fillAllDirectly(tab, this);
    }

    @Override
    public DensityFunction mapAll(Visitor v) {
        return v.apply(new MasquesFunction(terrain.mapAll(v), grottes.mapAll(v)));
    }

    @Override
    public double minValue() {
        return -20.0;
    }

    @Override
    public double maxValue() {
        return Math.max(1.0, terrain.maxValue());
    }

    @Override
    public KeyDispatchDataCodec<? extends DensityFunction> codec() {
        return CODEC;
    }
}

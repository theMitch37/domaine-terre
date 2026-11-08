package fr.domaineaubin.terre.monde;

import com.mojang.serialization.Codec;
import fr.domaineaubin.terre.api.Lieu;
import fr.domaineaubin.terre.api.LieuxTerre;
import net.minecraft.core.BlockPos;
import net.minecraft.world.level.WorldGenLevel;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.levelgen.feature.Feature;
import net.minecraft.world.level.levelgen.feature.FeaturePlaceContext;
import net.minecraft.world.level.levelgen.feature.configurations.NoneFeatureConfiguration;

/**
 * Mer des lieux (08/11/2026) : dans les colonnes inondées d'un lieu, rien ne flotte au-dessus du fond voulu. Autour de
 * Capri, des bancs de sable et de gravier restaient suspendus jusqu'à 15 blocs au-dessus du fond, sur un tiers de la
 * zone (en mer, le biome n'est pas celui du lieu : sa propre feature n'y passe pas). Avant la végétation.
 */
public class MerDesLieuxFeature extends Feature<NoneFeatureConfiguration> {
    public MerDesLieuxFeature(Codec<NoneFeatureConfiguration> codec) {
        super(codec);
    }

    @Override
    public boolean place(FeaturePlaceContext<NoneFeatureConfiguration> ctx) {
        if (LieuxTerre.liste().isEmpty()) return false;
        WorldGenLevel niveau = ctx.level();
        int x0 = ctx.origin().getX() & ~15, z0 = ctx.origin().getZ() & ~15;
        Terrain t = Terrain.get();
        BlockPos.MutableBlockPos p = new BlockPos.MutableBlockPos();
        boolean modifie = false;
        for (int dx = 0; dx < 16; dx++) {
            for (int dz = 0; dz < 16; dz++) {
                int x = x0 + dx, z = z0 + dz;
                Lieu l = LieuxTerre.a(x, z);
                if (l == null) continue;
                double fond = t.hauteur(x, z);
                if (fond >= 60 || !l.inonde(x, z, fond)) continue;
                for (int y = (int) Math.floor(fond) + 2; y <= Terrain.NIVEAU_MER - 1; y++) {
                    BlockState b = niveau.getBlockState(p.set(x, y, z));
                    if (!b.isAir() && !b.is(Blocks.WATER)) {
                        niveau.setBlock(p, Blocks.WATER.defaultBlockState(), 2);
                        modifie = true;
                    }
                }
            }
        }
        return modifie;
    }
}

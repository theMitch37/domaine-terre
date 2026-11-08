package fr.domaineaubin.terre.monde;

import com.mojang.serialization.Codec;
import net.minecraft.core.BlockPos;
import net.minecraft.tags.FluidTags;
import net.minecraft.util.RandomSource;
import net.minecraft.util.random.WeightedRandom;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.entity.MobSpawnType;
import net.minecraft.world.level.WorldGenLevel;
import net.minecraft.world.level.biome.MobSpawnSettings;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.levelgen.Heightmap;
import net.minecraft.world.level.levelgen.feature.Feature;
import net.minecraft.world.level.levelgen.feature.FeaturePlaceContext;
import net.minecraft.world.level.levelgen.feature.configurations.NoneFeatureConfiguration;

import java.util.ArrayList;
import java.util.List;

/**
 * Bêtes des rives (08/11/2026) : à la génération, un chunk sur deux qui a une berge d'eau douce reçoit un groupe
 * d'animaux des rives de sa région (FauneTerre.rives : crocodiles du Nil, loutres, tortues…), posé sur la berge.
 */
public class RivesFeature extends Feature<NoneFeatureConfiguration> {
    public RivesFeature(Codec<NoneFeatureConfiguration> codec) {
        super(codec);
    }

    @Override
    public boolean place(FeaturePlaceContext<NoneFeatureConfiguration> ctx) {
        WorldGenLevel n = ctx.level();
        RandomSource r = ctx.random();
        if (r.nextInt(2) != 0) return false;
        int x0 = ctx.origin().getX() & ~15, z0 = ctx.origin().getZ() & ~15;
        if (!FauneTerre.get().active() || !FauneTerre.eauDansChunk(x0, z0)) return false;
        if (n.getHeight(Heightmap.Types.OCEAN_FLOOR_WG, x0 + 8, z0 + 8) < Terrain.NIVEAU_MER - 40) return false;
        List<BlockPos> rives = new ArrayList<>();
        BlockPos.MutableBlockPos v = new BlockPos.MutableBlockPos();
        for (int k = 0; k < 40 && rives.size() < 8; k++) {
            int x = x0 + r.nextInt(16), z = z0 + r.nextInt(16);
            int y = n.getHeight(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES, x, z);
            BlockState sol = n.getBlockState(v.set(x, y - 1, z));
            if (!sol.isSolid() || !sol.getFluidState().isEmpty() || !n.isEmptyBlock(v.set(x, y, z))
                    || !n.isEmptyBlock(v.set(x, y + 1, z))) continue;
            if (eauDouceProche(n, v, x, y, z)) rives.add(new BlockPos(x, y, z));
        }
        if (rives.isEmpty()) return false;
        BlockPos c = rives.get(0);
        List<MobSpawnSettings.SpawnerData> l = FauneTerre.get().rives(c.getX(), c.getZ());
        if (l.isEmpty()) return false;
        MobSpawnSettings.SpawnerData d = WeightedRandom.getRandomItem(r, l).orElse(null);
        if (d == null) return false;
        int nb = d.minCount + r.nextInt(1 + d.maxCount - d.minCount);
        boolean pose = false;
        for (int i = 0; i < nb; i++) {
            BlockPos p = rives.get(i % rives.size());
            Entity e = d.type.create(n.getLevel());
            if (!(e instanceof Mob m)) continue;
            m.moveTo(p.getX() + 0.5, p.getY(), p.getZ() + 0.5, r.nextFloat() * 360f, 0f);
            m.finalizeSpawn(n, n.getCurrentDifficultyAt(p), MobSpawnType.CHUNK_GENERATION, null, null);
            n.addFreshEntityWithPassengers(m);
            pose = true;
        }
        return pose;
    }

    /** Eau douce à moins de 3 blocs, au niveau du sol ou juste dessous (pas la mer : le fond y est bas). */
    private static boolean eauDouceProche(WorldGenLevel n, BlockPos.MutableBlockPos v, int x, int y, int z) {
        for (int dx = -3; dx <= 3; dx++) {
            for (int dz = -3; dz <= 3; dz++) {
                for (int dy = -2; dy <= 0; dy++) {
                    if (n.getFluidState(v.set(x + dx, y + dy, z + dz)).is(FluidTags.WATER)
                            && !Terrain.get().enMer(x + dx, z + dz)) return true;
                }
            }
        }
        return false;
    }
}

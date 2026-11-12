package fr.domaineaubin.terre.monde;

import com.mojang.serialization.Codec;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Registry;
import net.minecraft.core.registries.Registries;
import net.minecraft.resources.ResourceKey;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.tags.BlockTags;
import net.minecraft.util.RandomSource;
import net.minecraft.world.level.WorldGenLevel;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.chunk.ChunkGenerator;
import net.minecraft.world.level.levelgen.Heightmap;
import net.minecraft.world.level.levelgen.feature.ConfiguredFeature;
import net.minecraft.world.level.levelgen.feature.Feature;
import net.minecraft.world.level.levelgen.feature.FeaturePlaceContext;
import net.minecraft.world.level.levelgen.feature.configurations.NoneFeatureConfiguration;
import net.minecraft.world.level.levelgen.feature.configurations.OreConfiguration;
import net.minecraft.world.level.levelgen.structure.templatesystem.TagMatchTest;
import net.minecraftforge.registries.ForgeRegistries;

import java.util.List;

/**
 * Minerais par profondeur et par région (12/11/2026, demandes de Maxime : « plus profond = plus précieux », les montagnes
 * riches en fer, charbon et émeraudes, et des « zones riches » réelles). Remplace les minerais vanilla dans les terroirs
 * (biome_modifier minerais_vanilla) ; seule la forme des filons reste celle de Minecraft (on pose ses configured features).
 *
 * Étages (y absolus) : couches hautes 0 → surface (charbon, cuivre, un peu de fer) ; montagne 120 → 200 (fer, charbon,
 * émeraudes, un peu d'or) ; sommets au-dessus de 200 (peu) ; profondeurs 0 → −150 (fer, or, lapis, un peu de redstone) ;
 * −150 → −400 (or, redstone, lapis, premiers diamants) ; abîmes −400 → fond (diamants, redstone et or riches).
 *
 * Zones riches (vraies provinces minières) : les minerais de surface y sont 4 fois plus abondants ; les minerais profonds
 * (or, redstone, lapis, diamant) y remontent vers la surface (comme les kimberlites de Kimberley), sans être plus nombreux
 * que dans les abîmes : on les trouve sans affronter le fond. Zinc de Create seulement si Create est installé.
 */
public class MineraisFeature extends Feature<NoneFeatureConfiguration> {
    private static final int CHARBON = 0, FER = 1, CUIVRE = 2, OR = 3, REDSTONE = 4, LAPIS = 5, DIAMANT = 6,
            EMERAUDE = 7, ZINC = 8, NB = 9;

    /** {minerai, lon, lat, rayon en km réels} — rayon plein aux 3/5, nul au bord. */
    private static final double[][] ZONES = {
            // fer
            {FER, 6.0, 49.3, 70}, {FER, 20.2, 67.85, 40}, {FER, 118.5, -22.5, 250}, {FER, -43.8, -20.2, 70},
            {FER, -50.2, -6.1, 60}, {FER, -92.5, 47.5, 90}, {FER, 33.4, 47.9, 50}, {FER, -67.0, 54.0, 150},
            {FER, 85.5, 22.0, 80},
            // charbon
            {CHARBON, 7.2, 51.5, 50}, {CHARBON, 3.0, 50.4, 45}, {CHARBON, 19.0, 50.2, 50}, {CHARBON, -81.0, 38.5, 180},
            {CHARBON, 112.5, 37.5, 160}, {CHARBON, -3.5, 51.7, 30}, {CHARBON, 86.5, 54.5, 110}, {CHARBON, -105.5, 44.0, 90},
            {CHARBON, 148.5, -22.5, 120}, {CHARBON, 38.0, 48.0, 70}, {CHARBON, 86.4, 23.7, 50}, {CHARBON, 151.2, -32.8, 50},
            {CHARBON, 29.0, -26.0, 80},
            // cuivre
            {CUIVRE, -69.0, -23.5, 150}, {CUIVRE, -70.3, -33.2, 50}, {CUIVRE, 27.5, -12.5, 110}, {CUIVRE, -111.0, 33.0, 90},
            {CUIVRE, 60.0, 55.0, 120}, {CUIVRE, -5.2, 50.2, 25}, {CUIVRE, -112.15, 40.5, 25}, {CUIVRE, -71.0, -15.0, 90},
            {CUIVRE, 106.8, 43.0, 40}, {CUIVRE, 137.0, -6.0, 50},
            // or
            {OR, 27.5, -26.5, 70}, {OR, -139.0, 64.0, 60}, {OR, -120.5, 38.5, 70}, {OR, -1.8, 6.5, 60},
            {OR, 121.5, -30.75, 90}, {OR, 143.8, -37.3, 45}, {OR, 150.0, 63.0, 120}, {OR, -116.0, 40.8, 60},
            {OR, -78.5, -7.0, 60}, {OR, -43.6, -19.9, 40},
            // redstone (cinabre)
            {REDSTONE, -4.84, 38.78, 40}, {REDSTONE, -75.0, -12.8, 40}, {REDSTONE, 14.03, 46.0, 25},
            {REDSTONE, -121.8, 37.17, 20}, {REDSTONE, 109.2, 27.5, 60},
            // lapis-lazuli
            {LAPIS, 70.8, 36.2, 60}, {LAPIS, -71.0, -30.6, 25}, {LAPIS, 103.0, 51.5, 25},
            // diamants
            {DIAMANT, 24.8, -28.7, 50}, {DIAMANT, 25.0, -23.0, 80}, {DIAMANT, 114.0, 62.5, 130},
            {DIAMANT, 23.5, -6.5, 80}, {DIAMANT, -110.6, 64.7, 50}, {DIAMANT, 128.4, -16.7, 35},
            {DIAMANT, 20.5, -8.5, 70}, {DIAMANT, -11.0, 8.5, 40}, {DIAMANT, 78.5, 16.5, 40},
            // émeraudes
            {EMERAUDE, -74.1, 5.5, 55}, {EMERAUDE, -41.0, -14.0, 70}, {EMERAUDE, 28.2, -13.0, 25}, {EMERAUDE, 69.7, 35.5, 25},
            // zinc (Create)
            {ZINC, 141.45, -31.95, 50}, {ZINC, 139.5, -20.7, 50}, {ZINC, -162.9, 68.06, 30}, {ZINC, -81.4, 48.7, 40},
            {ZINC, -6.7, 53.65, 30}, {ZINC, -102.6, 22.8, 50}, {ZINC, -77.05, -9.53, 40}, {ZINC, 19.0, 50.3, 40},
    };

    private static final String[] NOMS = {"ore_coal", "ore_coal_buried", "ore_iron", "ore_iron_small", "ore_copper_small",
            "ore_copper_large", "ore_gold", "ore_gold_buried", "ore_redstone", "ore_lapis", "ore_lapis_buried",
            "ore_diamond_small", "ore_diamond_large", "ore_diamond_buried", "ore_emerald"};
    private static final int C_CHARBON = 0, C_CHARBON_ENF = 1, C_FER = 2, C_FER_PETIT = 3, C_CUIVRE = 4, C_CUIVRE_GROS = 5,
            C_OR = 6, C_OR_ENF = 7, C_REDSTONE = 8, C_LAPIS = 9, C_LAPIS_ENF = 10, C_DIAMANT = 11, C_DIAMANT_GROS = 12,
            C_DIAMANT_ENF = 13, C_EMERAUDE = 14;

    private static volatile OreConfiguration zinc;
    private static volatile boolean zincCherche;

    public MineraisFeature(Codec<NoneFeatureConfiguration> codec) {
        super(codec);
    }

    @Override
    public boolean place(FeaturePlaceContext<NoneFeatureConfiguration> ctx) {
        WorldGenLevel niveau = ctx.level();
        ChunkGenerator gen = ctx.chunkGenerator();
        RandomSource r = ctx.random();
        int x0 = ctx.origin().getX() & ~15, z0 = ctx.origin().getZ() & ~15;
        int sol = niveau.getHeight(Heightmap.Types.OCEAN_FLOOR_WG, x0 + 8, z0 + 8) - 1;
        int fond = niveau.getMinBuildHeight() + 5;
        double[] m = richesse(x0 + 8, z0 + 8);
        Registry<ConfiguredFeature<?, ?>> reg = niveau.registryAccess().registryOrThrow(Registries.CONFIGURED_FEATURE);
        ConfiguredFeature<?, ?>[] cf = new ConfiguredFeature<?, ?>[NOMS.length];
        for (int i = 0; i < NOMS.length; i++) {
            cf[i] = reg.get(ResourceKey.create(Registries.CONFIGURED_FEATURE, new ResourceLocation("minecraft", NOMS[i])));
        }
        Pose p = new Pose(niveau, gen, r, x0, z0);
        double fer = 1 + 3 * m[FER], charbon = 1 + 3 * m[CHARBON], cuivre = 1 + 3 * m[CUIVRE], emeraude = 1 + 3 * m[EMERAUDE];

        // couches hautes : 0 → surface (au plus 120)
        int haut = Math.min(sol, 120);
        p.bande(cf[C_CHARBON], 0, haut, 22 * charbon);
        p.bande(cf[C_CUIVRE], 0, haut, 12 * cuivre);
        p.bande(cf[C_CUIVRE_GROS], 0, haut, 1.5 * cuivre);
        p.bande(cf[C_FER_PETIT], 0, haut, 5 * fer);
        // montagne : 120 → 200
        int mont = Math.min(sol, 200);
        p.bande(cf[C_FER], 120, mont, 16 * fer);
        p.bande(cf[C_CHARBON], 120, mont, 12 * charbon);
        p.bande(cf[C_EMERAUDE], 120, mont, 30 * emeraude);
        p.bande(cf[C_OR], 120, mont, 1.5);
        // sommets : au-dessus de 200, peu de minerai
        p.bande(cf[C_FER], 200, sol, 4 * fer);
        p.bande(cf[C_CHARBON], 200, sol, 3 * charbon);
        p.bande(cf[C_EMERAUDE], 200, sol, 6 * emeraude);
        // profondeurs : 0 → −150
        p.bande(cf[C_FER], -150, 0, 10 * fer);
        p.bande(cf[C_FER_PETIT], -150, 0, 4 * fer);
        p.bande(cf[C_CUIVRE], -150, 0, 3 * cuivre);
        p.bande(cf[C_CHARBON_ENF], -60, 0, 4 * charbon);
        p.bande(cf[C_OR], -150, 0, 2.5);
        p.bande(cf[C_LAPIS], -150, 0, 1.5);
        p.bande(cf[C_REDSTONE], -150, 0, 1.5);
        // −150 → −400
        p.bande(cf[C_FER_PETIT], -400, -150, 2);
        p.bande(cf[C_OR], -400, -150, 3);
        p.bande(cf[C_OR_ENF], -400, -150, 1);
        p.bande(cf[C_REDSTONE], -400, -150, 4);
        p.bande(cf[C_LAPIS], -400, -150, 1);
        p.bande(cf[C_LAPIS_ENF], -400, -150, 1);
        p.bande(cf[C_DIAMANT], -400, -150, 0.6);
        // abîmes : −400 → fond
        p.bande(cf[C_DIAMANT], fond, -400, 5);
        p.bande(cf[C_DIAMANT_GROS], fond, -400, 0.4);
        p.bande(cf[C_DIAMANT_ENF], fond, -400, 3);
        p.bande(cf[C_REDSTONE], fond, -400, 8);
        p.bande(cf[C_OR], fond, -400, 4);
        p.bande(cf[C_LAPIS_ENF], fond, -400, 2);

        // zones riches : les minerais profonds remontent (pas plus nombreux qu'aux abîmes)
        if (m[DIAMANT] > 0) {                            // cheminées de kimberlite
            p.bande(cf[C_DIAMANT], -140, -20, 2.5 * m[DIAMANT]);
            p.bande(cf[C_DIAMANT_ENF], -140, -20, 1 * m[DIAMANT]);
        }
        if (m[OR] > 0) {                                 // filons et placers près de la surface
            p.bande(cf[C_OR], -80, Math.min(sol, 120), 3 * m[OR]);
            p.bande(cf[C_OR_ENF], -80, 0, 1 * m[OR]);
        }
        if (m[REDSTONE] > 0) p.bande(cf[C_REDSTONE], -120, Math.min(sol, 40), 4 * m[REDSTONE]);
        if (m[LAPIS] > 0) {
            p.bande(cf[C_LAPIS], -100, Math.min(sol, 60), 1.5 * m[LAPIS]);
            p.bande(cf[C_LAPIS_ENF], -100, 0, 1 * m[LAPIS]);
        }
        if (m[ZINC] > 0) {
            OreConfiguration z = zinc();
            if (z != null) p.bandeZinc(z, -20, Math.min(sol, 70), 10 * m[ZINC]);
        }
        return p.pose;
    }

    /** Richesse de chaque minerai en ce point, de 0 à 1. */
    public static double[] richesse(int x, int z) {
        double[] m = new double[NB];
        for (double[] zone : ZONES) {
            double rayon = zone[3] * 1000.0 / 250.0 * (Terrain.BLOCS_PAR_DEGRE / 445.28);
            double dx = x - Terrain.x(zone[1]), dz = z - Terrain.z(zone[2]);
            double d = Math.sqrt(dx * dx + dz * dz);
            if (d >= rayon) continue;
            double t = Math.max(0, (d - 0.6 * rayon) / (0.4 * rayon));
            double v = 1 - t * t * (3 - 2 * t);
            int k = (int) zone[0];
            m[k] = Math.max(m[k], v);
        }
        return m;
    }

    private static OreConfiguration zinc() {
        if (!zincCherche) {
            Block b = ForgeRegistries.BLOCKS.getValue(new ResourceLocation("create", "zinc_ore"));
            Block d = ForgeRegistries.BLOCKS.getValue(new ResourceLocation("create", "deepslate_zinc_ore"));
            if (b != null && b != Blocks.AIR && d != null && d != Blocks.AIR) {
                zinc = new OreConfiguration(List.of(
                        OreConfiguration.target(new TagMatchTest(BlockTags.STONE_ORE_REPLACEABLES), b.defaultBlockState()),
                        OreConfiguration.target(new TagMatchTest(BlockTags.DEEPSLATE_ORE_REPLACEABLES), d.defaultBlockState())), 12);
            }
            zincCherche = true;
        }
        return zinc;
    }

    /** Pose des filons dans une tranche, avec une densité en filons par chunk pour 100 couches. */
    private static final class Pose {
        final WorldGenLevel niveau;
        final ChunkGenerator gen;
        final RandomSource r;
        final int x0, z0;
        boolean pose;

        Pose(WorldGenLevel niveau, ChunkGenerator gen, RandomSource r, int x0, int z0) {
            this.niveau = niveau;
            this.gen = gen;
            this.r = r;
            this.x0 = x0;
            this.z0 = z0;
        }

        int nombre(int bas, int haut, double densite) {
            if (haut <= bas || densite <= 0) return 0;
            double n = densite * (haut - bas) / 100.0;
            int k = (int) n;
            if (r.nextDouble() < n - k) k++;
            return k;
        }

        void bande(ConfiguredFeature<?, ?> cf, int bas, int haut, double densite) {
            if (cf == null) return;
            int n = nombre(bas, haut, densite);
            for (int i = 0; i < n; i++) {
                BlockPos pos = new BlockPos(x0 + r.nextInt(16), bas + r.nextInt(haut - bas), z0 + r.nextInt(16));
                pose |= cf.place(niveau, gen, r, pos);
            }
        }

        void bandeZinc(OreConfiguration z, int bas, int haut, double densite) {
            int n = nombre(bas, haut, densite);
            for (int i = 0; i < n; i++) {
                BlockPos pos = new BlockPos(x0 + r.nextInt(16), bas + r.nextInt(haut - bas), z0 + r.nextInt(16));
                pose |= Feature.ORE.place(z, niveau, gen, r, pos);
            }
        }
    }
}

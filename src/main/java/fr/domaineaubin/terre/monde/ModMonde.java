package fr.domaineaubin.terre.monde;

import com.mojang.serialization.Codec;
import fr.domaineaubin.terre.DomaineTerre;
import net.minecraft.core.registries.Registries;
import net.minecraft.world.level.biome.BiomeSource;
import net.minecraft.world.level.levelgen.DensityFunction;
import net.minecraft.world.level.levelgen.feature.Feature;
import net.minecraft.world.level.levelgen.feature.configurations.NoneFeatureConfiguration;
import net.minecraftforge.registries.ForgeRegistries;
import net.minecraftforge.registries.DeferredRegister;
import net.minecraftforge.registries.RegistryObject;

/** Enregistrement des types de génération du mod. */
public final class ModMonde {
    public static final DeferredRegister<Codec<? extends DensityFunction>> TYPES_DENSITE =
            DeferredRegister.create(Registries.DENSITY_FUNCTION_TYPE, DomaineTerre.MOD_ID);

    public static final RegistryObject<Codec<? extends DensityFunction>> TERRE =
            TYPES_DENSITE.register("terre", TerreFunction.CODEC::codec);
    public static final RegistryObject<Codec<? extends DensityFunction>> MASQUES =
            TYPES_DENSITE.register("masques", MasquesFunction.CODEC::codec);

    public static final DeferredRegister<Feature<?>> FEATURES =
            DeferredRegister.create(ForgeRegistries.FEATURES, DomaineTerre.MOD_ID);

    public static final RegistryObject<Feature<NoneFeatureConfiguration>> FLEUVES =
            FEATURES.register("fleuves", () -> new FleuveFeature(NoneFeatureConfiguration.CODEC));

    public static final RegistryObject<Feature<NoneFeatureConfiguration>> FOSSES =
            FEATURES.register("fosses", () -> new FosseFeature(NoneFeatureConfiguration.CODEC));

    public static final RegistryObject<Feature<NoneFeatureConfiguration>> MER_DES_LIEUX =
            FEATURES.register("mer_des_lieux", () -> new MerDesLieuxFeature(NoneFeatureConfiguration.CODEC));

    public static final RegistryObject<Feature<NoneFeatureConfiguration>> RIVES =
            FEATURES.register("rives", () -> new RivesFeature(NoneFeatureConfiguration.CODEC));

    public static final DeferredRegister<Codec<? extends BiomeSource>> SOURCES_BIOMES =
            DeferredRegister.create(Registries.BIOME_SOURCE, DomaineTerre.MOD_ID);

    public static final RegistryObject<Codec<? extends BiomeSource>> SOURCE_TERRE =
            SOURCES_BIOMES.register("terre", () -> TerroirBiomeSource.CODEC);

    private ModMonde() {
    }
}

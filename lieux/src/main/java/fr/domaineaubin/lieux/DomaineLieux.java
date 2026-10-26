package fr.domaineaubin.lieux;

import com.mojang.logging.LogUtils;
import fr.domaineaubin.terre.api.LieuxTerre;
import net.minecraft.world.level.levelgen.feature.Feature;
import net.minecraft.world.level.levelgen.feature.configurations.NoneFeatureConfiguration;
import net.minecraftforge.eventbus.api.IEventBus;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.fml.javafmlmod.FMLJavaModLoadingContext;
import net.minecraftforge.registries.DeferredRegister;
import net.minecraftforge.registries.ForgeRegistries;
import net.minecraftforge.registries.RegistryObject;
import org.slf4j.Logger;

/**
 * Addon « Domaine d'Aubin - Lieux uniques » : sculpte des sites naturels célèbres dans le monde du mod Terre.
 */
@Mod(DomaineLieux.MOD_ID)
public class DomaineLieux {
    public static final String MOD_ID = "domaine_terre_lieux";
    public static final Logger LOGGER = LogUtils.getLogger();

    public static final DeferredRegister<Feature<?>> FEATURES = DeferredRegister.create(ForgeRegistries.FEATURES, MOD_ID);
    public static final RegistryObject<Feature<NoneFeatureConfiguration>> STRATES =
            FEATURES.register("strates", () -> new StratesFeature(NoneFeatureConfiguration.CODEC));

    public DomaineLieux() {
        IEventBus bus = FMLJavaModLoadingContext.get().getModEventBus();
        FEATURES.register(bus);
        LieuxTerre.inscrire(GrandCanyon.INSTANCE);
        LieuxTerre.inscrire(Verdon.INSTANCE);
        // lot 1 (Europe) : lieux en grille, calculés par outils/lieux_cotiers.py
        LieuxTerre.inscrire(new LieuGrille("etretat", LieuGrille.Palette.CRAIE));
        LieuxTerre.inscrire(new LieuGrille("moher", LieuGrille.Palette.MOHER));
        LieuxTerre.inscrire(new LieuGrille("douvres", LieuGrille.Palette.CRAIE_PURE));
        LieuxTerre.inscrire(new LieuGrille("pilat", LieuGrille.Palette.DUNE, true));   // en tuiles (26/10)
        LieuxTerre.inscrire(new LieuGrille("mont_saint_michel", LieuGrille.Palette.BAIE));
        LOGGER.info("Domaine d'Aubin - Lieux uniques : {} lieu(x) inscrit(s).", LieuxTerre.liste().size());
    }
}

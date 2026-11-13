package fr.domaineaubin.village;

import com.mojang.logging.LogUtils;
import fr.domaineaubin.terre.api.StructuresTerre;
import fr.domaineaubin.terre.monde.TerroirBiomeSource;
import net.minecraft.core.registries.Registries;
import net.minecraft.world.level.dimension.LevelStem;
import net.minecraft.world.level.levelgen.structure.placement.StructurePlacementType;
import net.minecraftforge.common.MinecraftForge;
import net.minecraftforge.event.server.ServerAboutToStartEvent;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.fml.javafmlmod.FMLJavaModLoadingContext;
import net.minecraftforge.registries.DeferredRegister;
import net.minecraftforge.registries.RegistryObject;
import org.slf4j.Logger;

/**
 * Domaine Village 0.1 (13/11/2026) : les villages vanilla aux emplacements des vraies villes, identiques dans tous
 * les mondes, et quelques structures vanilla rallumées. Sans cet addon, le mod Terre est un monde vierge.
 */
@Mod(DomaineVillage.MOD_ID)
public final class DomaineVillage {
    public static final String MOD_ID = "domaine_terre_village";
    public static final Logger LOGGER = LogUtils.getLogger();

    private static final DeferredRegister<StructurePlacementType<?>> PLACEMENTS =
            DeferredRegister.create(Registries.STRUCTURE_PLACEMENT, MOD_ID);
    public static final RegistryObject<StructurePlacementType<PlacementFixe>> FIXE =
            PLACEMENTS.register("fixe", () -> () -> PlacementFixe.CODEC);

    /** Structures vanilla rallumées dans les mondes Terre (0.1). */
    private static final String[] RALLUMEES = {
            "village_plains", "village_desert", "village_savanna", "village_snowy", "village_taiga",
            "swamp_hut", "mineshaft", "mineshaft_mesa", "buried_treasure"};

    public DomaineVillage() {
        PLACEMENTS.register(FMLJavaModLoadingContext.get().getModEventBus());
        for (String s : RALLUMEES) StructuresTerre.rallumer(s);
        MinecraftForge.EVENT_BUS.addListener(this::demarrage);
        MinecraftForge.EVENT_BUS.addListener((net.minecraftforge.event.RegisterCommandsEvent e) -> CommandeVillage.enregistrer(e.getDispatcher()));
    }

    private void demarrage(ServerAboutToStartEvent e) {
        LevelStem stem = e.getServer().registryAccess().registryOrThrow(Registries.LEVEL_STEM).get(LevelStem.OVERWORLD);
        Points.terre = stem != null && stem.generator().getBiomeSource() instanceof TerroirBiomeSource;
        LOGGER.info("Domaine Village : monde Terre {}, {} villages", Points.terre ? "oui" : "non",
                Points.taille("villages", PlacementFixe.CASE));
    }
}

package fr.domaineaubin.terre;

import com.mojang.logging.LogUtils;
import fr.domaineaubin.terre.monde.ModMonde;
import net.minecraftforge.eventbus.api.IEventBus;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.fml.javafmlmod.FMLJavaModLoadingContext;
import org.slf4j.Logger;

/**
 * Point d'entrée du mod « Domaine d'Aubin - Terre ».
 */
@Mod(DomaineTerre.MOD_ID)
public class DomaineTerre {
    public static final String MOD_ID = "domaine_terre";
    public static final Logger LOGGER = LogUtils.getLogger();

    public DomaineTerre() {
        IEventBus bus = FMLJavaModLoadingContext.get().getModEventBus();
        ModMonde.TYPES_DENSITE.register(bus);
        ModMonde.FEATURES.register(bus);
        ModMonde.SOURCES_BIOMES.register(bus);
        LOGGER.info("Domaine d'Aubin - Terre : mod chargé.");
    }
}

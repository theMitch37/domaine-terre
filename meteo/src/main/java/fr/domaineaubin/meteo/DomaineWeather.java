package fr.domaineaubin.meteo;

import com.mojang.logging.LogUtils;
import net.minecraft.server.level.ServerPlayer;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.common.MinecraftForge;
import net.minecraftforge.event.RegisterCommandsEvent;
import net.minecraftforge.event.entity.player.PlayerEvent;
import net.minecraftforge.event.server.ServerStartedEvent;
import net.minecraftforge.fml.DistExecutor;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.fml.event.lifecycle.FMLClientSetupEvent;
import net.minecraftforge.fml.event.lifecycle.FMLCommonSetupEvent;
import net.minecraftforge.fml.javafmlmod.FMLJavaModLoadingContext;
import org.slf4j.Logger;

/**
 * Domaine Weather : le vrai climat de chaque région pour le mod Domaine d'Aubin - Terre (étape 02 de la feuille de
 * route). 0.1 (13/11/2026) : saisons par hémisphère, pluie selon le climat, durée du jour selon la saison et la
 * latitude, catastrophes seulement là où elles existent, tornades sans dégâts aux blocs. 0.2 : vents dominants,
 * heure solaire locale.
 */
@Mod(DomaineWeather.MOD_ID)
public final class DomaineWeather {
    public static final String MOD_ID = "domaine_weather";
    public static final Logger LOGGER = LogUtils.getLogger();

    public DomaineWeather() {
        var bus = FMLJavaModLoadingContext.get().getModEventBus();
        bus.addListener(this::commun);
        bus.addListener(this::client);
        MinecraftForge.EVENT_BUS.addListener(this::connexion);
        MinecraftForge.EVENT_BUS.addListener(this::demarre);
        MinecraftForge.EVENT_BUS.addListener(this::commandes);
        DistExecutor.unsafeRunWhenOn(Dist.CLIENT, () -> ClientMeteo::bus);
    }

    private void commun(FMLCommonSetupEvent e) {
        e.enqueueWork(Reseau::enregistrer);
    }

    private void client(FMLClientSetupEvent e) {
        e.enqueueWork(ClientMeteo::installer);
    }

    private void connexion(PlayerEvent.PlayerLoggedInEvent e) {
        if (e.getEntity() instanceof ServerPlayer j) Reseau.envoyer(j, Saisons.terre(j.server.overworld()));
    }

    /** Décision de Maxime (13/11) : tornades et tempêtes ne détruisent jamais de blocs. */
    private void demarre(ServerStartedEvent e) {
        JourNuit.reinitialiserServeur();
        try {
            weather2.config.ConfigTornado.Storm_Tornado_grabBlocks = false;
            LOGGER.info("Domaine Weather : tornades sans dégâts aux blocs ; {} zones de tornades",
                    Climat.zones().tornades.size());
        } catch (Throwable t) {
            LOGGER.warn("Domaine Weather : réglage de Weather2 impossible ({})", t.toString());
        }
    }

    private void commandes(RegisterCommandsEvent e) {
        CommandeMeteo.enregistrer(e.getDispatcher());
    }
}

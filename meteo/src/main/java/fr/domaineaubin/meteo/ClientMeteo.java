package fr.domaineaubin.meteo;

import net.minecraft.client.Minecraft;
import net.minecraft.core.Holder;
import net.minecraft.world.level.biome.Biome;
import net.minecraftforge.client.event.ClientPlayerNetworkEvent;
import net.minecraftforge.common.MinecraftForge;
import sereneseasons.api.season.ISeasonColorProvider;
import sereneseasons.init.ModTags;
import sereneseasons.season.SeasonColorHandlers;
import sereneseasons.season.SeasonTime;
import sereneseasons.util.SeasonColorUtil;

/** Côté client : couleurs des feuilles et de l'herbe selon l'hémisphère, fin de connexion. */
public final class ClientMeteo {
    private ClientMeteo() {
    }

    static void bus() {
        MinecraftForge.EVENT_BUS.addListener(fr.domaineaubin.meteo.vagues.RenduVagues::dessiner);
        MinecraftForge.EVENT_BUS.addListener(fr.domaineaubin.meteo.vagues.NageHoule::tick);
        MinecraftForge.EVENT_BUS.addListener((ClientPlayerNetworkEvent.LoggingOut e) -> {
            Saisons.terreClient = false;
            JourNuit.reinitialiserClient();
        });
    }

    /** Au sud de l'équateur, les couleurs suivent la saison locale (interface prévue par Serene Seasons). */
    static void installer() {
        SeasonColorHandlers.registerResolverOverride(SeasonColorHandlers.ResolverType.GRASS,
                (orig, saison, actuelle, biome, x, z) -> sud(biome, z)
                        ? SeasonColorUtil.applySeasonalGrassColouring(fournisseur(biome, z), biome, orig) : actuelle);
        SeasonColorHandlers.registerResolverOverride(SeasonColorHandlers.ResolverType.FOLIAGE,
                (orig, saison, actuelle, biome, x, z) -> sud(biome, z)
                        ? SeasonColorUtil.applySeasonalFoliageColouring(fournisseur(biome, z), biome, orig) : actuelle);
    }

    private static boolean sud(Holder<Biome> biome, double z) {
        return Saisons.terreClient && Saisons.sud(z) && !biome.is(ModTags.Biomes.BLACKLISTED_BIOMES);
    }

    private static ISeasonColorProvider fournisseur(Holder<Biome> biome, double z) {
        SeasonTime t = Saisons.locale(Minecraft.getInstance().level, z);
        return biome.is(ModTags.Biomes.TROPICAL_BIOMES) ? t.getTropicalSeason() : t.getSubSeason();
    }

    /** z du joueur local (calendrier). */
    public static double zJoueur() {
        var j = Minecraft.getInstance().player;
        return j == null ? 0 : j.getZ();
    }
}

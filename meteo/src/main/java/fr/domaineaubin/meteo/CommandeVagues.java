package fr.domaineaubin.meteo;

import com.mojang.brigadier.CommandDispatcher;
import com.mojang.brigadier.arguments.DoubleArgumentType;
import com.mojang.brigadier.arguments.IntegerArgumentType;
import com.mojang.brigadier.context.CommandContext;
import fr.domaineaubin.meteo.vagues.Houle;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.network.chat.Component;

import java.util.Locale;

/**
 * /vagues : réglage des vagues en jeu, sans redémarrer (prototype). Écrit aussi config/domaine_weather_vagues.json.
 * /vagues amplitude <0-5> | /vagues on | /vagues off | /vagues rayon <8-128> | /vagues (état).
 * Limite : en solo seulement (le client et le serveur partagent les réglages) ; en multi, chaque client garde son
 * fichier de config.
 */
public final class CommandeVagues {
    private CommandeVagues() {
    }

    static void enregistrer(CommandDispatcher<CommandSourceStack> d) {
        d.register(Commands.literal("vagues").requires(s -> s.hasPermission(2))
                .executes(CommandeVagues::etat)
                .then(Commands.literal("amplitude")
                        .then(Commands.argument("valeur", DoubleArgumentType.doubleArg(0, 5))
                                .executes(c -> {
                                    Houle.regler(DoubleArgumentType.getDouble(c, "valeur"), null, null);
                                    return etat(c);
                                })))
                .then(Commands.literal("rayon")
                        .then(Commands.argument("blocs", IntegerArgumentType.integer(8, 128))
                                .executes(c -> {
                                    Houle.regler(null, null, IntegerArgumentType.getInteger(c, "blocs"));
                                    return etat(c);
                                })))
                .then(Commands.literal("masque")
                        .then(Commands.literal("on").executes(c -> masque(c, false)))
                        .then(Commands.literal("off").executes(c -> masque(c, true))))
                .then(Commands.literal("ici").executes(CommandeVagues::ici))
                .then(Commands.literal("on").executes(c -> {
                    Houle.regler(null, true, null);
                    return etat(c);
                }))
                .then(Commands.literal("off").executes(c -> {
                    Houle.regler(null, false, null);
                    return etat(c);
                })));
    }

    /** Solo : coupe ou remet le masque de la surface plate du jeu (diagnostic des trous). */
    private static int masque(CommandContext<CommandSourceStack> c, boolean coupe) {
        fr.domaineaubin.meteo.vagues.MasqueEau.coupe = coupe;
        net.minecraftforge.fml.DistExecutor.unsafeRunWhenOn(net.minecraftforge.api.distmarker.Dist.CLIENT,
                () -> fr.domaineaubin.meteo.vagues.MasqueEau::rafraichir);
        c.getSource().sendSuccess(() -> Component.literal("§6[Vagues]§r surface plate du jeu "
                + (coupe ? "gardée partout (masque coupé)" : "masquée sous la houle")), false);
        return 1;
    }

    /** Solo : état de la colonne visée (ou sous les pieds) vu par le client : masque, mémoire, recalcul, biome. */
    private static int ici(CommandContext<CommandSourceStack> c) {
        String[] t = {"client indisponible"};
        net.minecraftforge.fml.DistExecutor.unsafeRunWhenOn(net.minecraftforge.api.distmarker.Dist.CLIENT,
                () -> () -> t[0] = fr.domaineaubin.meteo.vagues.DiagnosticVagues.colonneVisee());
        c.getSource().sendSuccess(() -> Component.literal("§6[Vagues]§r " + t[0]), false);
        fr.domaineaubin.meteo.DomaineWeather.LOGGER.info("[Vagues] ici : {}", t[0]);
        return 1;
    }

    private static int etat(CommandContext<CommandSourceStack> c) {
        Houle.Reglages r = Houle.reglages();
        String t = String.format(Locale.ROOT, "§6[Vagues]§r %s | multiplicateur %.2f | rayon %d blocs",
                r.actif ? "actives" : "coupées", r.amplitude, r.rayon);
        c.getSource().sendSuccess(() -> Component.literal(t), false);
        // 0.4.0 : la mer ici (climat réel ERA5, mois de Serene Seasons, variation de la région)
        var l = c.getSource().getLevel();
        var p = c.getSource().getPosition();
        if (Saisons.terre(l)) {
            double lat = fr.domaineaubin.terre.monde.Terrain.lat(p.z), lon = fr.domaineaubin.terre.monde.Terrain.lon(p.x);
            double[] hm = Houle.hsMois(l, lat, lon);
            double hs = Houle.hs(l, p.x, p.z), am = Houle.amplitudeRegion(l, p.x, p.z);
            String[] mois = {"janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre",
                    "octobre", "novembre", "décembre"};
            String u = String.format(Locale.ROOT, "§6[Vagues]§r %s : Hs moyenne %.1f m, tempête %.1f m ; maintenant %.1f m"
                            + " -> amplitude %.2f (creux-crête ≈ %.1f blocs au large)",
                    mois[(int) Math.floor(Houle.mois(l)) % 12], hm[0], hm[1], hs, am, 2 * am);
            c.getSource().sendSuccess(() -> Component.literal(u), false);
        }
        return 1;
    }
}

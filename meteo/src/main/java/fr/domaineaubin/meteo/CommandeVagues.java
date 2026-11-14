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
        String t = String.format(Locale.ROOT, "§6[Vagues]§r %s | amplitude %.2f (creux-crête ≈ %.1f blocs) | rayon %d blocs",
                r.actif ? "actives" : "coupées", r.amplitude, 2 * r.amplitude, r.rayon);
        c.getSource().sendSuccess(() -> Component.literal(t), false);
        return 1;
    }
}

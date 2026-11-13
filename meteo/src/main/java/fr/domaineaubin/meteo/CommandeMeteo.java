package fr.domaineaubin.meteo;

import com.mojang.brigadier.CommandDispatcher;
import com.mojang.brigadier.arguments.DoubleArgumentType;
import com.mojang.brigadier.context.CommandContext;
import fr.domaineaubin.terre.monde.Terrain;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerLevel;
import sereneseasons.season.SeasonTime;

import java.util.Locale;

/**
 * /meteo ici : la météo telle que Domaine Weather la voit à la position du joueur (saison locale, climat, chance de
 * pluie, durée du jour, catastrophes possibles). /meteo point <lat> <lon> : pareil pour n'importe quel lieu.
 */
public final class CommandeMeteo {
    private CommandeMeteo() {
    }

    static void enregistrer(CommandDispatcher<CommandSourceStack> d) {
        d.register(Commands.literal("meteo")
                .then(Commands.literal("ici").executes(c -> afficher(c, c.getSource().getPosition().x, c.getSource().getPosition().z)))
                .then(Commands.literal("point")
                        .then(Commands.argument("latitude", DoubleArgumentType.doubleArg(-90, 90))
                                .then(Commands.argument("longitude", DoubleArgumentType.doubleArg(-180, 180))
                                        .executes(c -> afficher(c,
                                                Terrain.x(DoubleArgumentType.getDouble(c, "longitude")),
                                                Terrain.z(DoubleArgumentType.getDouble(c, "latitude"))))))));
    }

    private static int afficher(CommandContext<CommandSourceStack> c, double x, double z) {
        ServerLevel level = c.getSource().getServer().overworld();
        if (!Saisons.terre(level)) {
            c.getSource().sendFailure(Component.literal("Domaine Weather : ce monde n'est pas un monde Terre."));
            return 0;
        }
        SeasonTime s = Saisons.locale(level, z);
        int k = Climat.koppen(x, z);
        double part = JourNuit.partDuJour(Saisons.latitude(z), Saisons.fractionAnnee(level));
        Climat.Zone t = Climat.zoneTornade(x, z);
        String texte = String.format(Locale.ROOT,
                "§6[Météo]§r lat %.2f, lon %.2f (%s)%n"
                        + "Saison locale : %s (tropiques : %s)%n"
                        + "Climat : %s | pluie : %d %% des nuages à cette saison%n"
                        + "Jour : %.1f h, nuit : %.1f h (sur 24 h) | soleil levé %.0f %% des 20 min%n"
                        + "Tornades : %s | sable : %s | neige : %s",
                Saisons.latitude(z), Terrain.lon(x), Saisons.sud(z) ? "hémisphère sud" : "hémisphère nord",
                s.getSubSeason().toString().toLowerCase(Locale.ROOT), s.getTropicalSeason().toString().toLowerCase(Locale.ROOT),
                Climat.nomKoppen(k), Climat.pluie(k, s.getSeason()),
                part * 24, (1 - part) * 24, part * 100,
                t != null ? "oui (" + t.nom + ")" : "non",
                Climat.sablePossible(x, z) ? "oui" : "non", Climat.neigePossible(x, z) ? "oui" : "non");
        c.getSource().sendSuccess(() -> Component.literal(texte), false);
        return 1;
    }
}

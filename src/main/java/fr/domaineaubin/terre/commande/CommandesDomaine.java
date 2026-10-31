package fr.domaineaubin.terre.commande;

import com.mojang.brigadier.CommandDispatcher;
import com.mojang.brigadier.arguments.DoubleArgumentType;
import com.mojang.brigadier.arguments.StringArgumentType;
import com.mojang.brigadier.context.CommandContext;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import fr.domaineaubin.terre.DomaineTerre;
import fr.domaineaubin.terre.monde.Terrain;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.commands.SharedSuggestionProvider;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.level.chunk.LevelChunk;
import net.minecraft.world.level.levelgen.Heightmap;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.event.RegisterCommandsEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;

/**
 * Commandes de test :
 *   /domaine aller <latitude> <longitude>   téléporte à des coordonnées réelles
 *   /domaine lieu <nom>                     téléporte à un lieu connu
 *   /domaine ici                            affiche latitude, longitude, altitude réelle et terroir
 */
@Mod.EventBusSubscriber(modid = DomaineTerre.MOD_ID, bus = Mod.EventBusSubscriber.Bus.FORGE)
public final class CommandesDomaine {

    /** Lieux de test : nom -> {latitude, longitude}. */
    private static final Map<String, double[]> LIEUX = new LinkedHashMap<>();

    static {
        LIEUX.put("paris", new double[]{48.857, 2.352});
        LIEUX.put("londres", new double[]{51.507, -0.128});
        LIEUX.put("rome", new double[]{41.893, 12.483});
        LIEUX.put("mont_blanc", new double[]{45.833, 6.865});
        LIEUX.put("bretagne", new double[]{48.390, -4.486});
        LIEUX.put("fjords", new double[]{61.110, 6.700});
        LIEUX.put("le_caire", new double[]{30.044, 31.236});
        LIEUX.put("sahara", new double[]{23.400, 8.800});
        LIEUX.put("kilimandjaro", new double[]{-3.067, 37.353});
        LIEUX.put("everest", new double[]{27.988, 86.925});
        LIEUX.put("tibet", new double[]{31.500, 88.000});
        LIEUX.put("pekin", new double[]{39.904, 116.407});
        LIEUX.put("tokyo", new double[]{35.676, 139.650});
        LIEUX.put("new_york", new double[]{40.713, -74.006});
        LIEUX.put("grand_canyon", new double[]{36.107, -112.113});
        LIEUX.put("verdon", new double[]{43.800, 6.310});
        LIEUX.put("sainte_croix", new double[]{43.7655, 6.1525});
        LIEUX.put("etretat", new double[]{49.700, 0.205});
        LIEUX.put("moher", new double[]{52.968, -9.415});
        LIEUX.put("douvres", new double[]{51.1409, 1.3542});
        LIEUX.put("pilat", new double[]{44.589, -1.200});
        LIEUX.put("mont_saint_michel", new double[]{48.6121, -1.5114});
        // lot 2 (montagne, cascades, fjords) : relief réel agrandi (zoom) ; points de vue aux positions agrandies
        LIEUX.put("gavarnie", new double[]{42.760, -0.010});
        LIEUX.put("gullfoss", new double[]{64.322, -20.112});
        LIEUX.put("skogafoss", new double[]{63.515, -19.511});
        LIEUX.put("plitvice", new double[]{45.021, 15.620});
        LIEUX.put("geiranger", new double[]{62.076, 7.383});
        LIEUX.put("preikestolen", new double[]{59.1515, 6.393});
        LIEUX.put("cervin", new double[]{46.031, 7.707});
        LIEUX.put("tre_cime", new double[]{46.665, 12.306});
        // lot 3
        LIEUX.put("mer_de_glace", new double[]{46.049, 6.888});
        LIEUX.put("jokulsarlon", new double[]{64.065, -16.209});
        LIEUX.put("amazonie", new double[]{-3.465, -62.215});
        LIEUX.put("rio", new double[]{-22.907, -43.173});
        LIEUX.put("andes", new double[]{-13.163, -72.545});
        LIEUX.put("sydney", new double[]{-33.869, 151.209});
        LIEUX.put("seine_rouen", new double[]{49.440, 1.090});
        LIEUX.put("loire_orleans", new double[]{47.902, 1.909});
        LIEUX.put("rhin_cologne", new double[]{50.938, 6.960});
        LIEUX.put("nil_louxor", new double[]{25.687, 32.640});
        LIEUX.put("mississippi", new double[]{35.150, -90.050});
        LIEUX.put("tahiti", new double[]{-17.650, -149.430});
        LIEUX.put("martinique", new double[]{14.640, -61.020});
        LIEUX.put("santorin", new double[]{36.410, 25.430});
    }

    private CommandesDomaine() {
    }

    @SubscribeEvent
    public static void onRegisterCommands(RegisterCommandsEvent event) {
        CommandDispatcher<CommandSourceStack> d = event.getDispatcher();
        d.register(Commands.literal("domaine")
                .requires(s -> s.hasPermission(2))
                .then(Commands.literal("aller")
                        .then(Commands.argument("latitude", DoubleArgumentType.doubleArg(-84, 84))
                                .then(Commands.argument("longitude", DoubleArgumentType.doubleArg(-180, 180))
                                        .executes(c -> aller(c,
                                                DoubleArgumentType.getDouble(c, "latitude"),
                                                DoubleArgumentType.getDouble(c, "longitude"), null)))))
                .then(Commands.literal("lieu")
                        .then(Commands.argument("nom", StringArgumentType.word())
                                .suggests((c, b) -> SharedSuggestionProvider.suggest(LIEUX.keySet(), b))
                                .executes(c -> {
                                    String nom = StringArgumentType.getString(c, "nom").toLowerCase(Locale.ROOT);
                                    double[] ll = LIEUX.get(nom);
                                    if (ll == null) {
                                        c.getSource().sendFailure(Component.literal("Lieu inconnu : " + nom));
                                        return 0;
                                    }
                                    return aller(c, ll[0], ll[1], nom);
                                })))
                .then(Commands.literal("ici").executes(CommandesDomaine::ici))
                .then(Commands.literal("depart")
                        .then(Commands.argument("continent", StringArgumentType.word())
                                .suggests((c, b) -> SharedSuggestionProvider.suggest(
                                        java.util.List.of("europe", "afrique", "asie", "ameriques", "oceanie"), b))
                                .executes(c -> depart(c, StringArgumentType.getString(c, "continent")))))
                .then(Commands.literal("exporter").executes(c -> {
                    try {
                        int n = ExportBiomes.exporter(c.getSource().getServer());
                        c.getSource().sendSuccess(() -> Component.literal("Export terminé : " + n + " biomes dans run/export_biomes"), false);
                        return 1;
                    } catch (Exception e) {
                        c.getSource().sendFailure(Component.literal("Export raté : " + e.getMessage()));
                        return 0;
                    }
                })));
    }

    private static int aller(CommandContext<CommandSourceStack> c, double lat, double lon, String nom)
            throws CommandSyntaxException {
        ServerPlayer joueur = c.getSource().getPlayerOrException();
        ServerLevel niveau = c.getSource().getLevel();
        int x = (int) Math.floor(Terrain.x(lon));
        int z = (int) Math.floor(Terrain.z(lat));
        // force la génération du chunk, puis lit la hauteur réelle du sol
        LevelChunk chunk = niveau.getChunk(x >> 4, z >> 4);
        int y = chunk.getHeight(Heightmap.Types.MOTION_BLOCKING, x & 15, z & 15) + 1;
        joueur.teleportTo(niveau, x + 0.5, y + 1, z + 0.5, joueur.getYRot(), joueur.getXRot());
        String lieu = nom != null ? nom + " " : "";
        c.getSource().sendSuccess(() -> Component.literal(String.format(Locale.ROOT,
                "Téléporté %s(%.3f, %.3f) -> x=%d y=%d z=%d", lieu, lat, lon, x, y + 1, z)), false);
        return 1;
    }

    private static int ici(CommandContext<CommandSourceStack> c) {
        Vec3 p = c.getSource().getPosition();
        final int x = (int) Math.floor(p.x);
        final int z = (int) Math.floor(p.z);
        final Terrain t = Terrain.get();
        final double lat = Terrain.lat(z);
        final double lon = Terrain.lon(x);
        final String terroir = t.carte().nomTerroir(t.carte().terroir(lon, lat));
        c.getSource().sendSuccess(() -> Component.literal(String.format(Locale.ROOT,
                "Lat %.3f, lon %.3f | altitude réelle %.0f m | sol visé y=%.1f | pente %.0f m/km | terroir : %s",
                lat, lon, t.altitudeReelle(x, z), t.hauteur(x, z), t.pente(x, z), terroir)), false);
        return 1;
    }

    /** Pose le joueur sur une terre habitable au hasard du continent (« ameriques » comprend l'Océanie). */
    private static int depart(CommandContext<CommandSourceStack> c, String continent) throws CommandSyntaxException {
        ServerPlayer joueur = c.getSource().getPlayerOrException();
        ServerLevel niveau = c.getSource().getServer().overworld();
        Terrain t = Terrain.get();
        java.util.Random rnd = new java.util.Random();
        for (int essai = 0; essai < 4000; essai++) {
            double lat = -56 + rnd.nextDouble() * 126, lon = -180 + rnd.nextDouble() * 360;
            int ter = t.carte().terroir(lon, lat);
            if (ter == 0) continue;
            String cont = t.carte().continent(ter);
            boolean bon = cont.equals(continent) || (continent.equals("ameriques") && cont.equals("oceanie"));
            if (!bon) continue;
            int x = (int) Math.floor(Terrain.x(lon)), z = (int) Math.floor(Terrain.z(lat));
            double alt = t.altitudeReelle(x, z);
            int k = t.carte().climat(lon, lat);
            // habitable : pas de haute montagne, pas de pente forte, pas de toundra / glace, pas collé à la mer
            if (alt < 2 || alt > 1500 || t.pente(x, z) > 25 || k >= 29 || t.distanceCote(x, z) < 6) continue;
            LevelChunk chunk = niveau.getChunk(x >> 4, z >> 4);
            int y = chunk.getHeight(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES, x & 15, z & 15);
            if (!niveau.getFluidState(new net.minecraft.core.BlockPos(x, y, z)).isEmpty()) continue;
            joueur.teleportTo(niveau, x + 0.5, y + 1, z + 0.5, joueur.getYRot(), joueur.getXRot());
            final String nom = t.carte().nomTerroir(ter);
            c.getSource().sendSuccess(() -> Component.literal("Départ : " + nom), false);
            return 1;
        }
        c.getSource().sendFailure(Component.literal("Aucune terre trouvée pour : " + continent));
        return 0;
    }
}

package fr.domaineaubin.terre.commande;

import com.mojang.brigadier.CommandDispatcher;
import com.mojang.brigadier.arguments.DoubleArgumentType;
import com.mojang.brigadier.arguments.StringArgumentType;
import com.mojang.brigadier.context.CommandContext;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import fr.domaineaubin.terre.DomaineTerre;
import fr.domaineaubin.terre.monde.ReliefFin;
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
        LIEUX.put("chaussee", new double[]{55.2293, -6.5116});
        LIEUX.put("meteores", new double[]{39.6761, 21.6146});
        LIEUX.put("etna", new double[]{37.7745, 14.760});
        LIEUX.put("vesuve", new double[]{40.973, 14.5824});
        LIEUX.put("geysir", new double[]{64.296, -20.3024});
        // grottes (MAJ 1) : l'entrée réelle ; rien ne les signale en jeu, la commande ne sert qu'aux essais
        LIEUX.put("padirac", new double[]{44.8583, 1.7819});
        LIEUX.put("han", new double[]{50.1352, 5.2126});
        LIEUX.put("postojna", new double[]{45.7826, 14.2040});
        LIEUX.put("eisriesenwelt", new double[]{47.5530, 13.2458});
        LIEUX.put("fingal", new double[]{56.3819, -6.3500});
        LIEUX.put("capri", new double[]{40.6187, 14.1366});
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
                .then(Commands.literal("zoo").executes(CommandesDomaine::zoo))
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
        CommandSourceStack source = c.getSource();
        int x = (int) Math.floor(Terrain.x(lon));
        int z = (int) Math.floor(Terrain.z(lat));
        String lieu = nom != null ? nom + " " : "";
        // 1.0.1 : le relief de la destination est téléchargé d'abord, sans bloquer le serveur
        boolean tout = ReliefFin.quandPret(x, z, () -> {
            if (joueur.isRemoved()) return;
            // force la génération du chunk, puis lit la hauteur réelle du sol
            LevelChunk chunk = niveau.getChunk(x >> 4, z >> 4);
            int y = chunk.getHeight(Heightmap.Types.MOTION_BLOCKING, x & 15, z & 15) + 1;
            joueur.teleportTo(niveau, x + 0.5, y + 1, z + 0.5, joueur.getYRot(), joueur.getXRot());
            source.sendSuccess(() -> Component.literal(String.format(Locale.ROOT,
                    "Téléporté %s(%.3f, %.3f) -> x=%d y=%d z=%d", lieu, lat, lon, x, y + 1, z)), false);
        });
        if (!tout) source.sendSuccess(() -> Component.literal("Téléchargement du relief de la destination…"), false);
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
        return depart(c.getSource(), joueur, continent, 0) ? 1 : 0;
    }

    /**
     * Cherche une terre habitable du continent, attend son relief (1.0.1 : sans bloquer le serveur), puis vérifie le
     * sol dans le chunk généré ; si c'est de l'eau, recommence (au plus 20 destinations).
     */
    private static boolean depart(CommandSourceStack source, ServerPlayer joueur, String continent, int tentative) {
        ServerLevel niveau = source.getServer().overworld();
        Terrain t = Terrain.get();
        java.util.Random rnd = new java.util.Random();
        if (tentative < 20) {
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
                final String nom = t.carte().nomTerroir(ter);
                boolean tout = ReliefFin.quandPret(x, z, () -> {
                    if (joueur.isRemoved()) return;
                    LevelChunk chunk = niveau.getChunk(x >> 4, z >> 4);
                    int y = chunk.getHeight(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES, x & 15, z & 15);
                    if (!niveau.getFluidState(new net.minecraft.core.BlockPos(x, y, z)).isEmpty()) {
                        depart(source, joueur, continent, tentative + 1);
                        return;
                    }
                    joueur.teleportTo(niveau, x + 0.5, y + 1, z + 0.5, joueur.getYRot(), joueur.getXRot());
                    source.sendSuccess(() -> Component.literal("Départ : " + nom), false);
                });
                if (!tout && tentative == 0)
                    source.sendSuccess(() -> Component.literal("Téléchargement du relief de la région…"), false);
                return true;
            }
        }
        source.sendFailure(Component.literal("Aucune terre trouvée pour : " + continent));
        return false;
    }

    /**
     * Zoo (10/11/2026) : les grandes bêtes alignées devant le joueur, immobiles et nommées, pour comparer leurs tailles
     * entre elles et au joueur (1,8 bloc = 1,8 m). Les espèces absentes du pack sont sautées.
     */
    private static final String[] ZOO = {
            "alexsmobs:crocodile", "naturalist:alligator", "alexsmobs:caiman", "untamedwilds:hippo", "naturalist:hippo",
            "alexsmobs:elephant", "naturalist:elephant", "untamedwilds:rhino", "alexsmobs:rhinoceros", "naturalist:rhino",
            "naturalist:giraffe", "naturalist:zebra", "untamedwilds:bison", "alexsmobs:bison", "wildernature:bison",
            "untamedwilds:bear", "alexsmobs:grizzly_bear", "naturalist:bear", "untamedwilds:big_cat", "naturalist:lion",
            "alexsmobs:tiger", "untamedwilds:camel", "minecraft:camel", "minecraft:horse", "minecraft:cow",
            "alexsmobs:gazelle", "alexsmobs:kangaroo", "alexsmobs:emu", "alexsmobs:komodo_dragon", "untamedwilds:monitor"};

    private static int zoo(CommandContext<CommandSourceStack> c) throws CommandSyntaxException {
        ServerPlayer j = c.getSource().getPlayerOrException();
        ServerLevel n = j.serverLevel();
        Vec3 dir = Vec3.directionFromRotation(0, j.getYRot());
        Vec3 cote = new Vec3(-dir.z, 0, dir.x);
        Vec3 base = j.position().add(dir.scale(6));
        double t = 0;
        int nb = 0;
        for (String id : ZOO) {
            net.minecraft.resources.ResourceLocation rl = net.minecraft.resources.ResourceLocation.tryParse(id);
            var type = rl == null ? null
                    : net.minecraft.core.registries.BuiltInRegistries.ENTITY_TYPE.getOptional(rl).orElse(null);
            if (type == null || !rl.equals(net.minecraft.world.entity.EntityType.getKey(type))) continue;
            var e = type.create(n);
            if (!(e instanceof net.minecraft.world.entity.Mob m)) continue;
            Vec3 p = base.add(cote.scale(t));
            int y = n.getHeight(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES, (int) Math.floor(p.x), (int) Math.floor(p.z));
            m.moveTo(p.x, y, p.z, j.getYRot() + 180f, 0f);
            m.finalizeSpawn(n, n.getCurrentDifficultyAt(m.blockPosition()), net.minecraft.world.entity.MobSpawnType.COMMAND, null, null);
            m.setNoAi(true);
            m.setPersistenceRequired();
            m.setCustomName(Component.literal(id + String.format(Locale.ROOT, " (%.1f x %.1f)", m.getBbWidth(), m.getBbHeight())));
            m.setCustomNameVisible(true);
            n.addFreshEntityWithPassengers(m);
            t += Math.max(m.getBbWidth(), 1.0) + 2.5;
            nb++;
        }
        int total = nb;
        c.getSource().sendSuccess(() -> Component.literal("Zoo : " + total + " bêtes alignées (immobiles ; /kill @e[type=!player,distance=..120] pour les retirer)"), false);
        return nb;
    }
}

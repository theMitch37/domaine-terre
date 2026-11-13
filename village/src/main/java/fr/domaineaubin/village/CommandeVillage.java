package fr.domaineaubin.village;

import com.mojang.brigadier.CommandDispatcher;
import com.mojang.brigadier.arguments.IntegerArgumentType;
import fr.domaineaubin.terre.api.LieuxTerre;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.Registries;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.tags.TagKey;
import net.minecraft.world.level.levelgen.Heightmap;

/** /village point <x> <z> : biome et hauteur du sol à un point, types de village possibles (pour le banc et les tests). */
final class CommandeVillage {
    private static final String[] TYPES = {"plains", "desert", "savanna", "snowy", "taiga"};

    private CommandeVillage() {
    }

    /**
     * Diagnostic : hauteur estimée par le générateur (celle que les structures utilisent avant que le chunk existe)
     * et hauteur réelle au centre du chunk, biome de bruit à plusieurs hauteurs.
     */
    private static int colonne(CommandSourceStack src, int x, int z) {
        ServerLevel l = src.getServer().overworld();
        int cx = (x & ~15) + 8, cz = (z & ~15) + 8;
        var gen = l.getChunkSource().getGenerator();
        var rs = l.getChunkSource().randomState();
        int estime = gen.getFirstOccupiedHeight(cx, cz, Heightmap.Types.WORLD_SURFACE_WG, l, rs);
        int reel = l.getChunk(cx >> 4, cz >> 4).getHeight(Heightmap.Types.WORLD_SURFACE_WG, cx & 15, cz & 15);
        StringBuilder b = new StringBuilder("[Colonne] centre (" + cx + ", " + cz + ") estimée y=" + estime + " réelle y=" + reel + " |");
        for (int y : new int[]{estime, reel, 40, 0, -60}) {
            var h = gen.getBiomeSource().getNoiseBiome(cx >> 2, y >> 2, cz >> 2, rs.sampler());
            b.append(" y").append(y).append("=").append(h.unwrapKey().map(k -> k.location().getPath()).orElse("?"));
        }
        String t = b.toString();
        src.sendSuccess(() -> Component.literal(t), false);
        return 1;
    }

    static void enregistrer(CommandDispatcher<CommandSourceStack> d) {
        d.register(Commands.literal("village").requires(s -> s.hasPermission(2))
                .then(Commands.literal("colonne")
                        .then(Commands.argument("x", IntegerArgumentType.integer())
                                .then(Commands.argument("z", IntegerArgumentType.integer())
                                        .executes(c -> colonne(c.getSource(), IntegerArgumentType.getInteger(c, "x"),
                                                IntegerArgumentType.getInteger(c, "z"))))))
                .then(Commands.literal("point")
                        .then(Commands.argument("x", IntegerArgumentType.integer())
                                .then(Commands.argument("z", IntegerArgumentType.integer())
                                        .executes(c -> {
                                            int x = IntegerArgumentType.getInteger(c, "x"), z = IntegerArgumentType.getInteger(c, "z");
                                            ServerLevel l = c.getSource().getServer().overworld();
                                            int y = l.getChunk(x >> 4, z >> 4).getHeight(Heightmap.Types.WORLD_SURFACE_WG, x & 15, z & 15);
                                            var biome = l.getBiome(new BlockPos(x, y, z));
                                            StringBuilder types = new StringBuilder();
                                            for (String t : TYPES) {
                                                var tag = TagKey.create(Registries.BIOME, new ResourceLocation("minecraft", "has_structure/village_" + t));
                                                if (biome.is(tag)) types.append(t).append(' ');
                                            }
                                            String b = biome.unwrapKey().map(k -> k.location().toString()).orElse("?");
                                            String txt = "[Village] (" + x + ", " + z + ") y=" + y + " biome " + b + " | types : "
                                                    + (types.length() == 0 ? "aucun" : types.toString().trim())
                                                    + (LieuxTerre.a(x, z) != null ? " | dans un lieu unique" : "");
                                            c.getSource().sendSuccess(() -> Component.literal(txt), false);
                                            return 1;
                                        })))));
    }
}

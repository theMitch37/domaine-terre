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

    static void enregistrer(CommandDispatcher<CommandSourceStack> d) {
        d.register(Commands.literal("village").requires(s -> s.hasPermission(2))
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

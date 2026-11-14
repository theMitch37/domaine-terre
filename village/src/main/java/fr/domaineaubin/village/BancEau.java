package fr.domaineaubin.village;

import net.minecraft.commands.CommandSourceStack;
import net.minecraft.core.registries.Registries;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.tags.FluidTags;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.NoiseColumn;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.chunk.ChunkAccess;
import net.minecraft.world.level.chunk.ChunkStatus;
import net.minecraft.world.level.levelgen.structure.BoundingBox;
import net.minecraft.world.level.levelgen.structure.StructurePiece;
import net.minecraft.world.level.levelgen.structure.StructureStart;

import java.io.PrintWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Banc « villages sur l'eau » (14/11/2026) : /village eau [pas]. Pour chaque village de la liste (un sur « pas »), le
 * serveur calcule le vrai plan du village (départ de structure du chunk), puis chaque pièce est comparée au vrai
 * terrain du moteur (colonne de base, eau des fleuves, lacs et mers comprise, sans les structures) : une pièce « sur
 * l'eau » a au moins un point de son emprise (grille de 3 blocs) dont le haut du terrain, sous la pièce, est de l'eau.
 * Résultat : village_eau.txt dans le dossier du serveur. Indépendant de la règle du mixin (qui lit la carte Terre).
 */
final class BancEau {
    private BancEau() {
    }

    static int lancer(CommandSourceStack src, int pas) {
        ServerLevel l = src.getServer().overworld();
        var gen = l.getChunkSource().getGenerator();
        var rs = l.getChunkSource().randomState();
        var reg = l.registryAccess().registryOrThrow(Registries.STRUCTURE);
        List<ChunkPos> points = new ArrayList<>(Points.liste("villages", PlacementFixe.CASE).values());
        points.sort((a, b) -> a.x != b.x ? Integer.compare(a.x, b.x) : Integer.compare(a.z, b.z));
        Map<Long, Boolean> eaux = new HashMap<>();
        int villages = 0, absents = 0, villagesMouilles = 0, pieces = 0, piecesMouillees = 0;
        long t0 = System.currentTimeMillis();
        StringBuilder detail = new StringBuilder();
        for (int i = 0; i < points.size(); i += Math.max(1, pas)) {
            ChunkPos c = points.get(i);
            ChunkAccess ch = l.getChunkSource().getChunk(c.x, c.z, ChunkStatus.STRUCTURE_STARTS, true);
            StructureStart depart = null;
            String type = "?";
            for (var e : ch.getAllStarts().entrySet()) {
                String nom = reg.getKey(e.getKey()) == null ? "?" : reg.getKey(e.getKey()).getPath();
                if (nom.startsWith("village_") && e.getValue().isValid()) {
                    depart = e.getValue();
                    type = nom;
                }
            }
            if (depart == null) {
                absents++;
                continue;
            }
            villages++;
            int mouillees = 0;
            for (StructurePiece p : depart.getPieces()) {
                pieces++;
                if (surEau(p.getBoundingBox(), gen, l, rs, eaux)) mouillees++;
            }
            piecesMouillees += mouillees;
            if (mouillees > 0) {
                villagesMouilles++;
                detail.append(String.format("%d pièces sur l'eau / %d  %s  (%d, %d)%n", mouillees,
                        depart.getPieces().size(), type, c.getMiddleBlockX(), c.getMiddleBlockZ()));
            }
            if (villages % 200 == 0) {
                DomaineVillage.LOGGER.info("Banc eau : {} villages, {} sur l'eau, {} s", villages, villagesMouilles,
                        (System.currentTimeMillis() - t0) / 1000);
                eaux.clear();
            }
        }
        String bilan = String.format("BILAN eau (%s) : %d villages générés (%d points sans village), %d avec au moins une "
                        + "pièce sur l'eau ; %d pièces sur %d sur l'eau ; %d s",
                System.getProperty("domaineVillage.eau", "oui"), villages, absents, villagesMouilles, piecesMouillees,
                pieces, (System.currentTimeMillis() - t0) / 1000);
        try (PrintWriter w = new PrintWriter(Files.newBufferedWriter(Path.of("village_eau.txt"), StandardCharsets.UTF_8))) {
            w.println(bilan);
            w.print(detail);
        } catch (Exception e) {
            DomaineVillage.LOGGER.error("Banc eau : écriture impossible", e);
        }
        DomaineVillage.LOGGER.info(bilan);
        src.sendSuccess(() -> Component.literal("[Banc eau] " + bilan), false);
        return 1;
    }

    private static boolean surEau(BoundingBox b, net.minecraft.world.level.chunk.ChunkGenerator gen, ServerLevel l,
                                  net.minecraft.world.level.levelgen.RandomState rs, Map<Long, Boolean> eaux) {
        for (int x = b.minX(); ; x = Math.min(x + 3, b.maxX())) {
            for (int z = b.minZ(); ; z = Math.min(z + 3, b.maxZ())) {
                long cle = ((long) x << 32) ^ (z & 0xFFFFFFFFL) ^ ((long) b.minY() << 52);
                Boolean e = eaux.get(cle);
                if (e == null) {
                    e = colonneEau(gen.getBaseColumn(x, z, l, rs), b.minY(), b.maxY());
                    eaux.put(cle, e);
                }
                if (e) return true;
                if (z >= b.maxZ()) break;
            }
            if (x >= b.maxX()) break;
        }
        return false;
    }

    /** Le haut du terrain (premier bloc non vide en descendant, entre le haut de la pièce + 4 et son bas - 6) est de l'eau. */
    private static boolean colonneEau(NoiseColumn col, int minY, int maxY) {
        for (int y = maxY + 4; y >= minY - 6; y--) {
            BlockState s = col.getBlock(y);
            if (s.isAir()) continue;
            return s.getFluidState().is(FluidTags.WATER);
        }
        return false;
    }
}

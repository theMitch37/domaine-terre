package fr.domaineaubin.meteo.vagues;

import net.minecraft.client.Minecraft;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.core.BlockPos;
import net.minecraft.world.phys.BlockHitResult;
import net.minecraft.world.phys.HitResult;
import net.minecraft.world.phys.Vec3;

import java.util.Locale;

/** /vagues ici (0.3.4) : ce que le client sait de la colonne visée, pour comprendre un trou dans la mer. */
public final class DiagnosticVagues {
    private DiagnosticVagues() {
    }

    public static String colonneVisee() {
        Minecraft mc = Minecraft.getInstance();
        ClientLevel level = mc.level;
        if (level == null || mc.player == null) return "pas de monde";
        BlockPos b = mc.player.blockPosition();
        HitResult h = mc.player.pick(64, 1, true);                       // true : s'arrête sur l'eau
        if (h instanceof BlockHitResult r && h.getType() == HitResult.Type.BLOCK) b = r.getBlockPos();
        int x = b.getX(), z = b.getZ(), y = level.getSeaLevel() - 1;
        BlockPos s = new BlockPos(x, y, z);
        Vec3 c = mc.gameRenderer.getMainCamera().getPosition();
        return String.format(Locale.ROOT,
                "%d %d | masque %s (carré %s, coupé %s) | profondeur %d, gardée %d, recalcul %d | mer %s | y%d : %s %s | au-dessus : %s | biome %s | distance %.0f",
                x, z, MasqueEau.masquer(level, x, y, z), MasqueEau.dansCarre(x, z), MasqueEau.coupe,
                Houle.profondeur(level, x, z), Houle.profondeurGardee(level, x, z), Houle.profondeurDirecte(level, x, z),
                Houle.mer(level, x, y, z), y, level.getBlockState(s).getBlock().getDescriptionId(),
                level.getFluidState(s).isSource() ? "(source)" : "(" + level.getFluidState(s).getAmount() + ")",
                level.getBlockState(s.above()).getBlock().getDescriptionId(),
                level.getBiome(s).unwrapKey().map(k -> k.location().toString()).orElse("?"),
                Math.sqrt((x - c.x) * (x - c.x) + (z - c.z) * (z - c.z)));
    }
}

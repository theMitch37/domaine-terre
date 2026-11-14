package fr.domaineaubin.meteo.mixin;

import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.math.Axis;
import fr.domaineaubin.meteo.vagues.Houle;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.entity.BoatRenderer;
import net.minecraft.world.entity.vehicle.Boat;
import net.minecraft.world.level.Level;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/**
 * Prototype des vagues : la barque penche avec la pente de la houle (tangage et roulis), avant sa rotation de cap :
 * son pont s'aligne sur la surface de l'eau (normale (−dh/dx, 1, −dh/dz)).
 */
@Mixin(BoatRenderer.class)
public abstract class BarqueRenduMixin {
    @Inject(method = "render(Lnet/minecraft/world/entity/vehicle/Boat;FFLcom/mojang/blaze3d/vertex/PoseStack;Lnet/minecraft/client/renderer/MultiBufferSource;I)V",
            at = @At(value = "INVOKE", target = "Lcom/mojang/blaze3d/vertex/PoseStack;mulPose(Lorg/joml/Quaternionf;)V", ordinal = 0))
    private void domaineWeather$pencher(Boat b, float cap, float partiel, PoseStack ps, MultiBufferSource tampons,
                                        int lumiere, CallbackInfo ci) {
        if (!Houle.actif()) return;
        Level l = b.level();
        if (l.dimension() != Level.OVERWORLD || b.getY() < l.getSeaLevel() - 3 || b.getY() > l.getSeaLevel() + 3 + 2 * Houle.reglages().amplitude) return;
        double a = Houle.amplitude(l, b.getX(), b.getZ());
        if (a <= 0.02) return;
        double[] p = Houle.pente(b.getX(), b.getZ(), Houle.temps(l, partiel), a);
        ps.mulPose(Axis.XP.rotation((float) -Math.atan(p[1])));
        ps.mulPose(Axis.ZP.rotation((float) Math.atan(p[0])));
    }
}

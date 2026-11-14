package fr.domaineaubin.meteo.mixin;

import fr.domaineaubin.meteo.vagues.Houle;
import it.unimi.dsi.fastutil.objects.Object2DoubleMap;
import net.minecraft.tags.FluidTags;
import net.minecraft.tags.TagKey;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.vehicle.Boat;
import net.minecraft.world.level.material.Fluid;
import net.minecraft.world.phys.AABB;
import net.minecraftforge.common.ForgeMod;
import net.minecraftforge.fluids.FluidType;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

import java.util.Set;

/**
 * Eau virtuelle (Domaine Weather 0.3.0) : entre l'eau plate du jeu et la surface de la houle, en pleine mer, tout se
 * passe comme dans l'eau pour les entités : nage (rapide comprise), flottaison, chute amortie, respiration, poissons qui
 * ne s'étouffent pas. Même formule que la surface dessinée et la barque. Les barques gardent leur propre règle.
 */
@Mixin(Entity.class)
public abstract class EauVagueMixin {
    @Shadow protected boolean wasTouchingWater;
    @Shadow protected Object2DoubleMap<TagKey<Fluid>> fluidHeight;
    @Shadow(remap = false) protected Object2DoubleMap<FluidType> forgeFluidTypeHeight;
    @Shadow @Final private Set<TagKey<Fluid>> fluidOnEyes;
    @Shadow(remap = false) private FluidType forgeFluidTypeOnEyes;

    @Shadow public abstract AABB getBoundingBox();
    @Shadow public abstract double getEyeY();
    @Shadow public abstract double getX();
    @Shadow public abstract double getZ();
    @Shadow public abstract net.minecraft.world.level.Level level();
    @Shadow public abstract void resetFallDistance();
    @Shadow public abstract void clearFire();

    @Inject(method = "updateInWaterStateAndDoWaterCurrentPushing", at = @At("TAIL"))
    private void domaineWeather$eauDeVague(CallbackInfo ci) {
        Entity moi = (Entity) (Object) this;
        if (moi instanceof Boat) return;
        AABB b = getBoundingBox();
        double s = Houle.surface(level(), getX(), getZ(), b.minY, b.maxY);
        if (Double.isNaN(s) || b.minY >= s) return;
        double h = Math.min(b.maxY, s) - b.minY;                      // hauteur d'eau sur l'entité, comme le jeu
        if (h <= fluidHeight.getDouble(FluidTags.WATER)) return;       // déjà plus mouillée par la vraie eau
        fluidHeight.put(FluidTags.WATER, h);
        forgeFluidTypeHeight.put(ForgeMod.WATER_TYPE.get(), h);
        if (!wasTouchingWater) {
            wasTouchingWater = true;
            resetFallDistance();
            clearFire();
        }
    }

    @Inject(method = "updateFluidOnEyes", at = @At("TAIL"))
    private void domaineWeather$yeuxDansLaVague(CallbackInfo ci) {
        if ((Object) this instanceof Boat || fluidOnEyes.contains(FluidTags.WATER)) return;
        double y = getEyeY() - 0.11111111;                               // comme le jeu (respiration sous les yeux)
        double s = Houle.surface(level(), getX(), getZ(), y, y);
        if (Double.isNaN(s) || y >= s) return;
        fluidOnEyes.add(FluidTags.WATER);
        forgeFluidTypeOnEyes = ForgeMod.WATER_TYPE.get();
    }
}

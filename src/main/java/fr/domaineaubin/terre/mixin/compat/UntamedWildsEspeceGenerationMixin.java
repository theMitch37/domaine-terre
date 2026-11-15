package fr.domaineaubin.terre.mixin.compat;

import fr.domaineaubin.terre.monde.FauneSpawns;
import net.minecraft.core.Holder;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.level.biome.Biome;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.ModifyVariable;

/**
 * 15/11/2026 : même choix d'espèce par notre table pour les bêtes nées par les features d'Untamed Wilds (mer, eaux
 * douces : FaunaSpawn.performWorldGenSpawning, qui tire l'espèce lui-même puis supprime la bête si le code vaut 99).
 * La bête (variable locale 23) est gardée pour le fil courant juste avant le tirage (variable locale 11).
 */
@Pseudo
@Mixin(targets = "untamedwilds.world.FaunaSpawn", remap = false)
public abstract class UntamedWildsEspeceGenerationMixin {
    private static final ThreadLocal<Mob> BETE = new ThreadLocal<>();
    private static final ThreadLocal<Holder<Biome>> BIOME = new ThreadLocal<>();

    @ModifyVariable(method = "performWorldGenSpawning", remap = false, index = 24, at = @At(value = "STORE", remap = false))
    private static Holder<Biome> domaineTerre$biome(Holder<Biome> b) {
        BIOME.set(b);
        return b;
    }

    @ModifyVariable(method = "performWorldGenSpawning", remap = false, index = 23, at = @At(value = "STORE", remap = false))
    private static Mob domaineTerre$bete(Mob m) {
        BETE.set(m);
        return m;
    }

    @ModifyVariable(method = "performWorldGenSpawning", remap = false, index = 11,
            at = @At(value = "INVOKE_ASSIGN", remap = false,
                    target = "Luntamedwilds/entity/ISpecies;setSpeciesByBiome(Lnet/minecraft/core/Holder;Lnet/minecraft/world/entity/MobSpawnType;)I"))
    private static int domaineTerre$espece(int v) {
        Mob m = BETE.get();
        Holder<Biome> b = BIOME.get();
        BETE.remove();
        BIOME.remove();
        return m == null ? v : FauneSpawns.especeUntamedWilds(m, v, b);
    }
}

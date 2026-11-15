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
 * 15/11/2026 : l'espèce d'une bête d'Untamed Wilds née dans le monde (table du mod Terre, apparitions) est choisie par
 * notre table, plus par les biomes d'Untamed Wilds (voir FauneSpawns.especeUntamedWilds). Cible : le résultat de
 * ISpecies.setSpeciesByBiome dans ComplexMob.finalizeSpawn (m_6518_, variable locale 7 d'Untamed Wilds 4.0.4).
 * Facultatif : sans Untamed Wilds, cette mixin est ignorée.
 */
@Pseudo
@Mixin(targets = "untamedwilds.entity.ComplexMob", remap = false)
public abstract class UntamedWildsEspeceMixin {
    private static final ThreadLocal<Holder<Biome>> BIOME = new ThreadLocal<>();

    /** Le vrai biome de la bête (variable locale 6, lue dans le monde en génération), gardé pour le tirage. */
    @ModifyVariable(method = "m_6518_", remap = false, index = 6, at = @At(value = "STORE", remap = false))
    private Holder<Biome> domaineTerre$biome(Holder<Biome> b) {
        BIOME.set(b);
        return b;
    }

    @ModifyVariable(method = "m_6518_", remap = false, index = 7,
            at = @At(value = "INVOKE_ASSIGN", remap = false,
                    target = "Luntamedwilds/entity/ISpecies;setSpeciesByBiome(Lnet/minecraft/core/Holder;Lnet/minecraft/world/entity/MobSpawnType;)I"))
    private int domaineTerre$espece(int v) {
        Object moi = this;
        Holder<Biome> b = BIOME.get();
        BIOME.remove();
        return moi instanceof Mob m ? FauneSpawns.especeUntamedWilds(m, v, b) : v;
    }
}

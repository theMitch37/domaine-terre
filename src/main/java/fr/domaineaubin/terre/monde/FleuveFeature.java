package fr.domaineaubin.terre.monde;

import com.mojang.serialization.Codec;
import net.minecraft.world.level.levelgen.feature.Feature;
import net.minecraft.world.level.levelgen.feature.FeaturePlaceContext;
import net.minecraft.world.level.levelgen.feature.configurations.NoneFeatureConfiguration;

/**
 * Ancienne pose de l'eau des fleuves. Désormais les vallées sont creusées sous le niveau de la mer
 * et le moteur les remplit lui-même : cette feature ne fait plus rien (gardée pour ne pas casser
 * le biome modifier et les mondes existants).
 */
public class FleuveFeature extends Feature<NoneFeatureConfiguration> {
    public FleuveFeature(Codec<NoneFeatureConfiguration> codec) {
        super(codec);
    }

    @Override
    public boolean place(FeaturePlaceContext<NoneFeatureConfiguration> ctx) {
        return false;
    }
}

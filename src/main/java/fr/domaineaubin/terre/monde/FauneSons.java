package fr.domaineaubin.terre.monde;

import fr.domaineaubin.terre.DomaineTerre;
import net.minecraft.core.Holder;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.sounds.SoundEvent;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.event.PlayLevelSoundEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.registries.ForgeRegistries;

import java.util.Optional;

/**
 * Cris empruntés (11/11/2026, test en jeu : « les cerfs font un bruit de mouton ») : le cerf et le renne de Better
 * Animals Plus n'ont pas de cri à eux et reprennent celui du mouton. Le son d'une bête part d'une position (pas d'une
 * entité) : un son de mouton joué à la place exacte d'un cerf de Better Animals Plus devient celui du cerf de Naturalist
 * (ou de WilderNature).
 */
@Mod.EventBusSubscriber(modid = DomaineTerre.MOD_ID, bus = Mod.EventBusSubscriber.Bus.FORGE)
public final class FauneSons {
    private FauneSons() {
    }

    @SubscribeEvent
    public static void son(PlayLevelSoundEvent.AtPosition event) {
        Holder<SoundEvent> s = event.getSound();
        if (s == null || event.getLevel() == null) return;
        ResourceLocation id = s.unwrapKey().map(k -> k.location()).orElse(null);
        if (id == null || !id.getNamespace().equals("minecraft")) return;
        // 12/11/2026 (test en jeu : « l'élan de Better Animals Plus a un bruit de vache ») : cri de l'élan d'Alex's Mobs
        if (id.getPath().startsWith("entity.cow.")) {
            Vec3 p = event.getPosition();
            boolean elan = !event.getLevel().getEntitiesOfClass(Entity.class, new AABB(p, p).inflate(0.05),
                    e -> "betteranimalsplus:moose".equals(String.valueOf(ForgeRegistries.ENTITY_TYPES.getKey(e.getType())))).isEmpty();
            if (!elan) return;
            String quoi = id.getPath().substring("entity.cow.".length());
            if (quoi.equals("step") || quoi.equals("milk")) return;
            son(quoi.equals("ambient") ? "alexsmobs:moose_idle" : "alexsmobs:moose_hurt").ifPresent(event::setSound);
            return;
        }
        if (!id.getPath().startsWith("entity.sheep.")) return;
        Vec3 p = event.getPosition();
        boolean cerf = !event.getLevel().getEntitiesOfClass(Entity.class, new AABB(p, p).inflate(0.05),
                e -> estCerf(e.getType())).isEmpty();
        if (!cerf) return;
        String quoi = id.getPath().substring("entity.sheep.".length());   // ambient, hurt, death, step, shear
        if (quoi.equals("step")) return;
        Optional<Holder<SoundEvent>> n = remplacement(quoi);
        n.ifPresent(event::setSound);
    }

    private static boolean estCerf(EntityType<?> t) {
        ResourceLocation k = ForgeRegistries.ENTITY_TYPES.getKey(t);
        return k != null && k.getNamespace().equals("betteranimalsplus")
                && (k.getPath().equals("deer") || k.getPath().equals("reindeer"));
    }

    private static Optional<Holder<SoundEvent>> remplacement(String quoi) {
        boolean cri = quoi.equals("ambient");
        Optional<Holder<SoundEvent>> h = son(cri ? "naturalist:entity.deer.ambient" : "naturalist:entity.deer.hurt");
        if (h.isEmpty()) h = son(cri ? "wildernature:deer_ambient" : quoi.equals("death") ? "wildernature:deer_death"
                : "wildernature:deer_hurt");
        return h;
    }

    private static Optional<Holder<SoundEvent>> son(String id) {
        ResourceLocation r = ResourceLocation.tryParse(id);
        if (r == null || !ForgeRegistries.SOUND_EVENTS.containsKey(r)) return Optional.empty();
        return ForgeRegistries.SOUND_EVENTS.getHolder(r);
    }
}

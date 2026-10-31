package fr.domaineaubin.lieux.bloc;

import fr.domaineaubin.lieux.DomaineLieux;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.entity.BlockEntityType;
import net.minecraft.world.level.block.state.BlockBehaviour;
import net.minecraft.world.level.material.MapColor;
import net.minecraft.world.level.block.SoundType;
import net.minecraftforge.eventbus.api.IEventBus;
import net.minecraftforge.registries.DeferredRegister;
import net.minecraftforge.registries.ForgeRegistries;
import net.minecraftforge.registries.RegistryObject;

/**
 * Blocs propres aux lieux (lot 3) : fumerolle (volcans, champs géothermiques) et geyser (Strokkur). Ils ne servent
 * qu'à la génération (pas d'objet) ; leurs effets (fumée, jets d'eau) sont des particules côté client.
 */
public final class BlocsLieux {
    private BlocsLieux() {}

    public static final DeferredRegister<Block> BLOCS = DeferredRegister.create(ForgeRegistries.BLOCKS, DomaineLieux.MOD_ID);
    public static final DeferredRegister<BlockEntityType<?>> ENTITES =
            DeferredRegister.create(ForgeRegistries.BLOCK_ENTITY_TYPES, DomaineLieux.MOD_ID);

    public static final RegistryObject<Block> FUMEROLLE = BLOCS.register("fumerolle", () -> new BlocFumant(
            BlockBehaviour.Properties.of().mapColor(MapColor.TERRACOTTA_YELLOW).strength(1.5f, 6.0f)
                    .sound(SoundType.TUFF).requiresCorrectToolForDrops(), false));
    public static final RegistryObject<Block> GEYSER = BLOCS.register("geyser", () -> new BlocFumant(
            BlockBehaviour.Properties.of().mapColor(MapColor.QUARTZ).strength(1.5f, 6.0f)
                    .sound(SoundType.CALCITE).requiresCorrectToolForDrops(), true));

    @SuppressWarnings("DataFlowIssue")
    public static final RegistryObject<BlockEntityType<EntiteFumante>> ENTITE_FUMANTE = ENTITES.register("fumant",
            () -> BlockEntityType.Builder.of(EntiteFumante::new, FUMEROLLE.get(), GEYSER.get()).build(null));

    public static void inscrire(IEventBus bus) {
        BLOCS.register(bus);
        ENTITES.register(bus);
    }
}

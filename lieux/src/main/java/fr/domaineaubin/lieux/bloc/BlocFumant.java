package fr.domaineaubin.lieux.bloc;

import net.minecraft.core.BlockPos;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.BaseEntityBlock;
import net.minecraft.world.level.block.RenderShape;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.entity.BlockEntityTicker;
import net.minecraft.world.level.block.entity.BlockEntityType;
import net.minecraft.world.level.block.state.BlockState;
import org.jetbrains.annotations.Nullable;

/** Bloc qui fume (fumerolle) ou qui jaillit (geyser) : tout se passe côté client, dans {@link EntiteFumante}. */
public class BlocFumant extends BaseEntityBlock {
    final boolean geyser;

    public BlocFumant(Properties p, boolean geyser) {
        super(p);
        this.geyser = geyser;
    }

    @Override
    public RenderShape getRenderShape(BlockState etat) {
        return RenderShape.MODEL;
    }

    @Nullable
    @Override
    public BlockEntity newBlockEntity(BlockPos pos, BlockState etat) {
        return new EntiteFumante(pos, etat);
    }

    @Nullable
    @Override
    public <T extends BlockEntity> BlockEntityTicker<T> getTicker(Level niveau, BlockState etat, BlockEntityType<T> type) {
        if (!niveau.isClientSide) {
            // 12/11/2026 : l'eau du geyser brûle (dégâts côté serveur)
            return geyser ? createTickerHelper(type, BlocsLieux.ENTITE_FUMANTE.get(), EntiteFumante::tickServeur) : null;
        }
        return createTickerHelper(type, BlocsLieux.ENTITE_FUMANTE.get(), EntiteFumante::tickClient);
    }
}

package fr.domaineaubin.meteo.mixin;

import fr.domaineaubin.meteo.ClientMeteo;
import fr.domaineaubin.meteo.Saisons;
import net.minecraft.network.chat.Component;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.TooltipFlag;
import net.minecraft.world.level.Level;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Redirect;
import sereneseasons.api.season.ISeasonState;
import sereneseasons.item.CalendarItem;

import java.util.List;

/** Serene Seasons : le calendrier affiche la saison là où se trouve le joueur. */
@Mixin(CalendarItem.class)
public abstract class CalendrierMixin {
    @Redirect(method = "appendHoverText",
            at = @At(value = "INVOKE", target = "Lsereneseasons/api/season/ISeasonState;getSeasonCycleTicks()I", remap = false))
    private int domaineWeather$saisonDuJoueur(ISeasonState etat, ItemStack pile, Level level, List<Component> lignes, TooltipFlag f) {
        return Saisons.ticksLocaux(level, etat.getSeasonCycleTicks(), ClientMeteo.zJoueur());
    }
}

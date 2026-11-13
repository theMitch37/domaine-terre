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

/**
 * Serene Seasons : le calendrier affiche la saison là où se trouve le joueur. Le jar de Serene Seasons est déjà
 * en noms SRG : appendHoverText y porte le nom m_7373_ (Item.appendHoverText en 1.20.1). Facultatif (require 0) :
 * si le nom change, seul le calendrier reste sur la saison du nord.
 */
@Mixin(value = CalendarItem.class, remap = false)
public abstract class CalendrierMixin {
    @Redirect(method = "m_7373_", require = 0,
            at = @At(value = "INVOKE", target = "Lsereneseasons/api/season/ISeasonState;getSeasonCycleTicks()I"))
    private int domaineWeather$saisonDuJoueur(ISeasonState etat, ItemStack pile, Level level, List<Component> lignes, TooltipFlag f) {
        return Saisons.ticksLocaux(level, etat.getSeasonCycleTicks(), ClientMeteo.zJoueur());
    }
}

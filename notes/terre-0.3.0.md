# Domaine d'Aubin – Terre 0.3.0

## English

**The map is now fixed: every world shows the same real Earth, with the same biomes in the same places.**

### New
- **Fixed biome map** based on real land cover (Copernicus Global Land Service, 2019), combined with the Köppen climate and the relief. Forests, savannas, deserts, steppes, tundra and wetlands are where they really are. The land surface no longer relies on random biome placement (oceans and caves are unchanged).
- **1:250 is now the default world type** ("Default"). Earth 1:500 and Earth 1:1000 are still available in the world type list.
- **Inland lakes** take the region and climate of their shores: no more beaches, seals or ocean fish in the middle of the continent.
- **Natural borders**: transitions between regions and climates are irregular instead of straight lines.
- **17 region tags** (`domaine_terre:region/...`) grouping the terroirs, for modpack makers and datapacks.
- **Real snow line**: temperatures adjusted on 38 biomes, so snow falls where it should (and no longer in hot canyons).
- **Desert cliffs** are now sandstone on steep slopes.
- **Beaches and stony shores** only appear along the real sea.
- API for the *Unique Places* addon.

### Important
- **Start a new world.** Existing worlds still open (their scale is saved), but newly generated chunks will use the new biome map and won't match the old ones.
- Recommended companion mod: **Ecologics** (required by the modpack's terroir datapack).

Land cover data: Copernicus Global Land Service, Land Cover 100m v3.0.1 (2019), CC BY 4.0.

---

## Français

**La carte est désormais fixe : chaque monde montre la même vraie Terre, avec les mêmes biomes aux mêmes endroits.**

### Nouveautés
- **Carte des biomes fixe**, d'après la couverture du sol réelle (Copernicus Global Land Service, 2019), croisée avec le climat de Köppen et le relief. Forêts, savanes, déserts, steppes, toundra et marais sont là où ils sont vraiment. La surface des terres ne dépend plus du hasard (océans et grottes inchangés).
- **Le 1:250 devient le type de monde par défaut** (« Par défaut »). Terre 1:500 et Terre 1:1000 restent disponibles dans la liste des types de monde.
- **Lacs intérieurs** : ils prennent la région et le climat de leurs rives. Fini les plages, les phoques et les poissons de mer au milieu du continent.
- **Frontières naturelles** : les passages d'une région ou d'un climat à l'autre sont irréguliers, plus en ligne droite.
- **17 tags de régions** (`domaine_terre:region/...`) qui regroupent les terroirs, pour les créateurs de modpacks et de datapacks.
- **Limite des neiges réelle** : températures corrigées sur 38 biomes, la neige tombe là où elle doit (et plus dans les canyons chauds).
- **Falaises du désert en grès** sur les pentes raides.
- **Plages et côtes rocheuses** seulement au bord de la vraie mer.
- API pour l'addon *Lieux uniques*.

### Important
- **Créez un nouveau monde.** Les anciens mondes s'ouvrent toujours (leur échelle est enregistrée), mais les nouveaux chunks suivront la nouvelle carte des biomes et ne raccorderont pas avec les anciens.
- Mod conseillé : **Ecologics** (nécessaire au datapack des terroirs du modpack).

Données de couverture du sol : Copernicus Global Land Service, Land Cover 100m v3.0.1 (2019), CC BY 4.0.

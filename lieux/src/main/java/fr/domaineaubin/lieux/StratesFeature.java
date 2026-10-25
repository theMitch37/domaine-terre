package fr.domaineaubin.lieux;

import com.mojang.serialization.Codec;
import fr.domaineaubin.terre.api.Lieu;
import fr.domaineaubin.terre.api.LieuxTerre;
import fr.domaineaubin.terre.monde.Terrain;
import net.minecraft.core.BlockPos;
import net.minecraft.tags.BlockTags;
import net.minecraft.world.level.WorldGenLevel;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.levelgen.Heightmap;
import net.minecraft.world.level.levelgen.feature.Feature;
import net.minecraft.world.level.levelgen.feature.FeaturePlaceContext;
import net.minecraft.world.level.levelgen.feature.configurations.NoneFeatureConfiguration;

/**
 * Sculpte les parois des lieux ({@link LieuSculpte}) bloc par bloc, rebouche tout vide sous la surface des zones
 * protégées (grottes et ravins vanilla), puis colore les parois en couches.
 * Ne touche que les blocs de son propre chunk, avant la végétation : rien ne peut se retrouver en l'air.
 * Une seule feature pour tous les lieux : chaque biome de lieu l'appelle, elle demande au lieu de la colonne.
 */
public class StratesFeature extends Feature<NoneFeatureConfiguration> {

    public StratesFeature(Codec<NoneFeatureConfiguration> codec) {
        super(codec);
    }

    @Override
    public boolean place(FeaturePlaceContext<NoneFeatureConfiguration> ctx) {
        WorldGenLevel niveau = ctx.level();
        int x0 = (ctx.origin().getX() >> 4) << 4;
        int z0 = (ctx.origin().getZ() >> 4) << 4;
        BlockPos.MutableBlockPos pos = new BlockPos.MutableBlockPos();
        boolean modifie = false;
        for (int dx = 0; dx < 16; dx++) {
            for (int dz = 0; dz < 16; dz++) {
                int x = x0 + dx, z = z0 + dz;
                Lieu l = LieuxTerre.a(x, z);
                if (!(l instanceof LieuSculpte lieu)) continue;
                double rebord = lieu.rebordSiParoi(x, z);
                boolean protege = lieu.protege(x, z);
                if (Double.isNaN(rebord) && !protege) continue;
                int sommet = niveau.getHeight(Heightmap.Types.OCEAN_FLOOR_WG, x, z) - 1;
                int min = lieu.sculpteMin();
                double vise = Double.NaN;          // surface visée (y), si le lieu la connaît exactement
                boolean taillee = false;
                if (!Double.isNaN(rebord)) {
                    // sculpture : le sol prend exactement la hauteur nette (falaises verticales, replats), au-dessus de l'eau
                    double cible = lieu.hauteurNette(x, z);
                    taillee = !Double.isNaN(cible);
                    if (taillee) {
                        vise = cible;
                        int t = Math.max(min, (int) Math.floor(cible));
                        if (sommet > t) {
                            for (int y = sommet; y > t; y--) {
                                BlockState b = niveau.getBlockState(pos.set(x, y, z));
                                // sous le niveau de la mer, on creuse de l'eau (le moteur ne la fait pas couler pendant la génération)
                                if (b.getFluidState().isEmpty() && !b.isAir())
                                    niveau.setBlock(pos, (y <= 62 ? Blocks.WATER : Blocks.AIR).defaultBlockState(), 2);
                            }
                            sommet = t;
                        } else if (sommet < t && cible >= min) {
                            for (int y = Math.max(sommet + 1, min); y <= t; y++) {
                                niveau.setBlock(pos.set(x, y, z), Blocks.STONE.defaultBlockState(), 2);
                            }
                            sommet = t;
                        }
                        modifie = true;
                    } else {
                        double r = lieu.remblai(x, z);
                        if (!Double.isNaN(r)) {
                            vise = r;
                            if (sommet < Math.floor(r) - 1 && r >= min) {
                                int t = (int) Math.floor(r);
                                for (int y = Math.max(sommet + 1, min); y <= t; y++) {
                                    niveau.setBlock(pos.set(x, y, z), Blocks.STONE.defaultBlockState(), 2);
                                }
                                sommet = t;
                                modifie = true;
                            }
                        }
                    }
                }
                // anti-hasard : grottes, ravins (même venus des chunks voisins) et poches d'eau rebouchés sous la surface
                if (protege) {
                    if (Double.isNaN(vise)) vise = Terrain.get().hauteur(x, z);
                    int haut = (int) Math.floor(vise);
                    int bas = Math.max(lieu.fondStrates(), haut - PROFONDEUR_PROTEGEE);
                    boolean videDessous = false;
                    for (int y = bas; y <= haut; y++) {
                        BlockState b = niveau.getBlockState(pos.set(x, y, z));
                        boolean vide = b.isAir() || !b.getFluidState().isEmpty();
                        // à la surface même, un seul bloc manquant n'est qu'une marche du terrain : on ne bouche que les trous
                        if (vide && (y < haut || videDessous)) {
                            niveau.setBlock(pos, remplissage(y, haut).defaultBlockState(), 2);
                            if (y > sommet) sommet = y;
                            modifie = true;
                        }
                        videDessous = vide;
                    }
                }
                if (Double.isNaN(rebord)) continue;
                // le plateau garde son sol (herbe, forêt) : seules les parois et le fond sont colorés
                for (int y = sommet; y >= lieu.fondStrates(); y--) {
                    BlockState b = niveau.getBlockState(pos.set(x, y, z));
                    if (!remplacable(b)) continue;
                    if (b.is(BlockTags.DIRT) && lieu.garderSol(y, rebord, sommet, taillee)) continue;
                    niveau.setBlock(pos, y == sommet ? lieu.sommet(x, y, z, rebord) : lieu.strate(x, y, z, rebord), 2);
                    modifie = true;
                }
            }
        }
        // blocs en surplomb (arches) des lieux qui touchent ce chunk
        for (Lieu l : LieuxTerre.liste()) {
            if (l instanceof LieuSculpte lieu && (lieu.concerne(x0, z0) || lieu.concerne(x0 + 15, z0)
                    || lieu.concerne(x0, z0 + 15) || lieu.concerne(x0 + 15, z0 + 15))) {
                lieu.poser(niveau, x0, z0);
            }
        }
        return modifie;
    }

    /** Profondeur (blocs) sous la surface visée où aucun vide n'est toléré dans un lieu. */
    private static final int PROFONDEUR_PROTEGEE = 18;

    /** Bloc de rebouchage : sol (herbe, terre) près de la surface des terres, roche ailleurs. */
    private static net.minecraft.world.level.block.Block remplissage(int y, int haut) {
        if (haut <= 62) return Blocks.STONE;
        if (y == haut) return Blocks.GRASS_BLOCK;
        return y >= haut - 3 ? Blocks.DIRT : Blocks.STONE;
    }

    private static boolean remplacable(BlockState b) {
        if (b.isAir() || !b.getFluidState().isEmpty()) return false;
        return b.is(BlockTags.BASE_STONE_OVERWORLD) || b.is(BlockTags.DIRT) || b.is(Blocks.GRAVEL)
                || b.is(Blocks.SAND) || b.is(Blocks.RED_SAND) || b.is(BlockTags.SNOW) || b.is(Blocks.CLAY);
    }

    /** Petite ondulation déterministe des couches (évite des lignes parfaitement droites). */
    public static double ondulation(int x, int z) {
        return ((((x * 73856093) ^ (z * 19349663)) & 7) - 3.5) * 0.0015;
    }
}

package fr.domaineaubin.terre.monde;

import fr.domaineaubin.terre.api.Lieu;
import fr.domaineaubin.terre.api.LieuxTerre;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.mojang.datafixers.util.Pair;
import com.mojang.serialization.Codec;
import com.mojang.serialization.codecs.RecordCodecBuilder;
import fr.domaineaubin.terre.DomaineTerre;
import net.minecraft.core.Holder;
import net.minecraft.core.HolderGetter;
import net.minecraft.core.registries.Registries;
import net.minecraft.resources.RegistryOps;
import net.minecraft.resources.ResourceKey;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.biome.BiomeSource;
import net.minecraft.world.level.biome.Climate;
import net.minecraft.world.level.biome.MultiNoiseBiomeSourceParameterList;
import net.minecraft.world.level.biome.MultiNoiseBiomeSourceParameterLists;
import net.minecraft.util.RandomSource;
import net.minecraft.world.level.levelgen.synth.ImprovedNoise;

import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import java.util.stream.Stream;

/**
 * Source de biomes « domaine_terre:terre » : chaque point prend son terroir sur la carte,
 * puis le climat vanilla choisit parmi les biomes autorisés de ce terroir (copies domaine_terre:terroir/biome).
 * Océans, plages et biomes souterrains restent les biomes vanilla.
 */
public class TerroirBiomeSource extends BiomeSource {

    public static final Codec<TerroirBiomeSource> CODEC = RecordCodecBuilder.create(i -> i.group(
            RegistryOps.retrieveGetter(Registries.BIOME),
            RegistryOps.retrieveGetter(Registries.MULTI_NOISE_BIOME_SOURCE_PARAMETER_LIST),
            Codec.INT.optionalFieldOf("echelle", 500).forGetter(TerroirBiomeSource::echelle)
    ).apply(i, TerroirBiomeSource::new));

    private static final Set<String> OCEANS = Set.of("ocean", "deep_ocean", "warm_ocean", "lukewarm_ocean",
            "deep_lukewarm_ocean", "cold_ocean", "deep_cold_ocean", "frozen_ocean", "deep_frozen_ocean");
    private static final Set<String> CAVERNES = Set.of("lush_caves", "dripstone_caves", "deep_dark");
    private static final Set<String> COTES = Set.of("beach", "stony_shore", "snowy_beach");

    private final HolderGetter<Biome> biomes;
    private final HolderGetter<MultiNoiseBiomeSourceParameterList> parametres;
    private volatile Tables tables;

    private record Tables(List<Climate.ParameterList<Holder<Biome>>> parTerroir, Climate.ParameterList<Holder<Biome>> mer,
                          Set<Holder<Biome>> tous, List<String> cles, List<Holder<Biome>> lieux,
                          List<Holder<Biome>[]> fixes, java.util.Map<String, Holder<Biome>[]> mers,
                          List<Holder<Biome>> lacs, List<Holder<Biome>> fleuves) {
    }

    /** Océan vanilla -> température des biomes domaine_terre:mer/<température>_<bande> (couleurs des eaux, 04/11/2026). */
    private static final java.util.Map<String, String> TEMP_MER = java.util.Map.of(
            "warm_ocean", "chaude", "lukewarm_ocean", "tiede", "deep_lukewarm_ocean", "tiede",
            "ocean", "temperee", "deep_ocean", "temperee", "cold_ocean", "froide", "deep_cold_ocean", "froide",
            "frozen_ocean", "gelee", "deep_frozen_ocean", "gelee");
    private static final String[] BANDES_MER = {"cote", "plateau", "large", "abysse"};

    private final int echelle;

    /** Décalage des points de lecture des cartes terroir et climat : frontières irrégulières, pas en escalier. */
    private static final ImprovedNoise BRUIT_FRONTIERE = new ImprovedNoise(RandomSource.create(20261019L));

    public TerroirBiomeSource(HolderGetter<Biome> biomes, HolderGetter<MultiNoiseBiomeSourceParameterList> parametres, int echelle) {
        this.biomes = biomes;
        this.parametres = parametres;
        this.echelle = echelle;
    }

    public int echelle() {
        return echelle;
    }

    private Holder<Biome> vanilla(String chemin) {
        return biomes.getOrThrow(ResourceKey.create(Registries.BIOME, new ResourceLocation("minecraft", chemin)));
    }

    private Tables tables() {
        Tables t = tables;
        if (t != null) return t;
        synchronized (this) {
            if (tables != null) return tables;
            // points climatiques de l'Overworld vanilla (biome vanilla de référence pour chaque point)
            List<Pair<Climate.ParameterPoint, Holder<Biome>>> points =
                    parametres.getOrThrow(MultiNoiseBiomeSourceParameterLists.OVERWORLD).value().parameters().values();

            JsonObject listes = lireListes();
            Set<Holder<Biome>> tous = new LinkedHashSet<>();
            List<Climate.ParameterList<Holder<Biome>>> parTerroir = new ArrayList<>();
            parTerroir.add(null); // index 0 = mer
            List<String> cles = new ArrayList<>();
            cles.add("mer");
            // l'ordre des terroirs suit terroirs.json (index 1..29)
            for (String cle : ordreTerroirs()) {
                cles.add(cle);
                Set<String> autorises = new HashSet<>();
                for (JsonElement e : listes.getAsJsonArray(cle)) autorises.add(e.getAsString());
                List<Pair<Climate.ParameterPoint, Holder<Biome>>> l = new ArrayList<>();
                for (var p : points) {
                    String chemin = p.getSecond().unwrapKey().map(k -> k.location().getPath()).orElse("");
                    Holder<Biome> h;
                    if (autorises.contains(chemin)) {
                        h = biomes.getOrThrow(ResourceKey.create(Registries.BIOME,
                                new ResourceLocation(DomaineTerre.MOD_ID, cle + "/" + chemin)));
                    } else if (OCEANS.contains(chemin) || CAVERNES.contains(chemin)) {
                        h = vanilla(chemin);
                    } else {
                        continue;
                    }
                    l.add(Pair.of(p.getFirst(), h));
                    tous.add(h);
                }
                parTerroir.add(new Climate.ParameterList<>(l));
            }
            List<Pair<Climate.ParameterPoint, Holder<Biome>>> mer = new ArrayList<>();
            for (var p : points) {
                String chemin = p.getSecond().unwrapKey().map(k -> k.location().getPath()).orElse("");
                if (OCEANS.contains(chemin) || CAVERNES.contains(chemin) || COTES.contains(chemin)) {
                    Holder<Biome> h = vanilla(chemin);
                    mer.add(Pair.of(p.getFirst(), h));
                    tous.add(h);
                }
            }
            // biomes uniques des lieux (addons), dans l'ordre du registre
            List<Holder<Biome>> lieux = new ArrayList<>();
            for (Lieu lieu : LieuxTerre.liste()) {
                Holder<Biome> h = biomes.getOrThrow(ResourceKey.create(Registries.BIOME, lieu.biome()));
                lieux.add(h);
                tous.add(h);
            }
            // carte des biomes fixe : pour chaque terroir, la copie de chaque biome de biomes.json (null si absente)
            List<Holder<Biome>[]> fixes = new ArrayList<>();
            fixes.add(null);
            List<String> noms = new ArrayList<>();
            noms.add("");
            if (TerroirBiomeSource.class.getResource("/domaine_terre/carte/biomes.json") != null) {
                for (JsonElement e : lireJson("biomes.json").getAsJsonArray()) noms.add(e.getAsString());
            }
            for (int i = 1; i < cles.size(); i++) {
                @SuppressWarnings("unchecked")
                Holder<Biome>[] tab = new Holder[noms.size()];
                // seulement les copies qui existent (terroirs_biomes.json) : demander une clé absente
                // au registre déjà gelé fait planter le jeu au lieu de répondre « absent »
                Set<String> existants = new HashSet<>();
                if (listes.has(cles.get(i))) {
                    for (JsonElement e : listes.getAsJsonArray(cles.get(i))) existants.add(e.getAsString());
                }
                for (int b = 1; b < noms.size(); b++) {
                    if (!existants.contains(noms.get(b))) continue;
                    Holder<Biome> h = biomes.getOrThrow(ResourceKey.create(Registries.BIOME,
                            new ResourceLocation(DomaineTerre.MOD_ID, cles.get(i) + "/" + noms.get(b))));
                    tab[b] = h;
                    tous.add(h);
                }
                fixes.add(tab);
            }
            // océans recolorés selon la profondeur du fond (outils/couleurs_eau.py)
            java.util.Map<String, Holder<Biome>[]> mers = new java.util.HashMap<>();
            if (TerroirBiomeSource.class.getResource("/data/domaine_terre/worldgen/biome/mer/temperee_cote.json") != null) {
                for (String temp : new LinkedHashSet<>(TEMP_MER.values())) {
                    @SuppressWarnings("unchecked")
                    Holder<Biome>[] tab = new Holder[BANDES_MER.length];
                    for (int i = 0; i < BANDES_MER.length; i++) {
                        tab[i] = biomes.getOrThrow(ResourceKey.create(Registries.BIOME,
                                new ResourceLocation(DomaineTerre.MOD_ID, "mer/" + temp + "_" + BANDES_MER[i])));
                        tous.add(tab[i]);
                    }
                    mers.put(temp, tab);
                }
            }
            // un biome « lac » par terroir (eau plus claire que celle des fleuves), s'il existe
            List<Holder<Biome>> lacs = new ArrayList<>();
            lacs.add(null);
            for (int i = 1; i < cles.size(); i++) {
                Holder<Biome> h = null;
                if (TerroirBiomeSource.class.getResource("/data/domaine_terre/worldgen/biome/" + cles.get(i) + "/lac.json") != null) {
                    h = biomes.getOrThrow(ResourceKey.create(Registries.BIOME,
                            new ResourceLocation(DomaineTerre.MOD_ID, cles.get(i) + "/lac")));
                    tous.add(h);
                }
                lacs.add(h);
            }
            List<Holder<Biome>> fleuves = new ArrayList<>();
            fleuves.add(null);
            for (int i = 1; i < cles.size(); i++) {
                Holder<Biome> h = null;
                if (TerroirBiomeSource.class.getResource("/data/domaine_terre/worldgen/biome/" + cles.get(i) + "/fleuve.json") != null) {
                    h = biomes.getOrThrow(ResourceKey.create(Registries.BIOME,
                            new ResourceLocation(DomaineTerre.MOD_ID, cles.get(i) + "/fleuve")));
                    tous.add(h);
                }
                fleuves.add(h);
            }
            tables = new Tables(parTerroir, new Climate.ParameterList<>(mer), tous, cles, lieux, fixes, mers, lacs, fleuves);
            return tables;
        }
    }

    private static JsonObject lireListes() {
        return lireJson("terroirs_biomes.json").getAsJsonObject();
    }

    private static List<String> ordreTerroirs() {
        JsonArray tab = lireJson("terroirs.json").getAsJsonArray();
        List<String> cles = new ArrayList<>();
        for (JsonElement e : tab) cles.add(e.getAsJsonObject().get("cle").getAsString());
        return cles;
    }

    private static JsonElement lireJson(String nom) {
        try (InputStream in = TerroirBiomeSource.class.getResourceAsStream("/domaine_terre/carte/" + nom)) {
            if (in == null) throw new IOException(nom + " introuvable");
            return JsonParser.parseReader(new InputStreamReader(in, StandardCharsets.UTF_8));
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
    }

    @Override
    protected Codec<? extends BiomeSource> codec() {
        return CODEC;
    }

    @Override
    protected Stream<Holder<Biome>> collectPossibleBiomes() {
        return tables().tous().stream();
    }

    @Override
    public Holder<Biome> getNoiseBiome(int x, int y, int z, Climate.Sampler sampler) {
        Tables t = tables();
        int bx = x << 2, bz = z << 2;
        // lieu unique : son biome passe avant le terroir (en surface, ou plus bas si le lieu le demande)
        if (!t.lieux().isEmpty()) {
            List<Lieu> lieux = LieuxTerre.liste();
            for (int i = 0; i < lieux.size() && i < t.lieux().size(); i++) {
                Lieu l = lieux.get(i);
                double h = Terrain.get().hauteur(bx, bz);
                // 04/11 : la mer autour d'un lieu côtier (Capri, Staffa) garde les biomes de mer : sinon rectangle de
                // couleur d'eau et coutures de sable droites sur le fond, aux bords des données du lieu
                if (h < Terrain.NIVEAU_MER - 1 && Terrain.get().enMer(bx, bz)) continue;
                if (l.dansBiome(bx, bz) && (y << 2) > l.basBiome(bx, bz, h)) {
                    return t.lieux().get(i);
                }
            }
        }
        // les cartes ont des pixels de 3' (~22 blocs en 1:250) : on lit à un point décalé par un bruit
        double fx = bx + BRUIT_FRONTIERE.noise(bx / 70.0, 0.0, bz / 70.0) * 30.0
                + BRUIT_FRONTIERE.noise(bx / 17.0, 3.0, bz / 17.0) * 9.0;
        double fz = bz + BRUIT_FRONTIERE.noise(bx / 70.0, 7.0, bz / 70.0) * 30.0
                + BRUIT_FRONTIERE.noise(bx / 17.0, 11.0, bz / 17.0) * 9.0;
        double lonF = Terrain.lon(fx), latF = Terrain.lat(fz);
        int terroir = Terrain.get().carte().terroir(lonF, latF);
        boolean lac = terroir > 0 && Terrain.get().carte().lac(lonF, latF);
        Climate.ParameterList<Holder<Biome>> liste =
                terroir > 0 && terroir < t.parTerroir().size() ? t.parTerroir().get(terroir) : t.mer();
        Climate.TargetPoint p = sampler.sample(x, y, z);
        double lat = Math.abs(Terrain.lat(bz));
        double temp, hum;
        int k = Terrain.get().carte().climat(lonF, latF);
        if (terroir <= 0 || terroir >= t.parTerroir().size()) {
            // océans : température selon la latitude (chaud aux tropiques, gelé aux pôles)
            temp = 0.95 - lat * 0.0215 + p.temperature() / 10000.0 * 0.08;
            hum = p.humidity() / 10000.0;
        } else if (k >= 1 && k <= 30) {
            // climat réel Köppen-Geiger, avec un peu de variété vanilla
            temp = KOPPEN[k][0] + p.temperature() / 10000.0 * 0.12;
            hum = KOPPEN[k][1] + p.humidity() / 10000.0 * 0.12;
        } else {
            // secours (bord de côte hors carte Köppen) : latitude + altitude + terroir
            double alt = Math.max(0.0, Terrain.get().altitudeReelle(bx, bz));
            String cle = t.cles().get(terroir);
            double[] biais = BIAIS.getOrDefault(cle, new double[]{0.0, 0.0});
            temp = 0.45 - Math.max(0.0, lat - 15.0) * 0.017 - alt / 1000.0 * 0.25
                    + biais[0] * aride(cle, lat) + p.temperature() / 10000.0 * 0.15;
            hum = biais[1] + p.humidity() / 10000.0 * 0.35;
        }
        Climate.TargetPoint reel = new Climate.TargetPoint(
                Climate.quantizeCoord((float) Math.max(-1.0, Math.min(1.0, temp))),
                Climate.quantizeCoord((float) Math.max(-1.0, Math.min(1.0, hum))),
                // lac intérieur : biomes de terre du terroir (pas d'océan ni de plage, donc pas de faune marine)
                lac ? Math.max(p.continentalness(), Climate.quantizeCoord(0.1F)) : p.continentalness(), p.erosion(),
                // biomes de grottes seulement à plus de 16 blocs sous le sol
                (y << 2) > Terrain.get().hauteur(bx, bz) - 16 ? 0L : p.depth(), p.weirdness());
        Holder<Biome> choix = liste.findValue(reel);
        // carte des biomes fixe : à la surface des terres, le vrai biome remplace le choix climatique.
        // Océans, plages, côtes rocheuses et grottes gardent le choix vanilla.
        if (terroir > 0 && terroir < t.fixes().size()) {
            // 04/11 : sous l'eau d'un cours d'eau, biome « fleuve » du terroir (seule eau boueuse des grands fleuves
            // troubles) ; passe avant le lac : les lacs traversés par un fleuve faisaient des taches bleues dans le lit
            if (terroir < t.fleuves().size() && t.fleuves().get(terroir) != null && Terrain.get().eauDeFleuve(bx, bz)) {
                return t.fleuves().get(terroir);
            }
            // sous l'eau d'un lac : biome « lac » du terroir (couleur d'eau propre aux lacs)
            if (terroir < t.lacs().size() && t.lacs().get(terroir) != null && Terrain.get().eauDeLac(bx, bz)) {
                return t.lacs().get(terroir);
            }
            String chemin = choix.unwrapKey().map(c -> c.location().getPath()).orElse("");
            int fin = chemin.lastIndexOf('/');
            String type = fin >= 0 ? chemin.substring(fin + 1) : chemin;
            // plages et côtes rocheuses : seulement au bord de la vraie mer (moins de 3' de la côte, hors lac).
            // Ailleurs (lac Mead, plateaux), le bruit vanilla inventait des côtes rocheuses grises et enneigées.
            boolean vraieCote = COTES.contains(type) && !lac && Terrain.get().distanceCote(bx, bz) < 3.0;
            // 1:30 : plage seulement au ras de l'eau (à moins de ~20 blocs du rivage et sous y 68) ; les falaises
            // (Étretat) gardent le biome de terre et leur vraie roche au lieu de couches de sable
            if (vraieCote && Terrain.echelle() < 250 && (Terrain.get().distanceCote(bx, bz) > 20.0 * 60.0 / Terrain.BLOCS_PAR_DEGRE
                    || Terrain.get().hauteur(bx, bz) > Terrain.NIVEAU_MER + 4)) vraieCote = false;
            // 04/11 (Skógafoss) : un océan choisi par le bruit vanilla sur la terre ferme (près de la côte) n'est pas
            // de la mer : la terre garde son vrai biome
            boolean vraieMer = OCEANS.contains(type) && Terrain.get().hauteur(bx, bz) < Terrain.NIVEAU_MER - 1;
            if (!vraieMer && !CAVERNES.contains(type) && !vraieCote) {
                int b = Terrain.get().carte().biome(lonF, latF);
                Holder<Biome>[] tab = t.fixes().get(terroir);
                // 1:30 : la carte des biomes a des pixels de 3' (185 blocs, lisières droites) ; la vraie couverture
                // du sol à 10 m (WorldCover) redessine forêts, prairies, déserts et marais au bloc près
                if (Terrain.echelle() < 250) {
                    int s = ReliefFin.sol(bx, bz);
                    if (s >= 0) {
                        int r = parCouverture(s & 255, b, k, tab);
                        if (r > 0) return tab[r];
                    }
                }
                if (b > 0 && b < tab.length && tab[b] != null) return tab[b];
            }
        }
        return merSelonFond(t, choix, bx, bz);
    }

    // ---------------------------------------------------------------- 1:30 : biome d'après la couverture réelle

    private static volatile java.util.Map<String, Integer> indices;

    /** Index d'un biome dans biomes.json (1..n), 0 si absent (sans verrou une fois chargé : appelé très souvent). */
    private static int idx(String nom) {
        java.util.Map<String, Integer> m = indices;
        if (m == null) {
            synchronized (TerroirBiomeSource.class) {
                if (indices == null) {
                    java.util.Map<String, Integer> n = new java.util.HashMap<>();
                    int i = 1;
                    for (JsonElement e : lireJson("biomes.json").getAsJsonArray()) n.put(e.getAsString(), i++);
                    indices = n;
                }
                m = indices;
            }
        }
        return m.getOrDefault(nom, 0);
    }

    private static final Set<String> BOISES = Set.of("forest", "birch_forest", "flower_forest", "dark_forest", "taiga",
            "old_growth_pine_taiga", "old_growth_spruce_taiga", "snowy_taiga", "grove", "cherry_grove", "windswept_forest",
            "wooded_badlands", "jungle", "sparse_jungle", "bamboo_jungle", "mangrove_swamp", "swamp");
    private static final Set<String> SECS = Set.of("desert", "badlands", "wooded_badlands", "eroded_badlands", "savanna",
            "savanna_plateau", "windswept_savanna");

    private static String nom(int b) {
        if (indices == null) idx("plains");
        for (java.util.Map.Entry<String, Integer> e : indices.entrySet()) if (e.getValue() == b) return e.getKey();
        return "";
    }

    private static final String[] NOMS = new String[64];

    private static String nomDe(int b) {
        if (b <= 0 || b >= NOMS.length) return "";
        String n = NOMS[b];
        if (n == null) NOMS[b] = n = nom(b);
        return n;
    }

    /**
     * Biome d'un point en 1:30, d'après la couverture du sol ESA WorldCover (10 m) croisée avec le climat Köppen et le
     * biome de la carte 3'. Renvoie l'index du biome (0 = garder celui de la carte). Le biome de la carte est gardé
     * quand il colle déjà à la couverture (une forêt de bouleaux reste de bouleaux) ; sinon on prend le biome de ce
     * type qui va avec le climat réel.
     */
    static int parCouverture(int cov, int b, int k, Holder<Biome>[] tab) {
        String actuel = nomDe(b);
        boolean tropical = k >= 1 && k <= 3, desert = k == 4 || k == 5, steppe = k == 6 || k == 7;
        boolean polaire = k == 29 || k == 30, froid = k >= 17 && k <= 28;
        String voulu;
        switch (cov) {
            case 10 -> {                                        // arbres
                if (BOISES.contains(actuel) && !actuel.equals("swamp") && !actuel.equals("mangrove_swamp")) return 0;
                if (k == 1 || k == 2) voulu = "jungle";
                else if (k == 3) voulu = "savanna";
                else if (desert || steppe) voulu = actuel.contains("badlands") ? "wooded_badlands" : "savanna_plateau";
                else if (polaire) voulu = "snowy_taiga";
                else if (froid) voulu = "taiga";
                else voulu = "forest";
            }
            case 20, 30, 40 -> {                                // broussailles, prairie, cultures : terrain ouvert
                if (!BOISES.contains(actuel) || actuel.equals("swamp")) {
                    if (actuel.equals("swamp")) voulu = "plains";
                    else return 0;
                } else if (tropical || desert || steppe) voulu = actuel.contains("badlands") ? "badlands" : "savanna";
                else if (polaire) voulu = "snowy_plains";
                else voulu = actuel.contains("snowy") ? "snowy_plains" : "plains";
            }
            case 60 -> {                                        // sol nu : désert en pays sec, sinon la carte décide
                if (!(desert || steppe) || SECS.contains(actuel)) return 0;
                voulu = desert ? "desert" : "badlands";
            }
            case 90 -> voulu = desert || steppe ? null : "swamp";            // zones humides
            case 95 -> voulu = "mangrove_swamp";
            default -> voulu = null;
        }
        if (voulu == null) return 0;
        int i = idx(voulu);
        if (i > 0 && i < tab.length && tab[i] != null) return i;
        // le terroir n'a pas ce biome : un proche
        for (String repli : switch (voulu) {
            case "jungle" -> new String[]{"sparse_jungle", "bamboo_jungle", "forest"};
            case "savanna_plateau", "wooded_badlands" -> new String[]{"savanna", "windswept_savanna", "forest"};
            case "taiga" -> new String[]{"old_growth_spruce_taiga", "old_growth_pine_taiga", "snowy_taiga", "forest"};
            case "snowy_taiga" -> new String[]{"taiga", "old_growth_spruce_taiga"};
            case "forest" -> new String[]{"birch_forest", "dark_forest", "flower_forest", "taiga"};
            case "savanna" -> new String[]{"savanna_plateau", "windswept_savanna", "badlands", "plains"};
            case "badlands" -> new String[]{"eroded_badlands", "desert", "savanna"};
            case "desert" -> new String[]{"badlands", "savanna"};
            case "snowy_plains" -> new String[]{"plains"};
            case "mangrove_swamp" -> new String[]{"swamp"};
            default -> new String[]{"plains"};
        }) {
            int j = idx(repli);
            if (j > 0 && j < tab.length && tab[j] != null) return j;
        }
        return 0;
    }

    /**
     * Océan : la couleur de l'eau suit la vraie profondeur du fond. Côte (fond à moins de 6 blocs sous la surface),
     * plateau (6 à 20), large (jusqu'à y 10), abysse (fosses, fond sous y 10 depuis le 08/11/2026). La température reste celle choisie
     * par la latitude.
     */
    private static Holder<Biome> merSelonFond(Tables t, Holder<Biome> choix, int bx, int bz) {
        String chemin = choix.unwrapKey().map(c -> c.location().getPath()).orElse("");
        String temp = TEMP_MER.get(chemin);
        if (temp == null) return choix;
        Holder<Biome>[] tab = t.mers().get(temp);
        if (tab == null) return choix;
        double fond = Terrain.get().hauteur(bx, bz);
        double prof = Terrain.NIVEAU_MER - fond;
        int i = fond <= 10.0 ? 3 : prof < 6.0 ? 0 : prof < 20.0 ? 1 : 2;
        return tab[i];
    }

    /**
     * Classe Köppen-Geiger -> {température, humidité} dans l'espace climatique vanilla.
     * Température : < -0,45 gelé, < -0,15 froid, < 0,2 tempéré, < 0,55 chaud, sinon très chaud (déserts).
     * Humidité : < -0,35 aride … > 0,3 très humide (jungle, forêt sombre, vieille taïga).
     */
    private static final double[][] KOPPEN = {
            {0.0, 0.0},
            {0.40, 0.60},   // 1  Af  forêt tropicale humide -> jungle
            {0.40, 0.35},   // 2  Am  mousson -> jungle / forêt
            {0.40, -0.25},  // 3  Aw  savane tropicale -> savane
            {0.80, -0.60},  // 4  BWh désert chaud -> désert
            {0.70, -0.60},  // 5  BWk désert froid -> désert
            {0.40, -0.50},  // 6  BSh steppe chaude -> savane
            {0.00, -0.50},  // 7  BSk steppe froide -> plaines
            {0.10, -0.25},  // 8  Csa méditerranéen chaud -> plaines, forêt fleurie
            {0.00, -0.10},  // 9  Csb méditerranéen doux -> plaines, forêt
            {-0.20, 0.00},  // 10 Csc
            {0.35, 0.10},   // 11 Cwa subtropical à hiver sec -> forêt, jungle clairsemée
            {0.10, 0.00},   // 12 Cwb subtropical d'altitude -> forêt, plaines
            {-0.10, 0.00},  // 13 Cwc
            {0.15, 0.15},   // 14 Cfa subtropical humide -> forêt, bouleaux
            {0.00, 0.00},   // 15 Cfb océanique -> forêt, plaines
            {-0.30, 0.10},  // 16 Cfc océanique froid -> forêt, taïga
            {-0.20, -0.20}, // 17 Dsa
            {-0.20, -0.20}, // 18 Dsb
            {-0.50, 0.20},  // 19 Dsc
            {-0.60, 0.20},  // 20 Dsd
            {-0.10, 0.00},  // 21 Dwa continental à hiver sec -> forêt
            {-0.25, 0.10},  // 22 Dwb
            {-0.35, 0.25},  // 23 Dwc -> taïga
            {-0.60, 0.25},  // 24 Dwd -> taïga enneigée
            {-0.10, 0.05},  // 25 Dfa continental chaud -> forêt
            {-0.25, 0.15},  // 26 Dfb continental -> forêt, taïga
            {-0.35, 0.35},  // 27 Dfc subarctique -> taïga, vieille taïga
            {-0.60, 0.30},  // 28 Dfd subarctique extrême -> taïga enneigée
            {-0.60, -0.30}, // 29 ET  toundra -> plaines enneigées
            {-0.90, -0.50}, // 30 EF  calotte glaciaire -> plaines enneigées, pics de glace
    };

    /** Biais de température (déserts chauds) et d'humidité par terroir. */
    private static final java.util.Map<String, double[]> BIAIS = java.util.Map.ofEntries(
            java.util.Map.entry("sahara_sahel", new double[]{0.6, -0.7}),
            java.util.Map.entry("moyen_orient", new double[]{0.5, -0.6}),
            java.util.Map.entry("australie", new double[]{0.45, -0.5}),
            java.util.Map.entry("ouest_mexique", new double[]{0.35, -0.45}),
            java.util.Map.entry("maghreb", new double[]{0.15, -0.3}),
            java.util.Map.entry("afrique_australe", new double[]{0.15, -0.3}),
            java.util.Map.entry("steppes_tibet", new double[]{0.0, -0.35}),
            java.util.Map.entry("afrique_est", new double[]{0.0, -0.1}),
            java.util.Map.entry("amazonie", new double[]{0.0, 0.55}),
            java.util.Map.entry("asie_sud_est", new double[]{0.0, 0.55}),
            java.util.Map.entry("melanesie", new double[]{0.0, 0.55}),
            java.util.Map.entry("afrique_tropicale", new double[]{0.0, 0.45}),
            java.util.Map.entry("amerique_centrale", new double[]{0.0, 0.45}),
            java.util.Map.entry("inde", new double[]{0.0, 0.15}),
            java.util.Map.entry("chine", new double[]{0.0, 0.15}),
            java.util.Map.entry("japon_coree", new double[]{0.0, 0.15}),
            java.util.Map.entry("atlantique", new double[]{0.0, -0.05}));

    /** Le Sahel (sud du Sahara) n'a pas le biais « désert chaud » : il reste une savane. */
    private static double aride(String cle, double lat) {
        if (cle.equals("sahara_sahel")) return Math.max(0.0, Math.min(1.0, (lat - 13.0) / 5.0));
        return 1.0;
    }
}

package fr.domaineaubin.terre.commande;

import com.google.gson.GsonBuilder;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.mojang.serialization.DynamicOps;
import com.mojang.serialization.JsonOps;
import fr.domaineaubin.terre.DomaineTerre;
import net.minecraft.core.Registry;
import net.minecraft.core.RegistryAccess;
import net.minecraft.core.registries.Registries;
import net.minecraft.locale.Language;
import net.minecraft.resources.RegistryOps;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.MinecraftServer;
import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.levelgen.NoiseGeneratorSettings;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

/** Écrit dans run/export_biomes les définitions des biomes vanilla, leurs tags et leurs noms traduits. */
public final class ExportBiomes {
    private ExportBiomes() {
    }

    public static int exporter(MinecraftServer serveur) throws IOException {
        RegistryAccess ra = serveur.registryAccess();
        Registry<Biome> reg = ra.registryOrThrow(Registries.BIOME);
        DynamicOps<JsonElement> ops = RegistryOps.create(JsonOps.INSTANCE, ra);
        Path dossier = serveur.getServerDirectory().toPath().resolve("export_biomes");
        Files.createDirectories(dossier.resolve("biome"));
        var gson = new GsonBuilder().setPrettyPrinting().disableHtmlEscaping().create();
        JsonObject noms = new JsonObject();
        int n = 0;
        for (ResourceLocation id : reg.keySet()) {
            if (!id.getNamespace().equals("minecraft")) continue;
            Biome b = reg.get(id);
            JsonElement j = Biome.DIRECT_CODEC.encodeStart(ops, b)
                    .getOrThrow(false, e -> DomaineTerre.LOGGER.error("Export {} : {}", id, e));
            Files.writeString(dossier.resolve("biome").resolve(id.getPath() + ".json"), gson.toJson(j), StandardCharsets.UTF_8);
            String cle = "biome.minecraft." + id.getPath();
            noms.addProperty(id.getPath(), Language.getInstance().getOrDefault(cle));
            n++;
        }
        JsonObject tags = new JsonObject();
        reg.getTags().forEach(p -> {
            JsonArray tab = new JsonArray();
            p.getSecond().forEach(h -> h.unwrapKey().ifPresent(k -> tab.add(k.location().toString())));
            tags.add(p.getFirst().location().toString(), tab);
        });
        Files.writeString(dossier.resolve("tags.json"), gson.toJson(tags), StandardCharsets.UTF_8);
        Files.writeString(dossier.resolve("noms.json"), gson.toJson(noms), StandardCharsets.UTF_8);
        // réglages de bruit de l'Overworld (règles de surface : sable, terre cuite, neige…)
        NoiseGeneratorSettings ns = ra.registryOrThrow(Registries.NOISE_SETTINGS).get(new ResourceLocation("minecraft", "overworld"));
        JsonElement jn = NoiseGeneratorSettings.DIRECT_CODEC.encodeStart(ops, ns)
                .getOrThrow(false, e -> DomaineTerre.LOGGER.error("Export noise_settings : {}", e));
        Files.writeString(dossier.resolve("noise_settings_overworld.json"), gson.toJson(jn), StandardCharsets.UTF_8);
        DomaineTerre.LOGGER.info("Export : {} biomes, {} tags vers {}", n, tags.size(), dossier);
        return n;
    }
}

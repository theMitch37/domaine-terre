package fr.domaineaubin.meteo;

import net.minecraft.network.FriendlyByteBuf;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.level.ServerPlayer;
import net.minecraftforge.network.NetworkDirection;
import net.minecraftforge.network.NetworkEvent;
import net.minecraftforge.network.NetworkRegistry;
import net.minecraftforge.network.PacketDistributor;
import net.minecraftforge.network.simple.SimpleChannel;

import java.util.Optional;
import java.util.function.Supplier;

/**
 * Messages du serveur au client : « ce serveur est un monde Terre » (saisons, durée du jour) et, chaque seconde,
 * l'horloge (part du jour, vitesse) pour que le soleil avance sans à-coups côté client.
 */
public final class Reseau {
    private static final String VERSION = "2";
    public static final SimpleChannel CANAL = NetworkRegistry.newSimpleChannel(
            new ResourceLocation(DomaineWeather.MOD_ID, "principal"), () -> VERSION,
            NetworkRegistry.acceptMissingOr(VERSION), NetworkRegistry.acceptMissingOr(VERSION));

    private Reseau() {
    }

    public record MondeTerre(boolean terre) {
        static void ecrire(MondeTerre m, FriendlyByteBuf b) {
            b.writeBoolean(m.terre);
        }

        static MondeTerre lire(FriendlyByteBuf b) {
            return new MondeTerre(b.readBoolean());
        }

        static void traiter(MondeTerre m, Supplier<NetworkEvent.Context> ctx) {
            ctx.get().enqueueWork(() -> {
                Saisons.terreClient = m.terre;
                JourNuit.reinitialiserClient();
            });
            ctx.get().setPacketHandled(true);
        }
    }

    public record Horloge(double part, double facteur) {
        static void ecrire(Horloge m, FriendlyByteBuf b) {
            b.writeDouble(m.part);
            b.writeDouble(m.facteur);
        }

        static Horloge lire(FriendlyByteBuf b) {
            return new Horloge(b.readDouble(), b.readDouble());
        }

        static void traiter(Horloge m, Supplier<NetworkEvent.Context> ctx) {
            ctx.get().enqueueWork(() -> JourNuit.horlogeRecue(m.part, m.facteur));
            ctx.get().setPacketHandled(true);
        }
    }

    public static void enregistrer() {
        CANAL.registerMessage(0, MondeTerre.class, MondeTerre::ecrire, MondeTerre::lire, MondeTerre::traiter,
                Optional.of(NetworkDirection.PLAY_TO_CLIENT));
        CANAL.registerMessage(1, Horloge.class, Horloge::ecrire, Horloge::lire, Horloge::traiter,
                Optional.of(NetworkDirection.PLAY_TO_CLIENT));
    }

    public static void horloge(ServerPlayer joueur, double part, double facteur) {
        CANAL.send(PacketDistributor.PLAYER.with(() -> joueur), new Horloge(part, facteur));
    }

    public static void envoyer(ServerPlayer joueur, boolean terre) {
        CANAL.send(PacketDistributor.PLAYER.with(() -> joueur), new MondeTerre(terre));
    }
}

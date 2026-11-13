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

/** Un seul message : « ce serveur est un monde Terre » (le client en a besoin pour les saisons et la durée du jour). */
public final class Reseau {
    private static final String VERSION = "1";
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

    public static void enregistrer() {
        CANAL.registerMessage(0, MondeTerre.class, MondeTerre::ecrire, MondeTerre::lire, MondeTerre::traiter,
                Optional.of(NetworkDirection.PLAY_TO_CLIENT));
    }

    public static void envoyer(ServerPlayer joueur, boolean terre) {
        CANAL.send(PacketDistributor.PLAYER.with(() -> joueur), new MondeTerre(terre));
    }
}

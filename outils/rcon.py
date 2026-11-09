"""Commande RCON minimale (essai du client) : python outils/rcon.py <port> <mot de passe> <commande>..."""
import socket, struct, sys


def paquet(i, t, corps):
    b = corps.encode() + b"\0\0"
    return struct.pack("<iii", len(b) + 8, i, t) + b


def lire(s):
    n = struct.unpack("<i", s.recv(4))[0]
    d = b""
    while len(d) < n:
        d += s.recv(n - len(d))
    return d[8:-2].decode(errors="replace")


s = socket.create_connection(("127.0.0.1", int(sys.argv[1])), timeout=60)
s.sendall(paquet(1, 3, sys.argv[2]))
lire(s)
for c in sys.argv[3:]:
    s.sendall(paquet(2, 2, c))
    print(c, "->", lire(s), flush=True)

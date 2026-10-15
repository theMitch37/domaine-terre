"""Décode l'ETOPO 2022 (GeoTIFF float32, tuiles 256x256, deflate + prédicteur flottant)
et le réduit d'un facteur N (moyenne par blocs). Sortie : altitude_<N*1>min.npy (int16, mètres).
Usage : python3 etopo_reduire.py <fichier.tif> <facteur> <sortie.npy>
"""
import struct, sys, zlib
import numpy as np

src, fac, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
f = open(src, "rb")
hdr = f.read(8); bo = "<" if hdr[:2] == b"II" else ">"
f.seek(struct.unpack(bo + "I", hdr[4:8])[0])
n = struct.unpack(bo + "H", f.read(2))[0]
T = {3: ("H", 2), 4: ("I", 4), 16: ("Q", 8)}
tags = {}
for _ in range(n):
    tag, typ, cnt, val = struct.unpack(bo + "HHI4s", f.read(12))
    if typ not in T: continue
    fmt, sz = T[typ]
    if sz * cnt <= 4: data = val[:sz * cnt]
    else:
        p = struct.unpack(bo + "I", val)[0]; cur = f.tell(); f.seek(p); data = f.read(sz * cnt); f.seek(cur)
    tags[tag] = struct.unpack(bo + fmt * cnt, data)
W, H, TW, TH = tags[256][0], tags[257][0], tags[322][0], tags[323][0]
offs, lens = tags[324], tags[325]
assert tags[259][0] == 8 and tags[317][0] == 3, "compression inattendue"
ntx, nty = (W + TW - 1) // TW, (H + TH - 1) // TH
OW, OH = W // fac, H // fac
acc = np.zeros((OH, OW), np.float32)
pend = np.zeros((0, W), np.float32)   # lignes pleine résolution en attente
oy = 0
for ty in range(nty):
    row_buf = np.zeros((TH, ntx * TW), np.float32)
    for tx in range(ntx):
        i = ty * ntx + tx
        f.seek(offs[i]); raw = zlib.decompress(f.read(lens[i]))
        b = np.frombuffer(raw, np.uint8).reshape(TH, TW * 4)
        b = np.cumsum(b, axis=1, dtype=np.uint64).astype(np.uint8)   # annule la différenciation
        planes = b.reshape(TH, 4, TW)                                    # plans d'octets, poids fort d'abord
        row_buf[:, tx * TW:(tx + 1) * TW] = planes.transpose(0, 2, 1).copy().view(">f4").reshape(TH, TW)
    h = min(TH, H - ty * TH)
    blk = row_buf[:h, :W]
    pend = np.vstack([pend, np.where(blk < -20000, 0, blk)])
    k = pend.shape[0] // fac          # nombre de lignes de sortie complètes
    if k:
        acc[oy:oy + k] = pend[:k * fac].reshape(k, fac, OW, fac).mean(axis=(1, 3))
        oy += k; pend = pend[k * fac:]
    if ty % 6 == 0: print(f"bande {ty + 1}/{nty}", flush=True)
assert oy == OH, (oy, OH)
np.save(out, np.round(acc).astype(np.int16))
print("OK", OW, OH, int(acc.min()), int(acc.max()))

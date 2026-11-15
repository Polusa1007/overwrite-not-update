#!/usr/bin/env python3
"""Offline test of logw_to_trace.py on a small synthetic log, in the on-disk layout of dm-log-writes."""
import os
import random
import struct
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logw_to_trace as L

SS = 512
rng = random.Random(1)


def entry(sector, nr, flags, mark=b""):
    return (struct.pack("<QQQQ", sector, nr, flags, len(mark)) + mark).ljust(SS, b"\0")


d = tempfile.mkdtemp()
log, state, out = (os.path.join(d, n) for n in ("log", "state", "trace"))
a = bytes(rng.getrandbits(8) for _ in range(4096))
b = bytearray(a)
b[100:110] = b"X" * 10
c = bytes(rng.getrandbits(8) for _ in range(4096))
ent = [
    entry(8, 8, 0) + a,                         # block 1, first write
    entry(16, 8, 0) + a,                        # block 2, first write
    entry(24, 8, 0) + a,                        # block 3, first write
    entry(24, 8, L.DISCARD),                    # block 3 discarded, no payload in the log
    entry(0, 0, L.FLUSH),                       # empty flush
    entry(0, 0, L.MARK, b"tool"),
    entry(8, 8, 0) + bytes(b),                  # block 1 overwritten, 10 bytes differ at most
    entry(16, 8, 0) + c,                        # block 2 overwritten by random bytes
    entry(24, 8, 0) + c,                        # block 3 not an overwrite after the discard
    entry(40, 4, 0) + a[:2048],                 # block 5, partial first write
    entry(44, 4, 0) + a[2048:],                 # block 5, partial, counts as overwrite of the same block
]
with open(log, "wb") as fp:
    fp.write(struct.pack("<QQQI", L.MAGIC, 1, len(ent), SS).ljust(SS, b"\0"))
    for e in ent:
        fp.write(e)
L.convert(log, state, out)
raw = open(out, "rb").read()
rows = [L.REC.unpack_from(raw, i) for i in range(0, len(raw), L.REC.size)]
wr = [(r[1], r[5], r[6], r[3], r[4] >> 16, r[7]) for r in rows]     # lpn op over diff new xor
for w in wr:
    print(w)
ops = [r[1] for r in wr]
assert ops == [1, 1, 1, 2, 9, 1, 1, 1, 1, 1], ops
assert wr[0][2] == 0 and wr[3][0] == 3
b1, b2, b3, p1, p2 = wr[5:]
assert b1[0] == 1 and b1[2] == 1 and 1 <= b1[3] <= 10 and b1[5] < 200 and b1[4] > 3000
assert b2[0] == 2 and b2[2] == 1 and b2[3] > 3900 and b2[5] > 3000
assert b3[0] == 3 and b3[2] == 0
assert p1[0] == 5 and p1[2] == 0 and p2[0] == 5 and p2[2] == 1
assert os.path.getsize(state) >= 6 * 4096
print("all checks passed")

#!/usr/bin/env python3
"""Paper C, C2: turn a dm-log-writes log into the record format of the FEMU trace, so one analysis serves both.

    logw_to_trace.py LOG STATE_FILE OUT

Replays the log into a sparse STATE_FILE to know the old bytes of each 4-KiB block. The mark written just before the
tool becomes the op-9 record; zlib sizes are computed only after it. Standard library only, since it runs in the guest.
Record: t u64 (log index), lpn u32, ent u16 (0), diff u16, clz u32 (zlib size of the new page << 16), op u8, over u8,
pad u16 (zlib size of old XOR new)."""
import os
import struct
import sys
import zlib

MAGIC = 0x6a736677736872
FLUSH, FUA, DISCARD, MARK, META = 1, 2, 4, 8, 16
PAGE = 4096
REC = struct.Struct("<QIHHIBBH")
ENTRY = struct.Struct("<QQQQ")


def records(fd, sector_size, nr_entries):
    """Yields (index, sector, nr_sectors, flags, mark text, offset of the data)."""
    pos = sector_size
    for i in range(nr_entries):
        raw = os.pread(fd, sector_size, pos)
        if len(raw) < ENTRY.size:
            raise ValueError(f"log ends at entry {i} of {nr_entries}")
        sector, nr, flags, dlen = ENTRY.unpack_from(raw, 0)
        mark = raw[ENTRY.size:ENTRY.size + dlen] if flags & MARK else b""
        data = pos + sector_size
        yield i, sector, nr, flags, mark, data
        pos = data + (0 if flags & DISCARD else nr * sector_size)


def convert(log, state, out, mark_name=b"tool"):
    fd = os.open(log, os.O_RDONLY)
    magic, version, nr_entries, sector_size = struct.unpack("<QQQI", os.pread(fd, 28, 0))
    if magic != MAGIC:
        raise ValueError("not a log-writes log")
    st = os.open(state, os.O_RDWR | os.O_CREAT | os.O_TRUNC, 0o600)
    mapped = set()
    tool = False
    seen_mark = False
    t = 0
    with open(out, "wb") as fp:
        for i, sector, nr, flags, mark, data in records(fd, sector_size, nr_entries):
            t += 1
            if flags & MARK:
                if mark.rstrip(b"\0") == mark_name:
                    fp.write(REC.pack(t, 0, 0, 0, 0, 9, 0, 0))
                    tool = seen_mark = True
                continue
            if nr == 0:
                continue
            start, end = sector * sector_size, (sector + nr) * sector_size
            if flags & DISCARD:
                first, last = -(-start // PAGE), end // PAGE      # whole blocks only
                for b in range(first, last):
                    mapped.discard(b)
                    fp.write(REC.pack(t, b, 0, 0, 0, 2, 1, 0))
                continue
            payload = os.pread(fd, nr * sector_size, data)
            for b in range(start // PAGE, (end + PAGE - 1) // PAGE):
                off = b * PAGE
                old = os.pread(st, PAGE, off).ljust(PAGE, b"\0")
                s, e = max(off, start), min(off + PAGE, end)
                new = old[:s - off] + payload[s - start:e - start] + old[e - off:]
                os.pwrite(st, new, off)
                over = b in mapped
                mapped.add(b)
                diff, csz, xsz = 0, 0, 0
                if over:
                    diff = sum(x != y for x, y in zip(old, new))
                    if tool:
                        xor = bytes(x ^ y for x, y in zip(old, new))
                        xsz = min(len(zlib.compress(xor, 1)), 0xfffe)
                        csz = min(len(zlib.compress(new, 1)), 0xfffe) << 16
                fp.write(REC.pack(t, b, 0, diff, csz, 1, int(over), xsz))
    if not seen_mark:
        raise ValueError("the tool mark is not in the log")
    os.close(fd)
    os.close(st)


if __name__ == "__main__":
    convert(*sys.argv[1:4])

#!/usr/bin/env python3
"""Pilot: print which device blocks hold what, for ext4, XFS, Btrfs or F2FS, in the guest.
Reads metadata only, never file contents. One line per range: class first_block count.

    fs_map.py MNT DEV FS"""
import array
import fcntl
import os
import re
import struct
import subprocess
import sys

FS_IOC_FIEMAP = 0xC020660B
BLOCK = 4096
N = 256
XFS_IOC_GETBMAP = 0xC0205826
SKIP = 0x002 | 0x004 | 0x200   # unknown, delayed, inline: no device block of their own
translate = None               # Btrfs: FIEMAP gives logical addresses


def run(*cmd):
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, universal_newlines=True).stdout


def extents(fd):
    start = 0
    while True:
        buf = array.array("B", struct.pack("=QQIIII", start, 2 ** 64 - 1, 1, 0, N, 0) + b"\0" * (56 * N))
        try:
            fcntl.ioctl(fd, FS_IOC_FIEMAP, buf, True)
        except OSError:
            return
        mapped = struct.unpack_from("=I", buf, 20)[0]
        if not mapped:
            return
        last = False
        for i in range(mapped):
            lo, ph, ln = struct.unpack_from("=QQQ", buf, 32 + 56 * i)
            fl = struct.unpack_from("=I", buf, 32 + 56 * i + 40)[0]
            if not fl & SKIP:
                yield lo, ph, ln
            start = lo + ln
            last = fl & 1
        if last:
            return


def emit(cls, first, count):
    if count <= 0:
        return
    if translate is None:
        print(cls, first, count)
        return
    # Btrfs: split the logical range over its chunks
    a, end = first * BLOCK, (first + count) * BLOCK
    for lo, ln, ph in translate:
        s, e = max(a, lo), min(end, lo + ln)
        if s < e:
            print(cls, (ph + s - lo) // BLOCK, (e - s) // BLOCK)


def tree(root, prefix):
    for d, _, names in os.walk(root):
        fd = os.open(d, os.O_RDONLY)
        for _, ph, ln in extents(fd):
            emit(prefix + "_dir", ph // BLOCK, ln // BLOCK)
        os.close(fd)
        for name in names:
            p = os.path.join(d, name)
            if os.path.islink(p) or not os.path.isfile(p):
                continue
            size = os.path.getsize(p)
            tail = size // BLOCK if size % BLOCK else -1
            fd = os.open(p, os.O_RDONLY)
            for lo, ph, ln in extents(fd):
                b0, n, l0 = ph // BLOCK, ln // BLOCK, lo // BLOCK
                if l0 <= tail < l0 + n:
                    emit(prefix + "_body", b0, tail - l0)
                    emit(prefix + "_tail", b0 + tail - l0, 1)
                    emit(prefix + "_body", b0 + tail - l0 + 1, n - (tail - l0) - 1)
                else:
                    emit(prefix + "_body", b0, n)
            os.close(fd)


def rng(text):
    m = re.match(r"(\d+)(?:-(\d+))?", text)
    a = int(m.group(1))
    b = int(m.group(2)) if m.group(2) else a
    return a, b - a + 1


def meta_ext4(dev):
    out = run("dumpe2fs", dev)
    for pat in (r"superblock at (\d+)", r"Group descriptors at (\d+(?:-\d+)?)", r"Reserved GDT blocks at (\d+(?:-\d+)?)", r"Block bitmap at (\d+)", r"Inode bitmap at (\d+)", r"Inode table at (\d+(?:-\d+)?)"):
        for m in re.finditer(pat, out):
            emit("meta", *rng(m.group(1)))
    out = run("debugfs", "-R", "stat <8>", dev)
    for m in re.finditer(r"\((?:\d+(?:-\d+)?)\):(\d+(?:-\d+)?)", out):
        emit("journal", *rng(m.group(1)))


def meta_xfs(dev):
    out = run("xfs_db", "-r", "-c", "sb 0", "-c", "p logstart logblocks agcount agblocks agblklog", dev)
    v = {m.group(1): int(m.group(2)) for m in re.finditer(r"(\w+) = (\d+)", out)}
    mask = (1 << v["agblklog"]) - 1
    emit("journal", (v["logstart"] >> v["agblklog"]) * v["agblocks"] + (v["logstart"] & mask), v["logblocks"])
    for ag in range(v["agcount"]):
        emit("meta", ag * v["agblocks"], 8)     # AG headers and the first free-space and inode btree blocks


def chunks_btrfs(dev):
    """One row per chunk stripe: (logical, length, kind, physical). DUP chunks have two stripes."""
    out = run("btrfs", "inspect-internal", "dump-tree", "-t", "chunk", dev)
    rows = []
    for part in re.split(r"(?=item \d+ key \(FIRST_CHUNK_TREE CHUNK_ITEM)", out):
        m = re.search(r"CHUNK_ITEM (\d+)\).*?length (\d+) .*?type (\w+)", part, re.S)
        if m:
            for st in re.finditer(r"stripe \d+ devid \d+ offset (\d+)", part):
                rows.append((int(m.group(1)), int(m.group(2)), m.group(3), int(st.group(1))))
    return rows


def inodes_xfs(mnt, dev):
    """XFS inode chunks (64 inodes) and directory blocks of everything under mnt."""
    out = run("xfs_db", "-r", "-c", "sb 0", "-c", "p agblocks agblklog inopblog", dev)
    v = {m.group(1): int(m.group(2)) for m in re.finditer(r"(\w+) = (\d+)", out)}
    bits = v["agblklog"] + v["inopblog"]
    per = (64 >> v["inopblog"]) or 1
    seen = set()
    for d, dirs, names in os.walk(mnt):
        for name in [None] + dirs + names:
            p = d if name is None else os.path.join(d, name)
            ino = os.lstat(p).st_ino
            ag, agino = ino >> bits, ino & ((1 << bits) - 1)
            seen.add(ag * v["agblocks"] + ((agino & ~63) >> v["inopblog"]))
        fd = os.open(d, os.O_RDONLY)
        cls = "stale_dir" if os.path.relpath(d, mnt).startswith("old") else "src_dir"
        buf = array.array("B", struct.pack("=qqqiihh", 0, 0, -1, N + 1, 0, 0, 0)[:32] + b"\0" * (32 * N))
        try:
            fcntl.ioctl(fd, XFS_IOC_GETBMAP, buf, True)
            count = struct.unpack_from("=i", buf, 28)[0]
            for i in range(1, count + 1):
                _, block, length = struct.unpack_from("=qqq", buf, 32 * i)
                if block >= 0:
                    emit(cls, block // 8, length // 8)
        except OSError:
            pass
        os.close(fd)
    for b in sorted(seen):
        emit("inode", b, per)


def meta_f2fs(dev):
    """F2FS metadata areas, from the superblock at byte 1024. Node blocks live in the main area."""
    with open(dev, "rb") as fp:
        fp.seek(1024)
        sb = fp.read(128)
    assert struct.unpack_from("<I", sb, 0)[0] == 0xF2F52010
    seg0, cp, sit, nat, ssa, main = struct.unpack_from("<6I", sb, 72)
    print("# f2fs seg0", seg0, "cp", cp, "sit", sit, "nat", nat, "ssa", ssa, "main", main)
    emit("meta", 0, main)
    # node segments, from the segment types in the SIT; run after a sync, before any deletion
    subprocess.run(["dump.f2fs", "-s", "0~-1", dev], cwd="/tmp", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    n = 0
    try:
        with open("/tmp/dump_sit") as fp:
            for line in fp:
                m = re.search(r"segno:\s*(\d+).*?vblocks:\s*(\d+).*?seg_type:\s*(\d+)", line)
                if not m:
                    continue
                live, node = int(m.group(2)) > 0, int(m.group(3)) >= 3
                if node or not live:
                    emit(("node" if live else "dead_node") if node else "dead_data", seg0 + int(m.group(1)) * 512, 512)
                    n += 1
    except OSError:
        pass
    print("# f2fs node segments", n)


def main():
    global translate
    mnt, dev, fs = sys.argv[1:4]
    if len(sys.argv) > 4:                   # after the deletion: chunks allocated since the first map
        if fs == "btrfs":
            for lo, ln, typ, ph in chunks_btrfs(dev):
                if typ != "DATA":
                    print("postmeta", ph // BLOCK, ln // BLOCK)
        return
    if fs == "btrfs":
        rows = chunks_btrfs(dev)
        for row in rows:
            print("# chunk", *row)
        translate = None
        for lo, ln, typ, ph in rows:
            if typ != "DATA":
                emit("meta", ph // BLOCK, ln // BLOCK)
        for b in (16, 16384):               # superblock copies
            emit("meta", b, 1)
        translate = [(lo, ln, ph) for lo, ln, typ, ph in rows]
    tree(os.path.join(mnt, "src"), "src")
    if os.path.isdir(os.path.join(mnt, "live")):   # C7: data updated by the tool
        tree(os.path.join(mnt, "live"), "live")
    for name in sorted(os.listdir(mnt)):
        if name.startswith("old"):
            tree(os.path.join(mnt, name), "stale")
    if fs == "ext4":
        meta_ext4(dev)
    elif fs == "xfs":
        meta_xfs(dev)
        inodes_xfs(mnt, dev)
    elif fs == "f2fs":
        meta_f2fs(dev)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Paper C, post hoc (not pre-specified): where on the device a tool writes, by allocation group, for ext4 and XFS.

    python3 -I alloc_groups.py <out csv> <campaign>=<runs root> [<campaign>=<runs root> ...]

For each ext4 or XFS run under untrimmed deleted data (T0 with state SB, SC or SD), splits the device into the file
system's allocation groups (ext4: block groups of 32768 4-KiB blocks; XFS: the allocation groups whose headers
fs_map.py records as 8-block metadata extents at multiples of agblocks) and counts, per run, the groups, the groups
that hold blocks of the deleted copies (class freed in analyze_c.py), the tool-phase writes, and how many of these
writes fall into groups without freed blocks. Uses the block map and tool-phase mark of analyze_c.py unchanged."""
import csv
import glob
import gzip
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analyze_c as A  # noqa: E402

EXT4_GROUP = 32768


def xfs_agblocks(path):
    starts = []
    with gzip.open(path, "rt") as fp:
        for line in fp:
            p = line.split()
            if len(p) == 3 and p[0] == "meta" and p[2] == "8":
                starts.append(int(p[1]))
    starts = sorted(set(starts))
    assert len(starts) >= 2 and starts[0] == 0, starts[:4]
    ag = starts[1]
    assert all(s == i * ag for i, s in enumerate(starts)), starts
    return ag, len(starts)


def one(camp, path):
    parts = path.replace("\\", "/").split("/")
    fs = parts[-3]
    trim, state = parts[-2].split("_")[:2]
    tool, rep = parts[-1].rsplit("_", 1)
    rec = np.frombuffer(gzip.open(os.path.join(path, "trace.bin.gz")).read(), dtype=A.REC)
    rec = rec[np.argsort(rec["t"], kind="stable")]
    t0 = int(rec["t"][np.where(rec["op"] == 9)[0][0]])
    size = int(rec["lpn"].max()) + 1
    mp = os.path.join(path, "map.txt.gz")
    m, names, _ = A.load_map(mp, size)
    if fs == "ext4":
        gsize, ngroups = EXT4_GROUP, None
    else:
        gsize, ngroups = xfs_agblocks(mp)
    freed_ids = [i for i, c in enumerate(names) if A.GROUP.get(c) == "freed"]
    freed = np.isin(m, freed_ids)
    gid_all = np.arange(size) // gsize
    ng = int(gid_all.max()) + 1 if ngroups is None else ngroups
    freed_per_group = np.bincount(gid_all[freed], minlength=ng)
    w = rec[(rec["op"] == 1) & (rec["t"] >= t0)]
    wg = w["lpn"].astype(np.int64) // gsize
    in_freed_group = freed_per_group[np.clip(wg, 0, ng - 1)] > 0
    return [camp, fs, trim, state, tool, int(rep), gsize, ng, int((freed_per_group > 0).sum()), len(w),
            int((~in_freed_group).sum()), int(w["over"].sum())]


def main():
    out = sys.argv[1]
    rows = []
    for arg in sys.argv[2:]:
        camp, root = arg.split("=", 1)
        for fs in ("ext4", "xfs"):
            for d in sorted(glob.glob(os.path.join(root, fs, "T0_S[BCD]_W60", "*_*"))):
                if os.path.exists(os.path.join(d, "trace.bin.gz")):
                    rows.append(one(camp, d))
    with open(out, "w", newline="") as fp:
        w = csv.writer(fp)
        w.writerow(["campaign", "fs", "trim", "state", "tool", "rep", "group_blocks", "groups", "groups_with_freed",
                    "writes", "writes_outside_freed_groups", "overwrites"])
        w.writerows(rows)
    print(len(rows), "runs")


if __name__ == "__main__":
    main()

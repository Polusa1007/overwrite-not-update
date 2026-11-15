#!/usr/bin/env python3
"""Paper C, C6: released build on SC-T0 and SC-TF, all C1 tools, 3 replicates, one fixed random order (prereg/C6.md).

    c6_run_list.py > c6_runs.txt         line: fs trim state tool rep"""
import random

FS = ("ext4", "xfs", "btrfs", "f2fs")
TOOLS = ("copynr", "copy", "rsync", "targz", "git", "gzipf", "sqlite")
runs = [(fs, trim, "SC", t, rep) for fs in FS for t in TOOLS if t != "copy" or fs in ("xfs", "btrfs")
        for trim in ("T0", "TF") for rep in (1, 2, 3)]
assert len(runs) == 156
random.Random(20261113).shuffle(runs)
for r in runs:
    print(*r)

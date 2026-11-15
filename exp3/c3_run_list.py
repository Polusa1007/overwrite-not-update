#!/usr/bin/env python3
"""Paper C, C3: the 108 device-size runs in one fixed random order (prereg/C3.md).

    c3_run_list.py > c3_runs.txt         line: fs trim state tool rep
    c3_run_list.py smoke > c3_smoke.txt  one SC-TF targz run per file system, rep 0"""
import random
import sys

FS = ("ext4", "xfs", "btrfs", "f2fs")
if sys.argv[1:] == ["smoke"]:
    runs = [(fs, "TF", "SC", "targz", 0) for fs in FS]
else:
    runs = [(fs, trim, state, tool, rep) for fs in FS for tool in ("targz", "rsync", "sqlite")
            for trim, state in (("T0", "S0"), ("T0", "SC"), ("TF", "SC")) for rep in (1, 2, 3)]
    assert len(runs) == 108
    random.Random(20261110).shuffle(runs)
for r in runs:
    print(*r)

#!/usr/bin/env python3
"""Paper C, C7: the 72 runs of the update workloads in one fixed random order (prereg/C7.md).

    c7_run_list.py > c7_runs.txt         line: fs trim state tool rep
    c7_run_list.py smoke > c7_smoke.txt  four smoke runs, rep 0"""
import random
import sys

FS = ("ext4", "xfs", "btrfs", "f2fs")
if sys.argv[1:] == ["smoke"]:
    runs = [("ext4", "T0", "SC", "dbupd", 0), ("xfs", "T0", "SC", "logapp", 0), ("btrfs", "TF", "SC", "dbupd", 0),
            ("f2fs", "T0", "S0", "logapp", 0)]
else:
    runs = [(fs, trim, state, t, rep) for fs in FS for t in ("dbupd", "logapp")
            for trim, state in (("T0", "S0"), ("T0", "SC"), ("TF", "SC")) for rep in (1, 2, 3)]
    assert len(runs) == 72
    random.Random(20261114).shuffle(runs)
for r in runs:
    print(*r)

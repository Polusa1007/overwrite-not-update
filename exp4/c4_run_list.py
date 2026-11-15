#!/usr/bin/env python3
"""Paper C, C4: the 48 released-build validation runs in one fixed random order (prereg/C4.md).

    c4_run_list.py > c4_runs.txt         line: fs trim state tool rep
    c4_run_list.py smoke > c4_smoke.txt  two smoke runs, rep 0"""
import random
import sys

FS = ("ext4", "xfs", "btrfs", "f2fs")
if sys.argv[1:] == ["smoke"]:
    runs = [("ext4", "TF", "SC", "targz", 0), ("f2fs", "TD", "SC", "sqlite", 0)]
else:
    runs = [(fs, trim, "SC", tool, rep) for fs in FS for tool in ("targz", "sqlite")
            for trim in ("T0", "TD", "TF") for rep in (1, 2)]
    assert len(runs) == 48
    random.Random(20261111).shuffle(runs)
for r in runs:
    print(*r)

#!/usr/bin/env python3
"""Paper C, C5: the 36 runs of four deleted copies on the 14336-MiB device, in one fixed random order (prereg/C5.md).

    c5_run_list.py > c5_runs.txt         line: fs trim state tool rep
    c5_run_list.py smoke > c5_smoke.txt  one SD-T0 targz run per file system, rep 0"""
import random
import sys

FS = ("ext4", "xfs", "btrfs", "f2fs")
if sys.argv[1:] == ["smoke"]:
    runs = [(fs, "T0", "SD", "targz", 0) for fs in FS]
else:
    runs = [(fs, "T0", "SD", tool, rep) for fs in FS for tool in ("targz", "rsync", "sqlite") for rep in (1, 2, 3)]
    assert len(runs) == 36
    random.Random(20261112).shuffle(runs)
for r in runs:
    print(*r)

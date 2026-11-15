#!/usr/bin/env python3
"""Paper C, C2: the formal runs of parts B (churned state) and C (block layer) in one fixed random order.

    c2_run_list.py > c2_runs.txt          line: kind fs trim state tool rep   (kind churn | logw)
    c2_run_list.py smoke > c2_smoke.txt   one run per file system and part, rep 0, not manuscript data"""
import random
import sys

FS = ("ext4", "xfs", "btrfs", "f2fs")
TOOLS = ("targz", "rsync", "sqlite")
runs = []
if sys.argv[1:] == ["smoke"]:
    for fs in FS:
        runs.append(("churn", fs, "T0", "SG", "targz", 0))
        runs.append(("logw", fs, "TF", "SC", "targz", 0))
else:
    for fs in FS:
        for tool in TOOLS:
            for rep in range(1, 6):
                runs.append(("churn", fs, "T0", "SG", tool, rep))
            for trim in ("T0", "TF"):
                for rep in range(1, 4):
                    runs.append(("logw", fs, trim, "SC", tool, rep))
    assert len(runs) == 60 + 72
    random.Random(20261108).shuffle(runs)
for r in runs:
    print(*r)

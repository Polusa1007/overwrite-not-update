#!/usr/bin/env python3
"""Paper C: the 650 formal runs in one fixed random order. run_list.py > runs.txt"""
import random
TOOLS = ["copynr", "targz", "gzipf", "git", "rsync", "sqlite"]
runs = []
for fs in ("ext4", "xfs", "btrfs", "f2fs"):
    tools = TOOLS + (["copy"] if fs in ("xfs", "btrfs") else [])
    for tool in tools:
        for trim, state in (("T0", "S0"), ("T0", "SB"), ("T0", "SC"), ("TD", "SC"), ("TF", "SC")):
            for rep in range(1, 6):
                runs.append((fs, trim, state, tool, rep))
random.Random(20261107).shuffle(runs)
for r in runs:
    print(*r)

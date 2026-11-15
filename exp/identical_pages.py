#!/usr/bin/env python3
"""Paper C, post hoc (not pre-specified): overwrites whose new contents equal the old contents byte for byte.

    python3 -I identical_pages.py <runs root> <out csv> [processes]

Uses the classification of analyze_c.py unchanged (same trace, block map, groups and tool-phase mark) and counts, per
run and class group, the overwrites with known old contents and those among them with no differing byte (diff = 0).
Such a page needs no delta at all; a delta form other than XOR would find it as well."""
import csv
import glob
import gzip
import multiprocessing
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analyze_c as A  # noqa: E402


def one(path):
    parts = path.replace("\\", "/").split("/")
    fs = parts[-3]
    trim, state = parts[-2].split("_")[:2]
    tool, rep = parts[-1].rsplit("_", 1)
    rec = np.frombuffer(gzip.open(os.path.join(path, "trace.bin.gz")).read(), dtype=A.REC)
    rec = rec[np.argsort(rec["t"], kind="stable")]
    t0 = int(rec["t"][np.where(rec["op"] == 9)[0][0]])
    size = int(rec["lpn"].max()) + 1
    m, names, main = A.load_map(os.path.join(path, "map.txt.gz"), size)
    pre = rec[(rec["op"] == 1) & (rec["t"] < t0)]
    upre = np.unique(pre["lpn"])
    if main is not None:
        seg = (upre.astype(np.int64) - main) // A.SEG
        mapped = np.zeros(size // A.SEG + 2, dtype=bool)
        idx = np.nonzero(m)[0]
        idx = idx[idx >= main]
        mapped[(idx - main) // A.SEG] = True
        dead = (upre >= main) & ~mapped[np.clip(seg, 0, len(mapped) - 1)]
        names.append("dead_log")
        m[upre[dead]] = len(names) - 1
    if state == "SG":
        names.append("churned")
        cid = len(names) - 1
        m[upre[m[upre] == 0]] = cid
    w = rec[(rec["op"] == 1) & (rec["t"] >= t0)]
    _, first = np.unique(w["lpn"], return_index=True)
    is_first = np.zeros(len(w), dtype=bool)
    is_first[first] = True
    ov = w[w["over"] == 1]
    repeat = ~is_first[w["over"] == 1]
    known = ov["diff"] != 0xffff
    label = m[ov["lpn"]]
    rows = []
    for g in A.GROUPS:
        if g == "repeat":
            sel = repeat.copy()
        else:
            sel = np.zeros(len(ov), dtype=bool)
            for i, c in enumerate(names):
                if A.GROUP.get(c, "other") == g:
                    sel |= (label == i) & ~repeat
        k = sel & known
        rows.append([fs, trim, state, tool, int(rep), g, int(k.sum()), int((k & (ov["diff"] == 0)).sum())])
    return rows


def main():
    root, out = sys.argv[1:3]
    procs = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    paths = sorted(p for p in glob.glob(os.path.join(root, "*", "T?_S?_W60", "*_*"))
                   if os.path.exists(os.path.join(p, "trace.bin.gz")))
    with multiprocessing.Pool(procs) as pool:
        res = pool.map(one, paths, 4)
    with open(out, "w", newline="") as fp:
        w = csv.writer(fp)
        w.writerow(["fs", "trim", "state", "tool", "rep", "group", "known", "identical"])
        for rows in res:
            w.writerows(rows)
    print(len(res), "runs")


if __name__ == "__main__":
    main()

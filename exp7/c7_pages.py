#!/usr/bin/env python3
"""Paper C, C7 (prereg/C7.md): overwrites by what the page held before the tool, counting every overwrite of the page,
not only the first (the C1 classes count later overwrites of a page as tool rewrites).

    python3 -I c7_pages.py <runs root> <out csv> [processes]

Uses the trace, block map and tool-phase mark of exp/analyze_c.py unchanged. Per run and class group of the page
before the tool: overwrites, those with known old contents, and over these the summed compressed delta, the summed
min(compressed new page, 4096) and the summed min(delta, compressed new page, 4096). On a copy-on-write file system a
page may hold other data after its first overwrite; the class is still that of the page before the tool."""
import csv
import glob
import gzip
import multiprocessing
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "exp"))
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
            continue
        else:
            sel = np.zeros(len(ov), dtype=bool)
            for i, c in enumerate(names):
                if A.GROUP.get(c, "other") == g:
                    sel |= (label == i)
        k = sel & known
        dl = ov["pad"][k].astype(np.float64)
        nw = np.minimum((ov["clz"][k] >> 16).astype(np.float64), A.PAGE)
        rows.append([fs, trim, state, tool, int(rep), g, int(sel.sum()), int(k.sum()), float(dl.sum()), float(nw.sum()),
                     float(np.minimum(dl, nw).sum())])
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
        w.writerow(["fs", "trim", "state", "tool", "rep", "group", "n", "known", "delta_bytes", "comp_or_raw_bytes", "best_bytes"])
        for rows in res:
            w.writerows(rows)
    print(len(res), "runs")


if __name__ == "__main__":
    main()

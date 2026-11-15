#!/usr/bin/env python3
"""Paper C: run-level and cell-level measures from traces and block maps (prereg/C1.md, C2.md).

    python3 -I analyze_c.py <runs root> <out prefix> [processes]

Layout: <root>/<fs>/<trim>_<state>_W60/<tool>_<rep>/{trace.bin.gz,map.txt.gz,dump.hdr,workload.log}
Writes <prefix>_runs.csv, <prefix>_classes.csv (one row per run and class group) and <prefix>_cells.csv.
Only the old bytes of a write with known old content enter the byte measures."""
import csv
import glob
import gzip
import math
import multiprocessing
import os
import re
import sys

import numpy as np

REC = np.dtype([("t", "<u8"), ("lpn", "<u4"), ("ent", "<u2"), ("diff", "<u2"), ("clz", "<u4"), ("op", "u1"), ("over", "u1"), ("pad", "<u2")])
PAGE = 4096
SEG = 512
GROUP = {
    "stale_body": "freed", "stale_tail": "freed", "stale_dir": "freed", "churned": "freed",
    "src_body": "source", "src_tail": "source", "src_dir": "source",
    "live_body": "live", "live_tail": "live", "live_dir": "live",
    "meta": "metadata", "inode": "metadata", "node": "metadata", "journal": "metadata",
    "dead_node": "dead_log", "dead_data": "dead_log", "dead_log": "dead_log",
    "other": "other", "repeat": "repeat",
}
GROUPS = ["freed", "source", "live", "metadata", "dead_log", "repeat", "other"]
RC = (0.20, 0.35, 0.50)
T975 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262}


def load_map(path, size):
    """Returns the class-id array, the class names and the first block of the F2FS main area (or None)."""
    names = ["other"]
    ids = {"other": 0}
    m = np.zeros(size, dtype=np.uint8)
    post = []
    main = None
    with gzip.open(path, "rt") as fp:
        for line in fp:
            if line[0] == "#":
                f = re.search(r"# f2fs .*main (\d+)", line)
                if f:
                    main = int(f.group(1))
                continue
            c, a, n = line.split()
            a, n = int(a), int(n)
            if c == "postmeta":
                post.append((a, n))
                continue
            if c not in ids:
                ids[c] = len(names)
                names.append(c)
            if a < size:
                m[a:min(a + n, size)] = ids[c]
    for a, n in post:
        if "meta" not in ids:
            ids["meta"] = len(names)
            names.append("meta")
        part = m[a:min(a + n, size)]
        part[part == 0] = ids["meta"]
    return m, names, main


def one(path):
    parts = path.replace("\\", "/").split("/")
    fs = parts[-3]
    trim, state = parts[-2].split("_")[:2]
    tool, rep = parts[-1].rsplit("_", 1)
    key = [fs, trim, state, tool, int(rep)]
    rec = np.frombuffer(gzip.open(os.path.join(path, "trace.bin.gz")).read(), dtype=REC)
    rec = rec[np.argsort(rec["t"], kind="stable")]
    t0 = int(rec["t"][np.where(rec["op"] == 9)[0][0]])
    size = int(rec["lpn"].max()) + 1
    m, names, main = load_map(os.path.join(path, "map.txt.gz"), size)
    pre = rec[(rec["op"] == 1) & (rec["t"] < t0)]
    upre = np.unique(pre["lpn"])
    if main is not None:                    # F2FS: whole main-area segments written, without a mapped page
        seg = (upre.astype(np.int64) - main) // SEG
        mapped = np.zeros(size // SEG + 2, dtype=bool)
        idx = np.nonzero(m)[0]
        idx = idx[idx >= main]
        mapped[(idx - main) // SEG] = True
        dead = (upre >= main) & ~mapped[np.clip(seg, 0, len(mapped) - 1)]
        names.append("dead_log")
        m[upre[dead]] = len(names) - 1
    if state == "SG":                       # churned state: written earlier, in no live file now
        names.append("churned")
        cid = len(names) - 1
        m[upre[m[upre] == 0]] = cid
    pre_other = float(np.mean(m[upre] == 0)) if len(upre) else 0.0
    w = rec[(rec["op"] == 1) & (rec["t"] >= t0)]
    _, first = np.unique(w["lpn"], return_index=True)
    is_first = np.zeros(len(w), dtype=bool)
    is_first[first] = True
    ov = w[w["over"] == 1]
    repeat = ~is_first[w["over"] == 1]
    known = ov["diff"] != 0xffff
    delta = ov["pad"].astype(np.float64)
    new = (ov["clz"] >> 16).astype(np.float64)
    label = m[ov["lpn"]]
    rows = []
    for g in GROUPS:
        sel = np.zeros(len(ov), dtype=bool)
        if g == "repeat":
            sel = repeat.copy()
        else:
            for i, c in enumerate(names):
                if GROUP.get(c, "other") == g:
                    sel |= (label == i) & ~repeat
        k = sel & known
        n, nk = int(sel.sum()), int(k.sum())
        d = ov["diff"][k].astype(np.int64)
        rows.append(key + [g, n, nk, int((d > 0.9 * PAGE).sum()), int((d <= 0.1 * PAGE).sum()),
                           float(np.median(d)) if nk else float("nan"), float(delta[k].sum()), float(new[k].sum()),
                           float(np.minimum(np.minimum(delta[k], new[k]), PAGE).sum())])
    hdr = open(os.path.join(path, "dump.hdr")).read() if os.path.exists(os.path.join(path, "dump.hdr")) else ""
    ret = re.search(r"retained_now=(\d+)", hdr)
    secs = re.search(r"secs=([0-9.]+)", hdr)
    logp = os.path.join(path, "workload.log")
    run = key + [len(w), len(ov), f"{pre_other:.5f}", len(upre), int(np.sum((rec["op"] == 2) & (rec["t"] < t0))),
                 int(np.sum((rec["op"] == 2) & (rec["t"] >= t0))), int(known.sum()), ret.group(1) if ret else "",
                 secs.group(1) if secs else "", os.path.getsize(logp) if os.path.exists(logp) else ""]
    return run, rows


def ci(x):
    x = np.asarray(x, dtype=float)
    x = x[~np.isnan(x)]
    if len(x) == 0:
        return float("nan"), float("nan"), 0
    if len(x) == 1:
        return float(x[0]), float("nan"), 1
    return float(x.mean()), T975.get(len(x) - 1, 1.96) * float(x.std(ddof=1)) / math.sqrt(len(x)), len(x)


def main():
    root, prefix = sys.argv[1:3]
    procs = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    paths = sorted(p for p in glob.glob(os.path.join(root, "*", "T?_S?_W60", "*_*")) if os.path.exists(os.path.join(p, "trace.bin.gz")))
    with multiprocessing.Pool(procs) as pool:
        out = pool.map(one, paths, 4)
    KEY = ["fs", "trim", "state", "tool", "rep"]
    runs = [r for r, _ in out]
    classes = [c for _, rows in out for c in rows]
    with open(prefix + "_runs.csv", "w", newline="") as fp:
        w = csv.writer(fp)
        w.writerow(KEY + ["writes", "overwrites", "pre_unclassified", "pre_pages", "trims_prep", "trims_tool", "known_old", "retained_now", "secs", "workload_log_bytes"])
        w.writerows(runs)
    with open(prefix + "_classes.csv", "w", newline="") as fp:
        w = csv.writer(fp)
        w.writerow(KEY + ["group", "n", "known", "gt90", "le10", "median_changed", "delta_bytes", "new_bytes", "best_bytes"])
        w.writerows(classes)
    # per cell: mean and 95 % t half-width over replicates
    cells = {}
    for r in runs:
        cells.setdefault(tuple(r[:4]), {"share": []})["share"].append(r[6] / r[5] if r[5] else float("nan"))
    bygrp = {}
    for c in classes:
        bygrp.setdefault(tuple(c[:4]) + (c[5],), []).append(c)
    with open(prefix + "_cells.csv", "w", newline="") as fp:
        w = csv.writer(fp)
        w.writerow(KEY[:4] + ["measure", "group", "mean", "ci95", "reps"])
        for k, v in sorted(cells.items()):
            w.writerow(list(k) + ["overwrite_share", "all", *ci(v["share"])])
        for k, rows in sorted(bygrp.items()):
            cell, g = k[:4], k[4]
            total = {r[4]: 0 for r in rows}
            for r in runs:
                if tuple(r[:4]) == cell:
                    total[r[4]] = r[6]
            w.writerow(list(cell) + ["share_of_overwrites", g, *ci([r[6] / total[r[4]] if total[r[4]] else float("nan") for r in rows])])
            sel = [r for r in rows if r[7] > 0]
            if sel:
                w.writerow(list(cell) + ["gt90", g, *ci([r[8] / r[7] for r in sel])])
                w.writerow(list(cell) + ["le10", g, *ci([r[9] / r[7] for r in sel])])
                w.writerow(list(cell) + ["delta_ratio", g, *ci([r[11] / (r[7] * PAGE) for r in sel])])
                w.writerow(list(cell) + ["compress_ratio", g, *ci([r[12] / (r[7] * PAGE) for r in sel])])
        # evaluation gap: bytes written under the measured deltas against each assumed mean ratio
        for k in sorted(cells):
            per = {}
            for g in GROUPS:
                for r in bygrp.get(k + (g,), []):
                    a = per.setdefault(r[4], [0, 0.0, 0.0, 0.0])
                    a[0] += r[7]; a[1] += r[11]; a[2] += r[12]; a[3] += r[13]
            vals = [a for a in per.values() if a[0] > 0]
            if not vals:
                continue
            w.writerow(list(k) + ["measured_delta_ratio", "all", *ci([a[1] / (a[0] * PAGE) for a in vals])])
            w.writerow(list(k) + ["measured_compress_ratio", "all", *ci([a[2] / (a[0] * PAGE) for a in vals])])
            w.writerow(list(k) + ["measured_best_ratio", "all", *ci([a[3] / (a[0] * PAGE) for a in vals])])
            for rc in RC:
                w.writerow(list(k) + [f"measured_over_assumed_{rc}", "all", *ci([a[1] / (a[0] * PAGE * rc) for a in vals])])
    print(len(runs), "runs")


if __name__ == "__main__":
    main()

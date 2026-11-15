#!/usr/bin/env python3
"""Paper C: turn results/c1 and results/c2 into the numbers, tables and figures of the manuscript.

    python -I exp/make_paper.py            (run from paper_c/)

Writes manuscript/generated/numbers.tex (\\N... macros), manuscript/generated/tab_*.tex and
manuscript/figures/fig_*.pdf. Every experimental number in manuscript/main.tex comes from here; none is typed by hand.
Requires numpy and matplotlib."""
import csv
import math
import os
import re
from collections import defaultdict

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RES = os.path.join(ROOT, "results")
GEN = os.path.join(ROOT, "manuscript", "generated")
FIG = os.path.join(ROOT, "manuscript", "figures")
os.makedirs(GEN, exist_ok=True)
os.makedirs(FIG, exist_ok=True)

FS = ["ext4", "xfs", "btrfs", "f2fs"]
FSN = {"ext4": "ext4", "xfs": "XFS", "btrfs": "Btrfs", "f2fs": "F2FS"}
TOOLS = ["copynr", "copy", "rsync", "targz", "git", "gzipf", "sqlite"]
CONDS = [("T0", "S0"), ("T0", "SB"), ("T0", "SC"), ("TD", "SC"), ("TF", "SC")]
CONDN = {("T0", "S0"): "S0-T0", ("T0", "SB"): "SB-T0", ("T0", "SC"): "SC-T0", ("TD", "SC"): "SC-TD",
         ("TF", "SC"): "SC-TF", ("T0", "SG"): "SG-T0"}
GROUPS = ["freed", "source", "live", "metadata", "dead_log", "repeat", "other"]
GROUPN = {"freed": "freed", "source": "source tree", "live": "live files", "metadata": "metadata",
          "dead_log": "F2FS dead log", "repeat": "tool rewrite", "other": "unclassified"}
COPYLIKE = ["copynr", "rsync", "targz"]
RC = [0.20, 0.35, 0.50]
PAGE = 4096
# categorical slots of the reference palette, fixed order
COL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
GCOL = {"freed": COL[0], "source": COL[1], "live": COL[7], "metadata": COL[2], "dead_log": COL[3],
        "repeat": COL[6], "other": "#9a9a92"}
INK, INK2, GRID = "#1f1f1e", "#5c5c57", "#e4e3dd"

plt.rcParams.update({"font.family": "serif", "font.size": 8, "axes.edgecolor": INK2, "axes.labelcolor": INK,
                     "xtick.color": INK2, "ytick.color": INK2, "axes.linewidth": 0.6, "pdf.fonttype": 42})

N = {}


def num(key, val):
    N[key] = val


def macro_name(key):
    words = {"0": "Zero", "1": "One", "2": "Two", "3": "Three", "4": "Four", "5": "Five", "6": "Six", "7": "Seven",
             "8": "Eight", "9": "Nine"}
    return "N" + "".join(words.get(ch, ch) for ch in re.sub(r"[^A-Za-z0-9]", "", key))


def pct(x, d=0):
    return f"{100 * x:.{d}f}"


def f2(x, d=2):
    return f"{x:.{d}f}"


def read_cells(path):
    d = {}
    for x in csv.DictReader(open(path)):
        d[(x["fs"], x["trim"], x["state"], x["tool"], x["measure"], x["group"])] = \
            (float(x["mean"]), float(x["ci95"]) if x["ci95"] != "nan" else float("nan"), int(x["reps"]))
    return d


def read_rows(path):
    return list(csv.DictReader(open(path)))


c1 = read_cells(os.path.join(RES, "c1", "c1_cells.csv"))
r1 = read_rows(os.path.join(RES, "c1", "c1_runs.csv"))
k1 = read_rows(os.path.join(RES, "c1", "c1_classes.csv"))
ch = read_cells(os.path.join(RES, "c2", "churn_cells.csv"))
rch = read_rows(os.path.join(RES, "c2", "churn_runs.csv"))
kch = read_rows(os.path.join(RES, "c2", "churn_classes.csv"))
lw = read_cells(os.path.join(RES, "c2", "logw_cells.csv"))
rlw = read_rows(os.path.join(RES, "c2", "logw_runs.csv"))
gz = [line.strip().split(",") for line in open(os.path.join(RES, "c1", "c1_gzip_skips.csv")) if line.strip()]


def tools_of(fs):
    return [t for t in TOOLS if t != "copy" or fs in ("xfs", "btrfs")]


def get(d, fs, cond, tool, meas, group="all"):
    return d.get((fs, cond[0], cond[1], tool, meas, group), (float("nan"), float("nan"), 0))


# ------------------------------------------------------------------ counts and validity
num("RunsCOne", f"{len(r1):,}")
num("RunsChurn", str(len(rch)))
num("RunsLogw", str(len(rlw)))
num("CellsCOne", str(len({(r['fs'], r['trim'], r['state'], r['tool']) for r in r1})))
num("PairsCOne", str(len({(r['fs'], r['tool']) for r in r1})))
num("RepsCOne", str(max(get(c1, *k[:3], "overwrite_share")[2] for k in [(r['fs'], (r['trim'], r['state']), r['tool']) for r in r1])))
for name, rows in (("COne", r1), ("Churn", rch), ("Logw", rlw)):
    num(f"UnmappedMax{name}", pct(max(float(r["pre_unclassified"]) for r in rows), 2))
num("RetainedNonzero", str(sum(r["retained_now"] not in ("0",) for r in r1)))
num("WritesCOne", f"{sum(int(r['writes']) for r in r1) / 1e6:.0f}")
num("OverwritesCOne", f"{sum(int(r['overwrites']) for r in r1) / 1e6:.0f}")
unk = [r for r in r1 + rch + rlw if int(r["overwrites"]) > int(r["known_old"])]
num("UnknownOldPct", pct(sum(int(r["overwrites"]) - int(r["known_old"]) for r in r1) / sum(int(r["overwrites"]) for r in r1), 2))
num("UnknownOldFs", ", ".join(sorted({FSN[r["fs"]] for r in unk})))
skips = sorted({int(x[3]) for x in gz})
num("GzipRuns", str(len(gz)))
num("GzipSkips", "--".join(str(s) for s in (skips if len(skips) < 3 else [skips[0], skips[-1]])))
num("GzipExitRuns", str(sum(int(x[4]) > 0 for x in gz)))

# ------------------------------------------------------------------ RQ1
def share(fs, cond, tool, d=c1):
    return get(d, fs, cond, tool, "overwrite_share")[0]


def rng(vals, d=0):
    vals = [v for v in vals if not math.isnan(v)]
    return pct(min(vals), d), pct(max(vals), d)


S0, SB, SC, TD, TF = CONDS
a, b = rng([share(fs, S0, t) for fs in FS for t in COPYLIKE])
num("ShareCopySZeroMin", a); num("ShareCopySZeroMax", b)
a, b = rng([share(fs, c, t) for fs in FS for t in COPYLIKE for c in (SB, SC)])
num("ShareCopyStaleMin", a); num("ShareCopyStaleMax", b)
a, b = rng([share(fs, c, t) for fs in ("xfs", "btrfs", "f2fs") for t in COPYLIKE for c in (SB, SC)])
num("ShareCopyStaleOtherMin", a); num("ShareCopyStaleOtherMax", b)
a, b = rng([share("ext4", c, t) for t in COPYLIKE for c in (SB, SC)])
num("ShareCopyStaleExtMin", a); num("ShareCopyStaleExtMax", b)
a, b = rng([share(fs, c, t) for fs in FS for t in COPYLIKE for c in (TD, TF)])
num("ShareCopyTrimMin", a); num("ShareCopyTrimMax", b)
a, b = rng([share(fs, S0, t) for fs in FS for t in ("gzipf", "sqlite")])
num("ShareInplaceSZeroMin", a); num("ShareInplaceSZeroMax", b)
num("ShareBtrfsTDMax", pct(max(share("btrfs", TD, t) for t in tools_of("btrfs")), 2))
a, b = rng([share("f2fs", TD, t) for t in ("gzipf", "sqlite")])
num("ShareFTwoTDInplaceMin", a); num("ShareFTwoTDInplaceMax", b)
a, b = rng([share(fs, c, "sqlite") for fs in FS for c in CONDS])
num("ShareSqliteMin", a); num("ShareSqliteMax", b)
num("ShareXfsCopySZero", pct(share("xfs", S0, "copy")))
num("ShareXfsTargzSB", pct(share("xfs", SB, "targz")))
num("ShareXfsTargzSBci", pct(get(c1, "xfs", SB, "targz", "overwrite_share")[1]))
# the most variable cells: largest 95 % half-width of the overwrite share (ties listed)
hw = {(fs, c, t): get(c1, fs, c, t, "overwrite_share")[1] for fs in FS for c in CONDS for t in tools_of(fs)}
top = max(round(100 * v) for v in hw.values() if not math.isnan(v))
mv = [k for k, v in hw.items() if not math.isnan(v) and round(100 * v) == top]
num("MostVarList", ", ".join(f"{FSN[fs]} {t} under {CONDN[c]} ({pct(share(fs, c, t))}\\,\\% $\\pm$ {top})"
                             for fs, c, t in mv))
num("ShareBtrfsCopySC", pct(share("btrfs", SC, "copy")))

# ------------------------------------------------------------------ RQ2
def gshare(fs, cond, tool, g, d=c1):
    return get(d, fs, cond, tool, "share_of_overwrites", g)[0]


num("LiveMax", pct(max(gshare(fs, c, t, "live") for fs in FS for c in CONDS for t in tools_of(fs)), 1))
a, b = rng([gshare(fs, SC, t, "freed") for fs in ("ext4", "xfs", "btrfs") for t in COPYLIKE])
num("FreedCopySCMin", a); num("FreedCopySCMax", b)
a, b = rng([gshare("f2fs", SC, t, "freed") for t in COPYLIKE])
num("FreedFTwoSCMin", a); num("FreedFTwoSCMax", b)
a, b = rng([gshare("f2fs", SC, t, "dead_log") for t in COPYLIKE])
num("DeadFTwoSCMin", a); num("DeadFTwoSCMax", b)
num("FreedTrimMax", pct(max(gshare(fs, c, t, "freed") for fs in FS for c in (S0, TD, TF) for t in tools_of(fs)), 1))
a, b = rng([gshare(fs, c, "sqlite", "repeat") for fs in FS for c in CONDS])
num("RepeatSqliteMin", a); num("RepeatSqliteMax", b)
a, b = rng([gshare(fs, c, t, "metadata") for fs in ("ext4", "xfs") for t in ("copynr", "rsync", "targz") for c in (S0, TD, TF)])
num("MetaCopyNoStaleMin", a); num("MetaCopyNoStaleMax", b)
a, b = rng([gshare(fs, c, "gzipf", "source") for fs in FS for c in CONDS if c != TD])
num("GzipSourceMin", a); num("GzipSourceMax", b)
a, b = rng([gshare(fs, TD, "gzipf", "source") for fs in ("ext4", "xfs", "btrfs")])
num("GzipSourceTDMin", a); num("GzipSourceTDMax", b)
num("GzipSourceTDFTwo", pct(gshare("f2fs", TD, "gzipf", "source")))
num("OtherMax", pct(max(gshare(fs, c, t, "other") for fs in FS for c in CONDS for t in tools_of(fs)), 1))

# ------------------------------------------------------------------ RQ3
def dr(fs, cond, tool, m="measured_delta_ratio", d=c1):
    return get(d, fs, cond, tool, m)[0]


vals = [dr(fs, SC, t) for fs in FS for t in COPYLIKE]
num("DeltaCopySCMin", f2(min(vals))); num("DeltaCopySCMax", f2(max(vals)))
vals = [dr(fs, SC, t, "measured_over_assumed_0.35") for fs in FS for t in COPYLIKE]
num("OverRcCopySCMin", f"{min(vals):.1f}"); num("OverRcCopySCMax", f"{max(vals):.1f}")
vals = [dr(fs, c, t) for fs in ("ext4", "xfs", "btrfs") for t in COPYLIKE for c in (S0, TD, TF)]
num("DeltaCopyNoStaleMin", f2(min(vals))); num("DeltaCopyNoStaleMax", f2(max(vals)))
vals = [dr("f2fs", c, t) for t in COPYLIKE for c in (S0, TD, TF)]
num("DeltaFTwoNoStaleMin", f2(min(vals))); num("DeltaFTwoNoStaleMax", f2(max(vals)))
vals = [dr("f2fs", S0, t) for t in COPYLIKE]
num("DeltaFTwoSZeroMin", f2(min(vals))); num("DeltaFTwoSZeroMax", f2(max(vals)))
vals = [dr(fs, S0, t) for fs in ("ext4", "xfs", "btrfs") for t in COPYLIKE]
num("DeltaCopySZeroOtherMin", f2(min(vals))); num("DeltaCopySZeroOtherMax", f2(max(vals)))
vals = [dr(fs, c, t) for fs in FS for t in COPYLIKE for c in (TD, TF)]
num("DeltaCopyTrimAllMin", f2(min(vals))); num("DeltaCopyTrimAllMax", f2(max(vals)))
vals = [dr("f2fs", c, t) for t in COPYLIKE for c in (TD, TF)]
num("DeltaFTwoTrimMin", f2(min(vals))); num("DeltaFTwoTrimMax", f2(max(vals)))
vals = [dr(fs, c, "sqlite") for fs in FS for c in CONDS]
num("DeltaSqliteMin", f2(min(vals))); num("DeltaSqliteMax", f2(max(vals)))
cells = [(fs, c, t) for fs in FS for c in CONDS for t in tools_of(fs)]
worse = [k for k in cells if dr(*k) > dr(*k, "measured_compress_ratio")]
num("CellsDeltaWorse", str(len(worse)))
num("CellsAll", str(len(cells)))
worse_sc = [k for k in cells if k[1] in (SB, SC) and dr(*k) > dr(*k, "measured_compress_ratio")]
num("CellsDeltaWorseStale", str(len(worse_sc)))
num("CellsStale", str(sum(1 for k in cells if k[1] in (SB, SC))))
below = {rc: sum(1 for k in cells if dr(*k) <= rc) for rc in RC}
for rc in RC:
    num(f"CellsBelowRc{int(rc * 100)}", str(below[rc]))
num("DeltaExtCopynrSC", f2(dr("ext4", SC, "copynr")))
num("ComprExtCopynrSC", f2(dr("ext4", SC, "copynr", "measured_compress_ratio")))


# pooled per class group: bytes summed over runs
def pooled(rows, keep):
    p = defaultdict(lambda: [0, 0, 0, 0, 0.0, 0.0, 0.0])
    for r in rows:
        if not keep(r):
            continue
        a = p[(r["fs"], r["group"])]
        a[0] += int(r["n"]); a[1] += int(r["known"]); a[2] += int(r["gt90"]); a[3] += int(r["le10"])
        a[4] += float(r["delta_bytes"]); a[5] += float(r["new_bytes"]); a[6] += float(r["best_bytes"])
    return p


pool_all = pooled(k1, lambda r: True)
for fs in FS:
    for g in ("freed", "metadata", "repeat"):
        a = pool_all.get((fs, g))
        if a and a[1]:
            num(f"Pool{fs}{g}Delta", f2(a[4] / (a[1] * PAGE)))
            num(f"Pool{fs}{g}Gt", pct(a[2] / a[1]))
            num(f"Pool{fs}{g}Le", pct(a[3] / a[1]))

for g in ("freed", "repeat", "source"):
    vals = [pool_all[(fs, g)][4] / (pool_all[(fs, g)][1] * PAGE) for fs in FS if pool_all.get((fs, g)) and pool_all[(fs, g)][1]]
    num(f"Pool{g}DeltaMin", f2(min(vals))); num(f"Pool{g}DeltaMax", f2(max(vals)))

# cells counted as "delta larger": comparison of unrounded means; how many of them tie at two decimals
num("CellsDeltaWorseTie", str(sum(round(dr(*k), 2) == round(dr(*k, "measured_compress_ratio"), 2) for k in worse)))
# targz writes gzip output: compression ratio of its new pages; copynr and rsync separately
vals = [dr(fs, SC, "targz", "measured_compress_ratio") for fs in FS]
num("TargzComprSCMin", f2(min(vals))); num("TargzComprSCMax", f2(max(vals)))
vals = [dr(fs, SC, "targz") for fs in FS]
num("TargzDeltaSCMin", f2(min(vals))); num("TargzDeltaSCMax", f2(max(vals)))
vals = [dr(fs, SC, t) for fs in FS for t in ("copynr", "rsync")]
num("CopyRsDeltaSCMin", f2(min(vals))); num("CopyRsDeltaSCMax", f2(max(vals)))
vals = [dr(fs, SC, t, "measured_compress_ratio") for fs in FS for t in ("copynr", "rsync")]
num("CopyRsComprSCMin", f2(min(vals))); num("CopyRsComprSCMax", f2(max(vals)))
# what fstrim leaves for gzipf and sqlite
a, b = rng([gshare(fs, TF, "gzipf", "source") for fs in FS])
num("GzipTFSourceMin", a); num("GzipTFSourceMax", b)
vals = [dr(fs, TF, "gzipf") for fs in ("ext4", "xfs", "btrfs")]
num("GzipTFDeltaMin", f2(min(vals))); num("GzipTFDeltaMax", f2(max(vals)))
num("GzipTFDeltaFTwo", f2(dr("f2fs", TF, "gzipf")))
vals = [dr(fs, TF, "gzipf", "measured_compress_ratio") for fs in FS]
num("GzipTFComprMin", f2(min(vals))); num("GzipTFComprMax", f2(max(vals)))
vals = [dr(fs, TF, "sqlite") for fs in FS]
num("SqliteTFDeltaMin", f2(min(vals))); num("SqliteTFDeltaMax", f2(max(vals)))
vals = [dr(fs, TF, "sqlite", "measured_compress_ratio") for fs in FS]
num("SqliteTFComprMin", f2(min(vals))); num("SqliteTFComprMax", f2(max(vals)))
# post hoc (exp/net_gain.py): gain of storing the smallest of delta, compressed and raw page over the smaller of
# compressed and raw page, in % of a page (pooled over all main-campaign overwrites with known old contents)
ng1 = read_rows(os.path.join(RES, "posthoc", "c1_net_gain.csv"))
gain = defaultdict(lambda: [0, 0.0, 0.0])
for r in ng1:
    for key in (r["group"], "all", r["trim"] + r["state"], (r["fs"], r["group"])):
        x = gain[key]; x[0] += int(r["known"]); x[1] += float(r["comp_or_raw_bytes"]); x[2] += float(r["best_bytes"])
rep_known = sum(int(r["known"]) for r in k1 if r["group"] == "repeat")
num("RepeatSqliteShare", pct(sum(int(r["known"]) for r in k1 if r["group"] == "repeat" and r["tool"] == "sqlite") / rep_known))
for key in ("freed", "source", "metadata", "dead_log", "repeat", "all", "T0SC", "TFSC", "TDSC", "T0S0"):
    n_, nw, b_ = gain[key]
    num(f"Gain{key}", pct((nw - b_) / (n_ * PAGE), 1))
    num(f"Best{key}", f2(b_ / (n_ * PAGE)))
    num(f"Compr{key}", f2(nw / (n_ * PAGE)))

# ------------------------------------------------------------------ C2 part C
pc_rows = []
for trim in ("T0", "TF"):
    for fs in FS:
        for t in ("targz", "rsync", "sqlite"):
            cond = (trim, "SC")
            sa, sb = share(fs, cond, t), share(fs, cond, t, lw)
            da, db = dr(fs, cond, t), dr(fs, cond, t, d=lw)
            dis = abs(sa - sb) > 0.05 or abs(da - db) > 0.05
            pc_rows.append((cond, fs, t, sa, sb, da, db, dis))
num("PartCCells", str(len(pc_rows)))
num("PartCDisagree", str(sum(r[7] for r in pc_rows)))
num("PartCAgree", str(sum(not r[7] for r in pc_rows)))


def runs_of(rows, fs, trim, state, tool):
    return [int(r["overwrites"]) / int(r["writes"]) for r in rows
            if (r["fs"], r["trim"], r["state"], r["tool"]) == (fs, trim, state, tool)]


x = runs_of(r1, "ext4", "T0", "SC", "targz"); y = runs_of(rlw, "ext4", "T0", "SC", "targz")
num("ExtTargzFemuMin", pct(min(x))); num("ExtTargzFemuMax", pct(max(x)))
num("ExtTargzLogwMin", pct(min(y))); num("ExtTargzLogwMax", pct(max(y)))
y = runs_of(rlw, "btrfs", "TF", "SC", "rsync")
num("BtrfsRsyncLogwOutlier", pct(max(y), 1))
num("BtrfsRsyncLogwOthersMax", pct(sorted(y)[-2], 1))

# ------------------------------------------------------------------ C2 part B
SG = ("T0", "SG")
a, b = rng([share(fs, SG, t, ch) for fs in FS for t in ("targz", "rsync")])
num("ShareChurnCopyMin", a); num("ShareChurnCopyMax", b)
num("ShareChurnXfsTargz", pct(share("xfs", SG, "targz", ch)))
num("ShareChurnXfsTargzci", pct(get(ch, "xfs", SG, "targz", "overwrite_share")[1]))
hwc = {(fs, t): get(ch, fs, SG, t, "overwrite_share")[1] for fs in FS for t in ("targz", "rsync", "sqlite")}
topc = max(round(100 * v) for v in hwc.values() if not math.isnan(v))
num("ChurnMostVarList", " and ".join(f"{FSN[fs]} {t}" for (fs, t), v in hwc.items()
                                     if not math.isnan(v) and round(100 * v) == topc))
num("ChurnMostVarCi", str(topc))
num("LiveChurnMax", pct(max(gshare(fs, SG, t, "live", ch) for fs in FS for t in ("targz", "rsync", "sqlite")), 1))
lv = [(int(c["n"]), c["fs"], c["tool"]) for c in kch if c["group"] == "live" and int(c["n"])]
num("LiveChurnN", str(sum(x[0] for x in lv)))
num("LiveChurnRuns", str(len(lv)))
num("LiveChurnWhere", ", ".join(sorted({f"{FSN[f]} {t}" for _, f, t in lv})) or "none")
num("LiveChurnWhereText", f"all in one {FSN[lv[0][1]]} {lv[0][2]} run" if len(lv) == 1
    else f"in {len(lv)} runs ({', '.join(sorted({FSN[f] + ' ' + t for _, f, t in lv}))})")
num("UsedChurnNote", "45")

# ------------------------------------------------------------------ C3 device size
c3 = read_cells(os.path.join(RES, "c3", "c3_cells.csv"))
r3 = read_rows(os.path.join(RES, "c3", "c3_runs.csv"))
num("RunsCThree", str(len(r3)))
num("RepsCThree", str(max(int(v[2]) for v in c3.values())))
num("UnmappedMaxCThree", pct(max(float(r["pre_unclassified"]) for r in r3), 2))
num("RetainedNonzeroCThree", str(sum(r["retained_now"] != "0" for r in r3)))
size_rows = []
for fs in FS:
    for cond in (S0, SC, TF):
        for t in ("targz", "rsync", "sqlite"):
            sa, sb = share(fs, cond, t), share(fs, cond, t, c3)
            da, db = dr(fs, cond, t), dr(fs, cond, t, d=c3)
            size_rows.append((cond, fs, t, sa, sb, da, db, abs(sa - sb) > 0.05 or abs(da - db) > 0.05))
num("SizeCells", str(len(size_rows)))
num("SizeEffects", str(sum(r[7] for r in size_rows)))
num("SizeShareEffects", str(sum(abs(r[3] - r[4]) > 0.05 for r in size_rows)))
for fs in ("ext4", "xfs"):
    x = runs_of(r1, fs, "T0", "SC", "targz"); y = runs_of(r3, fs, "T0", "SC", "targz")
    num(f"Size{fs}TargzSevenMin", pct(min(x))); num(f"Size{fs}TargzSevenMax", pct(max(x)))
    num(f"Size{fs}TargzFourteenMin", pct(min(y))); num(f"Size{fs}TargzFourteenMax", pct(max(y)))
    num(f"Size{fs}TargzSeven", pct(share(fs, SC, "targz"))); num(f"Size{fs}TargzFourteen", pct(share(fs, SC, "targz", c3)))
ow = [int(r["overwrites"]) for r in r1 + r3 if (r["fs"], r["trim"], r["state"]) == ("btrfs", "TF", "SC") and r["tool"] in ("rsync", "targz")]
num("SizeBtrfsTFOverwritesMax", str(max(ow)))
others = [r for r in size_rows if not (r[0] == SC and r[2] == "targz" and r[1] in ("ext4", "xfs"))]
a, b = rng([share(fs, SC, t, c3) for fs in FS for t in ("targz", "rsync")])
num("SizeShareCopySCMin", a); num("SizeShareCopySCMax", b)
a, b = rng([gshare(fs, SC, t, "freed", c3) for fs in ("ext4", "xfs", "btrfs") for t in ("targz", "rsync")])
num("SizeFreedCopySCMin", a); num("SizeFreedCopySCMax", b)
vals = [dr(fs, SC, t, d=c3) for fs in FS for t in ("targz", "rsync")]
num("SizeDeltaCopySCMin", f2(min(vals))); num("SizeDeltaCopySCMax", f2(max(vals)))
num("SizeOtherShareDiffMax", f"{100 * max(abs(r[3] - r[4]) for r in others):.1f}")

# ------------------------------------------------------------------ post hoc (not pre-specified)
# Effect sizes as differences of means with Welch 95 % intervals, run-level ranges, median instead of mean, and
# leave-one-run-out. All use the per-run outputs above; none was part of the frozen specifications.
from scipy import stats

klw = read_rows(os.path.join(RES, "c2", "logw_classes.csv"))


def write(name, text):
    open(os.path.join(GEN, name), "w", encoding="utf-8").write("% generated by exp/make_paper.py\n" + text)


def per_run(runs, classes):
    """{(fs, trim, state, tool): {rep: (share, delta_ratio, compress_ratio)}}"""
    acc = defaultdict(lambda: [0, 0.0, 0.0])
    for c in classes:
        a = acc[(c["fs"], c["trim"], c["state"], c["tool"], c["rep"])]
        a[0] += int(c["known"]); a[1] += float(c["delta_bytes"]); a[2] += float(c["new_bytes"])
    out = defaultdict(dict)
    for r in runs:
        k = (r["fs"], r["trim"], r["state"], r["tool"])
        a = acc[k + (r["rep"],)]
        sh = int(r["overwrites"]) / int(r["writes"]) if int(r["writes"]) else float("nan")
        out[k][r["rep"]] = (sh, a[1] / (a[0] * PAGE) if a[0] else float("nan"), a[2] / (a[0] * PAGE) if a[0] else float("nan"))
    return out


P1, PLW = per_run(r1, k1), per_run(rlw, klw)


def vals(P, fs, cond, tool, i):
    return [v[i] for v in P.get((fs, cond[0], cond[1], tool), {}).values() if not math.isnan(v[i])]


def welch(a, b):
    """difference of means a - b and the half-width of its Welch 95 % interval"""
    a, b = np.asarray(a, float), np.asarray(b, float)
    d = a.mean() - b.mean()
    va, vb = a.var(ddof=1) / len(a), b.var(ddof=1) / len(b)
    se = math.sqrt(va + vb)
    if se == 0:
        return d, 0.0
    df = (va + vb) ** 2 / (va ** 2 / (len(a) - 1) + vb ** 2 / (len(b) - 1))
    return d, float(stats.t.ppf(0.975, df)) * se


def dcell(d, h, scale=100, dd=0):
    if math.isnan(d):
        return "--"
    s = f"{scale * d:+.{dd}f}"
    s = "0" if float(s) == 0 else s.replace("-", "$-$")
    return s if h == 0 else s + f"\\,$\\pm$\\,{scale * h:.{dd}f}"


# effect table: deleted data and TRIM, per file system and tool
EFF_TOOLS = ["copynr", "rsync", "targz", "gzipf", "sqlite"]
CONTRASTS = [("del", SC, S0, "SC-T0 $-$ S0-T0"), ("tf", SC, TF, "SC-T0 $-$ SC-TF"), ("td", SC, TD, "SC-T0 $-$ SC-TD")]
eff = {}
for fs in FS:
    for t in EFF_TOOLS:
        for name, ca, cb, _ in CONTRASTS:
            for i, m in ((0, "share"), (1, "delta")):
                a, b = vals(P1, fs, ca, t, i), vals(P1, fs, cb, t, i)
                eff[(fs, t, name, m)] = welch(a, b) if len(a) > 1 and len(b) > 1 else (float("nan"), float("nan"))
lines = ["\\begin{tabular}{ll" + "r" * 6 + "}", "\\toprule",
         " & & \\multicolumn{3}{c}{Overwrite share (percentage points)} & \\multicolumn{3}{c}{Delta ratio ($\\times 100$)} \\\\",
         "File system & Tool & " + " & ".join(c[3] for c in CONTRASTS) + " & " + " & ".join(c[3] for c in CONTRASTS) + " \\\\",
         "\\midrule"]
for fs in FS:
    for j, t in enumerate(EFF_TOOLS):
        row = [FSN[fs] if j == 0 else "", t]
        row += [dcell(*eff[(fs, t, c[0], "share")]) for c in CONTRASTS]
        row += [dcell(*eff[(fs, t, c[0], "delta")]) for c in CONTRASTS]
        lines.append(" & ".join(row) + " \\\\")
    lines.append("\\midrule" if fs != FS[-1] else "\\bottomrule")
lines.append("\\end{tabular}")
write("tab_effect.tex", "\n".join(lines) + "\n")

# effect numbers used in the text
cp = [(fs, t) for fs in FS for t in COPYLIKE]
lo = min(eff[(fs, t, "del", "share")][0] - eff[(fs, t, "del", "share")][1] for fs, t in cp)
num("EffDelShareLow", pct(lo))
a, b = rng([eff[(fs, t, "del", "share")][0] for fs, t in cp])
num("EffDelShareMin", a); num("EffDelShareMax", b)
for name in ("tf", "td"):
    a, b = rng([eff[(fs, t, name, "share")][0] for fs, t in cp])
    num(f"Eff{name}ShareMin", a); num(f"Eff{name}ShareMax", b)
    num(f"Eff{name}ShareLow", pct(min(eff[(fs, t, name, "share")][0] - eff[(fs, t, name, "share")][1] for fs, t in cp)))
# delta-ratio drop with fstrim: ext4/XFS/Btrfs against F2FS
for grp, fss in (("Other", ("ext4", "xfs", "btrfs")), ("FTwo", ("f2fs",))):
    v = [eff[(fs, t, "tf", "delta")][0] for fs in fss for t in COPYLIKE]
    num(f"EffTfDelta{grp}Min", f2(min(v))); num(f"EffTfDelta{grp}Max", f2(max(v)))
# in-place tools under the two TRIM mechanisms, and the TRIM records issued during the tool phase
OTHER3 = ("ext4", "xfs", "btrfs")
for t, tn in (("sqlite", "Sqlite"), ("gzipf", "Gzip")):
    for c, cn in ((S0, "SZero"), (TF, "TF"), (TD, "TD")):
        a, b = rng([share(fs, c, t) for fs in OTHER3])
        num(f"InPl{tn}{cn}Min", a); num(f"InPl{tn}{cn}Max", b)
        num(f"InPl{tn}{cn}FTwo", pct(share("f2fs", c, t)))


def trims_tool(fs, cond, tool):
    v = [int(r["trims_tool"]) for r in r1 if (r["fs"], r["trim"], r["state"], r["tool"]) == (fs, cond[0], cond[1], tool)]
    return sum(v) / len(v)


v = [trims_tool(fs, TD, "sqlite") for fs in OTHER3]
num("TrimToolSqliteTDMin", f"{min(v) / 1e3:,.0f}"); num("TrimToolSqliteTDMax", f"{max(v) / 1e3:,.0f}")
num("TrimToolSqliteTDFTwo", f"{trims_tool('f2fs', TD, 'sqlite') / 1e3:,.1f}")
num("TrimToolOtherMax", str(max(int(r["trims_tool"]) for r in r1 if r["trim"] != "TD")))
_tto = max(int(r["trims_tool"]) for r in r1 if r["trim"] != "TD")
num("TrimToolOtherText", "none in any other run" if _tto == 0 else f"at most {_tto} in any other run")

# block layer minus emulator, with Welch intervals (FEMU n = 5, block layer n = 3)
pc_eff = []
for cond, fs, t, *_ in pc_rows:
    a, b = vals(PLW, fs, cond, t, 0), vals(P1, fs, cond, t, 0)
    c_, d_ = vals(PLW, fs, cond, t, 1), vals(P1, fs, cond, t, 1)
    pc_eff.append((welch(a, b), welch(c_, d_) if len(c_) > 1 and len(d_) > 1 else (float("nan"), float("nan"))))
num("PartCCiExcludeZero", str(sum(1 for (s, _) in pc_eff if abs(s[0]) > s[1])))

# run-level robustness of the main claims
runs_sc = [v for fs in FS for t in COPYLIKE for v in vals(P1, fs, SC, t, 0)]
num("RunShareCopySCMin", pct(min(runs_sc)))
runs_trim = [v for fs in FS for t in COPYLIKE for c in (TD, TF) for v in vals(P1, fs, c, t, 0)]
num("RunShareCopyTrimMax", pct(max(runs_trim), 1))
runs_d = [v for fs in FS for t in COPYLIKE for v in vals(P1, fs, SC, t, 1)]
num("RunDeltaCopySCMin", f2(min(runs_d)))
num("RunsCopySC", str(len(runs_sc)))
# cells whose replicates spread over more than 20 percentage points
wide = [(fs, c, t, max(v) - min(v)) for fs in FS for c in CONDS for t in tools_of(fs)
        for v in [vals(P1, fs, c, t, 0)] if v and max(v) - min(v) > 0.20]
num("WideCells", str(len(wide)))
num("WideCellsList", ", ".join(f"{FSN[fs]} {t} {CONDN[c]}" for fs, c, t, _ in wide))
num("WideCellsStale", str(sum(1 for w in wide if w[1] in (SB, SC))))

# median instead of mean: delta larger than compressed new page
med_worse = sum(1 for (fs, c, t) in cells
                if np.median(vals(P1, fs, c, t, 1) or [np.nan]) > np.median(vals(P1, fs, c, t, 2) or [np.nan]))
num("CellsDeltaWorseMedian", str(med_worse))
# leave one run out: range of the count of cells with delta > compression
loo = []
for (fs, c, t) in cells:
    reps = P1.get((fs, c[0], c[1], t), {})
    for drop in reps:
        cnt = 0
        for (fs2, c2, t2) in cells:
            r2 = {k: v for k, v in P1.get((fs2, c2[0], c2[1], t2), {}).items() if (fs2, c2, t2, k) != (fs, c, t, drop)}
            dv = [v[1] for v in r2.values() if not math.isnan(v[1])]; cv = [v[2] for v in r2.values() if not math.isnan(v[2])]
            cnt += bool(dv and cv and np.mean(dv) > np.mean(cv))
        loo.append(cnt)
num("LooWorseMin", str(min(loo))); num("LooWorseMax", str(max(loo)))
num("LooWorseText", f"{min(loo)} cells in every case" if min(loo) == max(loo) else f"{min(loo)} to {max(loo)} cells")
# leave one run out for the SC-T0 copy-like delta range
lo_d = min(np.mean([v for k, v in enumerate(vals(P1, fs, SC, t, 1)) if k != j]) for fs in FS for t in COPYLIKE
           for j in range(len(vals(P1, fs, SC, t, 1))))
num("LooDeltaCopySCMin", f2(lo_d))

# part C with the Welch difference
lines = ["\\begin{tabular}{lllrrrrrl}", "\\toprule",
         "Condition & File system & Tool & \\multicolumn{3}{c}{Overwrite share (\\%)} & \\multicolumn{2}{c}{Delta ratio} & \\\\",
         " & & & FEMU & block layer & difference & FEMU & block layer & \\\\", "\\midrule"]
for (cond, fs, t, sa, sb, da, db, dis), (s, _) in zip(pc_rows, pc_eff):
    lines.append(" & ".join([CONDN[cond], FSN[fs], t, pct(sa, 1), pct(sb, 1), dcell(s[0], s[1], dd=1), f2(da), f2(db),
                             "disagrees" if dis else ""]) + " \\\\")
lines += ["\\bottomrule", "\\end{tabular}"]
write("tab_partc.tex", "\n".join(lines) + "\n")

# post hoc: overwrites whose new page equals the old one byte for byte (exp/identical_pages.py)
idr = read_rows(os.path.join(RES, "posthoc", "c1_identical.csv"))
tot = [sum(int(r["known"]) for r in idr), sum(int(r["identical"]) for r in idr)]
num("IdentAll", pct(tot[1] / tot[0], 1))
idg = defaultdict(lambda: [0, 0])
for r in idr:
    idg[(r["fs"], r["group"])][0] += int(r["known"]); idg[(r["fs"], r["group"])][1] += int(r["identical"])
num("IdentFreedOtherMax", pct(max(idg[(fs, "freed")][1] / idg[(fs, "freed")][0] for fs in ("ext4", "xfs", "f2fs")), 1))
num("IdentFreedBtrfs", pct(idg[("btrfs", "freed")][1] / idg[("btrfs", "freed")][0], 1))
num("IdentOtherClassMax", pct(max(v[1] / v[0] for (fs, g), v in idg.items() if g != "freed" and v[0]), 1))
high = [r for r in idr if r["group"] == "freed" and int(r["known"]) and int(r["identical"]) / int(r["known"]) > 0.05]
assert all((r["fs"], r["tool"]) == ("btrfs", "copynr") for r in high)
num("IdentHighRuns", str(len(high)))
btc = [int(r["identical"]) / int(r["known"]) for r in idr if (r["fs"], r["tool"], r["trim"], r["group"]) == ("btrfs", "copynr", "T0", "freed")
       and r["state"] in ("SB", "SC") and int(r["known"])]
num("IdentBtrfsCopynrRuns", str(len(btc)))
num("IdentBtrfsCopynrMin", pct(min(btc))); num("IdentBtrfsCopynrMax", pct(max(btc)))
for c in ("c3", "c4"):
    x = read_rows(os.path.join(RES, "posthoc", f"{c}_identical.csv"))
    num(f"IdentAll{c.upper()}", pct(sum(int(r["identical"]) for r in x) / sum(int(r["known"]) for r in x), 1))

# post hoc: allocation groups (exp/alloc_groups.py) for ext4 and XFS under untrimmed deleted data
ag = read_rows(os.path.join(RES, "posthoc", "alloc_groups.csv"))


def ag_sel(camp, fs, state, tool):
    return [r for r in ag if (r["campaign"], r["fs"], r["state"], r["tool"]) == (camp, fs, state, tool)]


for camp, state, lab in (("c1", "SC", "Seven"), ("c3", "SC", "Fourteen"), ("c5", "SD", "FourteenSD")):
    rs = ag_sel(camp, "ext4", state, "targz")
    out = [int(r["writes_outside_freed_groups"]) / int(r["writes"]) for r in rs]
    gf = [int(r["groups_with_freed"]) for r in rs]
    num(f"AgExtTargzOut{lab}Min", pct(min(out))); num(f"AgExtTargzOut{lab}Max", pct(max(out)))
    num(f"AgExtGroupsFreed{lab}Min", str(min(gf))); num(f"AgExtGroupsFreed{lab}Max", str(max(gf)))
    num(f"AgExtGroups{lab}", rs[0]["groups"])
xs = [r for r in ag if r["fs"] == "xfs"]
num("AgXfsGroups", "/".join(sorted({r["groups"] for r in xs})))
num("AgXfsAllFreed", "yes" if all(r["groups_with_freed"] == r["groups"] for r in xs) else "no")
num("AgXfsRuns", str(len(xs)))

# ------------------------------------------------------------------ C4 released build (pre-specified, prereg/C4.md)
c4 = read_cells(os.path.join(RES, "c4", "c4_cells.csv"))
r4 = read_rows(os.path.join(RES, "c4", "c4_runs.csv"))
P4 = per_run(r4, read_rows(os.path.join(RES, "c4", "c4_classes.csv")))
num("RunsCFour", str(len(r4)))
num("RepsCFour", str(max(int(v[2]) for v in c4.values())))
num("UnmappedMaxCFour", pct(max(float(r["pre_unclassified"]) for r in r4), 2))
num("ToolErrCFour", str(sum(int(r["workload_log_bytes"]) > 0 for r in r4)))
C4_CONDS = (SC, TD, TF)
c4_rows = []
for fs in FS:
    for cond in C4_CONDS:
        for t in ("targz", "sqlite"):
            sa, sb = share(fs, cond, t), share(fs, cond, t, c4)
            da, db = dr(fs, cond, t), dr(fs, cond, t, d=c4)
            s1, d1 = vals(P1, fs, cond, t, 0), vals(P1, fs, cond, t, 1)
            inr = 0
            runs = P4.get((fs, cond[0], cond[1], t), {})
            for s, d, _ in runs.values():
                ok_d = math.isnan(d) or (d1 and min(d1) <= d <= max(d1))
                inr += bool(min(s1) <= s <= max(s1) and ok_d)
            c4_rows.append((cond, fs, t, sa, sb, da, db, abs(sa - sb) <= 0.05 and abs(da - db) <= 0.05, inr, len(runs)))
num("CellsCFour", str(len(c4_rows)))
num("AgreeCFour", str(sum(r[7] for r in c4_rows)))
num("RunsInRangeCFour", str(sum(r[8] for r in c4_rows)))
num("ShareDiffMaxCFour", f"{100 * max(abs(r[3] - r[4]) for r in c4_rows):.1f}")
num("DeltaDiffMaxCFour", f2(max(abs(r[5] - r[6]) for r in c4_rows)))
num("DisagreeListCFour", ", ".join(f"{FSN[r[1]]} {CONDN[r[0]]} {r[2]}" for r in c4_rows if not r[7]))
# post hoc: how far runs outside the C1 range lie from it
out_s, out_d = [0.0], [0.0]
for (cond, fs, t, *_rest) in c4_rows:
    s1, d1 = vals(P1, fs, cond, t, 0), vals(P1, fs, cond, t, 1)
    for s, d, _ in P4[(fs, cond[0], cond[1], t)].values():
        out_s.append(max(0.0, min(s1) - s, s - max(s1)))
        if not math.isnan(d):
            out_d.append(max(0.0, min(d1) - d, d - max(d1)))
num("ShareOutMaxCFour", f"{100 * max(out_s):.2f}")
num("DeltaOutMaxCFour", f"{max(out_d):.3f}")
# the two cells named in the text: per-run values of C1 and C4
x1 = runs_of(r1, "xfs", "T0", "SC", "targz"); x4 = runs_of(r4, "xfs", "T0", "SC", "targz")
num("XfsTargzCOneFull", str(sum(v == 1.0 for v in x1))); num("XfsTargzCOneN", str(len(x1)))
num("XfsTargzCOneMin", pct(min(x1))); num("XfsTargzCFourFull", str(sum(v == 1.0 for v in x4)))
ow1 = [int(r["overwrites"]) for r in r1 if (r["fs"], r["trim"], r["state"], r["tool"]) == ("btrfs", "TF", "SC", "targz")]
ow4 = [int(r["overwrites"]) for r in r4 if (r["fs"], r["trim"], r["state"], r["tool"]) == ("btrfs", "TF", "SC", "targz")]
num("BtrfsTFTargzOwCOneMin", str(min(ow1))); num("BtrfsTFTargzOwCOneMax", str(max(ow1)))
num("BtrfsTFTargzOwCFourMin", str(min(ow4))); num("BtrfsTFTargzOwCFourMax", str(max(ow4)))

# ------------------------------------------------------------------ C5 deleted-data fraction (pre-specified, prereg/C5.md)
c5 = read_cells(os.path.join(RES, "c5", "c5_cells.csv"))
r5 = read_rows(os.path.join(RES, "c5", "c5_runs.csv"))
SD = ("T0", "SD")
num("RunsCFive", str(len(r5)))
num("RepsCFive", str(max(int(v[2]) for v in c5.values())))
num("UnmappedMaxCFive", pct(max(float(r["pre_unclassified"]) for r in r5), 2))
num("ToolErrCFive", str(sum(int(r["workload_log_bytes"]) > 0 for r in r5)))
size_eff = {(r[1], r[2]) for r in size_rows if r[0] == SC and r[7]}
# (label, data A, cond A, runs A, data B, cond B, runs B): A is the left column of the table
C5_CMP = [("one", c5, SD, r5, c1, SC, r1), ("two", c5, SD, r5, c3, SC, r3), ("three", c3, SC, r3, c1, SB, r1)]
c5_rows = []
for lab, da_, ca, ra, db_, cb, rb in C5_CMP:
    for fs in FS:
        for t in ("targz", "rsync", "sqlite"):
            sa, sb = share(fs, ca, t, da_), share(fs, cb, t, db_)
            ea, eb = dr(fs, ca, t, d=da_), dr(fs, cb, t, d=db_)
            fa, fb = gshare(fs, ca, t, "freed", da_), gshare(fs, cb, t, "freed", db_)
            xa, xb = runs_of(ra, fs, *ca, t), runs_of(rb, fs, *cb, t)
            dis = abs(sa - sb) > 0.05 or abs(ea - eb) > 0.05
            c5_rows.append((lab, fs, t, sa, sb, ea, eb, fa, fb, min(xa), max(xa), min(xb), max(xb), dis))
for lab in ("one", "two", "three"):
    rows = [r for r in c5_rows if r[0] == lab]
    W = lab.capitalize()
    num(f"CmpCells{W}", str(len(rows)))
    num(f"CmpDiffer{W}", str(sum(r[13] for r in rows)))
    num(f"CmpDifferList{W}", ", ".join(f"{FSN[r[1]]} {r[2]}" for r in rows if r[13]) or "none")
    num(f"CmpShareDiffMax{W}", f"{100 * max(abs(r[3] - r[4]) for r in rows):.1f}")
    num(f"CmpDeltaDiffMax{W}", f2(max(abs(r[5] - r[6]) for r in rows)))
    num(f"CmpHigher{W}", str(sum(r[13] and r[3] > r[4] + 0.05 for r in rows)))
# the C3 size-effect cells (SC-T0) under comparison 1
se = [r for r in c5_rows if r[0] == "one" and (r[1], r[2]) in size_eff]
num("SizeEffCellsList", ", ".join(f"{FSN[r[1]]} {r[2]}" for r in se))
num("SizeEffAgreeOne", str(sum(not r[13] for r in se)))
num("SizeEffCellsN", str(len(se)))
for r in se:
    k = f"{r[1]}{r[2]}"
    num(f"Cfive{k}ShareSD", pct(r[3])); num(f"Cfive{k}ShareSC", pct(r[4]))
    num(f"Cfive{k}SDMin", pct(r[9])); num(f"Cfive{k}SDMax", pct(r[10]))
    num(f"Cfive{k}ShareCThree", pct(share(r[1], SC, r[2], c3)))
a, b = rng([gshare(fs, SD, t, "freed", c5) for fs in ("ext4", "xfs", "btrfs") for t in ("targz", "rsync")])
num("FreedCopySDMin", a); num("FreedCopySDMax", b)

# ------------------------------------------------------------------ C6 released build, main conditions (prereg/C6.md)
c6 = read_cells(os.path.join(RES, "c6", "c6_cells.csv"))
r6 = read_rows(os.path.join(RES, "c6", "c6_runs.csv"))
P6 = per_run(r6, read_rows(os.path.join(RES, "c6", "c6_classes.csv")))
num("RunsCSix", str(len(r6)))
num("RepsCSix", str(max(int(v[2]) for v in c6.values())))
num("UnmappedMaxCSix", pct(max(float(r["pre_unclassified"]) for r in r6), 2))
num("ToolErrCSix", str(sum(int(r["workload_log_bytes"]) > 0 and r["tool"] != "gzipf" for r in r6)))
c6_rows = []
for cond in (SC, TF):
    for fs in FS:
        for t in tools_of(fs):
            sa, sb = share(fs, cond, t), share(fs, cond, t, c6)
            da, db = dr(fs, cond, t), dr(fs, cond, t, d=c6)
            s1, d1 = vals(P1, fs, cond, t, 0), vals(P1, fs, cond, t, 1)
            inr = 0
            runs = P6.get((fs, cond[0], cond[1], t), {})
            for s_, d_, _ in runs.values():
                ok_d = math.isnan(d_) or (d1 and min(d1) <= d_ <= max(d1))
                inr += bool(min(s1) <= s_ <= max(s1) and ok_d)
            dd = 0.0 if (math.isnan(da) and math.isnan(db)) else abs(da - db)
            agree = abs(sa - sb) <= 0.05 and not (dd > 0.05)
            c6_rows.append((cond, fs, t, sa, sb, da, db, agree, inr, len(runs)))
num("CellsCSix", str(len(c6_rows)))
num("AgreeCSix", str(sum(r[7] for r in c6_rows)))
num("RunsInRangeCSix", str(sum(r[8] for r in c6_rows)))
num("ShareDiffMaxCSix", f"{100 * max(abs(r[3] - r[4]) for r in c6_rows):.1f}")
num("DisagreeListCSix", ", ".join(f"{FSN[r[1]]} {CONDN[r[0]]} {r[2]}" for r in c6_rows if not r[7]) or "none")
num("DisagreeCSix", str(sum(not r[7] for r in c6_rows)))
# the six runs that ran on guest kernel 6.8.0-149 (kept, not used), against their reruns
rk = read_rows(os.path.join(RES, "c6", "c6_kernel149_runs.csv"))
kd = []
for r in rk:
    a = int(r["overwrites"]) / int(r["writes"])
    b = [int(x["overwrites"]) / int(x["writes"]) for x in r6
         if all(x[k] == r[k] for k in ("fs", "trim", "state", "tool", "rep"))][0]
    kd.append(abs(a - b))
num("KernelRuns", str(len(rk)))
num("KernelShareDiffMax", f"{100 * max(kd):.1f}")
# main-campaign cells compared with the released build in C4 or C6 (a cell counts as agreeing only if every comparison agreed)
rel = defaultdict(list)
for r in c4_rows + c6_rows:
    rel[(r[0], r[1], r[2])].append(r[7])
num("RelCells", str(len(rel)))
num("RelAgreeAll", str(sum(all(v) for v in rel.values())))
num("RelDisagreeAny", str(sum(not all(v) for v in rel.values())))

# ------------------------------------------------------------------ C7 update workloads (prereg/C7.md)
r7 = read_rows(os.path.join(RES, "c7", "c7_runs.csv"))
p7 = read_rows(os.path.join(RES, "c7", "c7_pages.csv"))
prep7 = read_rows(os.path.join(RES, "c7", "c7_prep.csv"))
C7CONDS = [S0, SC, TF]
C7TOOLS = ["dbupd", "logapp"]
C7G = ["live", "freed", "metadata", "dead_log", "other"]
RK = ("fs", "trim", "state", "tool", "rep")
ow7 = {tuple(r[k] for k in RK): (int(r["overwrites"]), int(r["writes"])) for r in r7}
pg7 = defaultdict(dict)
for r in p7:
    pg7[tuple(r[k] for k in RK)][r["group"]] = r


def c7_runs(fs=None, tool=None, cond=None):
    return [k for k in pg7 if (fs is None or k[0] in fs) and (tool is None or k[3] == tool)
            and (cond is None or (k[1], k[2]) == cond)]


def c7_gshare(k, g):
    o = ow7[k][0]
    return int(pg7[k][g]["n"]) / o if o else 0.0


def c7_ratio(keys, g, col):
    kn = sum(int(pg7[k][g]["known"]) for k in keys)
    return sum(float(pg7[k][g][col]) for k in keys) / (kn * PAGE) if kn else float("nan")


def c7_gain(keys, g):
    return 100 * (c7_ratio(keys, g, "comp_or_raw_bytes") - c7_ratio(keys, g, "best_bytes"))


def rr(xs, scale=100, d=0):
    a, b = f"{scale * min(xs):.{d}f}", f"{scale * max(xs):.{d}f}"
    return a if a == b else f"{a}--{b}"


num("RunsCSeven", str(len(r7)))
num("RepsCSeven", str(max(int(r["rep"]) for r in r7)))
num("UnmappedMaxCSeven", pct(max(float(r["pre_unclassified"]) for r in r7), 2))
num("ToolErrCSeven", str(sum(int(r["workload_log_bytes"]) > 0 for r in r7)))
num("PrepRunsCSeven", str(sum(int(r["live_mib"]) > 0 for r in prep7)))
for t, nm in (("dbupd", "Db"), ("logapp", "Log")):
    num(f"LiveMiB{nm}CSeven", rr([int(r["live_mib"]) for r in prep7 if r["tool"] == t], 1))
EX = ("ext4", "xfs")
NB = ("ext4", "xfs", "f2fs")
num("ShareCSeven", rr([o / w for o, w in ow7.values()]))
num("ShareBtrfsTFDbCSeven", rr([o / w for k, (o, w) in ow7.items() if k[:4] == ("btrfs", "TF", "SC", "dbupd")]))
num("ShareFtwoTFLogCSeven", rr([o / w for k, (o, w) in ow7.items() if k[:4] == ("f2fs", "TF", "SC", "logapp")]))
num("LiveDbExtXfsCSeven", rr([c7_gshare(k, "live") for k in c7_runs(EX, "dbupd")]))
num("LiveLogExtXfsCSeven", rr([c7_gshare(k, "live") for k in c7_runs(EX, "logapp")]))
num("LiveDbFtwoCSeven", rr([c7_gshare(k, "live") for k in c7_runs(("f2fs",), "dbupd")]))
num("LiveLogFtwoCSeven", rr([c7_gshare(k, "live") for k in c7_runs(("f2fs",), "logapp")]))
num("LiveDbFtwoSZeroCSeven", rr([c7_gshare(k, "live") for k in c7_runs(("f2fs",), "dbupd", S0)]))
num("DeadDbFtwoSZeroCSeven", rr([c7_gshare(k, "dead_log") for k in c7_runs(("f2fs",), "dbupd", S0)]))
num("LiveBtrfsMaxCSeven", pct(max(c7_gshare(k, "live") for k in c7_runs(("btrfs",))), 1))
num("LiveBtrfsNMaxCSeven", str(max(int(pg7[k]["live"]["n"]) for k in c7_runs(("btrfs",)))))
num("MetaBtrfsCSeven", rr([c7_gshare(k, "metadata") for k in c7_runs(("btrfs",))]))
num("MetaLogExtXfsCSeven", rr([c7_gshare(k, "metadata") for k in c7_runs(EX, "logapp")]))
num("OtherDbExtXfsSZeroCSeven", rr([c7_gshare(k, "other") for k in c7_runs(EX, "dbupd", S0)]))
num("FreedDbExtSCCSeven", rr([c7_gshare(k, "freed") for k in c7_runs(("ext4",), "dbupd") if k[2] == "SC"]))
num("FreedDbXfsSCCSeven", rr([c7_gshare(k, "freed") for k in c7_runs(("xfs",), "dbupd") if k[2] == "SC"]))
nbk = [[k] for k in c7_runs(NB) if int(pg7[k]["live"]["known"])]
num("LiveRunsCSeven", str(len(nbk)))
num("LiveDeltaCSeven", rr([c7_ratio(k, "live", "delta_bytes") for k in nbk], 1, 2))
num("LiveComprCSeven", rr([c7_ratio(k, "live", "comp_or_raw_bytes") for k in nbk], 1, 2))
num("LiveGainCSeven", rr([c7_gain(k, "live") for k in nbk], 1))
num("DbRestDeltaExtXfsCSeven", rr([c7_ratio([k], g, "delta_bytes") for k in c7_runs(EX, "dbupd")
                                   for g in ("freed", "other") if int(pg7[k][g]["known"]) > 1000], 1, 2))

# ------------------------------------------------------------------ numbers.tex
with open(os.path.join(GEN, "numbers.tex"), "w", encoding="utf-8") as fp:
    fp.write("% generated by exp/make_paper.py; do not edit\n")
    for k in sorted(N):
        fp.write(f"\\newcommand{{\\{macro_name(k)}}}{{{N[k]}}}\n")


# ------------------------------------------------------------------ tables
def ci_cell(m, c, scale=100, d=0):
    if math.isnan(m):
        return "--"
    if math.isnan(c):
        return f"{scale * m:.{d}f}"
    return f"{scale * m:.{d}f}\\,$\\pm$\\,{scale * c:.{d}f}"


def write(name, text):
    open(os.path.join(GEN, name), "w", encoding="utf-8").write("% generated by exp/make_paper.py\n" + text)


# overwrite share, all cells
lines = ["\\begin{tabular}{ll" + "r" * len(CONDS) + "}", "\\toprule",
         "File system & Tool & " + " & ".join(CONDN[c] for c in CONDS) + " \\\\", "\\midrule"]
for fs in FS:
    for i, t in enumerate(tools_of(fs)):
        row = [FSN[fs] if i == 0 else "", t]
        for c in CONDS:
            m, h, _ = get(c1, fs, c, t, "overwrite_share")
            row.append(ci_cell(m, h))
        lines.append(" & ".join(row) + " \\\\")
    lines.append("\\midrule" if fs != FS[-1] else "\\bottomrule")
lines.append("\\end{tabular}")
write("tab_share.tex", "\n".join(lines) + "\n")

# overwrite share, per-run minimum and maximum
lines = ["\\begin{tabular}{ll" + "r" * len(CONDS) + "}", "\\toprule",
         "File system & Tool & " + " & ".join(CONDN[c] for c in CONDS) + " \\\\", "\\midrule"]
for fs in FS:
    for i, t in enumerate(tools_of(fs)):
        row = [FSN[fs] if i == 0 else "", t]
        for c in CONDS:
            x = runs_of(r1, fs, c[0], c[1], t)
            row.append(f"{pct(min(x))}--{pct(max(x))}" if x else "--")
        lines.append(" & ".join(row) + " \\\\")
    lines.append("\\midrule" if fs != FS[-1] else "\\bottomrule")
lines.append("\\end{tabular}")
write("tab_share_range.tex", "\n".join(lines) + "\n")

# delta, compression and best ratio, all cells
lines = ["\\begin{tabular}{ll" + "c" * len(CONDS) + "}", "\\toprule",
         "File system & Tool & " + " & ".join(CONDN[c] for c in CONDS) + " \\\\", "\\midrule"]
for fs in FS:
    for i, t in enumerate(tools_of(fs)):
        row = [FSN[fs] if i == 0 else "", t]
        for c in CONDS:
            d_, cmp_ = dr(fs, c, t), dr(fs, c, t, "measured_compress_ratio")
            row.append("--" if math.isnan(d_) else (f"\\textbf{{{d_:.2f}}}/{cmp_:.2f}" if d_ > cmp_ else f"{d_:.2f}/{cmp_:.2f}"))
        lines.append(" & ".join(row) + " \\\\")
    lines.append("\\midrule" if fs != FS[-1] else "\\bottomrule")
lines.append("\\end{tabular}")
write("tab_ratio.tex", "\n".join(lines) + "\n")

# pooled per class group
lines = ["\\begin{tabular}{llrrrrrrr}", "\\toprule",
         "File system & Class & Overwrites & Delta ratio & Run mean & Compr.\\ ratio & Gain (\\%) & $>$90\\,\\% changed & $\\le$10\\,\\% changed \\\\",
         "\\midrule"]
for fs in FS:
    first = True
    for g in GROUPS:
        a = pool_all.get((fs, g))
        if not a or a[1] == 0:
            continue
        rm = [float(r["delta_bytes"]) / (int(r["known"]) * PAGE) for r in k1
              if r["fs"] == fs and r["group"] == g and int(r["known"]) > 0]
        lines.append(" & ".join([FSN[fs] if first else "", GROUPN[g], f"{a[1]:,}", f2(a[4] / (a[1] * PAGE)),
                                 f2(float(np.mean(rm))), f2(a[5] / (a[1] * PAGE)),
                                 pct((gain[(fs, g)][1] - gain[(fs, g)][2]) / (gain[(fs, g)][0] * PAGE), 1), pct(a[2] / a[1]), pct(a[3] / a[1])]) + " \\\\")
        first = False
    lines.append("\\midrule" if fs != FS[-1] else "\\bottomrule")
lines.append("\\end{tabular}")
write("tab_class.tex", "\n".join(lines) + "\n")

# part C: written in the post-hoc section, with the Welch difference

# part B
lines = ["\\begin{tabular}{llrrrrrrr}", "\\toprule",
         "File system & Tool & \\multicolumn{2}{c}{Overwrite share (\\%)} & \\multicolumn{2}{c}{Delta ratio} & \\multicolumn{3}{c}{SG-T0: share of overwrites (\\%)} \\\\",
         " & & SC-T0 & SG-T0 & SC-T0 & SG-T0 & churned & metadata & other classes \\\\", "\\midrule"]
for fs in FS:
    for i, t in enumerate(("targz", "rsync", "sqlite")):
        m, h, _ = get(ch, fs, SG, t, "overwrite_share")
        fr = gshare(fs, SG, t, "freed", ch); me = gshare(fs, SG, t, "metadata", ch)
        lines.append(" & ".join([FSN[fs] if i == 0 else "", t, ci_cell(share(fs, SC, t), get(c1, fs, SC, t, "overwrite_share")[1]),
                                 ci_cell(m, h), f2(dr(fs, SC, t)), f2(dr(fs, SG, t, d=ch)), pct(fr), pct(me),
                                 pct(max(0.0, 1 - fr - me))]) + " \\\\")
    lines.append("\\midrule" if fs != FS[-1] else "\\bottomrule")
lines.append("\\end{tabular}")
write("tab_partb.tex", "\n".join(lines) + "\n")

# C3 device size
lines = ["\\begin{tabular}{lllrrrrl}", "\\toprule",
         "Condition & File system & Tool & \\multicolumn{2}{c}{Overwrite share (\\%)} & \\multicolumn{2}{c}{Delta ratio} & \\\\",
         " & & & 7168\\,MiB & 14336\\,MiB & 7168\\,MiB & 14336\\,MiB & \\\\", "\\midrule"]
for cond, fs, t, sa, sb, da, db, eff in sorted(size_rows, key=lambda r: (CONDS.index(r[0]), FS.index(r[1]))):
    lines.append(" & ".join([CONDN[cond], FSN[fs], t, pct(sa, 1), pct(sb, 1), f2(da), f2(db),
                             "size effect" if eff else ""]) + " \\\\")
lines += ["\\bottomrule", "\\end{tabular}"]
write("tab_size.tex", "\n".join(lines) + "\n")

# C4 released build against C1
lines = ["\\begin{tabular}{lllrrrrcl}", "\\toprule",
         "Condition & File system & Tool & \\multicolumn{2}{c}{Overwrite share (\\%)} & \\multicolumn{2}{c}{Delta ratio} & Runs in & \\\\",
         " & & & main & released & main & released & main range & \\\\", "\\midrule"]
for cond, fs, t, sa, sb, da, db, agree, inr, n in sorted(c4_rows, key=lambda r: (CONDS.index(r[0]), FS.index(r[1]))):
    lines.append(" & ".join([CONDN[cond], FSN[fs], t, pct(sa, 1), pct(sb, 1), f2(da), f2(db), f"{inr}/{n}",
                             "" if agree else "disagrees"]) + " \\\\")
lines += ["\\bottomrule", "\\end{tabular}"]
write("tab_c4.tex", "\n".join(lines) + "\n")

# C5 three comparisons
CMPN = {"one": "1", "two": "2", "three": "3"}
lines = ["\\begin{tabular}{lllrrrrrrccl}", "\\toprule",
         "Comparison & File system & Tool & \\multicolumn{2}{c}{Overwrite share (\\%)} & \\multicolumn{2}{c}{Delta ratio}"
         " & \\multicolumn{2}{c}{Freed (\\%)} & \\multicolumn{2}{c}{Run range (\\%)} & \\\\",
         " & & & A & B & A & B & A & B & A & B & \\\\", "\\midrule"]
prev = None
for lab, fs, t, sa, sb, ea, eb, fa, fb, a0, a1, b0, b1, dis in c5_rows:
    if prev and prev != lab:
        lines.append("\\midrule")
    prev = lab
    lines.append(" & ".join([CMPN[lab], FSN[fs], t, pct(sa, 1), pct(sb, 1), f2(ea), f2(eb), pct(fa), pct(fb),
                             f"{pct(a0)}--{pct(a1)}", f"{pct(b0)}--{pct(b1)}", "differs" if dis else ""]) + " \\\\")
lines += ["\\bottomrule", "\\end{tabular}"]
write("tab_c5.tex", "\n".join(lines) + "\n")



# C6 released build on SC-T0 and SC-TF, all tools, against C1
lines = ["\\begin{tabular}{lllrrrrcl}", "\\toprule",
         "Condition & File system & Tool & \\multicolumn{2}{c}{Overwrite share (\\%)} & \\multicolumn{2}{c}{Delta ratio} & Runs in & \\\\",
         " & & & main & released & main & released & main range & \\\\", "\\midrule"]
for cond, fs, t, sa, sb, da, db, agree, inr, n in c6_rows:
    lines.append(" & ".join([CONDN[cond], FSN[fs], t, pct(sa, 1), pct(sb, 1), f2(da), f2(db), f"{inr}/{n}",
                             "" if agree else "disagrees"]) + " \\\\")
lines += ["\\bottomrule", "\\end{tabular}"]
write("tab_c6.tex", "\n".join(lines) + "\n")


# C7 update workloads: every overwrite by the class of its page before the tool (exp7/c7_pages.py)
lines = ["\\begin{tabular}{lllrrrrrrrrr}", "\\toprule",
         "Condition & File system & Tool & Overwrite & \\multicolumn{5}{c}{Share of overwrites (\\%), page before the tool} & \\multicolumn{3}{c}{Live pages} \\\\",
         " & & & share (\\%) & live & freed & metadata & dead log & none & delta & compr. & gain (\\%) \\\\", "\\midrule"]
for cond in C7CONDS:
    for fs in FS:
        for t in C7TOOLS:
            ks = c7_runs((fs,), t, cond)
            o = sum(ow7[k][0] for k in ks); w = sum(ow7[k][1] for k in ks)
            sh = [pct(sum(int(pg7[k][g]["n"]) for k in ks) / o, 0) for g in C7G]
            if fs != "f2fs":
                sh[3] = "--"
            d = c7_ratio(ks, "live", "delta_bytes")
            row = [CONDN[cond], FSN[fs], t, pct(o / w, 0)] + sh
            if sum(int(pg7[k]["live"]["known"]) for k in ks) >= 100:
                row += [f2(d), f2(c7_ratio(ks, "live", "comp_or_raw_bytes")), f"{c7_gain(ks, 'live'):.0f}"]
            else:
                row += ["--", "--", "--"]
            lines.append(" & ".join(row) + " \\\\")
lines += ["\\bottomrule", "\\end{tabular}"]
write("tab_c7.tex", "\n".join(lines) + "\n")

# ------------------------------------------------------------------ figures
def style(ax):
    ax.grid(axis="y", color=GRID, linewidth=0.5)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


# Fig. 1: overwrite share by condition, one panel per file system
fig, axes = plt.subplots(1, 4, figsize=(7.0, 2.3), sharey=True)
for ax, fs in zip(axes, FS):
    for t in tools_of(fs):
        i = TOOLS.index(t)
        m = [get(c1, fs, c, t, "overwrite_share") for c in CONDS]
        x = np.arange(len(CONDS)) + (i - 3) * 0.06
        rr = [runs_of(r1, fs, c[0], c[1], t) for c in CONDS]      # per-run minimum and maximum
        ax.errorbar(x, [100 * v[0] for v in m],
                    yerr=[[100 * (v[0] - min(q)) for v, q in zip(m, rr)], [100 * (max(q) - v[0]) for v, q in zip(m, rr)]],
                    color=COL[i], marker="o", markersize=3.2, linewidth=1.2, capsize=1.5, elinewidth=0.7, label=t)
    ax.set_xticks(range(len(CONDS)))
    ax.set_xticklabels([CONDN[c] for c in CONDS], rotation=45, ha="right")
    ax.set_title(FSN[fs], fontsize=8.5, color=INK)
    ax.set_ylim(-3, 103)
    style(ax)
axes[0].set_ylabel("Overwrite share of tool writes (%)")
h, l = [], []
for ax in axes:
    for hh, ll in zip(*ax.get_legend_handles_labels()):
        if ll not in l:
            h.append(hh); l.append(ll)
order = [l.index(t) for t in TOOLS if t in l]
fig.legend([h[i] for i in order], [l[i] for i in order], loc="upper center", ncol=7, frameon=False,
           bbox_to_anchor=(0.5, 1.06))
fig.tight_layout(rect=(0, 0, 1, 0.93))
fig.savefig(os.path.join(FIG, "fig_share.pdf"), bbox_inches="tight")
plt.close(fig)

# Fig. 2: what overwrites replace, SC-T0 and SC-TF
fig, axes = plt.subplots(1, 2, figsize=(7.0, 4.2), sharey=True)
rows = [(fs, t) for fs in FS for t in tools_of(fs)]
for ax, cond in zip(axes, (SC, TF)):
    left = np.zeros(len(rows))
    y = np.arange(len(rows))[::-1]
    for g in ["freed", "source", "metadata", "dead_log", "repeat", "other"]:
        v = np.array([gshare(fs, cond, t, g) for fs, t in rows])
        v = np.nan_to_num(v)
        ax.barh(y, 100 * v, left=100 * left, color=GCOL[g], height=0.78, edgecolor="white", linewidth=0.6,
                label=GROUPN[g])
        left += v
    sh = [share(fs, cond, t) for fs, t in rows]
    for yy, s in zip(y, sh):
        ax.text(101.5, yy, pct(s), va="center", fontsize=6.3, color=INK2)
    ax.set_xlim(0, 100)
    ax.set_title(f"{CONDN[cond]} (right: overwrite share, %)", fontsize=8.5, color=INK)
    ax.set_xlabel("Share of overwrites (%)")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
axes[0].set_yticks(np.arange(len(rows))[::-1])
axes[0].set_yticklabels([f"{FSN[fs]} {t}" for fs, t in rows], fontsize=7)
h, l = axes[0].get_legend_handles_labels()
fig.legend(h, l, loc="upper center", ncol=6, frameon=False, bbox_to_anchor=(0.5, 1.03))
fig.tight_layout(rect=(0, 0, 1, 0.95), w_pad=3.5)
fig.savefig(os.path.join(FIG, "fig_class.pdf"), bbox_inches="tight")
plt.close(fig)

# Fig. 3: per run and class, delta ratio minus compression ratio of the new pages (runs with >= 100 known overwrites)
FIG3_GROUPS = ["freed", "source", "metadata", "dead_log", "repeat"]
fig, ax = plt.subplots(figsize=(5.6, 2.6))
rng_j = np.random.default_rng(1)
for gi, g in enumerate(FIG3_GROUPS):
    for fi, fs in enumerate(FS):
        ys = [(float(r["delta_bytes"]) - float(r["new_bytes"])) / (int(r["known"]) * PAGE) for r in k1
              if r["fs"] == fs and r["group"] == g and int(r["known"]) >= 100]
        if not ys:
            continue
        xs = gi + (fi - 1.5) * 0.18 + rng_j.uniform(-0.06, 0.06, len(ys))
        ax.scatter(xs, ys, s=6, color=COL[fi], edgecolor="none", alpha=0.8, label=FSN[fs] if gi == 0 else None,
                   zorder=3)
ax.axhline(0, color=INK2, linewidth=0.7, linestyle="--", zorder=1)
ax.set_xticks(range(len(FIG3_GROUPS)))
ax.set_xticklabels([GROUPN[g] for g in FIG3_GROUPS])
ax.set_ylabel("Delta ratio $-$ compression ratio")
ax.yaxis.grid(True, color=GRID, linewidth=0.6)
ax.set_axisbelow(True)
for sp in ("top", "right"):
    ax.spines[sp].set_visible(False)
ax.legend(frameon=False, fontsize=6.5, loc="upper center", ncol=4, bbox_to_anchor=(0.5, 1.13), markerscale=2)
fig.tight_layout()
fig.savefig(os.path.join(FIG, "fig_ratio.pdf"), bbox_inches="tight")
plt.close(fig)
print(len(N), "macros; tables and figures written")

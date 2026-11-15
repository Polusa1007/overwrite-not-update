"""Where do TRIM records fall relative to the tool mark in block-layer traces, and do tool-phase overwrites hit pages
that a later TRIM record covers? Reads ~/c2_formal/logw traces (record format of logw_to_trace.py)."""
import glob, gzip, os, sys
import numpy as np
REC = np.dtype([("t", "<u8"), ("lpn", "<u4"), ("ent", "<u2"), ("diff", "<u2"), ("clz", "<u4"), ("op", "u1"), ("over", "u1"), ("pad", "<u2")])
pats = sys.argv[1:] or ["f2fs/TF_SC_W60/*", "xfs/TF_SC_W60/*", "ext4/TF_SC_W60/*", "btrfs/TF_SC_W60/*", "ext4/T0_SC_W60/targz_*"]
for pat in pats:
    for d in sorted(glob.glob(os.path.expanduser("~/c2_formal/logw/" + pat))):
        r = np.frombuffer(gzip.open(d + "/trace.bin.gz").read(), dtype=REC)
        mi = np.where(r["op"] == 9)[0][0]
        tool = r[mi + 1:]
        tr = np.where(tool["op"] == 2)[0]
        wr = np.where(tool["op"] == 1)[0]
        ov = tool[(tool["op"] == 1) & (tool["over"] == 1)]
        # pages trimmed after the mark
        late = set(tool["lpn"][tr].tolist())
        ov_late = int(np.isin(ov["lpn"], np.fromiter(late, dtype=np.uint32, count=len(late))).sum()) if late else 0
        first_tr = int(tr[0]) if len(tr) else -1
        last_tr = int(tr[-1]) if len(tr) else -1
        print("%-34s tool recs %8d writes %7d trims %7d (first at %7d, last at %7d) overwrites %7d of which on late-trimmed pages %7d" % (
            d.split("logw/")[1], len(tool), len(wr), len(tr), first_tr, last_tr, len(ov), ov_late))

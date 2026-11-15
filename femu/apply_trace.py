#!/usr/bin/env python3
"""Paper C: add the trace mode (ftl-trace.c, ftl-trace.h) to a clean FEMU tree at commit 2d50161f.

    python3 apply_trace.py <FEMU source root>

Copies ftl-trace.c and ftl-trace.h from this directory into hw/femu/bbssd/ and inserts one call at each point where
the FTL reads, writes or trims a page, plus the I/O-path copies of old bytes. Each insertion must match exactly once.
The FTL's mapping, garbage collection and timing are not changed."""
import os
import shutil
import sys

root = sys.argv[1]
here = os.path.dirname(os.path.abspath(__file__))
bb = os.path.join(root, "hw", "femu", "bbssd")
if os.path.exists(os.path.join(bb, "ftl-trace.c")):
    sys.exit("already applied")


def sub(rel, a, b):
    p = os.path.join(root, rel)
    s = open(p, encoding="utf-8").read()
    assert s.count(a) == 1, (rel, a)
    open(p, "w", encoding="utf-8").write(s.replace(a, b))


for f in ("ftl-trace.c", "ftl-trace.h"):
    shutil.copyfile(os.path.join(here, f), os.path.join(bb, f))

sub("hw/femu/meson.build", "'bbssd/ftl-exp.c',", "'bbssd/ftl-exp.c', 'bbssd/ftl-trace.c',")
sub("hw/femu/bbssd/ftl.h", "    uint64_t *rmap;     /* reverse mapptbl, assume it's stored in OOB */\n",
    "    uint64_t *rmap;     /* reverse mapptbl, assume it's stored in OOB */\n"
    "    struct ftl_trace *ftrace; /* paper C trace mode (ftl-trace.c); NULL when off */\n")
sub("hw/femu/bbssd/ftl-internal.h", "#endif /* __FEMU_BBSSD_FTL_INTERNAL_H */",
    "#include \"ftl-trace.h\"\n\n#endif /* __FEMU_BBSSD_FTL_INTERNAL_H */")
# init, per-request tick (control file), free
sub("hw/femu/bbssd/ftl.c", "        ssd_init_write_pointer(ssd);\n    }\n}\n",
    "        ssd_init_write_pointer(ssd);\n    }\n    ftl_trace_init(ssd);\n}\n")
sub("hw/femu/bbssd/ftl.c", "    ssd->pace_gen++;\n", "    ssd->pace_gen++;\n    ftl_trace_tick(ssd);\n")
sub("hw/femu/bbssd/ftl.c", "    ssd_free_write_buffer(ssd);\n", "    ssd_free_write_buffer(ssd);\n    ftl_trace_free(ssd);\n")
# reads
sub("hw/femu/bbssd/ftl-datapath.c", "    for (lpn = start_lpn; lpn <= end_lpn; lpn++) {\n        /*\n         * A page the write buffer",
    "    for (lpn = start_lpn; lpn <= end_lpn; lpn++) {\n        ftl_trace_read(ssd, lpn);\n        /*\n"
    "         * A page the write buffer")
# TRIMs: of a page that is not mapped, and of a mapped page (before FEMU invalidates it)
sub("hw/femu/bbssd/ftl-datapath.c",
    "        if (!mapped_ppa(&ppa) || !valid_ppa(ssd, &ppa)) {\n            (*already_invalid)++;",
    "        if (!mapped_ppa(&ppa) || !valid_ppa(ssd, &ppa)) {\n            ftl_trace_trim_unmapped(ssd, lpn);\n"
    "            (*already_invalid)++;")
sub("hw/femu/bbssd/ftl-datapath.c",
    "        } else {\n            mark_page_invalid(ssd, &ppa);\n            set_rmap_ent(ssd, INVALID_LPN, &ppa);",
    "        } else {\n            ftl_trace_trim(ssd, lpn);\n            mark_page_invalid(ssd, &ppa);\n"
    "            set_rmap_ent(ssd, INVALID_LPN, &ppa);")
# writes: before the old page is invalidated
sub("hw/femu/bbssd/ftl-map.c", "    struct ppa old = get_maptbl_ent(ssd, lpn);\n\n    if (mapped_ppa(&old)) {",
    "    struct ppa old = get_maptbl_ent(ssd, lpn);\n\n    ftl_trace_write(ssd, lpn, mapped_ppa(&old));\n"
    "    if (mapped_ppa(&old)) {")
# I/O path: old bytes before the payload (write) or the zeroing (TRIM) replaces them
sub("hw/femu/nvme-io.c", '#include "kvssd/kvssd.h"\n', '#include "kvssd/kvssd.h"\n#include "bbssd/ftl-trace.h"\n')
sub("hw/femu/nvme-io.c", "    ret = backend_rw(n->mbe, &req->qsg, &data_offset, req->is_write);\n",
    "    if (req->is_write && ns->ssd) {\n        ftl_trace_preimage(ns->ssd, data_offset, data_size, false);\n    }\n"
    "    ret = backend_rw(n->mbe, &req->qsg, &data_offset, req->is_write);\n")
sub("hw/femu/nvme-util.c", '#include "./nvme.h"\n', '#include "./nvme.h"\n#include "bbssd/ftl-trace.h"\n')
sub("hw/femu/nvme-util.c", "        backend_lock_range(n->mbe, off, len);\n        memset(",
    "        backend_lock_range(n->mbe, off, len);\n        if (ns->ssd) {\n"
    "            ftl_trace_preimage(ns->ssd, off, len, true);\n        }\n        memset(")
print("applied")

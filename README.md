# When an Overwrite Is Not an Update: artifact

Scripts, specifications and per-run results for the article "When an Overwrite Is Not an Update: Characterizing
File-System History and Content Locality in SSD Workloads". Every number, table and figure in the article is generated from the files in
`results/` by `exp/make_paper.py`.

In file headers and specifications, "Paper C" refers to this article, `paper_c/` to the root of this package, and C1
to C7 to its campaigns (C1 main, C2 churned state and block layer, C3 device size, C4 released build, C5 deleted-data
fraction, C6 released build on the main conditions, C7 update workloads).

## License

Copyright (c) 2026 Jia-You Sie and Ching-Cheng Huang.

This package, including the specifications and the result files, is free software: you can redistribute it and/or
modify it under the terms of the GNU General Public License, version 2, as published by the Free Software Foundation
(see `LICENSE`). It is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the
implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. The trace mode in `femu/` is a patch to FEMU,
which is itself licensed under the GPL, version 2.

## Contents

| Path | What it is |
|---|---|
| `prereg/C1.md` to `C7.md` | Specifications of the main, churned/block-layer, device-size, released-build, deleted-data-fraction, released-build-on-main-conditions and update-workload campaigns, each frozen before its formal runs |
| `prereg/MANIFEST` | SHA-256 hashes of the specifications and scripts at each freeze, with dated notes on later changes |
| `femu/` | The trace mode (`ftl-trace.c`, `ftl-trace.h`) and `apply_trace.py`, which adds it to stock FEMU |
| `exp/` | Main campaign (C1): guest-side run script, block map, run list, batch runner, analysis, paper generator; post hoc: `identical_pages.py` (byte-identical rewrites), `net_gain.py` (gain of storing deltas beyond compression), `alloc_groups.py` (writes by allocation group) |
| `exp2/` | Churned state and block-layer check (C2): aging, dm-log-writes conversion, run lists, TRIM-order check |
| `exp3/` | Device-size campaign (C3): run list and batch runner |
| `exp4/` | Released-build campaign (C4): run list and launcher |
| `exp5/` | Deleted-data-fraction campaign (C5): guest-side run script with four deleted copies (state SD), its generator, batch runner, run list and launcher |
| `exp6/` | Released build on SC-T0 and SC-TF (C6): run list and launcher |
| `exp7/` | Update workloads (C7): the two workloads (`c7_wl.py`), guest-side run script and block map with the `live` class, their generator, batch runner, run lists, launcher, and `c7_pages.py` (every overwrite by the class of its page before the tool) |
| `results/c1` to `c7` | Per-run (`*_runs.csv`), per-run-and-class (`*_classes.csv`) and per-cell (`*_cells.csv`) results; `results/c6/c6_kernel149_*` are the six C6 runs on the upgraded guest kernel, kept aside (see `prereg/MANIFEST`); `results/c7/c7_pages.csv` and `c7_prep.csv` are the C7 second measure and the size of the prepared data |
| `results/posthoc` | Post hoc per-run counts of byte-identical rewrites (`exp/identical_pages.py`, run on the traces of C1, C3 and C4), gain of deltas per run and class (`exp/net_gain.py`, C1) and writes by allocation group (`exp/alloc_groups.py`, C1, C3 and C5) |
| `install_f2fs_guest.sh` | Installs the F2FS tools in the guest image |
| `REDACTED.md` | Four local launcher scripts whose user name, key file and path were replaced by variables |
| `verify_hashes.sh` | Checks the files against `prereg/MANIFEST` |
| `LICENSE` | GNU General Public License, version 2 |

The raw traces of all campaigns (about 29 GB) are not in this repository. They are archived, together with this
package, at https://doi.org/10.5281/zenodo.24247377 (layout described in `README_traces.md` there), and they can
also be regenerated with the scripts below.

## Reproducing the numbers from the results

Requires Python 3 with numpy, scipy and matplotlib.

```
python3 -I exp/make_paper.py
```

This writes `manuscript/generated/numbers.tex` (every number cited in the text, as LaTeX macros),
`manuscript/generated/tab_*.tex` and `manuscript/figures/fig_*.pdf`. Analyses marked post hoc in the article are in the
section of `make_paper.py` headed "post hoc (not pre-specified)".

## Reproducing the results from traces

`exp/analyze_c.py <trace root> <output prefix> [processes]` turns a directory of traces into the three CSV files of
`results/`. It expects `<root>/<fs>/<TRIM>_<state>_W60/<tool>_<rep>/trace.bin.gz` and the block map written next to
each trace.

## Running the campaigns

The campaigns ran FEMU on a Linux cloud VM with nested virtualization (31 GiB RAM), one Ubuntu guest image for all runs
and guest kernel 6.8.0. Each run boots a fresh emulator, creates the file system, prepares the condition, runs one
tool and writes a trace.

1. Build the released FEMU build described under "Emulator".
2. Prepare the guest image with `/usr` as the source tree and the F2FS tools (`install_f2fs_guest.sh`).
3. Generate the run lists (`exp/run_list.py`, `exp2/c2_run_list.py`, `exp3/c3_run_list.py`, `exp4/c4_run_list.py`;
   seeds are in the specifications) or use the frozen lists `exp/runs.txt`, `exp2/c2_runs.txt`, `exp3/c3_runs.txt`,
   `exp4/c4_runs.txt`, `exp5/c5_runs.txt`, `exp6/c6_runs.txt`, `exp7/c7_runs.txt`.
4. On the VM, run `exp/c1_batch.sh`, `exp2/c2_batch.sh` or `exp3/c3_batch.sh` with an output directory, an instance
   number and a run list. The local launchers (`exp/c1_run.sh`, `exp2/c2_run.sh`, `exp3/c3_run.sh`) show the exact
   calls; set `VM_USER`, `SSH_KEY` and `PAPER_C` before using them. C4 uses `exp3/c3_batch.sh` with its own list;
   `exp4/c4_run.sh` shows the calls. C5 uses `exp5/c5_batch.sh`, which calls `exp5/femu_fs_c5.sh`; `exp5/c5_run.sh`
   shows the calls. C6 uses `exp3/c3_batch.sh` with its own list (`exp6/c6_run.sh`). C7 uses `exp7/c7_batch.sh`,
   which calls `exp7/femu_fs_c7.sh`; `exp7/c7_run.sh` shows the calls. Analyse C7 also with
   `exp7/c7_pages.py <trace root> <out csv> [processes]`.
5. Analyse with `exp/analyze_c.py` and regenerate the article's numbers with `exp/make_paper.py`.

The device-size campaign changes `blks_per_pl` to 2048 and `ssd_size` to 14336 in FEMU's `run-blackbox.sh`
(see `exp3/c3_run.sh`); C5 uses the same geometry with the released build (`exp5/c5_run.sh`).

## Emulator

Released build: FEMU (https://github.com/vtess/FEMU) at commit 2d50161f24c4cb86d58185b0efd44457412eadce, plus the
trace mode:

```
git clone https://github.com/vtess/FEMU && cd FEMU && git checkout 2d50161f24c4cb86d58185b0efd44457412eadce
python3 <artifact>/femu/apply_trace.py .
mkdir build-femu && cd build-femu && cp ../femu-scripts/femu-copy-scripts.sh . && ./femu-copy-scripts.sh .
./femu-compile.sh    # after installing FEMU's dependencies (pkgdep.sh)
```

`apply_trace.py` copies the two trace files into `hw/femu/bbssd/` and inserts one call at each point where the FTL
reads, writes or trims a page, plus the I/O-path copies of old bytes. The FTL's mapping, garbage collection and
timing are not changed. The trace mode is switched on with `FEMU_RFTL=trace`; the trace file and control file are
named by `FEMU_RFTL_TRACE` and `FEMU_RFTL_CTL`. These names are kept from the build used for C1 to C3 so that the
frozen run scripts work unchanged. RFTL is the name of an FTL from the authors' other, unpublished work; the variable
names `FEMU_RFTL*` and the comments in the frozen scripts that mention RFTL (for example "RFTL TRIM windows") are kept
from that code, because changing them would change the hashes in `prereg/MANIFEST`. All campaigns of this article ran
in the trace mode: the released build contains no RFTL code (only these names, and the
`[RFTL]` tag of its log lines), and the build used for C1 to C3 kept no page in this mode (see below). The record fields `ent` and the low half of `clz` are written as 0; `analyze_c.py`
reads neither.

Campaigns C1 to C3 ran on a FEMU build at the same commit whose FTL also contains a page-retention extension from
other, unpublished work. That build is not released. In the trace mode it keeps no page (every run reports
`retained_now = 0`, a column of `*_runs.csv`), and writes and TRIMs update the mapping as in stock FEMU. The two
scripts that patched it (`femu/patch_trace_only.py`, `femu/patch_delta.py`, hashed in `prereg/MANIFEST`) are not
released either; `verify_hashes.sh` reports them as NOT RELEASED. C4 (`prereg/C4.md`) runs the released build on 24
C1 conditions; the article reports the comparison (Section "Released build" and its table), including the
conditions where it does not agree.

## Changes after a freeze

`prereg/MANIFEST` lists them with dates. One concerns this package: `exp3/c3_run.sh` was changed during the C3
campaign, in its local waiting loop only; the VM-side scripts and the measurement were unchanged. `verify_hashes.sh`
reports it and the redacted launchers as expected differences. During C4 and in the first C5 launch the VM was powered off part-way through by the power-off timer that the launcher
starts in smoke mode, which the formal launch did not stop. `exp5/c5_run.sh` was changed after the C5 freeze to stop
it (launcher only; `verify_hashes.sh` reports it as expected). The runs in progress had produced no trace and were run
again; completed runs were kept (see the dated notes in `prereg/MANIFEST`). During C6, the guest's automatic upgrades
installed a newer kernel in one emulator instance; the six runs affected were kept aside and rerun on the original
kernel with automatic upgrades switched off, which they also were for all of C7 (see the C6 note in `prereg/MANIFEST`).

`prereg/C6.md`, `prereg/C7.md` and their notes in `prereg/MANIFEST` say that these campaigns followed a reviewer's
request. That reviewer was a person outside the author team who read a draft informally before submission, not a
journal's peer reviewer; the files are left unchanged because they are hash-locked.

#!/bin/sh
# Check the files of this package against prereg/MANIFEST. Run from the package root.
# Expected differences: exp3/c3_run.sh (changed after the C3 freeze, see MANIFEST), the launchers in REDACTED.md, and
# the two patches of the C1-C3 build, which are not released (README, "Emulator").
grep -v '^#' prereg/MANIFEST | while read -r h f; do
    f=${f#\*}
    [ -n "$f" ] || continue
    if [ ! -f "$f" ]; then
        case $f in
            femu/patch_trace_only.py|femu/patch_delta.py) echo "NOT RELEASED $f (patches the build used for C1-C3; see README)" ;;
            *) echo "MISSING  $f" ;;
        esac
    elif [ "$(sha256sum "$f" | cut -d' ' -f1)" = "$h" ]; then
        echo "OK       $f"
    else
        case $f in
            exp3/c3_run.sh|exp2/c2_run.sh|exp5/c5_run.sh) echo "EXPECTED $f (see MANIFEST notes and REDACTED.md)" ;;
            *) echo "DIFFERS  $f" ;;
        esac
    fi
done

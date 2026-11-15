#!/bin/bash
# Paper C, C2 runs in the fixed order of a run list; two passes, so a failed run is rerun once.
#   c2_batch.sh OUTROOT INST LIST
# churn: FEMU trace as in C1 (femu_churn.sh). logw: the trace comes from dm-log-writes in the guest (femu_logw.sh).
OUTROOT=$1; INST=$2; LIST=$3
export FEMU_RFTL_RWSTAT=1 FEMU_MAP=1 FEMU_MODE=trace
TRACE=/tmp/femu_trace_c2_i$INST.bin
export FEMU_RFTL_TRACE=$TRACE
for pass in 1 2; do
    while read -r kind fs trim s tool rep; do
        [ -z "$kind" ] && continue
        root=$OUTROOT/$kind/$fs
        out=$root/${trim}_${s}_W60/${tool}_$rep
        [ -s "$out/trace.bin.gz" ] && continue
        mkdir -p "$(dirname "$out")"
        mkdir "$out.claim" 2> /dev/null || continue
        echo "$(date -u +%FT%TZ) start $kind $fs $trim $s $tool $rep inst$INST pass$pass"
        sudo rm -f "$TRACE"
        rm -f "$out/dump.hdr" "$out/trace.bin.gz"
        ok=0
        if [ "$kind" = churn ]; then
            FEMU_FS=$fs INST=$INST ~/femu_churn.sh "$root" "$trim" "$s" W60 "$tool" "$rep" > "$OUTROOT/last_run_i$INST.log" 2>&1 \
                && [ -s "$out/map.txt.gz" ] && sudo gzip -1 -c "$TRACE" > "$out/trace.bin.gz" && ok=1
        else
            FEMU_FS=$fs INST=$INST ~/femu_logw.sh "$root" "$trim" "$s" W60 "$tool" "$rep" > "$OUTROOT/last_run_i$INST.log" 2>&1 \
                && [ -s "$out/map.txt.gz" ] && gzip -t "$out/trace.bin.gz" && [ "$(gzip -dc "$out/trace.bin.gz" | head -c 24 | wc -c)" = 24 ] && ok=1
        fi
        if [ $ok = 1 ]; then
            echo "$(date -u +%FT%TZ) done $kind $fs $trim $s $tool $rep inst$INST"
        else
            echo "$(date -u +%FT%TZ) FAILED $kind $fs $trim $s $tool $rep inst$INST pass$pass"
            cp "$OUTROOT/last_run_i$INST.log" "$out.fail$pass.log"
            rm -f "$out/trace.bin.gz"
        fi
        rmdir "$out.claim" 2> /dev/null
        sudo rm -f "$TRACE"
    done < "$LIST"
done
echo "$(date -u +%FT%TZ) campaign done inst$INST"

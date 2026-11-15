#!/usr/bin/env python3
"""Paper C, C2: derive the churned-state script and the block-layer script from exp/femu_fs.sh, leaving it unchanged.

    make_c2_scripts.py exp/femu_fs.sh femu_churn.sh femu_logw.sh"""
import sys

base = open(sys.argv[1], encoding="utf-8", newline="").read().replace("\r\n", "\n")


def sub(s, a, b):
    assert s.count(a) == 1, a
    return s.replace(a, b)


# churned state SG: map the live files after aging; nothing further is deleted
churn = sub(base, "    SB) STALE='sudo cp -a /usr /mnt/old1' ;;\n",
            "    SB) STALE='sudo cp -a /usr /mnt/old1' ;;\n"
            "    SG) STALE=\"sudo python3 /tmp/churn_age.py /mnt /usr $REP\" ;;\n")
churn = sub(churn, 'if [ -n "$STALE" ]; then\n',
            'if [ -n "$STALE" ]; then\n'
            '    G "echo $(base64 -w0 ~/churn_age.py) | base64 -d > /tmp/churn_age.py"\n')
open(sys.argv[2], "w", encoding="utf-8", newline="\n").write(churn)

# block layer: the same steps on a loop file through dm-log-writes in the guest; the FEMU SSD holds no data
logw = base.replace("/dev/nvme0n1", "/dev/mapper/lw")
logw = sub(logw, "export FEMU_RFTL=${FEMU_MODE:-trace} FEMU_RFTL_TRIM_MS=$TRIM_MS\n",
           "unset FEMU_RFTL FEMU_RFTL_TRACE FEMU_MODE\n")
logw = sub(logw, 'grep -a "\\[RFTL\\]" log | head -1 > "$OUT/femu.cfg"\n', ': > "$OUT/femu.cfg"\n')
a = 'if [ "$TRIM" = TD ]; then\n'
logw = sub(logw, a,
           """G 'sudo modprobe dm-log-writes; sudo dmsetup remove lw 2>/dev/null; sudo losetup -D; sudo rm -f /var/tmp/lw_*; sudo truncate -s 7168M /var/tmp/lw_data; sudo truncate -s 18G /var/tmp/lw_log; D=$(sudo losetup -f --show /var/tmp/lw_data); L=$(sudo losetup -f --show /var/tmp/lw_log); sudo dmsetup create lw --table "0 $(sudo blockdev --getsz $D) log-writes $D $L"; echo $D $L > /tmp/lw_devs'
""" + a)
a = "G 'sudo sh -c \"echo 3 > /proc/sys/vm/drop_caches\"'\n"
i = logw.index(a)
k = logw.index('t0=$(date +%s.%N)\n')
logw = logw[:i] + a + "G 'sudo sync; sudo dmsetup message lw 0 mark tool'\n" + logw[k:]
i = logw.index('ctl "dump $DUMP" "$DUMP.done"\n')
k = logw.index('stop\n', i)
logw = logw[:i] + r"""G "echo $(base64 -w0 ~/logw_to_trace.py) | base64 -d > /tmp/logw_to_trace.py"
G 'sudo umount /mnt && sudo dmsetup remove lw && read D L < /tmp/lw_devs && sudo sync && sudo python3 /tmp/logw_to_trace.py $L /var/tmp/lw_state /var/tmp/lw_trace.bin && sudo losetup -D'
G 'sudo gzip -1 -c /var/tmp/lw_trace.bin' > "$OUT/trace.bin.gz"
G 'sudo rm -f /var/tmp/lw_*'
echo "workload=$TOOL rep=$REP secs=$(echo "$t1 - $t0" | bc) trim=$TRIM state=$STATE" > "$OUT/dump.hdr"
""" + logw[k:]
open(sys.argv[3], "w", encoding="utf-8", newline="\n").write(logw)
print("ok")

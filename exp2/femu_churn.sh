#!/bin/bash
# E2 (revision/prereg/E2.md, option C): benign tools on ext4 in the FEMU guest
# with RFTL in the FTL, under five TRIM modes, two file-system states and two
# RFTL TRIM windows.  Each run boots FEMU and prepares a fresh file system.
#
#   femu_benign2.sh OUTROOT TRIM STATE WIN TOOL REP
#     TRIM  T0 no TRIM | T1 mount -o discard | T2 fstrim right after the tool
#           T3 fstrim 5 min after the tool | T4 fstrim 1 h after the tool
#     STATE S0 fresh (source tree only) | SA SB SC SH SM (E14) | S1 aged (three more copies written
#           and deleted without TRIM, as in femu_benign.sh)
#     WIN   W2 | W60  (RFTL TRIM window, FEMU_RFTL_TRIM_MS = 2000 | 60000)
#     TOOL  copy targz zstd gpgbk gzipf git sqlite rsync dd
#
# femu_benign2p.sh: femu_benign2.sh with INST=1|2 so that two FEMU instances
# run side by side.  Instance 1 keeps the paths and port of femu_benign2.sh;
# instance 2 runs from ~/femu_i2 with its own image, SSH port, control file
# and dump files, and each instance stops only its own QEMU.
set -euo pipefail
OUTROOT=$1; TRIM=$2; STATE=$3; WIN=$4; TOOL=$5; REP=$6
INST=${INST:-1}
OUT=$OUTROOT/${TRIM}_${STATE}_${WIN}/${TOOL}_$REP
[ -s "$OUT/dump.hdr" ] && exit 0
mkdir -p "$OUT"
if [ "$INST" = 1 ]; then
    cd ~/FEMU/build-femu; SUF=""; export SSH_PORT=8080 OSIMGF=$HOME/images/u20s.qcow2
else
    cd ~/femu_i$INST; SUF="_i$INST"; export SSH_PORT=$((8079 + INST)) OSIMGF=$HOME/images/u20s_i$INST.qcow2
fi
CTL=/tmp/femu_rftl_ctl$SUF
export FEMU_RFTL_CTL=$CTL
DUMP=/tmp/femu_dump$SUF.csv; PRE=/tmp/femu_pre$SUF.csv
QPAT="hostfwd=tcp::$SSH_PORT-"
G() { ./run-guest-ssh.sh "$@" < /dev/null; }
ctl() {
    sudo rm -f "$2"
    echo "$1" | sudo tee "$CTL" > /dev/null
    G 'sudo dd if=/dev/nvme0n1 of=/dev/null bs=4096 count=256 iflag=direct status=none'
    for i in $(seq 1 30); do [ -e "$2" ] && return 0; sleep 1; done
    echo "control command '$1' not acknowledged" >&2; return 1
}
stop() {
    if pgrep -f "$QPAT" > /dev/null; then
        G 'sudo poweroff' > /dev/null 2>&1 || true
        for i in $(seq 1 60); do pgrep -f "$QPAT" > /dev/null || break; sleep 2; done
        sudo pkill -f "$QPAT" || true; sleep 2
    fi
}

workload() {
    case $1 in
    copy)   echo 'cp -a /mnt/src /mnt/copy' ;;
    copynr) echo 'cp -a --reflink=never /mnt/src /mnt/copy' ;;
    targz)  echo 'tar czf /mnt/backup.tgz -C /mnt src' ;;
    zstd)   echo 'tar -I "zstd -3 -T2" -cf /mnt/backup.tar.zst -C /mnt src' ;;
    gpgbk)  echo 'tar cf - -C /mnt src | gpg --batch --pinentry-mode loopback --passphrase benign --symmetric -o /mnt/backup.tar.gpg' ;;
    gzipf)  echo 'find /mnt/src -type f -size +4k -print0 | xargs -0 -n 64 gzip -f' ;;
    git)    echo 'cd /mnt/src && git init -q && git config gc.auto 0 && git -c user.name=t -c user.email=t@t add -A && git -c user.name=t -c user.email=t@t commit -q -m snapshot && git gc -q' ;;
    sqlite) echo 'python3 /tmp/sqlite_wl.py /mnt/db.sqlite' ;;
    rsync)  echo 'rsync -a /mnt/src/ /mnt/rsynccopy/' ;;
    dd)     echo 'dd if=/mnt/src.tar of=/mnt/copy.img bs=1M conv=fsync status=none' ;;
    *) echo "unknown workload $1" >&2; exit 2 ;;
    esac
}

SQLITE_PY='import random, sqlite3, sys
random.seed(1)
db = sqlite3.connect(sys.argv[1]); c = db.cursor()
c.execute("create table t(id integer primary key, k text, v text)")
words = open("/usr/share/dict/words").read().split() if __import__("os").path.exists("/usr/share/dict/words") else [str(i) for i in range(50000)]
def row(): return " ".join(random.choice(words) for _ in range(60))
for b in range(200):
    c.executemany("insert into t(k, v) values (?, ?)", [(str(random.random()), row()) for _ in range(1000)])
    db.commit()
for b in range(400):
    for _ in range(250):
        c.execute("update t set v = ? where id = ?", (row(), random.randint(1, 200000)))
    db.commit()
db.close()'

case $WIN in W2) TRIM_MS=2000 ;; W60) TRIM_MS=60000 ;; *) echo "bad window $WIN" >&2; exit 2 ;; esac

stop
sudo rm -f "$CTL" "$CTL.done" "$DUMP" "$DUMP.done"
export FEMU_RFTL=${FEMU_MODE:-trace} FEMU_RFTL_TRIM_MS=$TRIM_MS
setsid nohup ./run-blackbox.sh < /dev/null > ~/femu_run$SUF.out 2>&1 &
for i in $(seq 1 80); do G true > /dev/null 2>&1 && break; sleep 3; done
grep -a "\[RFTL\]" log | head -1 > "$OUT/femu.cfg"
echo "trim=$TRIM state=$STATE win=$WIN trim_ms=$TRIM_MS tool=$TOOL rep=$REP inst=$INST parallel=1" >> "$OUT/femu.cfg"
G "echo $(printf '%s' "$SQLITE_PY" | base64 -w0) | base64 -d > /tmp/sqlite_wl.py"

# preparation (always without discard, so that the aged state keeps its stale blocks)
FS=${FEMU_FS:-ext4}
case $FS in
    ext4)  MKFS='sudo mkfs.ext4 -q -F /dev/nvme0n1'; MOPT='' ;;
    xfs)   MKFS='sudo mkfs.xfs -q -f /dev/nvme0n1'; MOPT='' ;;
    btrfs) MKFS='sudo mkfs.btrfs -q -f /dev/nvme0n1'; MOPT='-o nodiscard,compress=no' ;;
    f2fs)  MKFS='sudo mkfs.f2fs -q -f /dev/nvme0n1'; MOPT='-o nodiscard' ;;
    *) echo "unknown file system $FS" >&2; exit 2 ;;
esac
if [ "$TRIM" = TD ]; then
    case $FS in
        btrfs) MOPT='-o discard=sync,compress=no' ;;
        *) MOPT='-o discard' ;;
    esac
fi
G "$MKFS && sudo mount $MOPT /dev/nvme0n1 /mnt && sudo cp -a /usr /mnt/src && sudo sync"
G "echo $(base64 -w0 ~/fs_map.py) | base64 -d > /tmp/fs_map.py"
if [ "$STATE" = S0 ]; then
    G "sudo python3 /tmp/fs_map.py /mnt /dev/nvme0n1 $FS" | gzip -1 > "$OUT/map.txt.gz"
fi
if [ "$STATE" = S1 ]; then
    if [ -n "${FEMU_MAP:-}" ]; then          # E17: block map before the deletion
        G 'for i in 1 2 3; do sudo cp -a /usr /mnt/old$i; done && sudo sync'
        G "sudo python3 /tmp/fs_map.py /mnt /dev/nvme0n1 $FS" | gzip -1 > "$OUT/map.txt.gz"
        G 'sudo rm -rf /mnt/old1 /mnt/old2 /mnt/old3 && sudo sync'
    else
    G 'for i in 1 2 3; do sudo cp -a /usr /mnt/old$i; done && sudo sync && sudo rm -rf /mnt/old1 /mnt/old2 /mnt/old3 && sudo sync'
    fi
fi
# E14 (revision/prereg/E14.md): other amounts and contents of stale data
case $STATE in
    SB) STALE='sudo cp -a /usr /mnt/old1' ;;
    SG) STALE="sudo python3 /tmp/churn_age.py /mnt /usr $REP" ;;
    SC) STALE='for i in 1 2; do sudo cp -a /usr /mnt/old$i; done' ;;
    SA) STALE='sudo python3 /tmp/stale_prep.py /mnt/old1 half 1' ;;
    SH) STALE='for i in 1 2 3; do sudo python3 /tmp/stale_prep.py /mnt/old$i high $i; done' ;;
    SM) STALE='for i in 1 2 3; do sudo python3 /tmp/stale_prep.py /mnt/old$i mix $i; done' ;;
    *)  STALE='' ;;
esac
if [ -n "$STALE" ]; then
    G "echo $(base64 -w0 ~/churn_age.py) | base64 -d > /tmp/churn_age.py"
    G "echo $(base64 -w0 ~/stale_prep.py) | base64 -d > /tmp/stale_prep.py"
    G "$STALE && sudo sync && sudo df -m /mnt | tail -1" > "$OUT/prep.txt" 2>&1
    if [ -n "${FEMU_MAP:-}" ]; then          # E17: block map before the deletion
        G "sudo python3 /tmp/fs_map.py /mnt /dev/nvme0n1 $FS" | gzip -1 > "$OUT/map.txt.gz"
    fi
    G 'sudo rm -rf /mnt/old1 /mnt/old2 /mnt/old3 && sudo sync'
fi
if [ "$STATE" != S0 ]; then
    G "sudo python3 /tmp/fs_map.py /mnt /dev/nvme0n1 $FS post" | gzip -1 >> "$OUT/map.txt.gz"
    sleep 10                           # queued discards
    if [ "$TRIM" = TF ]; then
        G 'sudo fstrim -v /mnt && sudo sync' > "$OUT/prep_trim.txt" 2>&1
    fi
fi
if [ "$TOOL" = dd ]; then
    G 'sudo tar cf /mnt/src.tar -C /mnt src && sudo sync'
fi
if [ "$TRIM" = T1 ]; then
    G 'sudo mount -o remount,discard /mnt'
fi
G 'sudo sh -c "echo 3 > /proc/sys/vm/drop_caches"'
sleep 60                              # let any alarm of the preparation decay
G 'sudo dd if=/dev/zero of=/mnt/.tick bs=4096 count=1 oflag=direct,sync status=none'
sudo rm -f "$PRE"
ctl "dump $PRE" "$PRE.done"
grep '^#' "$PRE" > "$OUT/pre.hdr"
ctl reset "$CTL.done"
t0=$(date +%s.%N)
G "sudo bash -c '$(workload "$TOOL")'" > "$OUT/workload.log" 2>&1 || echo "exit=$?" >> "$OUT/workload.log"
G 'sudo sync'
t1=$(date +%s.%N)
case $TRIM in
    T2) G 'sudo fstrim -v /mnt' > "$OUT/fstrim.txt" 2>&1 || true ;;
    T3) sleep 300; G 'sudo fstrim -v /mnt' > "$OUT/fstrim.txt" 2>&1 || true ;;
    T4) sleep 3600; G 'sudo fstrim -v /mnt' > "$OUT/fstrim.txt" 2>&1 || true ;;
    T1) sleep 10 ;;                    # discards follow the journal commit (5 s)
    T0) : ;;
esac
sleep 5
G 'sudo du -sm /mnt/src; sudo df -m /mnt | tail -1' > "$OUT/fs.txt" 2>&1 || true
ctl "dump $DUMP" "$DUMP.done"
grep '^#' "$DUMP" > "$OUT/dump.hdr"
echo "workload=$TOOL rep=$REP secs=$(echo "$t1 - $t0" | bc) trim=$TRIM state=$STATE win=$WIN" >> "$OUT/dump.hdr"
stop

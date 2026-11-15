#!/usr/bin/env python3
"""Pilot: derive the run script for other file systems from femu/femu_benign2p.sh, leaving that file unchanged.

    make_fs_script.py IN OUT"""
import sys

s = open(sys.argv[1], encoding="utf-8", newline="").read().replace("\r\n", "\n")
a = "G 'sudo mkfs.ext4 -q -F /dev/nvme0n1 && sudo mount /dev/nvme0n1 /mnt && sudo cp -a /usr /mnt/src && sudo sync'\n"
assert s.count(a) == 1
b = r'''FS=${FEMU_FS:-ext4}
case $FS in
    ext4)  MKFS='sudo mkfs.ext4 -q -F /dev/nvme0n1'; MOPT='' ;;
    xfs)   MKFS='sudo mkfs.xfs -q -f /dev/nvme0n1'; MOPT='' ;;
    btrfs) MKFS='sudo mkfs.btrfs -q -f /dev/nvme0n1'; MOPT='-o nodiscard,compress=no' ;;
    f2fs)  MKFS='sudo mkfs.f2fs -q -f /dev/nvme0n1'; MOPT='-o nodiscard' ;;
    *) echo "unknown file system $FS" >&2; exit 2 ;;
esac
G "$MKFS && sudo mount $MOPT /dev/nvme0n1 /mnt && sudo cp -a /usr /mnt/src && sudo sync"
G "echo $(base64 -w0 ~/fs_map.py) | base64 -d > /tmp/fs_map.py"
if [ "$STATE" = S0 ]; then
    G "sudo python3 /tmp/fs_map.py /mnt /dev/nvme0n1 $FS" | gzip -1 > "$OUT/map.txt.gz"
fi
'''
s = s.replace(a, b)
a = """        G "echo $(base64 -w0 ~/stale_map.py) | base64 -d > /tmp/stale_map.py"
        G 'sudo python3 /tmp/stale_map.py /mnt /dev/nvme0n1' | gzip -1 > "$OUT/map.txt.gz"
        G 'sudo rm -rf /mnt/old1 /mnt/old2 /mnt/old3 && sudo sync'
"""
assert s.count(a) == 1
s = s.replace(a, """        G "sudo python3 /tmp/fs_map.py /mnt /dev/nvme0n1 $FS" | gzip -1 > "$OUT/map.txt.gz"
        G 'sudo rm -rf /mnt/old1 /mnt/old2 /mnt/old3 && sudo sync'
""")
a = "    copy)   echo 'cp -a /mnt/src /mnt/copy' ;;\n"
assert s.count(a) == 1
s = s.replace(a, a + "    copynr) echo 'cp -a --reflink=never /mnt/src /mnt/copy' ;;\n")
a = """        G "echo $(base64 -w0 ~/stale_map.py) | base64 -d > /tmp/stale_map.py"
        G 'sudo python3 /tmp/stale_map.py /mnt /dev/nvme0n1' | gzip -1 > "$OUT/map.txt.gz"
"""
assert s.count(a) == 1
s = s.replace(a, """        G "sudo python3 /tmp/fs_map.py /mnt /dev/nvme0n1 $FS" | gzip -1 > "$OUT/map.txt.gz"
""")
a = "export FEMU_RFTL=1 "
assert s.count(a) == 1
s = s.replace(a, "export FEMU_RFTL=${FEMU_MODE:-trace} ")
# paper C: TRIM before the tool. TD: discard on from mkfs; TF: fstrim after the deletion.
a = 'G "$MKFS && sudo mount $MOPT /dev/nvme0n1 /mnt'
assert s.count(a) == 1
s = s.replace(a, """if [ "$TRIM" = TD ]; then
    case $FS in
        btrfs) MOPT='-o discard=sync,compress=no' ;;
        *) MOPT='-o discard' ;;
    esac
fi
""" + a)
a = 'if [ "$TOOL" = dd ]; then\n'
assert s.count(a) == 1
s = s.replace(a, """if [ "$STATE" != S0 ]; then
    G "sudo python3 /tmp/fs_map.py /mnt /dev/nvme0n1 $FS post" | gzip -1 >> "$OUT/map.txt.gz"
    sleep 10                           # queued discards
    if [ "$TRIM" = TF ]; then
        G 'sudo fstrim -v /mnt && sudo sync' > "$OUT/prep_trim.txt" 2>&1
    fi
fi
""" + a)
open(sys.argv[2], "w", encoding="utf-8", newline="\n").write(s)

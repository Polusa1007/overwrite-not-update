#!/bin/bash
# In WSL: c6_run.sh IP formal [wait]. C6 (prereg/C6.md): the released trace build (~/FEMU_trace, stock FEMU
# 2d50161f + femu/apply_trace.py) on the C1 geometry, instances 3 and 4 (~/femu_i3, ~/femu_i4, copy-on-write overlays
# of the C1 image). Waits without output, then pulls to ~/c6_formal. A VM watchdog powers it off one hour after both
# instances finish (the VM stays on for that hour so that a further campaign can start).
IP=$1; MODE=$2
case $MODE in formal) LIST=c6_runs.txt; N=156 ;; *) echo "mode?"; exit 2 ;; esac
K="-n -i ${SSH_KEY:?set SSH_KEY} -o BatchMode=yes -o ServerAliveInterval=30 -o ConnectTimeout=20 -o StrictHostKeyChecking=accept-new"
SC="scp -i $SSH_KEY -o BatchMode=yes -o StrictHostKeyChecking=accept-new"
V=${VM_USER:?set VM_USER}@$IP
E=${PAPER_C:?set PAPER_C}
R=c6_$MODE
if [ "$3" != wait ]; then
$SC $E/exp/fs_map.py $E/exp/femu_fs.sh $E/exp3/c3_batch.sh $E/exp6/$LIST $V:~/ || exit 1
ssh $K $V "cd ~; sed -i 's/\r$//' c3_batch.sh femu_fs.sh fs_map.py $LIST; chmod +x c3_batch.sh femu_fs.sh; mkdir -p ~/$R
[ -x ~/FEMU_trace/build-femu/qemu-system-x86_64 ] || { echo no_trace_build; exit 1; }
B=~/femu_i2/run-blackbox.sh; [ -f \$B.c1 ] && cp \$B.c1 \$B
for i in 3 4; do
  mkdir -p ~/femu_i\$i; cp ~/femu_i2/run-guest-ssh.sh ~/femu_i\$i/
  sed 's#/home/[^/]*/FEMU/build-femu/qemu-system-x86_64#'\$HOME'/FEMU_trace/build-femu/qemu-system-x86_64#' \$B.c1 > ~/femu_i\$i/run-blackbox.sh
  chmod +x ~/femu_i\$i/run-blackbox.sh
  grep -q '^blks_per_pl=1024 ' ~/femu_i\$i/run-blackbox.sh && grep -q '^ssd_size=7168 ' ~/femu_i\$i/run-blackbox.sh \
    && grep -q 'FEMU_trace/build-femu/qemu-system-x86_64' ~/femu_i\$i/run-blackbox.sh || { echo setup_failed_\$i; exit 1; }
  [ -f ~/images/u20s_i\$i.qcow2 ] || qemu-img create -q -f qcow2 -b ~/images/u20s.qcow2 -F qcow2 ~/images/u20s_i\$i.qcow2
done
sha256sum ~/FEMU_trace/build-femu/qemu-system-x86_64 ~/FEMU_trace/hw/femu/bbssd/ftl-trace.c femu_fs.sh fs_map.py c3_batch.sh $LIST ~/femu_i3/run-blackbox.sh > ~/$R/versions.txt
(cd ~/FEMU_trace && git rev-parse HEAD && git diff --stat) >> ~/$R/versions.txt
find ~/$R -name '*.claim' -type d -exec rmdir {} + 2>/dev/null
pkill -f '^bash -c while'; true
for i in 3 4; do setsid nohup ~/c3_batch.sh ~/$R \$i ~/$LIST >> ~/$R/campaign_i\$i.log 2>&1 < /dev/null & done
setsid nohup bash -c 'while [ \$(cat ~/$R/campaign_i3.log ~/$R/campaign_i4.log 2>/dev/null | grep -c \"campaign done\") -lt 2 ]; do sleep 300; done; sleep 3600; sudo poweroff' > /dev/null 2>&1 < /dev/null &
sleep 1; pgrep -fc c3_batch" || exit 1
fi
fails=0
while true; do
    sleep 120
    n=$(ssh $K $V "cat ~/$R/campaign_i3.log ~/$R/campaign_i4.log 2>/dev/null | grep -c 'campaign done'; true") || { fails=$((fails+1)); [ $fails -gt 60 ] && { echo "VM unreachable: check that it is off"; exit 1; }; continue; }
    fails=0
    [ "$n" -ge 2 ] 2>/dev/null && break
done
mkdir -p ~/$R
ssh $K $V "tar cf - -C ~/$R --exclude=*.claim ." | tar xf - -C ~/$R
ssh $K $V "cat ~/$R/campaign_i3.log ~/$R/campaign_i4.log | grep -c FAILED; grep -h FAILED ~/$R/campaign_i*.log | tail -30; true"
n=$(find ~/$R -name trace.bin.gz | wc -l)
echo "pulled $n of $N"; du -sh ~/$R

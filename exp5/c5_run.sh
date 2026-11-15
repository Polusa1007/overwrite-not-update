#!/bin/bash
# In WSL: c5_run.sh IP smoke|formal [wait]. C5 (prereg/C5.md): four deleted copies (state SD) on the 14336-MiB device,
# with the released trace build (~/FEMU_trace, stock FEMU 2d50161f + femu/apply_trace.py), one instance (3, ~/femu_i3,
# copy-on-write overlay of the C1 image), geometry as in C3 (blks_per_pl=2048, ssd_size=14336). Waits without output,
# then pulls to ~/c5_<mode>. A VM watchdog powers it off one hour after the campaign ends; formal also powers it off at
# once after a complete pull; smoke leaves it on.
IP=$1; MODE=$2
case $MODE in smoke) LIST=c5_smoke.txt; N=4 ;; formal) LIST=c5_runs.txt; N=36 ;; *) echo "mode?"; exit 2 ;; esac
K="-n -i ${SSH_KEY:?set SSH_KEY} -o BatchMode=yes -o ServerAliveInterval=30 -o ConnectTimeout=20 -o StrictHostKeyChecking=accept-new"
SC="scp -i $SSH_KEY -o BatchMode=yes -o StrictHostKeyChecking=accept-new"
V=${VM_USER:?set VM_USER}@$IP
E=${PAPER_C:?set PAPER_C}
R=c5_$MODE
if [ "$3" != wait ]; then
$SC $E/exp/fs_map.py $E/exp5/femu_fs_c5.sh $E/exp5/c5_batch.sh $E/exp5/$LIST $V:~/ || exit 1
ssh $K $V "cd ~; sed -i 's/\r$//' c5_batch.sh femu_fs_c5.sh fs_map.py $LIST; chmod +x c5_batch.sh femu_fs_c5.sh; mkdir -p ~/$R
[ -x ~/FEMU_trace/build-femu/qemu-system-x86_64 ] || { echo no_trace_build; exit 1; }
B=~/femu_i2/run-blackbox.sh; [ -f \$B.c1 ] && cp \$B.c1 \$B
mkdir -p ~/femu_i3; cp ~/femu_i2/run-guest-ssh.sh ~/femu_i3/
sed -e 's#/home/[^/]*/FEMU/build-femu/qemu-system-x86_64#'\$HOME'/FEMU_trace/build-femu/qemu-system-x86_64#' \
    -e 's/^blks_per_pl=1024 /blks_per_pl=2048 /' -e 's/^ssd_size=7168 /ssd_size=14336 /' \$B.c1 > ~/femu_i3/run-blackbox.sh
chmod +x ~/femu_i3/run-blackbox.sh
grep -q '^blks_per_pl=2048 ' ~/femu_i3/run-blackbox.sh && grep -q '^ssd_size=14336 ' ~/femu_i3/run-blackbox.sh \
  && grep -q 'FEMU_trace/build-femu/qemu-system-x86_64' ~/femu_i3/run-blackbox.sh || { echo setup_failed; exit 1; }
[ -f ~/images/u20s_i3.qcow2 ] || qemu-img create -q -f qcow2 -b ~/images/u20s.qcow2 -F qcow2 ~/images/u20s_i3.qcow2
sha256sum ~/FEMU_trace/build-femu/qemu-system-x86_64 ~/FEMU_trace/hw/femu/bbssd/ftl-trace.c femu_fs_c5.sh fs_map.py c5_batch.sh $LIST ~/femu_i3/run-blackbox.sh > ~/$R/versions.txt
(cd ~/FEMU_trace && git rev-parse HEAD && git diff --stat) >> ~/$R/versions.txt
find ~/$R -name '*.claim' -type d -exec rmdir {} + 2>/dev/null
pkill -f '^bash -c while'; true
setsid nohup ~/c5_batch.sh ~/$R 3 ~/$LIST >> ~/$R/campaign_i3.log 2>&1 < /dev/null &
setsid nohup bash -c 'while ! grep -q \"campaign done\" ~/$R/campaign_i3.log 2>/dev/null; do sleep 300; done; sleep 3600; sudo poweroff' > /dev/null 2>&1 < /dev/null &
sleep 1; pgrep -fc c5_batch" || exit 1
fi
fails=0
while true; do
    sleep 300
    n=$(ssh $K $V "grep -c 'campaign done' ~/$R/campaign_i3.log 2>/dev/null; true") || { fails=$((fails+1)); [ $fails -gt 30 ] && { echo "VM unreachable: check that it is off"; exit 1; }; continue; }
    fails=0
    [ "$n" -ge 1 ] 2>/dev/null && break
done
mkdir -p ~/$R
ssh $K $V "tar cf - -C ~/$R --exclude=*.claim ." | tar xf - -C ~/$R
ssh $K $V "grep -c FAILED ~/$R/campaign_i3.log; grep -h FAILED ~/$R/campaign_i3.log | tail -30; for f in ~/$R/*/T0_SD_W60/*/prep.txt; do echo \$f; tail -1 \$f; done; true"
n=$(find ~/$R -name trace.bin.gz | wc -l)
echo "pulled $n of $N"; du -sh ~/$R
if [ "$MODE" = formal ] && [ "$n" = $N ]; then ssh $K $V 'sudo poweroff'; echo poweroff_sent; fi

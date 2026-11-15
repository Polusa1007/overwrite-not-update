#!/bin/bash
# In WSL: c3_run.sh IP smoke|formal. C3 (prereg/C3.md): C1 scripts on a 14336-MiB FEMU device, one instance (INST=2),
# whose run-blackbox.sh gets blks_per_pl=2048 and ssd_size=14336 (original kept as run-blackbox.sh.c1).
# Waits without output, then pulls to ~/c3_<mode>. A VM watchdog powers it off one hour after the campaign ends;
# formal also powers it off at once after a complete pull; smoke leaves it on.
IP=$1; MODE=$2
case $MODE in smoke) LIST=c3_smoke.txt; N=4 ;; formal) LIST=c3_runs.txt; N=108 ;; *) echo "mode?"; exit 2 ;; esac
K="-n -i ${SSH_KEY:?set SSH_KEY to the VM key} -o BatchMode=yes -o ServerAliveInterval=30 -o ConnectTimeout=20 -o StrictHostKeyChecking=accept-new"
SC="scp -i ${SSH_KEY:?set SSH_KEY to the VM key} -o BatchMode=yes -o StrictHostKeyChecking=accept-new"
V=${VM_USER:?set VM_USER}@$IP
E=${PAPER_C:?set PAPER_C to this directory}
R=c3_$MODE
if [ "$3" != wait ]; then
$SC $E/exp/fs_map.py $E/exp/femu_fs.sh $E/exp3/c3_batch.sh $E/exp3/$LIST $V:~/ || exit 1
ssh $K $V "cd ~; sed -i 's/\r$//' c3_batch.sh femu_fs.sh fs_map.py $LIST; chmod +x c3_batch.sh femu_fs.sh; mkdir -p ~/$R
B=~/femu_i2/run-blackbox.sh; [ -f \$B.c1 ] || cp \$B \$B.c1
sed -e 's/^blks_per_pl=1024 /blks_per_pl=2048 /' -e 's/^ssd_size=7168 /ssd_size=14336 /' \$B.c1 > \$B
grep -q '^blks_per_pl=2048 ' \$B && grep -q '^ssd_size=14336 ' \$B || { echo geometry_not_set; exit 1; }
sha256sum ~/FEMU/hw/femu/bbssd/ftl-rftl.c ~/FEMU/build-femu/qemu-system-x86_64 femu_fs.sh fs_map.py c3_batch.sh $LIST \$B > ~/$R/versions.txt
find ~/$R -name '*.claim' -type d -exec rmdir {} + 2>/dev/null
setsid nohup ~/c3_batch.sh ~/$R 2 ~/$LIST >> ~/$R/campaign_i2.log 2>&1 < /dev/null &
setsid nohup bash -c 'while ! grep -q \"campaign done\" ~/$R/campaign_i2.log 2>/dev/null; do sleep 300; done; sleep 3600; sudo poweroff' > /dev/null 2>&1 < /dev/null &
sleep 1; pgrep -fc c3_batch" || exit 1
fi
fails=0
while true; do
    sleep 300
    n=$(ssh $K $V "grep -c 'campaign done' ~/$R/campaign_i2.log 2>/dev/null; true") || { fails=$((fails+1)); [ $fails -gt 60 ] && { echo "VM unreachable: check that it is off"; exit 1; }; continue; }
    fails=0
    [ "$n" -ge 1 ] 2>/dev/null && break
done
mkdir -p ~/$R
ssh $K $V "tar cf - -C ~/$R --exclude=*.claim ." | tar xf - -C ~/$R
ssh $K $V "grep -h FAILED ~/$R/campaign_i2.log | wc -l; grep -h FAILED ~/$R/campaign_i2.log | tail -30"
n=$(find ~/$R -name trace.bin.gz | wc -l)
echo "pulled $n of $N"; du -sh ~/$R
if [ "$MODE" = formal ] && [ "$n" = $N ]; then ssh $K $V 'sudo poweroff'; echo poweroff_sent; fi

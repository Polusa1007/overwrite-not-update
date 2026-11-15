#!/bin/bash
# In WSL: c2_run.sh IP smoke|formal. Copies the C2 tools to the VM, starts two instances on the run list and waits
# without output, then pulls to ~/c2_<mode>. A VM watchdog powers it off one hour after both instances finish.
# formal also powers the VM off at once after a complete pull; smoke leaves it on for checking.
IP=$1; MODE=$2
case $MODE in smoke) LIST=c2_smoke.txt; N=8 ;; formal) LIST=c2_runs.txt; N=132 ;; *) echo "mode?"; exit 2 ;; esac
K="-n -i ${SSH_KEY:?set SSH_KEY to the VM key} -o BatchMode=yes -o ServerAliveInterval=30 -o ConnectTimeout=20 -o StrictHostKeyChecking=accept-new"
SC="scp -i ${SSH_KEY:?set SSH_KEY to the VM key} -o BatchMode=yes -o StrictHostKeyChecking=accept-new"
V=${VM_USER:?set VM_USER}@$IP
E=${PAPER_C:?set PAPER_C to this directory}/exp2
R=c2_$MODE
ssh-keygen -R "$IP" > /dev/null 2>&1
$SC $E/fs_map.py $E/femu_churn.sh $E/femu_logw.sh $E/churn_age.py $E/logw_to_trace.py $E/c2_batch.sh $E/$LIST $V:~/ || exit 1
ssh $K $V "cd ~; sed -i 's/\r$//' c2_batch.sh femu_churn.sh femu_logw.sh fs_map.py churn_age.py logw_to_trace.py $LIST
chmod +x c2_batch.sh femu_churn.sh femu_logw.sh; mkdir -p ~/$R
sha256sum ~/FEMU/hw/femu/bbssd/ftl-rftl.c ~/FEMU/build-femu/qemu-system-x86_64 femu_churn.sh femu_logw.sh fs_map.py churn_age.py logw_to_trace.py c2_batch.sh $LIST > ~/$R/versions.txt
find ~/$R -name '*.claim' -type d -exec rmdir {} + 2>/dev/null
for i in 1 2; do setsid nohup ~/c2_batch.sh ~/$R \$i ~/$LIST >> ~/$R/campaign_i\$i.log 2>&1 < /dev/null & done
setsid nohup bash -c 'while [ \$(grep -l \"campaign done\" ~/$R/campaign_i*.log 2>/dev/null | wc -l) -lt 2 ]; do sleep 300; done; sleep 3600; sudo poweroff' > /dev/null 2>&1 < /dev/null &
sleep 1; pgrep -fc c2_batch" || exit 1
fails=0
while true; do
    sleep 300
    n=$(ssh $K $V "grep -l 'campaign done' ~/$R/campaign_i*.log 2>/dev/null | wc -l") || { fails=$((fails+1)); [ $fails -gt 60 ] && { echo "VM unreachable: check that it is off"; exit 1; }; continue; }
    fails=0
    [ "$n" = 2 ] && break
done
mkdir -p ~/$R
ssh $K $V "tar cf - -C ~/$R --exclude=*.claim ." | tar xf - -C ~/$R
ssh $K $V "grep -h FAILED ~/$R/campaign_i*.log | wc -l; grep -h FAILED ~/$R/campaign_i*.log | tail -30"
n=$(find ~/$R -name trace.bin.gz | wc -l)
echo "pulled $n of $N"; du -sh ~/$R
if [ "$MODE" = formal ] && [ "$n" = $N ]; then ssh $K $V 'sudo poweroff'; echo poweroff_sent; fi

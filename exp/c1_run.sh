#!/bin/bash
# In WSL: c1_run.sh IP. Starts the formal runs and waits without output. On the VM a watchdog powers it off one hour
# after both instances finish, so the VM stops even if this waiter is lost; traces stay on the VM disk.
IP=$1
K="-n -i ${SSH_KEY:?set SSH_KEY to the VM key} -o BatchMode=yes -o ServerAliveInterval=30 -o ConnectTimeout=20 -o StrictHostKeyChecking=accept-new"
SC="scp -i ${SSH_KEY:?set SSH_KEY to the VM key} -o BatchMode=yes -o StrictHostKeyChecking=accept-new"
V=${VM_USER:?set VM_USER}@$IP
E=${PAPER_C:?set PAPER_C to this directory}/exp
ssh-keygen -R "$IP" > /dev/null 2>&1
$SC $E/fs_map.py $E/femu_fs.sh $E/c1_batch.sh $E/runs.txt $V:~/ || exit 1
ssh $K $V 'sed -i "s/\r$//" ~/c1_batch.sh ~/femu_fs.sh ~/fs_map.py ~/runs.txt; chmod +x ~/c1_batch.sh ~/femu_fs.sh; mkdir -p ~/c1_runs
sha256sum ~/FEMU/hw/femu/bbssd/ftl-rftl.c ~/FEMU/build-femu/qemu-system-x86_64 ~/femu_fs.sh ~/fs_map.py ~/runs.txt > ~/c1_runs/versions.txt; find ~/c1_runs -name "*.claim" -type d -exec rmdir {} + 2>/dev/null
for i in 1 2; do setsid nohup ~/c1_batch.sh ~/c1_runs $i >> ~/c1_runs/campaign_i$i.log 2>&1 < /dev/null & done
setsid nohup bash -c "while [ \$(grep -l \"campaign done\" ~/c1_runs/campaign_i*.log 2>/dev/null | wc -l) -lt 2 ]; do sleep 300; done; sleep 3600; sudo poweroff" > /dev/null 2>&1 < /dev/null &
sleep 1; pgrep -fc c1_batch' || exit 1
fails=0
while true; do
    sleep 300
    n=$(ssh $K $V 'grep -l "campaign done" ~/c1_runs/campaign_i*.log 2>/dev/null | wc -l') || { fails=$((fails+1)); [ $fails -gt 60 ] && { echo "VM unreachable: check that it is off"; exit 1; }; continue; }
    fails=0
    [ "$n" = 2 ] && break
done
mkdir -p ~/c1_runs
ssh $K $V 'tar cf - -C ~/c1_runs --exclude=*.claim .' | tar xf - -C ~/c1_runs
ssh $K $V 'grep -h FAILED ~/c1_runs/campaign_i*.log | wc -l; grep -h FAILED ~/c1_runs/campaign_i*.log | tail -30'
n=$(find ~/c1_runs -name trace.bin.gz | wc -l)
echo "pulled $n of 650"; du -sh ~/c1_runs
if [ "$n" = 650 ]; then ssh $K $V 'sudo poweroff'; echo poweroff_sent; else echo "incomplete: VM powers itself off within an hour"; fi

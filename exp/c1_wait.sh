#!/bin/bash
# In WSL: c1_wait.sh IP. Only waits for running formal runs, then fetches; starts nothing.
IP=$1
K="-n -i ${SSH_KEY:?set SSH_KEY to the VM key} -o BatchMode=yes -o ServerAliveInterval=30 -o ConnectTimeout=20 -o StrictHostKeyChecking=accept-new"
V=${VM_USER:?set VM_USER}@$IP
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

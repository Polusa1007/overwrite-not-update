#!/bin/bash
# Paper C: add F2FS to both FEMU guest images. Run once on the VM host, while no experiment runs.
#   bash install_f2fs_guest.sh
# Installs Ubuntu's f2fs-tools and the module package of the guest's running kernel, then checks that F2FS loads.
set -u
for INST in 1 2; do
    if [ "$INST" = 1 ]; then
        D=~/FEMU/build-femu; SUF=""; export SSH_PORT=8080 OSIMGF=$HOME/images/u20s.qcow2
    else
        D=~/femu_i$INST; SUF="_i$INST"; export SSH_PORT=$((8079 + INST)) OSIMGF=$HOME/images/u20s_i$INST.qcow2
    fi
    cd "$D" || exit 1
    export FEMU_RFTL_CTL=/tmp/femu_rftl_ctl$SUF
    setsid nohup ./run-blackbox.sh < /dev/null > ~/femu_f2fs$SUF.out 2>&1 &
    for i in $(seq 1 80); do ./run-guest-ssh.sh true < /dev/null > /dev/null 2>&1 && break; sleep 3; done
    ./run-guest-ssh.sh 'sudo apt-get update -qq && sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq f2fs-tools linux-modules-extra-$(uname -r) && sudo modprobe f2fs && grep -w f2fs /proc/filesystems && echo "instance OK: $(uname -r)"' < /dev/null
    echo "instance $INST exit code: $?"
    ./run-guest-ssh.sh 'sudo sync; sudo poweroff' < /dev/null > /dev/null 2>&1
    for i in $(seq 1 60); do pgrep -f "hostfwd=tcp::$SSH_PORT-" > /dev/null || break; sleep 2; done
done
echo finished

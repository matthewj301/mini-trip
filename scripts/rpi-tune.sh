#!/usr/bin/env bash
# Klipper-host Pi tuning, replicated from vcore3 (rat-race), verified there 2026-10-19: core 3 isolated and
# reserved for klippy; everything else (moonraker, nginx, ...) kept on cores 0-2; USB autosuspend off.
# Idempotent. Run ON the Pi as root: sudo ./rpi-tune.sh [--dry-run] [--overclock]. Takes effect after a reboot.
# --overclock: mild 2.0 GHz (stock Pi 4 rev 1.5 is 1.8), no extra voltage, no force_turbo; for a heatsink+fan host.
# vcore3's own overclock (2100 MHz, over_voltage=14, force_turbo=1) is watercooled and deliberately NOT copied.
set -euo pipefail
DRY=0; OC=0
for a in "$@"; do case $a in --dry-run) DRY=1;; --overclock) OC=1;; *) echo "unknown arg $a"; exit 1;; esac; done
run() { if ((DRY)); then echo "[dry-run] $*"; else eval "$*"; fi; }

CMDLINE=/boot/firmware/cmdline.txt; [[ -f $CMDLINE ]] || CMDLINE=/boot/cmdline.txt
FLAGS=(isolcpus=3 nohz_full=3 rcu_nocbs=3 usbcore.autosuspend=-1)

[[ $(nproc --all) -eq 4 ]] || { echo "expected a 4-core Pi; refusing (core 3 isolation assumes 4 cores)"; exit 1; }
run "cp -n $CMDLINE $CMDLINE.pre-tune || true"
line=$(tr -d '\n' < "$CMDLINE")
for f in "${FLAGS[@]}"; do
  [[ " $line " == *" $f "* ]] || line="$line $f"
done
if ((DRY)); then echo "[dry-run] $CMDLINE -> $line"; else echo "$line" > "$CMDLINE"; fi

if ((OC)); then
  CFG=/boot/firmware/config.txt; [[ -f $CFG ]] || CFG=/boot/config.txt
  run "cp -n $CFG $CFG.pre-tune"
  grep -q '^arm_freq=' "$CFG" || run "printf '\\n[pi4]\\narm_freq=2000\\n' >> $CFG"
fi

run "mkdir -p /etc/systemd/system.conf.d /etc/systemd/system/klipper.service.d /etc/NetworkManager/conf.d"
run "printf '[Manager]\nDefaultCPUAffinity=0 1 2\n' > /etc/systemd/system.conf.d/cpu-affinity.conf"
run "printf '[Service]\nCPUAffinity=3\n' > /etc/systemd/system/klipper.service.d/cpu-affinity.conf"
# Wi-Fi power save off (vcore3 does this via an iw udev rule; NetworkManager hosts use wifi.powersave=2).
run "printf '[connection]\nwifi.powersave = 2\n' > /etc/NetworkManager/conf.d/wifi-powersave-off.conf"
run "systemctl daemon-reload"
echo "Done. Reboot to apply; then verify: cat /sys/devices/system/cpu/isolated (3), taskset -pc \$(pgrep -f klippy.py) (3)."

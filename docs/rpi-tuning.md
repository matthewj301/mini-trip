# Raspberry Pi Klipper/Kalico host tuning

Reference for tuning a Pi that runs Klippy. Origin: `vcore3` (rat-race), replicated to `tri-zero` (mini-trip) on
2026-10-19. Apply the same to other fleet hosts with `scripts/rpi-tune.sh`.

## What it does

Reserves CPU core 3 for `klippy` so USB/serial timing is not disturbed by Moonraker, nginx, cameras or the kernel.

| Layer | Setting | Purpose |
| --- | --- | --- |
| `cmdline.txt` | `isolcpus=3` | Scheduler does not place tasks on core 3 |
| `cmdline.txt` | `nohz_full=3 rcu_nocbs=3` | No timer ticks or RCU callbacks on core 3 |
| `cmdline.txt` | `usbcore.autosuspend=-1` | USB autosuspend off (MCU links must never nap) |
| systemd manager | `DefaultCPUAffinity=0 1 2` (`/etc/systemd/system.conf.d/cpu-affinity.conf`) | All services default to cores 0-2 |
| `klipper.service` | `CPUAffinity=3` (drop-in `klipper.service.d/cpu-affinity.conf`) | Only klippy runs on core 3 |
| NetworkManager | `wifi.powersave = 2` (`conf.d/wifi-powersave-off.conf`) | Wi-Fi power save off (vcore3 uses an `iw` udev rule instead) |
| CPU governor | `performance` (`/etc/tmpfiles.d/cpu-governor.conf`) | Pi 4 has one clock domain; `ondemand` idles the whole chip (incl. klippy's core 3) at 600 MHz and ramps on demand. Measured on tri-zero: 2000 -> 600 MHz within seconds of idle |
| `config.txt` (optional) | `[pi4] arm_freq=2000` | Mild overclock, `--overclock` only |

Already standard on these hosts, nothing to do: `noatime` on `/`. The stock governor is `ondemand` (set at boot by
`raspi-config.service`); it is NOT left as-is, see the governor row. On vcore3 `force_turbo=1` pins the clock at 2.1 GHz
so its governor never mattered, but it is set to `performance` too for consistency.

## Apply

Requires a 4-core Pi (script refuses otherwise), root, and a reboot.

```sh
scp scripts/rpi-tune.sh pi@<host>:/tmp/
ssh pi@<host> 'sudo /tmp/rpi-tune.sh --dry-run [--overclock]'   # inspect first
ssh pi@<host> 'sudo /tmp/rpi-tune.sh [--overclock]'
ssh pi@<host> 'sudo reboot'
```

The script is idempotent, backs up `cmdline.txt` and `config.txt` as `*.pre-tune`, and uses the Trixie path
`/boot/firmware/` (falls back to `/boot/`). Passwordless sudo is needed for non-interactive runs:
`echo "pi ALL=(ALL) NOPASSWD:ALL" | sudo tee /etc/sudoers.d/010_pi-nopasswd` (then `chmod 440`, `visudo -cf`) from a
real terminal; a tool-driven shell has no TTY for the password prompt.

## Verify (after reboot)

```sh
cat /sys/devices/system/cpu/isolated                 # 3
taskset -pc $(pgrep -f klippy.py | head -1)          # 3
taskset -pc $(pgrep -f moonraker | head -1)          # 0-2
grep -o "isolcpus=3 nohz_full=3 rcu_nocbs=3 usbcore.autosuspend=-1" /proc/cmdline
cat /sys/module/usbcore/parameters/autosuspend       # -1
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor   # performance
vcgencmd get_throttled                               # 0x0
```

Then confirm Klipper is `ready` and every MCU is in `ls /dev/serial/by-id/`.

## Overclock policy

- **vcore3** is watercooled and runs `arm_freq=2100`, `over_voltage=14`, `force_turbo=1`. Do not copy that to
  air-cooled hosts.
- **tri-zero** (GeeekPi low-profile heatsink + PWM fan) uses `arm_freq=2000` only: stock Pi 4 rev 1.5 is 1800 MHz, no
  extra voltage, no `force_turbo` (the `performance` governor holds 2.0 GHz; there is no idle downclock). Validate any host with a load test and watch
  `vcgencmd get_throttled` (must stay `0x0`) and `measure_temp`.
- Skip `--overclock` entirely if the host has no active cooling. Klippy gains little from clock speed; core isolation
  is the real benefit.

## Gotchas

- Hosts with a BTT EBB36 toolboard have hung at boot with the board attached (tri-zero history). Unplug USB
  toolboards before the reboot, replug, then `FIRMWARE_RESTART`.
- `iw` is not installed on trixie images; that is why Wi-Fi power save uses a NetworkManager drop-in here.
- `rtk` can mangle `ls`/`grep` output when verifying over SSH; use `/bin/ls` or `/usr/bin/grep` if counts look wrong.
- Rollback: restore `/boot/firmware/cmdline.txt.pre-tune` and `config.txt.pre-tune`, delete the three drop-ins above,
  `systemctl daemon-reload`, reboot.

## Applied hosts

| Host | Date | Overclock | Notes |
| --- | --- | --- | --- |
| vcore3 (rat-race) | before 2026-10-19 | 2100 MHz, watercooled | Reference; klipper unit edited in place rather than a drop-in. Governor set to `performance` 2026-10-19 (was `ondemand`, moot under force_turbo) |
| tri-zero (mini-trip) | 2026-10-19 | 2000 MHz, heatsink+fan | Via `scripts/rpi-tune.sh --overclock`; governor `performance` |

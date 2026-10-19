# Raspberry Pi Klipper/Kalico host tuning

Reference for tuning a Pi that runs Klippy. Origin: `vcore3` (rat-race), replicated to `tri-zero` (mini-trip),
`doomcube` and `K3D` (k3) on 2026-10-19. Apply the same to other fleet hosts with `scripts/rpi-tune.sh`.

## What it does

Reserves CPU core 3 for `klippy` so USB/serial timing is not disturbed by Moonraker, nginx, cameras or the kernel, and
holds the clock at maximum so klippy never waits on a frequency ramp.

| Layer | Setting | Purpose |
| --- | --- | --- |
| `cmdline.txt` | `isolcpus=3` | Scheduler does not place tasks on core 3 |
| `cmdline.txt` | `nohz_full=3 rcu_nocbs=3` | No timer ticks or RCU callbacks on core 3 |
| `cmdline.txt` | `usbcore.autosuspend=-1` | USB autosuspend off (MCU links must never nap) |
| systemd manager | `DefaultCPUAffinity=0 1 2` (`/etc/systemd/system.conf.d/cpu-affinity.conf`) | All services default to cores 0-2 |
| `klipper.service` | `CPUAffinity=3` (drop-in `klipper.service.d/cpu-affinity.conf`) | Only klippy runs on core 3 |
| NetworkManager | `wifi.powersave = 2` (`conf.d/wifi-powersave-off.conf`) | Wi-Fi power save off (hosts without NetworkManager use an `iw` udev rule instead) |
| CPU governor | `performance` (`/etc/tmpfiles.d/cpu-governor.conf`, or `/etc/default/cpufrequtils` on older images) | Pi 4 has one clock domain; `ondemand` idles the whole chip (incl. klippy's core 3) at 600 MHz and adds ramp-up latency. Measured on tri-zero: 2000 -> 600 MHz within seconds of idle |
| `config.txt` (optional) | `[pi4] arm_freq=2000` | Mild overclock, `--overclock` only |

Already standard on these hosts, nothing to do: `noatime` on `/`. Do not rely on the stock governor: it is `ondemand`
on fresh images and `performance` has to be set explicitly. On vcore3 `force_turbo=1` pins the clock at 2.1 GHz so its
governor never mattered, but it is set to `performance` too for consistency.

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

Reboot only when the printer is idle (`print_stats.state` is `complete`/`standby`).

**Older images (Bullseye, no NetworkManager):** the script writes a NetworkManager drop-in that does nothing there and
a klipper drop-in that may duplicate an edit already in the unit. Check what is already in place and apply only the
gaps by hand. doomcube is the example, see Applied hosts.

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

Then confirm Klipper is `ready` and every MCU is in `ls /dev/serial/by-id/` (and `can0` is up on CAN hosts). Verification
is read-only: do not home, move or heat anything to check.

## Temperatures and cooling

Expected readings, not faults:

- **Electronics-bay fans run only while a stepper driver is enabled.** There is no reason to run them while the printer
  is idle, so an idle printer has warm electronics by design. Do not add always-on or temperature-triggered fans.
- On doomcube, idle with fans off, the Pi (`rpi` sensor) sits at 64-66 C and the Octopus at about 50 C. When the fans
  start they fall to about 50 C and 41 C within minutes. K3 idles steady at 54.5-55 C (Pi) and 43.5 C (Octopus).
- The real limit is the Pi's 80 C soft throttle. Investigate only if `vcgencmd get_throttled` is non-zero, or if
  temperatures stay high while the fans are running during a print.
- Do not switch hosts to `ondemand` to lower idle temperature. Under print load klippy keeps its core busy so the
  clock ramps to maximum anyway, and the ramp latency risks `Timer too close` errors for little gain.

Quick read-only check of a host's sensors (Moonraker, no motion):
`curl -s localhost:7125/printer/objects/query?temperature_sensor%20Pi` and `vcgencmd measure_temp`.

## Overclock policy

- **vcore3** is watercooled and runs `arm_freq=2100`, `over_voltage=14`, `force_turbo=1`. Do not copy that to
  air-cooled hosts.
- **tri-zero** (GeeekPi low-profile heatsink + PWM fan) uses `arm_freq=2000` only: stock Pi 4 rev 1.5 is 1800 MHz, no
  extra voltage, no `force_turbo` (the `performance` governor holds 2.0 GHz; there is no idle downclock). Validate any
  host with a load test and watch `vcgencmd get_throttled` (must stay `0x0`) and `measure_temp`.
- **doomcube** (rev 1.5) predates this doc: `arm_freq=2000` with `over_voltage=6`, bay fans as above. Leave as is.
- **K3** (rev 1.1) runs the stock 1500 MHz. Cooling is not characterized, so no `--overclock`.
- Skip `--overclock` entirely if the host has no active cooling. Klippy gains little from clock speed; core isolation
  is the real benefit.

## OS versions

| Host | OS | Python (klippy/moonraker venvs) | Kernel | Userland |
| --- | --- | --- | --- | --- |
| doomcube | Bullseye (Debian 11) | 3.9.2 | 6.1.21 (64-bit) | **32-bit** |
| K3D (k3) | Bookworm (Debian 12) | 3.11.2 | 6.12.87 | 64-bit |
| tri-zero | Trixie (Debian 13) | not re-checked | not re-checked | not re-checked |

(doomcube and K3D read live 2026-10-19. A Pi 4 can boot a 64-bit kernel over 32-bit userland, which is what doomcube
does; `getconf LONG_BIT` shows the userland.)

**Is one OS version faster for Klipper? No measured evidence either way.** A web search found no Klipper benchmark
across Bullseye/Bookworm/Trixie, and nothing has been measured on this fleet. Expectation, not data: the hot paths
(step compression, kinematics) are C via cffi, and the MCUs do the real-time stepping, so the host only has to stay
ahead of the queue. The part that could differ is klippy's pure-Python work (gcode parsing, lookahead, Jinja macros,
mesh math): CPython 3.11+ is generally faster than 3.9, and 64-bit userland helps a little. Core isolation and the
`performance` governor are worth far more than the OS version. **Do not upgrade for speed; upgrade for support.**

Reasons that do justify upgrading (from Debian's published schedule, not re-checked here): Bullseye's Debian LTS window
ended in August 2026, so doomcube is on an unsupported base; newer Klipper/Moonraker/Kalico releases track newer Python.
Python 3.13 on Trixie needed `greenlet` >= 3.1.0; tri-zero runs Kalico on Trixie, so that is resolved for this fleet.

To measure before committing to a move, compare the `sysload` and `cputime` fields on the `Stats` lines in `klippy.log`
while printing the same gcode on the same host before and after. Different printers are not comparable.

### Upgrading to the next major version

**Recommendation: reflash, do not `dist-upgrade`.** Raspberry Pi supports fresh installs only, and in-place major
upgrades are known to break. Klipper hosts are cheap to rebuild because everything that matters is in git or in
`~/printer_data`, and a reflash keeps the old card as an instant rollback.

Order, easiest and least risky first:

1. **tri-zero**: already Trixie, the reference build. Copy its package and service choices.
2. **K3D**: Bookworm -> Trixie, already 64-bit. Reflash is easy; an in-place `apt` upgrade is the least bad
   fallback here.
3. **doomcube**: Bullseye is 32-bit userland, which **cannot be converted to 64-bit in place**, and an in-place path
   would have to step 11 -> 12 -> 13 (no skipping). Reflash only.

Reflash procedure (per host, printer idle, do not touch the running card):

1. **Capture state** from the old host: `~/printer_data/config` (already in git), `~/printer_data/database`
   (Moonraker DB: history, Spoolman and update-manager state), `~/printer_data/gcodes`, crowsnest/KlipperScreen config,
   `/etc/udev/rules.d`, CAN config (`can0` interface file, doomcube), `/etc/sudoers.d`, Wi-Fi/static-IP settings, and
   `klipper_mcu` build config if the host MCU is used. Record `pip freeze` and `systemctl list-unit-files --state=enabled`.
2. **Flash a spare card/SSD** with Raspberry Pi Imager (64-bit, Lite for headless): set hostname, user `pi`, SSH key and
   Wi-Fi in the customization step so it boots reachable.
3. **Install the stack** with KIAUH: Kalico/Klipper, Moonraker, the web UI, crowsnest, KlipperScreen as needed. MCU
   firmware is not touched by an OS change; do not reflash MCUs.
4. **Restore** `printer_data` and the OS-level files from step 1, then `scripts/rpi-tune.sh [--overclock]` (set the
   governor once, see Gotchas), and reboot.
5. **Verify** with the block above, plus `FIRMWARE_RESTART` only once Klipper reports `ready` and every MCU and `can0`
   is present. No motion until you choose to home.
6. **Keep the old card** labeled and untouched for a week. Rollback is swapping it back.

If an in-place upgrade is ever attempted anyway: full card image first, change `sources.list`/`sources.list.d` to the
next codename, `apt update && apt full-upgrade`, answer config-file prompts by keeping local versions of `cmdline.txt`,
sudoers and NetworkManager files, reboot, then re-run Verify. Over SSH only, a networking change (dhcpcd to
NetworkManager) can lock you out; have physical access.

## Gotchas

- Hosts with a BTT EBB36 toolboard have hung at boot with the board attached (tri-zero history). Unplug USB
  toolboards before the reboot, replug, then `FIRMWARE_RESTART`. doomcube's EBB36 is on CAN and rebooted cleanly.
- `cmdline.txt` must stay a single line. Some images ship a trailing blank line, so appending with `sed 's/$/ flag/'`
  puts the flag on a second line and duplicates it. The script strips newlines first; do the same by hand
  (`tr -d '\n'`) and check `wc -l` is 1.
- `iw` is not installed on trixie images; that is why Wi-Fi power save uses a NetworkManager drop-in there. Bullseye
  hosts (doomcube) have `/usr/sbin/iw` and use a udev rule (`070-wifi-powersave.rules`).
- The governor can already be persisted by `/etc/default/cpufrequtils` (`GOVERNOR="performance"`, present on K3 and
  doomcube). Do not stack the `tmpfiles.d` rule on top; both set the same value but there should be one owner per host.
- `rtk` can mangle `ls`/`grep` output when verifying over SSH; use `/bin/ls` or `/usr/bin/grep` if counts look wrong.
- Rollback: restore `/boot/firmware/cmdline.txt.pre-tune` and `config.txt.pre-tune`, delete the four files the script
  writes (`cpu-affinity.conf` x2, `wifi-powersave-off.conf`, `cpu-governor.conf`), `systemctl daemon-reload`, reboot.

## Applied hosts

| Host | OS | Date | Clock | Governor set by | Notes |
| --- | --- | --- | --- | --- | --- |
| vcore3 (rat-race) | | before 2026-10-19 | 2100 MHz, watercooled | `performance` set 2026-10-19 (was `ondemand`, moot under `force_turbo`) | Reference; klipper unit edited in place rather than a drop-in |
| tri-zero (mini-trip) | Trixie | 2026-10-19 | 2000 MHz, heatsink+fan | `tmpfiles.d` (script) | Via `scripts/rpi-tune.sh --overclock` |
| doomcube | Bullseye | 2026-10-19 | 2000 MHz, `over_voltage=6` | `cpufrequtils` | Already had isolation, `DefaultCPUAffinity`, `CPUAffinity=3` in the unit, udev Wi-Fi rule. Only `usbcore.autosuspend=-1` added by hand to `/boot/cmdline.txt` (backup `.pre-tune`). CAN toolhead |
| K3D (k3) | Bookworm | 2026-10-19 | 1500 MHz stock (rev 1.1) | `cpufrequtils` | Via `scripts/rpi-tune.sh` without `--overclock` (script version before the governor change; governor was already `performance`). USB Beacon + main MCU; rebooted cleanly |

doomcube and K3D verified after reboot against the Verify block (isolated `3`, klippy `3`, moonraker `0-2`, autosuspend
`-1`, `get_throttled` `0x0`, Klipper `ready`, all MCUs present). tri-zero and vcore3 were verified when applied.

# Tri-Zero clean Kalico install

The active `printer.cfg` now uses local Kalico configuration and Doomcube's
reviewed lifecycle. RatOS is not loaded. This is an offline source migration;
the rebuilt machine has not been commissioned or print-tested.

## Install state (2026-10-14, host `pi@192.168.30.80`)

Kalico `v2026.10.00-98-ga6796621`, Moonraker, Mainsail and klipper_tmc_autotune are installed; Octopus Pro H723,
EBB36 v1.2 and the Klipper Expander are Katapult-flashed and connected by USB. `~/printer_data/config` is a git checkout of this repo's `main` (set up 2026-10-19; the Pi has a GitHub deploy key). A daily
cron job (`5 4 * * *`: `git add .; git commit -m 'automated backup'; git push`, the fleet standard) commits and pushes Pi-side
changes, including `klipper-variables.cfg` and `SAVE_CONFIG` output. Update the Pi with `git pull` there; do not rsync into it. Since 2026-10-20 a second cron job (`*/10 * * * *`, `git pull --rebase --autostash`) pulls `main` automatically, and the 04:05 backup now pulls before pushing; both share a `flock` on `/tmp/config-git.lock`. A pull never restarts Klipper: run `RESTART` to load new config. Pull log: `/tmp/config-pull.log`.
The pre-deploy stub config is backed up in `~/config-backup-20261014`.
Layout follows the fleet (K3D/Doomcube):

- `printer.cfg`: entrypoint, `_PRINTER_VARS`, absolute includes, SAVE_CONFIG block.
- `custom/mcus/`: one file per board (serials, pin aliases, MCU temp sensors). Expander MOSFET0-3 = PA0-PA3.
- `custom/tri-zero/` (fleet layout, as `custom/doomcube/`): `tri-zero.cfg`, `hardware.cfg`, `limits.cfg`, `steppers.cfg` + `steppers/{xy,z}/`, `sensorless-homing/`. `custom/default_includes.cfg` owns persistence and pause/resume; `custom/mcus/rpi.cfg` owns `[virtual_sdcard]`.
- `custom/fans/`, `custom/sensors/`, `custom/macros/`, `custom/tuning/`.
- Persistence is `klipper-variables.cfg` (fresh install; legacy RatOS keys dropped). `mainsail.cfg` is not included
  (the fleet macros own PAUSE/RESUME/CANCEL_PRINT). KAMP is not used (fallback purge).
- TMC Autotune is enabled. Shake&Tune is not installed. `custom/tuning/resonance.cfg` is disabled until the EBB36
  firmware is rebuilt with `CONFIG_WANT_ADXL345=y`; the Octopus ADXL inherited from RatOS was removed.

Installed-version checks (2026-10-19): Kalico parses the full config and compiles every template (69); `scripts/verify_migration.py`
and the 11 recorder regressions pass on the host (they need the Pi's absolute `/home/pi/...` includes, so run them there from
`~/printer_data/config/scripts` with `/home/pi/klippy-env/bin/python`). Klipper reaches `ready` with all three boards connected.
The 2026-10-14 `ADC out of range` shutdowns are resolved: the bed and EBB36 hotend sensors are wired and read plausible values.
The EBB36 has previously hung the Pi at boot when attached; unplug it before rebooting, replug, then `FIRMWARE_RESTART`.

Added 2026-10-19: BTT SFS V2.0 on Octopus (`custom/sensors/sfs.cfg`; switch `PG12`, motion `PG13`, aliases in
`custom/mcus/octopus-pro-h723.cfg`; `PG13` doubles as the unused `z0_diag_pin`). ZeroClick probe moved to EBB36 `PA4`
(alias `toolboard_t0:probe_pin`, pull-up, polarity unchanged). Parsed and `ready` on the host; sensor polarity and probe
attach/detach states not yet exercised.
Bed wired and enabled (`[heater_bed]`, watermark control until an attended `PID_CALIBRATE`; thermistor reads room temp).
Hotend now uses MPC: `custom/hotends/tk.cfg` is identical to Doomcube's (same hotend/heater/PT1000; `heater_power 80`,
`cooling_fan: fan`, max_temp 500) and is the single owner of hotend model/limits; `hardware.cfg` keeps only wiring
(pins, pull-up). The stale earlier-build extruder PID block was removed from SAVE_CONFIG. MPC is uncalibrated: run
`MPC_CALIBRATE HEATER=extruder FAN_BREAKPOINTS=7` attended (heats to 200 C) before any hotend heating. Doomcube's saved
MPC constants were deliberately not copied. Pi tuning from vcore3 is staged in `scripts/rpi-tune.sh` (not yet applied; needs reboot).

Assumptions needing physical confirmation:

- Chamber thermistor on Octopus T0 (PF4): reads a plausible ~25 C NTC 100K value; type assumed
  `NTC 100K MGB18-104F39050L32`. PF3 and PF5 read open.
- Fan headers are confirmed (live `SET_FAN_SPEED` test, 2026-10-19; aliases in `custom/mcus/octopus-pro-h723.cfg`): FAN0 PA8 deck bay
  electronics, FAN1 PE5 chamber filter, FAN2 PD12 + FAN3 PD13 aux part cooling, FAN4 PD14 + FAN5 PD15 motor cooling;
  Expander MOSFET2 (PA2) + MOSFET3 (PA3) stepper-driver fans (MOSFET0/1 tested empty).
- Retained earlier-build values (currents, 50,000 mm/s2, PID, probe offset, input shaper, skew) are not requalified.

## Ownership and retained hardware

Board pin aliases live in `custom/mcus/`; drivers, extruder and kinematics in `custom/tri-zero/hardware.cfg`,
with Z drivers owned by `custom/tri-zero/steppers/z/steppers.cfg`. Rapidburner, Sherpa Mini 10T, triple-Z, fan and limit
profiles remain authoritative. RatOS files were removed.

The entire `SAVE_CONFIG` block is unchanged except the removed bed PID block (see Install state): PID, probe offset,
mesh, input shaper and skew profiles remain calibration history. The old saved
mesh named `ratos` is not automatically loaded. Existing limits (including
50,000 mm/s²) and calibration numbers describe the earlier build; they are not
newly qualified values for the rebuild.

ZeroClick keeps the original physical route:

- Attach: `(1,100) -> (1,118) -> (28,118) -> (28,100) -> (1,100)`.
- Detach: `(1,100) -> (28,100) -> (28,118) -> (1,118) -> (1,100)`.

It reads the probe after `QUERY_PROBE` executes: triggered means detached; open
means attached. Docking requires XY homing, raises clearance when Z is known,
and verifies the resulting probe state. Probe-operation wrappers own attachment
and detachment; there are no moving `activate_gcode`/`deactivate_gcode` hooks.
A failed probe operation stops without attempting a blind dock move.
`PROBE_CALIBRATE` detaches and returns to the successful post-probe position for
manual calibration. Sensorless homing retains the effective root currents
(X: 0.82 A, Y: 0.69 A), applies them to both CoreXY motors, and restores both
configured run currents and acceleration on error or success.

## Lifecycle and slicer compatibility

New profiles can call:

```gcode
PRINT_START HOTEND_TEMP=260 BED_TEMP=100 MATERIAL=ABS TOOL=0
PRINT_END
```

The legacy `START_PRINT EXTRUDER_TEMP=... BED_TEMP=... INITIAL_TOOL=...` alias
remains, including comma-separated temperature lists and its former `M83`
relative-extrusion contract. `END_PRINT` also remains. New `PRINT_START` callers
must set their intended extrusion mode in slicer start G-code.

Startup warms the nozzle to 150°C for probing, uses the interruptible SD hold,
then performs tilt, final Z home, adaptive mesh, final nozzle heating and a small
line purge. The saved skew profile is applied only after probing/purge. There
is no Beacon, fake `T0`, mandatory KAMP or MMU dependency. Nonzero slicer filament
slots are ignored when no enabled tool system exists. The guarded MMU paths are
available if Happy Hare is installed/configured later; this machine has no MMU
hardware configuration or MMU qualification today.

No chamber sensor is configured. A positive `TARGET_CHAMBER_TEMP` or legacy
`CHAMBER_TEMP` fails preflight before startup heat/motion. Soak defaults to zero
until a rebuild-specific policy is selected. Bed-controlled cooldown remains
available for warp-prone materials. Normal completion retains Z motor support;
cancellation shuts heaters down and cancels SD before optional cleanup, without
homing or parking. Notifications are local console messages until a Moonraker
notifier is configured.

## Verification and commissioning

Source validation:

```sh
python scripts/verify_migration.py --kalico-source /path/to/kalico
KALICO_SOURCE=/path/to/kalico python -m unittest discover -s scripts -p test_migration.py
```

Jinja2 is required. The verifier uses Kalico's real include/SAVE_CONFIG parser
and compiles every active G-code template; it does not instantiate firmware
modules or connect to MCUs. Recorder regressions exercise docking checks,
homing failure cleanup, calibration return position, startup temperature,
slicer compatibility and cancellation order.

After the hardware is available, commissioning still needs board/pin and heater
checks, probe switch polarity and dock clearance, sensorless homing, all three
Z directions, tilt/probe repeatability, fresh Z offset/PID as appropriate, and
start/pause/resume/cancel/timeout/print tests. Test the unknown-Z clearance hop
with the bed away from its travel limit. Revalidate the retained motion limits,
input shaping and extrusion calibration for the rebuild before using them at
full performance.

Reference source inspected: local Kalico `84a4105726e22c5c15943e791b5cdb3beff52e77`
(configuration parser, homing override, probe/manual probe, safe-Z homing), and
RatOS configuration `7582e8cc0d9a89f282d29b24a2b36e0c9e97419c` for inherited
Voron V0.1 bed thermistor and sensorless behavior. The local printer profiles,
not the upstream defaults, supply physical docking geometry and overrides.

## Display (2026-10-19)

HelixScreen v1.0.5 (`curl -sSL https://releases.helixscreen.org/install.sh | sh`, systemd service `helixscreen`, install dir
`~/helixscreen`, config dir `~/printer_data/config/helixscreen/`, Moonraker update-manager entry) drives the 800x480 HDMI-A-2
panel. KlipperScreen is not installed (`KlipperScreen.conf` in this repo is unused). The panel is mounted upside down:
`display.rotate: 180` in `~/helixscreen/config/settings.json` (software rotation; DRM has no hardware rotation here). That
file lives in the install dir and is not in the git backup. The USB touch controller is a QDtech MPI5001 (`event4`); it can
enumerate late, so `sudo systemctl restart helixscreen` after replugging it. The printer type is left unset for the user to
choose on the first-run wizard. The polkit power-off/reboot rule failed to install, so on-screen Shutdown/Reboot may be refused.

## Stepper buzz results (2026-10-20)

- Z: `stepper_z` = back motor, `stepper_z1` = front right, `stepper_z2` = front left (viewed from the front). Matches `[z_tilt]` `z_positions` order in `custom/probes/zeroclick.cfg`. All three move the bed the same way: (-) toward the toolhead, (+) away. Z directions are correct as configured (z2 has `!z0_dir_pin`).
- XY: with the original pin assignment `G1 X10` went right but `G1 Y10` went forward, so the CoreXY A/B roles were mirrored. dir pins cannot fix that, so the X and Y driver slots are swapped in `custom/mcus/octopus-pro-h723.cfg` (`x_*` = MOTOR 1, `y_*` = MOTOR 0); `hardware.cfg` now uses the aliases and `printer.cfg` no longer sets `dir_pin`. Re-verify `G91` / `G1 X10` (right) and `G1 Y10` (back) after deploying, then sensorless homing.

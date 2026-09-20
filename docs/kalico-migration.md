# Tri-Zero clean Kalico install

The active `printer.cfg` now uses local Kalico configuration and Doomcube's
reviewed lifecycle. RatOS is not loaded. This is an offline source migration;
the rebuilt machine has not been commissioned or print-tested.

## Install-specific work

1. Install Kalico and Moonraker for user `pi` with the usual
   `~/printer_data/{config,gcodes,comms}` layout. Use Kalico, not upstream Klipper:
   these macros require native Python (`!!include`), synchronous `emit`,
   `set_gcode_variable`, `wait_moves`, and `SET_KINEMATIC_POSITION SET_HOMED/CLEAR_HOMED`.
2. Flash the Octopus Pro H723 and EBB36 v1.2 using their actual bootloader/USB
   settings. In `custom/kalico/mcus.cfg`, replace both clearly marked serial
   placeholders with the resulting `/dev/serial/by-id/...` paths. No RatOS udev
   rules or Linux host MCU are needed by this configuration.
3. Use this repository as `~/printer_data/config`, including its existing
   `ratos-variables.cfg`. That filename is intentionally retained: existing keys
   are not renamed/deleted, and fleet state keys are added by startup macros.
   Moonraker's UDS path is `/home/pi/printer_data/comms/klippy.sock`.
4. Install a normal Mainsail/Fluidd frontend separately. `moonraker.conf` no
   longer loads RatOS defaults, its frontend fork, or its theme/update managers.
   Existing authorization settings are retained.
5. Shake&Tune and TMC Autotune profiles are retained but commented out in the
   entrypoint so a clean Kalico installation has no missing extension dependency.
   Install those packages before enabling the corresponding includes. Standard
   TMC drivers use the retained currents and `driver_SGT: 1`, matching the prior
   autotune sensorless threshold selection. Disabling autotune is not evidence
   that its complete driver register tuning has been reproduced.

The serial placeholders deliberately prevent connection until the boards are
identified. Nothing in this migration flashes, restarts, or moves the printer.

## Ownership and retained hardware

`custom/kalico/hardware.cfg` contains this printer's generated board pin aliases,
base drivers, thermistor and heater definitions. Local rapidburner, Sherpa Mini
10T, triple-Z, fan and limit profiles remain authoritative. `RatOS.cfg`, the old
sensorless files and the external `RatOS/` symlink are inactive historical files.
They are not edited or required by the active include chain.

The entire `SAVE_CONFIG` block is byte-for-byte unchanged: PID, probe offset,
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

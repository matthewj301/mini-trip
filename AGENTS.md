# Mini-Trip / Tri-Zero rebuild — agent instructions

This is the actual Tri-Zero printer config. The sibling `tri-zero` repository
contains mechanical designs. User direction (2026-09-20): migrate this rebuild
to the shared infrastructure whose master is Doomcube. The user confirmed a fresh Kalico flash. Existing config uses RatOS; replace
its dependencies in the migration rather than layering duplicate lifecycle macros.

## Boundaries

Finish the requested outcome, preserve unrelated work and report source checks,
runtime checks and physical qualification separately. Do not copy another printer's
calibration, limits, motor currents, pins, probe offsets or firmware assumptions.
Historical settings describe the earlier build; verify them for the rebuilt hardware.
RatOS is gone; do not edit SAVE_CONFIG as a shortcut. Changes to ownership/includes must be explicit and preserve calibration.
Documentation and local checks do not authorize deployment, flashing or motion.

## Task routes

| Task | Read |
| --- | --- |
| Shared macro migration or interface change | [Fleet route](docs/fleet.md), `fleet.json`, master contract and findings |
| Hardware or active config | `printer.cfg` includes, `custom/mcus/`, `custom/tri-zero/`, toolhead/stepper profiles; [install state](docs/kalico-migration.md) |
| Homing or leveling | `custom/probes/zeroclick.cfg`, `custom/probes/probe_macros.cfg` |
| Lifecycle or saved variables | `custom/macros/`, `custom/default_includes.cfg`; `klipper-variables.cfg` is the persistence target |
| Firmware tuning | Available `klipper-prod` skill; characterize the rebuilt machine rather than importing tuned values |

Trace includes from `printer.cfg`; absolute `/home/pi/...` includes map to this checkout.
Resolve installed firmware and macro ownership before replacing start/end/pause/
resume/cancel or probe hooks. Fix and verify master defects before propagating them.

The Pi's `~/printer_data/config` is a checkout of `main` with a daily automated-backup job: update it with `git pull`, never rsync into it, and expect `klipper-variables.cfg` and SAVE_CONFIG to be committed from the Pi. Display/touch notes are in [install state](docs/kalico-migration.md).

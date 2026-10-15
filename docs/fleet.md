# Tri-Zero shared infrastructure adoption

Doomcube is the master: read [fleet contract v1](../../doomcube/docs/fleet/v1/contract.md)
and its [unresolved findings](../../doomcube/docs/fleet/v1/findings.md) before porting.
Local [fleet.json](../fleet.json) records observed capabilities and migration boundaries.
The master checkout and versioned baseline are explicit source dependencies.

The user selected this direction on 2026-09-20. The user confirmed a fresh Kalico flash for the rebuild. Current source still
uses RatOS; no shared lifecycle has been enabled. RatOS compatibility is not a
target requirement, but its hardware/probe/calibration details must be preserved. This is migration context, not evidence that
adoption is finished, and not a request to perform migration during unrelated work.

Adoption sequence:

1. Use the confirmed fresh Kalico target and record the installed revision when flashed.
   Resolve the rebuilt hardware. Preserve this machine's
   pin map, triple-Z geometry, ZeroClick docking, limits and calibration history.
2. Resolve the existing RatOS lifecycle/probe include chain from installed or matching
   source. Inventory commands the custom probe and M106/M107 overrides depend on.
3. Select applicable Doomcube modules after master defects pass their regression
   checks. Do not import Beacon/MMU/QGL/chamber-fan hardware dependencies by default.
4. Establish one lifecycle owner and an explicit persistence migration. Adapt probe,
   leveling, fan and purge integration to this build; preserve public slicer inputs.
5. Run source/template checks, installed-version validation and then an authorized
   calibration/physical qualification session. A source-only migration is unqualified.

Run the read-only inventory from Doomcube:
`python3 scripts/fleet/check.py --repos . ../K3D ../rat-race ../mini-trip --json`.
It reports incomplete external dependencies; it does not replace the RatOS or Kalico
parser. Snapmaker is outside this infrastructure family.

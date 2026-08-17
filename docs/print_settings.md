# Print settings — starting values (Bambu Lab A1 mini, PETG, 0.4 mm)

These are **conservative starting points, not universal truths**. Tune to
your filament and printer. Both parts print **as oriented in the STL** —
carrier base flat on the plate, no rotation, **no supports**.

## Full carrier — `exports/lilygo_a7670_simhat_carrier.stl`

| Setting | Start value | Why |
|---|---|---|
| Layer height | 0.20 mm | ledges/bridges are 2.2–2.6 mm; even layers matter more than speed |
| First layer | 0.24 mm | |
| Wall loops | **4** (1.6 mm) | rails are 3.2 mm → solid-ish walls, clips get perimeter strength |
| Top/bottom | 4 / 4 | base is 3.2 mm → fully printed top+bottom shells |
| Infill | 15 % Gyroid | frame carries load in the rails, not the infill |
| Filament | PETG | as specified; do NOT print clips in PLA (brittle at flex roots) |
| Nozzle/bed | 250 °C / 80 °C | typical PETG start point |
| Cooling | 30–50 % fan | some fan helps clip detail; too much hurts layer bonding |
| Elephant foot | 0.2 mm | keeps outer rails/ears within tolerance |
| Brim | **Not needed** | large flat base, low warp risk |
| Supports | **None** | all overhangs are ≤2.6 mm bridges or grow from the plate; antenna tray walls are 4.5 mm vertical flanges — support-free |
| Orientation | As exported | clip arms flex in-plane with layers — do not reorient |

Clip-critical note: the snap arms are 2.0 mm thick = 4 perimeters at 0.4 mm
nozzle, no infill dependence. If you must choose, favor **more walls over
more infill**.

## Snap-fit test coupon — `exports/simhat_clip_test.stl` (print this FIRST)

Same settings as above; takes ~20 g of filament. Four bays:

| Bay position | Notches | XY clearance |
|---|---|---|
| bottom-left | 1 | 0.20 mm |
| bottom-right | 2 | 0.30 mm |
| top-left | 3 | 0.40 mm |
| top-right | 4 | 0.50 mm |

Test with a scrap of PCB-material of matching thickness (or the SimHat
itself, relay side down, gently): the target bay holds the board with a
clear click, releases with light finger pressure on the fins, and shows no
white stress marks at the flex roots after ~10 cycles. Then set
`SIMHAT_PCB_XY_CLEAR` in `cad/parameters.py` to the winning value and
rebuild (`python scripts/build.py`).

## Low-profile fit-check template — `exports/lilygo_a7670_simhat_carrier_lowprofile.stl`

Same material settings; only 9 mm tall, ~15–20 minutes, ~8 g. Purpose:
verify XY dimensions and the M1.6 hole pattern with real screws before
committing to the 2 h full print. Lay the A7670X on the 4 bosses (18650
holder hangs through the open frame); sight the SimHat outline against
the pad/lip/fence footprint at a desk edge (relay overhangs below).

## Sections — `exports/sections/*.stl`

Same settings; each section is a standalone printable piece (A7670 plate,
SimHat cage, antenna tray + end wall with its 2 mounting tabs). Use to
re-print just one region after a parameter tweak instead of the whole
carrier. They are a volume-partition of the full carrier — iterate and
verify with them, then rebuild the whole.

## After-print checks

- Caliper the SimHat bay: PCB should slide in with the coupon's chosen feel.
- Inspect clip roots for delamination lines (if present: raise bed/nozzle
  temp 5 °C, slow outer walls to 50 %).
- M1.6 pilots: an M1.6 screw should need 2–3 firm turns to bite; if it
  spins, drop `A7670_PILOT_D` to 1.25 and rebuild.

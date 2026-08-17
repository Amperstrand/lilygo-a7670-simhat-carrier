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

## After-print checks

- Caliper the SimHat bay: PCB should slide in with the coupon's chosen feel.
- Inspect clip roots for delamination lines (if present: raise bed/nozzle
  temp 5 °C, slow outer walls to 50 %).
- M1.6 pilots: an M1.6 screw should need 2–3 firm turns to bite; if it
  spins, drop `A7670_PILOT_D` to 1.25 and rebuild.

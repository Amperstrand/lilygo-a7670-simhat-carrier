# Print settings — starting values (Bambu Lab A1 mini, PETG, 0.4 mm)

These are **conservative starting points, not universal truths**. Tune to
your filament and printer. Both parts print **as oriented in the STL** —
carrier base flat on the plate, no rotation, **no supports**.

## PRINT THIS FIRST: calibration mini-coupon — `exports/lilygo_calicheck_mini.3mf`

**~21 g, ~13-18 min, one plate, no supports, no brim.** Open the 3MF in
Bambu Studio and slice at 0.28-0.32 mm / 2-3 walls / 5-10 % gyroid.
Enable thin-wall detection (the Ø1.2-1.6 gauge holes and clip arms need
single-perimeter walls).

Layout (as sliced, plate on bed):

| Feature | Where | What to report back |
|---|---|---|
| M1.6 pilot-hole ladder Ø1.20→1.60 | top-right row, left→right increasing | smallest Ø an M1.6 screw taps into snugly |
| PCB thickness stair 1.0/1.2/1.4/1.6 | left wall, bottom→top | which slit the T-SimHat edge slides into freely |
| Antenna width slits 19.8/20.2/20.6 | left-of-center tall blocks, bottom→top | which slit the sticker slides through with light drag |
| Snap-clip bay (production geometry) | right side | does the SimHat clip-end (relay DOWN, as installed) snap under the hooks and release with finger pressure? |

This coupon calibrates the four printer-dependent numbers the whole
design leans on. Report the three numbers + clip feel, then the full
carrier prints with confidence.

## Second: Gridfinity fit-check tray — `exports/lilygo_fitcheck_tray_gridfinity.3mf`

Open the **3MF directly in Bambu Studio** (File → Open) and slice with:

| Setting | Fast (target ~15 min) | Balanced |
|---|---|---|
| Layer height | 0.32 mm | 0.28 mm |
| Wall loops | 2 | 3 |
| Top / bottom | 3 / 2 | 4 / 3 |
| Infill | 5 % Gyroid | 10 % Gyroid |
| Speeds | default Draft profile | default profile |
| Brim / supports | none / none | none / none |

Model is ~16.7 g of PETG → expect **12–18 min** on an A1 mini. Enable
"Arachne"/thin-wall detection so the Ø1.25 gauge pins slice cleanly (they
print as a single perimeter spiral). The tray is deliberately NOT durable:
1.2 mm walls, 0.6 mm floors.

**What it verifies (in one print):**
1. A7670X **hole pattern** — drop the board (battery installed is fine)
   over the 4 pins; all 4 engage = positions correct. Pin Ø1.25 fits the
   modelled drill; the plated Ø1.73 spec stays a caliper/screw check.
2. A7670X **outline** — board lands on its support rib without touching
   fences/walls.
3. SimHat **outline + cage XY** — relay-down board rests flat, edges at
   0.3 mm from the three fence gauges.
4. Antenna sticker **fits the 110 × 20 channel** and slides to the stop.

After the check it stays useful: it clips onto any **Gridfinity 3 × 4
baseplate** (or sits on the desk) as a tray for the boards + antenna
during assembly. Boards sit proud of the low walls by design.

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

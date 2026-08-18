# Assembly & service guide

## Parts needed

| Part | Qty | Note |
|---|---|---|
| Printed carrier | 1 | PETG, settings in `print_settings.md` |
| M1.6 × 8 mm pan-head screws | 4 | A7670X (self-tap into printed pilots) |
| M3 screws + nuts or enclosure bosses | 4 | carrier→enclosure (or VHB tape instead) |
| Jumper wires (Dupont / harness) | as needed | boards are NOT plugged into each other |

## Install the T-SimHat (tool-less, do this first)

Orientation: **relay + terminal block face DOWN** (toward the carrier),
pin-header sockets face UP.

1. Tilt the board ~15°, relay side down.
2. Feed the FAR end (header-socket end, away from release tabs) under the
   fixed capture lip first, then lower the near end toward the support pads.
3. Press the near (clip) end down firmly with a thumb over each clip until
   both hooks click over the PCB edge. The board is now captured in X, Y,
   Z and rotation.

Routing tip: pre-attach jumper wires to the up-facing headers before
snapping the board in — the sockets are fully accessible either way, but
pre-wiring is faster.

## Install the LTE sticker antenna (tool-less)

The full-band sticker antenna (SMA coax) lives in the slide-in tray at the
far end of the carrier, flat on the tray floor.

1. Before printing, caliper the sticker and set `ANT_SLIDE` (dimension
   along the slide direction = the sticker's SHORTER side) and `ANT_W` in
   `cad/parameters.py`, then rebuild — the tray, frame and envelope check
   all resize from those two numbers.
2. Feed the coax through the notch in the frame rail, connector first,
   from the tray side toward the boards.
3. Slide the sticker into the channels (flared mouths self-guide it) until
   it touches the end stop. It sits flat by construction; the adhesive
   backing is optional — sticking it down makes it permanent.
4. Screw the SMA plug onto the modem's MAIN RF jack (either SMA if you
   also use GNSS). Route spare coax through the cable-tie slots.

## Install the T-A7670X

Orientation note: the board mounts **rotated 180°** (`A7670_ROT_180`) so
its pin headers face the SimHat sockets across the wiring channel —
jumpers stay ~15–25 mm. Mounting is **screwless by default**: four
christmas-tree snap plugs (no screws needed).

1. Fit the 18650 into the board's under-side holder first (if used).
2. Lower the board **straight down** over the four plugs near the
   clip-end and USB-end corners; the plug fins flex through the PCB
   holes and click above the board. Press each corner until seated.
3. Removal: pull the board straight up firmly (all four plugs release);
   a spudger under an edge helps. `A7670_MOUNT = "screws"` in
   `cad/parameters.py` restores the M1.6-pilot variant if you later
   want screws.
4. USB-C (away from the SimHat), SIM tray, buttons, battery JST and
   both SMA jacks stay accessible.

## Wire the boards

- Jumpers run from the SimHat headers across the 12 mm center channel to
  the A7670 edge pins. Nothing passes under either board.
- Use the 8 cable-tie slots in the channel rails for bundling/strain
  relief — 3.6 × 7 mm slots take standard mini cable ties.
- Antennas: SMA jacks are clear on the board's long edges; route cables
  out over the frame edge nearest your enclosure cable glands.

## Mount the carrier in the enclosure

- **Screws:** 4 M3 slotted points. Two corner ears at the +Y end; two
  slotted tabs on the antenna-tray end wall at −Y (slots run fore-aft, so
  boss spacing tolerance is ±3 mm on both axes). Loosely fit all four,
  align, tighten.
- **Tape instead:** two 24 × 24 mm flat pads under the board centerlines
  accept VHB tape; frame underside is flat there by design.
- **Low-profile template as a wall bracket:** the 9 mm template can be
  screwed flat against an enclosure wall through its 4 M3 ear slots;
  boards face outward. (No snap clips on that variant — retention is
  screws for the A7670X and gravity/lip for a laid-in SimHat; use the full
  carrier for proper tool-less retention.)

Do not drill the enclosure shell — either method works with stock bosses
or a flat internal surface.

## Service

**Remove the T-SimHat** (no tools): squeeze both release fins toward each
other (or press each outward individually) → hooks release the PCB edge →
lift the clip end ~0.2 mm → slide the board ~4 mm toward the clips (away
from the fixed lip) → lift out. The relay never touches anything on this
path (validated against the manufacturer STEP).

**Remove the T-A7670X**: unscrew 4 × M1.6 → lift straight up. Clearance
above is unobstructed.

**Terminal-block wiring note**: the relay's screw terminals face down
toward the base. Wire them BEFORE snapping the SimHat in, or remove the
board (10 s, tool-less) to change terminal wiring later.

## What to check before first trust in the print

1. Coupon fit result transferred to `SIMHAT_PCB_XY_CLEAR` (if not 0.30).
2. Caliper the SimHat PCB thickness — if it is 1.6 mm not 1.0 mm, increase
   `SIMHAT_PCB_T_CLEAR` to taste (0.2 mm default still functions; the
   cage gap self-adjusts by design margin) and rebuild.
3. Caliper the antenna sticker (L × W) and coax; set `ANT_W` (long dim),
   `ANT_SLIDE` (short dim), `ANT_CABLE_L` and rebuild.
4. Confirm whether your A7670X has the 18650 holder (default assumes yes,
   25 mm standoffs) and whether stacking-header pins are soldered (25 mm
   already clears them).
5. Optional 15-minute sanity print: the low-profile template
   (`exports/lilygo_a7670_simhat_carrier_lowprofile.stl`) — lay each board
   on it: A7670X holes should drop over the 4 bosses for a real M1.6 screw
   fit; SimHat outline should match the pad/lip/fence footprint (relay
   overhangs through the open frame — test at a desk edge).

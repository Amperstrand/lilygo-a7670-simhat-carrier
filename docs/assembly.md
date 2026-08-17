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

1. Lower the board onto the 4 standoff bosses, PCB holes over the pilots.
   USB-C, SIM tray, buttons, battery/JST and both SMA antenna jacks are
   all on accessible edges/faces (nothing faces the base).
2. Drive 4 × M1.6 screws straight down. They self-tap the PETG pilots —
   first assembly only needs ~1 Nm; stop at snug. Do not overtighten.

## Wire the boards

- Jumpers run from the SimHat headers across the 12 mm center channel to
  the A7670 edge pins. Nothing passes under either board.
- Use the 8 cable-tie slots in the channel rails for bundling/strain
  relief — 3.6 × 7 mm slots take standard mini cable ties.
- Antennas: SMA jacks are clear on the board's long edges; route cables
  out over the frame edge nearest your enclosure cable glands.

## Mount the carrier in the enclosure

- **Screws:** 4 M3 slotted ears at the frame corners. Slots are 7.5 mm
  long, so ±3 mm of boss-spacing tolerance per ear. Loosely fit all four,
  align, then tighten.
- **Tape instead:** two 24 × 24 mm flat pads under the board centerlines
  accept VHB tape; frame underside is flat there by design.

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
3. If your A7670X has stacking-header pins soldered underneath, set
   `A7670_STANDOFF_H = 21.0` and rebuild before printing.

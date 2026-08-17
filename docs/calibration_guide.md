# Calibration coupon — check & feedback guide

Companion image: `exports/lilygo_calicheck_guide.png` (same picture is
served on the LAN). Work through the four numbered tests in order, then
the secondary checks, then paste the template at the bottom back to me
(filled in) together with photos.

## ① M1.6 hole ladder — top-right, 5 holes left→right

The holes are Ø 1.20 / 1.30 / 1.40 / 1.50 / 1.60 mm (labels under each).

**Do:** try an M1.6 screw in each hole, left to right. In the small ones
it should bite (feels like it's cutting a thread); in the big ones it
spins freely.

**Report:** the smallest hole where the screw still *bites*.
That number +0.1 mm becomes the self-tap pilot diameter in the 8.5 mm
deep standoff bosses (`A7670_PILOT_D`). The coupon plate is thin, so
bite here is conservative — the deep boss grips better.

## ② PCB thickness stair — left wall, bottom→top

Four horizontal slits, heights 1.0 / 1.2 / 1.4 / 1.6 mm.

**Do:** slide the T-SimHat's short edge into each slit from the side,
bottom to top.

**Report:** the first slit the edge enters freely (no forcing). Even
better: caliper the board edge and give me the number. This resolves
whether your board is the STEP's 1.0 mm or the more common 1.6 mm.

## ③ Antenna width slits — three tall blocks, bottom→top

Wide vertical slits, widths 19.8 / 20.2 / 20.6 mm.

**Do:** push the antenna sticker through each slit in turn.

**Report:** which width feels like "light drag" — slides through but you
feel contact. Also caliper the sticker (should be ~110 × 20). Sets the
tray's running clearance (`ANT_SIDE_CLEAR`).

## ④ Snap-clip bay — bottom-right, two yellow hook arms

This bay reproduces the production snap exactly: same profile, same
clearance, board at the same height, relay DOWN as installed.

**Do:**
1. Hold the T-SimHat upright over the bay, **relay/terminal side facing
   down** (components toward the plate).
2. Lower the board's terminal-block end between the two hook arms until
   it **clicks** under both hooks. The two green pads are where the board
   rests.
3. Pinch both release fins outward (away from each other) and lift the
   board out. Repeat 5–10 times.

**Report:** did it click? insertion force (gentle / firm / couldn't);
release easy? any white stress marks at the arm roots after cycling? a
visible gap between hook and board when seated? If it's too tight, the
full carrier moves to 0.40 mm clearance; too loose, 0.20.

## ⑤–⑧ Secondary checks

- **⑤ Plate size:** caliper X and Y. Model says 92.0 × 64.0 mm. More
  than ±0.3 mm off → we add XY shrinkage compensation globally.
- **⑥ First layer:** flat on a table? corners lifting? obvious elephant
  foot (measure plate thickness at a corner; model is 1.6 mm)?
- **⑦ Smallest holes:** are the Ø1.20 holes round and open, or partially
  clogged?
- **⑧ General quality:** stringing across slits, delamination lines on
  the two tall pads (19 mm — the same height class as the carrier cage).

## Feedback template (copy, fill, paste back)

```
CALIBRATION FEEDBACK (coupon v0.4.1)

1. M1.6 ladder:  smallest biting hole = ____ (1.20/1.30/1.40/1.50/1.60)
   notes: ________________________________________________

2. SimHat thickness: first free slit = ____ mm
   caliper of board edge = ____ mm

3. Antenna: free at 19.8? ___   light drag at 20.2? ___   20.6? ___
   sticker caliper = ____ × ____ mm

4. Clip bay:  clicked? Y/N    force: gentle/firm/impossible
   release: easy/hard    white marks after cycling? Y/N
   hook gap when seated: none/small/large

5. Plate: X = ____ mm   Y = ____ mm   (target 92.0 × 64.0)

6. First layer flat? Y/N   elephant foot? Y/N   corner thickness = ____ mm

7. Ø1.2 holes open+round? Y/N

8. Stringing / delamination / other: ________________________________

Photos attached: top view, hole ladder close-up, board clicked into bay
```

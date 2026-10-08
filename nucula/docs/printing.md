# Printing guide (PETG assumed)

## Order

1. **V0 calibration coupon** (`V0_calibration_coupon.stl`, 150 × 44 × 4.3 mm,
   ~6 g) — print FIRST, calibrate, THEN trust the shells.
2. V1: `V1_bottom_shell` + `V1_lid_closed`
3. Optional: `V2_lid_screen_popout` (bottom is shared with V1)
4. Optional: `V3_bottom_shell_full` + `V3_lid_keyboard_blister`

## Coupon interpretation

| Bay | Feature | What to check |
|---|---|---|
| A | Ø 1.55 / 1.70 / 1.85 / 2.00 / 2.20 holes | spare self-tap pilots; find the clean-thread size |
| B | 1.2 / 1.4 / 1.6 / 1.8 mm tunnels (2.2 below top) | slide a board scrap: the 1.6+mask laminate must pass |
| C | production lip over a 1.6 mm slot | lip bite feel = the real board retention feel |
| D | 0.30 / 0.40 / 0.50 / 0.60 mm slits | wire-lane clearance pick |
| E | pop-out panel with 3 bridges | snap the panel out: bridge strength + pick feel |

## Settings (starting points)

* Material: PETG (never PLA for the snap tabs/lid).
* Nozzle 0.4, wall `WALL_T = 1.6` = 4 perimeters; top/bottom `FLOOR_T`/`ROOF_T`
  = 1.4.
* Layer 0.2 mm.
* **Bottom shell: print as-is (z=0 face on the bed)** — the battery bump
  forms a shallow open bowl on the bed; no supports.
* **Lid: print exterior-face-down** — the pop-out panel(s) and their
  bridges print flat on the bed; the 1.7 mm general-roof step around the
  V2 deck is the only bridge and is edge-anchored.
* Cooling: moderate; the pop-out bridges need to solidify before the deck
  walls run over them.
* Infill: 25 % gyroid is plenty; the structure is walls.

## Post-processing

* V2: to fit the display — pop the window panel (push the pick notch on
  the inside face), trim the hinge nubs, glue the glass to the lid
  underside on the four included standoff pads, connect the glass flex to
  a 24-way 0.5 mm FFC jumper, route it under the glass and plug it into
  DS1 (flex route validated in `screen_glass_fits`).
* V3: the J3 hatch pops the same way when you decide to fit a keypad header.
* Deburr the mouse-bite remnants on the PCB before the first fit; the case
  tolerates 2.0 mm stubs + 0.30 mm spread but cleaner is better.

## Assembly

1. Battery into the floor pocket, wires routed: JST rear exit → over the
   board top lane (z 7 channel) → remnant-channel drop → under-board run →
   battery terminals. The lane is boolean-validated (`wire_route_clear`).
2. Plug the JST housing onto J2 (reachable through the left-wall service
   bay).
3. Board into the tray: NFC end first under the v=0 lip, then roll the
   cut edge over the stop ribs; the lips snap over the edges.
4. Lid: lip under the wall tops, press the 4 snap tabs (pry at the NFC-end
   corner notch to open).
5. RESET/BOOT: press the moulded plungers through the roof holes.

# Design specification & audit — Nucula enclosure rev 1

Design intent in words, then the audit evidence for every sentence.
Evidence: `analysis/interference_report.json` (**57/57 PASS**, this run)
+ `analysis/testing_status.json`.

## Spec

1. **The unit houses one Nucula main PCB (keyboard breakaway removed,
   60 × 73 mm) or the full 60 × 110 board — never both at once.**
   Audit: `seated_board_bottom_interference = 0` for V1/V2 (main) and V3
   (full) beyond named lip contacts; `component_clearance` clean for all
   100+ placed parts in each mode.
2. **The board rests in a tray captured by retention lips on the three
   factory edges (u=0, u=60, v=0) and located — not clamped — at the
   routed cut edge by two stop ribs.**
   Audit: lips are the only board/bottom contact (INTENDED, subtracted);
   `cut_edge_located_not_clamped` (0.30 mm rib gap);
   `remnant_clearance = 0` (0.30 mm spread around every tab/bridge stub).
   No screws touch the board: it has no mounting holes, and every corner
   is adjacent to antenna/connector zones — snap-fit lid instead.
3. **NFC first.** Nothing metallic exists anywhere in the enclosure; shell
   faces over the 40 × 40 coil are ≤ 1.6 mm; no structure above the coil
   plane inside the PCB's own antenna rule areas.
   Audit: `nfc_battery_clear = 0`, `nfc_no_structure_over_coil = 0`,
   `nfc_reading_path_thin` (floor 1.4 / roof 1.4 / wall 1.6 ≤ NFC_WALL_T).
   Deliberate, documented: V2's glass hovers part of the rule area
   (dielectric) — `screen_glass_nfc_disclosure` + measurement item.
4. **ESP32-C3 antenna gets air.** The module's overhang clears through an
   open wall window (u 60.2..61.95, v 47..65.3, z 1.6..7.0); no battery or
   wiring in the antenna zone.
   Audit: `esp32_keepout_clear` (battery 0 / wires 0).
5. **USB-C accepts a fully seated common cable.** Opening = 13.0 × 6.5 mm
   plug envelope + 0.6 mm clearance + external lead-in chamfer; plug +
   overmold + cable-bend void (26 mm reach) contains zero shell material.
   Audit: `usb_envelope_clear = 0`, `usb_opening_size` (14.2 × 7.71 mm).
6. **The battery connector stays serviceable without tools.** A service bay
   in the left wall (46.3..54.2 v-band) exposes the JST PH housing; the
   lid snaps off; the battery pocket lives in the floor behind the
   ESP32/USB end, clear of both antennas, with swell + wire headroom.
   Audit: `battery_seat_clear = 0`, `wire_route_clear = 0` (JST housing
   contact INTENDED).
7. **Screen option is a printing decision, not a redesign.** V2's lid
   prints with the window closed behind a 1.0 mm pop-out panel (4 bridges
   + pick notch); pop it only when fitting the glass.
   Audit: `popout_panel_intact`, `screen_glass_fits` (0 part contact).
8. **Keyboard-attached variant keeps the future open.** V3 adds 37 mm of
   body, a factory-edge stop, and a J3 service blister with a pop-out
   hatch sized for a 1×9 2.54 mm header (8.7 mm).
   Audit: `j3_header_fits_blister = 0` with the header fitted.
9. **Prints flat, support-free, in PETG on a ~220 mm bed.** Largest part
   64.8 × 115.6 × 15.8 mm. Lid prints exterior-face-down (the pop-out
   panels and bridge walls print on the bed; the 1.7 mm roof step is the
   only small bridge).
10. **Every dimension is parametric and the model regenerates
    deterministically.** Audit: `build:deterministic_rebuild` PASS.

## Known gaps (deliberate, documented)

- No physical print feedback yet — this release exists to close it (coupon first).
- Battery cell is a documented placeholder (30 × 22 × 6.0 mm).
- OLED glass outline/flex are conservative assumptions pending measurement.
- NFC range is the hardware repo's own open item; the enclosure adds a
  measured-later reading path (≤1.6 mm PETG everywhere over the coil).

# Assembly guide — Nucula enclosure rev 1

Reference renders: `output/renders/detail_battery_pocket.png`,
`detail_usb_battery_ports.png`, `OPTIONS_overview.png`.

## What you need

* Printed parts (docs/printing.md): V1 bottom + V1 or V2 lid (V3 set for
  the keyboard-attached variant).
* Nucula board, keyboard section separated (docs/keyboard-breakaway.md of
  the hardware repo: cut the central bridge FIRST, then snap the tabs,
  trim remnants).
* 1S LiPo/Li-ion pack that fits the pocket (placeholder 30 × 22 × 6 mm),
  with a JST PH plug crimped.
* Optional display kit: SSD1309 2.42" glass + 24-way 0.5 mm FFC jumper
  (≥25 mm), only for the V2 lid with the window popped.

## Bottom shell preparation

1. Inspect the battery pocket (floor, behind the USB end): no strings,
   the pocket rim sits 0.15 mm below the board underside plane.
2. Dry-fit the board: NFC end (v=0) under its lip first, then roll the
   cut edge over the two stop ribs. The lips on u=0 (interrupted at the
   service bay + USB), u=60 (interrupted at the antenna window) and v=0
   should all capture. The board must NOT rest on any component — only
   lips, corner pads, rim locators.
3. Battery wires: harness exits the JST housing rear (toward +u),
   climbs into the z≈7 lane, runs the u≈19/21 lane to the cut edge,
   drops through the remnant channel between the stop ribs, then runs
   under the board to the pocket. Leave slack at the housing for the
   2.6 mm bend radius.
4. Plug the harness onto J2 (top-entry). The left-wall service bay gives
   finger access if you ever need to unplug without opening the case.

## Board + lid

5. Seat the board (step 2). Check: USB connector face aligns with the
   wall opening; JST housing visible in the service bay; charge LED under
   the Ø2.2 lid hole.
6. Fit the lid: lip under all wall tops, then press the four snap tabs
   (left wall v≈15/30, right wall v≈15/38). Open again by prying the
   lid edge at the NFC-end corner notch.

## V2 display option

7. Pop the window panel from the INSIDE (push the pick notch; the four
   bridges snap). Trim nubs flush.
8. Adhesive-mount the glass on the four standoff pads under the window,
   emitting face toward the opening.
9. Glass flex → FFC jumper → route under the glass → fold down at
   DS1 → insert into the FH12 socket (contacts face the flex).
10. Before closing, power over USB and confirm the display; then snap
    the lid.

## V3 keyboard-attached option

* Same steps with the full 60×110 board; the keyboard section lives
  under the long roof. The J3 service blister + hatch stay closed until
  you fit a keypad header (then pop the hatch, fit the header through
  it, and the blister provides the 8.7 mm clearance).

## Checks after first assembly

* USB cable inserts fully, no wall contact (validated envelope).
* Buttons click through the plungers (0.3 mm gap to the B3U actuators).
* NFC read with a card on the lid over the coil half of the case.
* Battery unplugs through the service bay with the lid on.

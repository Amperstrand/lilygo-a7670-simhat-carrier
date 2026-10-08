# Geometry provenance

Every number used by the enclosure, and where it came from. Classes:
**extracted_kicad** (parsed from `nucula-v2.kicad_pcb` / footprint libs),
**derived_kicad** (computed from extracted geometry), **manufacturer_doc**
(Nucula repo doc or component drawing), **conservative_assumption**
(documented guess — measure before rev 2), **enclosure_design_decision**
(our choice — a changeable parameter).

## Board (all extracted_kicad / derived_kicad)

| Quantity | Value | Source |
|---|---|---|
| Outline | 60.000 × 110.000 mm | Edge.Cuts stitch, cross-checks docs/keyboard-breakaway.md |
| Thickness | 1.60 mm | `(general (thickness 1.6))` |
| Coordinate origin | KiCad (50, 50) = local (u0, v0) | derived from outline bbox |
| Main section | v 0..73 | routed gap edge (Edge.Cuts), matches keyboard-breakaway.md |
| Gap | v 73..75, corner r = 4 at both ends | Edge.Cuts |
| Support tabs | u 8.75..15.25 and 44.75..51.25 (rounded ends) | Edge.Cuts point-in-polygon |
| Central bridge | u 27.25..32.75 | inner slot boundaries |
| ESP32 antenna notch | u 55..60 × v 47.14..65.14 (18 × 5) | Edge.Cuts |
| Outer corner radii | r = 4 (all four corners) | Edge.Cuts arcs |

## Key components (bbox = pads+courtyard, derived_kicad)

| Ref | Part | u-extent | v-extent | Height | Height provenance |
|---|---|---|---|---|---|
| J1 | GCT USB4105-GF-A (USB-C) | −0.79..8.15 (shell face −0.80) | 56.42..67.36 | 3.31 | manufacturer_doc: GCT drawing |
| J2 | JST PH B2B-PH-SM4-TB | housing 2.39..10.0 (silk) | 46.82..54.98 | 5.60 | manufacturer_doc: JST drawing |
| DS1 | Hirose FH12A-24S-0.5SH | 21.2..38.8 | 53.6..61.6 | 2.00 | manufacturer_doc: Hirose drawing |
| U3 | ESP32-C3-WROOM-02-N4 (repo STEP) | 41.0..61.0 (antenna trace 54.92..60.57 overhangs the notch) | 47.14..65.14 | 3.20 | extracted_kicad: STEP bbox |
| U8 | PCF8574T (SOIC-16W) | 4.22..16.08 | 92.69..103.50 | 2.70 | conservative_assumption |
| J3 | 1×09 2.54 header (DNP) | 18.07..41.93 | 105.73..109.27 | 8.70 if fitted | conservative_assumption |
| SW1/SW2 | Omron B3U-1000P (RESET/BOOT) | centres (56.5, 34.0) / (56.5, 29.0) | — | 1.80 | conservative_assumption |
| D3 | Charge LED (0603) | centre (15.5, 44.0) | — | 0.70 | conservative_assumption |
| U1 | TP4054 (SOT-23-5) | 11.45..15.55 | 49.80..53.20 | 1.45 | conservative_assumption: JEDEC max |
| A1 | NFC coil (etched copper) | 10.75..50.75 | 1.00..41.00 | 0.035 | manufacturer_doc: 40×40 footprint property; cross-checked vs PCB rule areas |

## Keepouts / envelopes

| Zone | Extent | Provenance |
|---|---|---|
| NFC keepout | u 8.25..53.25 × v −1.5..43.5, all z | extracted_kicad: PCB antenna rule areas (verbatim) |
| ESP32 antenna keepout | u 52.0..61.5 × v 44.0..68.34, all z | derived_kicad trace bbox + 2.9 mm metal margin |
| USB plug envelope | mating face u −0.8, reach 26 mm, 13.0 × 6.5 plug | manufacturer_doc (GCT "6.5 Max", 12.x plug) + design decision |
| Battery pocket | u 7..55.6 × v 45.8..71.9, z −5.3..1.2 | enclosure_design_decision |
| Remnant envelope | 3 stub zones + 0.30 spread, v 73..75.2 | enclosure_design_decision |

## Battery wire route (enclosure_design_decision)

J2 rear exit (u 10.0, v 50.9 ± 0.65, z = board_top + 2.0 per JST drawing)
→ −v corridor (J2 housing vs U1) → z 7.0 lane at u 19.2/20.6 (east of Q1,
west of the stop ribs, between remnant zones) → drop through the remnant
channel (v 73.58..75.08) → under-board run at z 0.78 → battery terminals.
Full-board mode: same start, z 7.0 over the whole keyboard section, drop
through the 2.0 mm channel at the factory edge v = 110.

## Heights not in the table

All unlisted SMD bodies use 1.00 mm (conservative_assumption: generic
passives ≤ 1.0). Change `COMP_HEIGHTS` in `cad/parameters.py` if your
build uses taller parts; the validator re-checks everything.

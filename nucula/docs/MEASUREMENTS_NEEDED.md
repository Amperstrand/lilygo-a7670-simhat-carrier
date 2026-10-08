# MEASUREMENTS_NEEDED.md

Physical inputs this design assumed or deferred. Rev 2 should fold each
answer back into `cad/parameters.py` and re-run `scripts/validate.py`.

| # | Unknown | Current assumption | How to measure | Blocks |
|---|---|---|---|---|
| 1 | Battery cell L × W × T | 30 × 22 × 6.0 mm (LP-series-ish placeholder) | calipers on the chosen protected 1S cell | pocket fit, bump depth, case thickness |
| 2 | Battery wire gauge + JST harness length | 2 × Ø1.3, PH housing rear exit at 2.0 mm | calipers + the real harness | wire lane, service bay reach |
| 3 | NFC range, closed case (coil + lid + battery) | unknown (hardware repo's own open item) | card + PN7160 read-log distance, lid on, battery in | rev-2 wall/floor thinning |
| 4 | NFC impact of the V2 glass over part of the coil rule area | dielectric, tolerated | repeat measurement 3 with the glass fitted | V2 viability as-is |
| 5 | OLED glass outline | 29.4 × 57.5 × 1.9 mm (2.42" SSD1309 candidate) | calipers on the real glass (QDtech OLED242W ordering code unconfirmed in the repo) | window + deck size |
| 6 | NFP1309-02Y flex length | 12 mm assumed; design plans a 25 mm FFC jumper | measure the flex; buy a 24-way 0.5 mm jumper | display assembly |
| 7 | ESP32-C3 TRP with the open wall window | expected better than closed wall | range/throughput test vs bare board | keep/discard the window |
| 8 | Mouse-bite remnant geometry after the user's cut | ≤2.0 mm stub, ±0.30 spread | calipers after the first real separation | end-wall gap, stop-rib windows |
| 9 | Snap-tab retention force | unmeasured | pull test on the first print | tab count/size |
| 10 | Lip bite feel on the real 1.6 mm laminate | 0.65 mm overhang, 1.1 mm lip | coupon bay C squeeze test | RAIL_LIP_OVERHANG |
| 11 | USB plug boots in the wild | 13.0 × 6.5 envelope + 0.6 clearance | plug 3-5 common cables fully | opening size |
| 12 | Charge-LED visibility through the V2 deck hole | dim (3+ mm deep hole) | eyeball with the board powered | LED window shape / light pipe |
| 13 | J3 blister usability with a real keypad cable | hatch 26 × 5.5 mm | dry-fit a keypad pigtail | hatch size |

## Board-side observations (do NOT fix here)

* The JST PH housing (5.6 mm) sets the interior height — a lower battery
  connector on a future PCB rev would drop the case ~3 mm.
* The display socket faces the NFC coil; any glass over the coil-side of
  the board trades NFC aperture for display area. The enclosure chose the
  connector-end placement (zero coil overlap) at +3.3 mm of case height.
* The board has no mounting holes; if a future rev adds M2 holes at the
  connector-end corners, switch the tray to screw bosses and delete the
  snap tabs.

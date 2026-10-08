# Engineering audit — requirement traceability

Method: boolean common-volume checks against the KiCad-derived reference
model (`analysis/interference_report.json`, 57/57 PASS). "mm³" = unexpected
common volume after subtracting named INTENDED contacts.

| # | Requirement | Verdict | Evidence |
|---|---|---|---|
| 1 | First build the authoritative PCB mechanical model from KiCad; no hand-transcribed dimensions | **met** | `scripts/extract_kicad_geometry.py`; 60×110 outline, 1.6 thickness, 131 footprints, tab/bridge/notch topology all parsed; cross-checked vs docs (keyboard-breakaway.md, nfc-antenna.md) |
| 2 | Main PCB = board after keyboard separation (~60×73) — verified programmatically | **met** | Edge.Cuts point-in-polygon: main section v 0..73; tabs/bridge remnant zones mapped |
| 3 | Keep KiCad orientation as the global frame | **met** | board-local (u,v) = KiCad (X−50, Y−50); transform documented in extract script |
| 4 | No OLED window, no keypad openings in the base design | **met** | V1 lid closed; V2 window is an optional pop-out (user decision); V3 hatch is service-only |
| 5 | Cut edge never used for tight location; prefer factory edges | **met** | stop ribs at 0.30 mm gap facing routed windows between remnant zones; v=0/u/u=60 edges + pocket rim carry the rest |
| 6 | PCB retention without mounting holes; no force on parts/solder/USB/battery/NFC | **met** | 3-edge lips (0.65 overhang, INTENDED contact), 4 corner under-board pads on bare laminate, pocket rim locators, stop ribs; `seated_board_*` + `component_clearance` = 0 |
| 7 | NFC keepout: 3D, no battery/screws/inserts/magnets/metal above or behind the coil | **met** | `nfc_battery_clear`, `nfc_no_structure_over_coil`, snap-fit + plastic plungers; disclosure: V2 glass partially overlays the rule area (dielectric, measured later) |
| 8 | Thin wall adjacent to coil (NFC_WALL_T, 1.2–2.0) | **met** | all shell faces over the coil ≤ 1.6 (`nfc_reading_path_thin`) |
| 9 | ESP32 antenna keepout, plastic-only | **met** | `esp32_keepout_clear`; plus an open wall window so the overhang clears |
| 10 | Battery: conservative placeholder, swell allowance, wide pocket (no point clamps), wire routing without pinch, away from both antennas | **met** | pocket 47.5×26.1×7.5 void for a 30×22×6 cell; `battery_seat_clear`, `wire_route_clear`, `esp32_keepout_clear`, `nfc_battery_clear` |
| 11 | USB-C real mating envelope, full insertion, zero intersection, external chamfer, wall strength | **met** | `usb_envelope_clear = 0`, `usb_opening_size` (14.2 × 7.71), lead-in chamfer, bay is wall-local |
| 12 | Buttons: derive function, then regular access or tool hole | **met** | SW1 RESET / SW2 BOOT (net-derivable, BOM value) → recovery use → Ø3.2 ports + moulded plastic plungers |
| 13 | Fastening: simplest reliable, metal away from antennas, boss clearances verified | **met (deviation documented)** | snap-fit lid chosen OVER screws: the board has no holes, all four corners are antenna/connector-adjacent, and boss shafts could not clear the corner voids (r4) without two-tier posts. Screws would violate "metal away from antennas" or need bosses inside component zones. Coupon retains a pilot ladder if a future rev wants screws |
| 14 | Coupon reuses production geometry | **met** | `shell.coupon()` consumes RAIL_LIP_*, SCREEN_BRIDGE_*, slit ladder |
| 15 | Automated validation incl. INTENDED/FAILURE classification | **met** | 57 checks; intended contacts named (lips, J2 wire exit, plunger hover); deterministic-rebuild check included |
| 16 | Renders as illustrations, close-ups for feature verification | **met** | `output/renders/OPTIONS_overview.png` + 15 per-view PNGs + 5 detail PNGs |
| 17 | Machine-readable reports | **met** | `interference_report.json`, `testing_status.json`, `parts_manifest.json`, `render_manifest.json` |
| 18 | Deliver STEP + STL + docs | **met** | `output/exports/*.step|stl` (8 parts), this docs set |
| 19 | Variants: calibration / minimal (USB+battery access) / screen pop-out / keyboard-attached | **met** | V0/V1/V2/V2b/V3 all built, validated, rendered |
| 20 | Testing status visible everywhere | **met** | `testing_status.json` + README matrix: boolean-verified vs requires-physical-print vs requires-measurement |
| 21 | PCB not modified; blockers recorded, not "fixed" | **met** | `docs/MEASUREMENTS_NEEDED.md` board-side section |
| 22 | Reusable architecture for future revs (display/keypad versions) | **met** | parameters + provenance + validation framework are variant-driven; `screen_window`/`kb_blister` flags already implement the extension points |

## Deviations from the original brief (documented)

1. **Snap-fit instead of screws** (req. 13): reasons above; reversible by
   setting `SCREW_*` params and re-adding posts in a rev-2 branch.
2. **ESP32 antenna wall window**: brief said "plastic-only in the zone" —
   the open slot goes further (air path) because the module overhangs the
   board edge by 1.0 mm and a closed 1.6 mm wall would collide; RF-wise
   it is the better reading environment. Measure (item 7).
3. **Battery under the board, connector end** (not beside the board):
   keeps the case 60 mm wide (wallet-like); the wire route threads the
   JST rear exit, the remnant channel and the under-board gap — all
   boolean-verified. If the real cell exceeds 30 × 22 × 6, the pocket
   grows and the case thickens — parameters handle it.

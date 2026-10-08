# Nucula Enclosure — Rev 1 (no display / no keypad, optional pop-out screen)

Parametric, 3D-printable enclosure for the **Nucula board** (zeugmaster/nucula-board).
The KiCad board file is the single geometric authority: every board dimension in
this project is parsed from `nucula-v2.kicad_pcb` / its footprint libraries —
nothing is hand-transcribed.

Built with the methodology of
`Amperstrand/lilygo-a7670-simhat-carrier` (this repo's root
[AGENTS.md](../AGENTS.md) lessons): measure first, boolean-volume
validation as the pass gate, calibration coupon before any real print,
renders are never evidence.

## Status (see `analysis/` for the machine-readable truth)

| Item | Status |
|---|---|
| Boolean validation | **57 / 57 checks PASS** (`analysis/interference_report.json`) |
| Deterministic rebuild | PASS (hash-identical STL on rebuild) |
| Physical print feedback | **NOT closed** — print `V0` coupon first |
| RF / battery measurements | **NOT taken** — `docs/MEASUREMENTS_NEEDED.md` |

## Variants (all from one parameter set — `cad/parameters.py`)

| Variant | Parts | Purpose |
|---|---|---|
| **V0** | `V0_calibration_coupon` | **Print FIRST.** Pilot-hole ladder, board-thickness stairs, real lip-bite bay, wire-lane slits, pop-out bridge feel |
| **V1** | `V1_bottom_shell` + `V1_lid_closed` | No screen, no keyboard (board broken away). Accessible USB-C + battery service bay |
| **V2** | `V1_bottom_shell` + `V2_lid_screen_popout` | Same print as V1's bottom; lid with a **pop-out OLED window printed closed** — pop it only if you fit the display glass |
| **V3** | `V3_bottom_shell_full` + `V3_lid_keyboard_blister` | Keyboard breakaway **NOT removed** (60×110 board). J3 keypad-header service blister with its own pop-out hatch |

Renders: `output/renders/OPTIONS_overview.png` (plus per-view PNGs and
`detail_*.png` close-ups). Renders illustrate; they are not evidence.

## Print order

1. `V0_calibration_coupon.stl` — calibrate (docs/printing.md)
2. `V1_bottom_shell.stl` + `V1_lid_closed.stl`
3. (optional) `V2_lid_screen_popout.stl`
4. (optional) `V3_bottom_shell_full.stl` + `V3_lid_keyboard_blister.stl`

## Regenerate everything

```sh
python3 scripts/extract_kicad_geometry.py   # KiCad -> analysis/*.json
python3 scripts/validate.py                 # 57 boolean checks -> interference_report.json
python3 scripts/build.py                    # STEP + STL -> output/exports
python3 scripts/render.py                   # PNG renders -> output/renders
```

Requires: Python 3.11+, `cadquery` (2.6), `playwright` + chromium (renders only).

**Portability:** the extracted geometry (`analysis/*.json`) is committed, so
`validate.py` / `build.py` work out of the box. Re-extraction from KiCad
needs the hardware repo: `NUCULA_REPO=/path/to/nucula-board
python3 scripts/extract_kicad_geometry.py` (defaults to
`~/my-project/reference-repos/nucula-board`).

## Layout

```
cad/parameters.py     ALL parameters + provenance tags + variant configs
cad/reference.py      board solids, component solids, keepouts, envelopes, wire sweep
cad/shell.py          bottom shell, lid (closed/popout/kb_blister), coupon
scripts/              extract / validate / build / render
analysis/             pcb_geometry.json, component_geometry.json,
                      interference_report.json, testing_status.json
output/exports/       STEP + STL per part
output/renders/       PNG renders + options overview
docs/                 design_spec, geometry_provenance, assembly, printing,
                      MEASUREMENTS_NEEDED, engineering_audit
reference/            ESP32 STEP (from the Nucula repo), three.js for renders
```

## Hard rules baked into the design

* The routed cut edge (v = 73) is **located, never clamped** — two stop ribs
  face the factory-routed windows *between* the mouse-bite remnant zones;
  the remnant envelope (2.0 mm stub + 0.30 mm spread) stays clear.
* **No metal anywhere.** Snap-fit lid (4 tabs), plastic plungers over
  RESET/BOOT, no inserts — nothing metallic near the NFC coil or the
  ESP32-C3 antenna.
* NFC: shell faces over the coil are ≤ `NFC_WALL_T` (1.6 mm); no structure
  above the coil plane inside the PCB's own antenna rule areas.
* Battery: pocket in the floor *behind* the ESP32/USB end (clear of the coil),
  swell clearance, wire route leaves the JST rear exit and drops through the
  remnant channel — all boolean-checked.
* USB-C: opening admits a fully-seated 13.0 × 6.5 mm plug envelope plus
  cable-bend service void — zero shell material inside it.

If you find a mechanical blocker in the *board*, do not "fix" it here —
record it in `docs/MEASUREMENTS_NEEDED.md`. The PCB is not modified by this
project.

# LILYGO T-A7670X + T-SimHat Combined Carrier

Parametric, 3D-printable internal electronics carrier that holds a
**LILYGO T-A7670X ESP32 modem board** and a **LILYGO T-SimHat (single-relay
variant)** side-by-side — mounted separately, wired together with jumpers —
for subsequent installation inside a waterproof enclosure.

Fully scripted in **Python + CadQuery**, driven by **manufacturer STEP/DXF
geometry** (no guessed dimensions), validated programmatically, and
regenerable with one command.

![Assembly render](https://github.com/Amperstrand/lilygo-a7670-simhat-carrier/blob/main/renders/assembly.png)

![Contact sheet](https://github.com/Amperstrand/lilygo-a7670-simhat-carrier/blob/main/renders/contact_sheet.png)

*T-SimHat (amber) flipped — relay down, headers up. T-A7670X (green) on
25 mm standoffs (18650 + holder underneath). LTE sticker-antenna slide-in
tray at the far end. Full carrier 133 × 157.5 mm.*

## Explore in 3D

- **Interactive in-browser**: open any `.stl` on GitHub — it renders in a
  built-in 3D viewer you can rotate: [carrier](exports/lilygo_a7670_simhat_carrier.stl),
  [low-profile template](exports/lilygo_a7670_simhat_carrier_lowprofile.stl),
  [clip coupon](exports/simhat_clip_test.stl), [A7670 section](exports/sections/a7670_section.stl),
  [SimHat cage section](exports/sections/simhat_cage_section.stl),
  [antenna tray section](exports/sections/antenna_tray_section.stl).
- **Download & spin anywhere**: [assembly GLB](exports/lilygo_a7670_simhat_assembly.glb)
  and [carrier GLB](exports/lilygo_a7670_simhat_carrier.glb) open in Windows
  3D Viewer, macOS Preview, Blender, https://gltf-viewer.donmccurdy.com.
- **Renders**: GitHub blob URLs — 9 labeled views incl. per-board close-ups
  (`a7670_closeup.png`, `simhat_closeup.png`) and the contact sheet.
  Rendered by `scripts/build.py`; regenerated on every push via CI.

## Key measured dimensions (from manufacturer CAD)

| Item | Value | Source |
|---|---|---|
| T-A7670X PCB | 33.071 × 110.54 × 1.2 mm | STEP cross-section + DXF dim `33.071` |
| T-A7670X mounting holes | 4 × Ø1.73 mm, 27.71 × 105.59 mm grid | DXF hole-callout dims, cross-checked vs STEP cylinders |
| T-A7670X mounting | **screwless snap plugs** (christmas-tree; `A7670_MOUNT="screws"` restores M1.6 pilots) | Ø1.70 STEP holes, true centers measured off placed geometry |
| T-A7670X battery | 18650 + holder under board → 25 mm standoffs | user hardware + product docs |
| T-SimHat PCB | 33.0 × 94.8 × **1.0 mm** | STEP cross-section (verify with calipers: some batches 1.6) |
| T-SimHat mounting holes | **none** (hence snap-in cage) | STEP |
| T-SimHat relay | OMRON G5LE-class, 16.5 × 22.7 × 18.25 mm, single relay confirmed in STEP | STEP solids |
| LTE sticker antenna | ~110 × 20 mm sticker, 10–15 cm coax (user-measured; parametric `ANT_W`/`ANT_SLIDE`/`ANT_CABLE_L`) | — |

## Layout: rotated for short jumpers

The A7670X is mounted rotated 180° (`A7670_ROT_180`) so its pin-header
rails land at the same end as the SimHat's up-facing sockets: jumpers
cross the 16 mm wiring channel at ~15–25 mm instead of ~120 mm, and the
SMA antenna jacks face the channel for a clean coax run to the tray.

## Antenna tray

The bundled full-band LTE sticker (~110 × 20 mm, SMA coax, three punched
holes) lies flat in a slide-in tray at the carrier's far end: floor keeps
it flat, flared channel walls locate it, end stop + friction retain it
(adhesive optional), and a coax notch passes the cable through the frame
rail to the modem's SMA jacks — which face the wiring channel after the
board rotation. **Caliper your sticker and set `ANT_W`/`ANT_SLIDE` before
printing.**

## Print variants (all parametric)

| Variant | File | Print height | Purpose |
|---|---|---|---|
| **Calibration mini-coupon** | `exports/lilygo_calicheck_mini.3mf` | ~28 mm local, ~21 g, **~15 min** | **FIRST PRINT**: M1.6 pilot-hole ladder, SimHat thickness stair, antenna width slits, real snap-clip bay — calibrates every printer-dependent number before anything bigger |
| **Gridfinity fit-check tray** | `exports/lilygo_fitcheck_tray_gridfinity.3mf` | 33 mm pins / 7 mm body, ~17 g | second print: gauge pins verify the A7670 hole pattern with battery installed; SimHat outline + fence gauges; antenna channel; then clips onto any Gridfinity 3×4 baseplate |
| Full carrier | `exports/lilygo_a7670_simhat_carrier.stl` | ~40 mm | production holder |
| Low-profile template | `exports/lilygo_a7670_simhat_carrier_lowprofile.stl` | **9 mm** | batteryless screw-fit + cage-outline check (relay/holder hang through the open frame); wall-mountable via M3 ear slots. Build: `CARRIER_PROFILE=low python scripts/build.py` |
| Snap coupon | `exports/simhat_clip_test.stl` | ~35 mm bay | pick XY clearance 0.20–0.50 (superseded for feel by the mini-coupon bay, still useful for clearance sweep) |
| Sections | `exports/sections/*.stl` | varies | iterate one region cheaply (A7670 plate / SimHat cage / antenna tray); volume-partition of the full carrier |

Print order: **calicheck mini (~15 min) → Gridfinity tray → coupon (optional) → full carrier.**
Design intent + audit table: `docs/design_spec.md`.

## Port access (validated)

Keep-clear service envelopes with zero printed-material interference:
USB-C plug, both SMA antenna connectors, SIM-tray swap zone, battery JST,
SimHat jumper-socket zone, relay/terminal cavity, and the 18650 battery
keep-out under the A7670X — see `analysis/interference_report.json`.

## Status

`v0.3.0-validated` — all 34 validation checks pass; CI pipeline ensures renders stay fresh; carrier 22g PETG (was 40g); physically test-printed calicheck mini recommended before full print.

## How the T-SimHat is held

No screws, no load on components:

- **4 support pads** (6 × 6 mm) contact **bare laminate only**, at grid
  positions verified clear of all 77 component solids in the STEP model
- **Fixed capture lip** at the far end (2 segments) hooks over the PCB top edge
- **2 flexible corner clips** at the near end snap over the PCB edge;
  flexure bends **in the XY print plane** (14 mm arms, ~1.6 % strain — PETG-safe)
- **3 fences** locate X/Y; board cannot slide or rotate
- **Removal:** press both release tabs → lift clip end 0.15 mm → slide out
  from under the lip (validated collision-free, incl. relay/SMD sweep paths)

## Quick start

```bash
uv venv .venv && uv pip install --python .venv/bin/python cadquery ezdxf trimesh numpy pillow lxml
.venv/bin/python scripts/analyze_step.py   # already run; regenerates analysis/*.json
.venv/bin/python scripts/build.py          # rebuilds exports/ (full + low) + renders/ + GLB/3MF
.venv/bin/python scripts/validate.py       # 18 checks -> analysis/interference_report.json
CARRIER_PROFILE=low .venv/bin/python scripts/validate.py   # low-profile checks (11)
```

## Printing

- **First print the coupon:** `exports/simhat_clip_test.stl` — four labeled
  clearance variants (0.20/0.30/0.40/0.50 mm, notch-counted). Pick the best
  fit, then set `SIMHAT_PCB_XY_CLEAR` in `cad/parameters.py` and rebuild.
- Full carrier: flat on the plate as modeled, no supports needed.
  PETG starting settings in `docs/print_settings.md`.

## Reference provenance

Manufacturer geometry lives in `references/` (MIT-licensed, © LILYGO),
copied from the forks in `vendor/` — see `references/PROVENANCE.md` for
exact upstream commits. Forks: `Amperstrand/T-SimHat`,
`Amperstrand/LilyGo-Modem-Series` (upstream: `Xinyuan-LilyGO/...`).

## Layout

```
cad/parameters.py     every dimension in one place (measured values load from analysis/*.json)
cad/holder.py         parametric model: base frame, standoffs, snap cage, ears
scripts/analyze_step.py   STEP -> geometry JSON (holes, PCB slab, components)
scripts/analyze_dxf.py    DXF dimension cross-check
scripts/build.py      regenerates exports/ and renders/
scripts/validate.py   interference, watertight, envelope, features, removal
exports/              carrier + coupon STL/STEP, assembly STEP
analysis/             machine-readable geometry + validation reports
docs/                 design decisions, assembly, print settings
```

All parameters — standoff height, board gap, clip geometry, ear positions,
pad locations, clearances — are in `cad/parameters.py`.

## Repository

- GitHub: `Amperstrand/lilygo-a7670-simhat-carrier` (private)
- Branch: `cad/combined-carrier-v1`

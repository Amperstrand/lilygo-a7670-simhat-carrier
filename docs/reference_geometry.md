# Reference geometry — manufacturer CAD measurements

All values below were extracted programmatically from LILYGO's own STEP/DXF
files (see `references/PROVENANCE.md` for exact upstream commits). Nothing
was scaled from screenshots. Raw machine-readable output:
`analysis/a7670_geometry.json`, `analysis/a7670_dxf.json`,
`analysis/simhat_geometry.json`.

Method: cross-sectional area sweep + horizontal planar-face clustering
(PCB slab), thin-slab island sectioning (outline, component map), cylindrical
face enumeration (holes), DXF `DIMENSION` measurement extraction (hole
callouts). `scripts/analyze_step.py` and `scripts/analyze_dxf.py` regenerate
everything.

## T-A7670X (`T-A7670X-Board-3D.stp`, part name `SIM7000G_PCB_0415`)

LILYGO reuses one PCB outline across the SIM7000G/A7670 family; the STEP is
labelled SIM7000G but LILYGO ships it as the A7670 mechanical reference in
`dimensions/esp32/`.

| Measurement | Value | Source |
|---|---|---|
| PCB outline | **33.071 × 110.541 mm** | STEP cross-section; DXF dimension `33.071` agrees exactly |
| PCB thickness | 1.2 mm | STEP slab (planar faces z −1.2…0) |
| Mounting holes | **4 × Ø1.73 mm** (DXF callout 1.7296; STEP cylinder Ø1.700) | DXF hole dimensions + STEP cylinders, same centers |
| Hole centers, board-local from PCB lower-left corner | (2.591, 2.286), (30.328, 2.337), (2.616, 107.874), (30.328, 107.874) | STEP/DXF consensus |
| Hole grid | 27.71 × 105.59 mm, slightly asymmetric (DXF dims 27.737 / 27.711) | DXF |
| Header pin holes | 2 × 16 × Ø1.42 mm, 2.54 mm pitch, 38.10 mm row length, along both long edges | STEP cylinders + DXF dims |
| Corner fillets | R2.0 (these appear as Ø4.0 cylinders in naive face scans — they are outline fillets, **not** holes) | STEP |

Resulting screw size: **M1.6** (Ø1.6 screw in Ø1.73 hole). M2 would ream the
PCB holes; do not use.

Component envelopes (board-local, PCB top = z0, heights above/below surface):

| Zone | X | Y | Z extent | Note |
|---|---|---|---|---|
| Top shield/modem zone A | 2.7–26.9 | 10.7–34.9 | +0…2.4 | shield can |
| Top zone B (USB end) | 7.3–25.3 | 79.5–111.0 | +0…3.1 | USB + buttons end |
| Top zone C | 2.0–16.0 | 36.6–48.3 | +0…1.3 | low parts |
| Bottom shield | 6.1–27.1 | 12.7–101.8 | −0…8.5 | under PCB |
| Bottom stacking-header pins (optional HW) | 2 rails 2.54 pitch | both long edges | −0…15.0 | **only if 16 mm stacking headers are soldered** |
| SIM tray, SMA antenna jacks, USB-C | board edges (y≈80–104 end and long-edge x≈26–30) | | protrude past edges | island map in JSON |

## T-SimHat (`t-simhat-pcb.stp`, part name `T-SIMHAT-PCB`)

| Measurement | Value |
|---|---|
| PCB outline | **33.0 × 94.8 mm** |
| PCB thickness | **1.0 mm** (STEP slab; ⚠ verify with calipers — some production runs use 1.6 mm FR4; snap gap tolerates both but confirm before trusting the coupon result) |
| Mounting holes | **none** (hence the snap-in cage) |

Variant check: exactly **one** relay-class solid is present
(16.5 × 22.7 mm footprint, 18.25 mm tall ≈ OMRON G5LE-14 class), matching
the single-relay T-SimHat. The repo's second variant (T-SimHat-INA219) adds
a current-sensor assembly; this STEP does not contain it, so treat the
central strip and far end as populated territory (we did — see pads below).

Component envelopes (STEP-native coords; board is x −16.5…16.5,
y −94.8…0; the **y = 0 end faces the snap clips** on the carrier):

| Zone (STEP side) | X | Y (STEP) | v on carrier (=−Y) | Height | Carrier orientation |
|---|---|---|---|---|---|
| **Relay** (largest solid, 6805 mm³) | −16.5…0 | −29.2…−6.5 | 6.5…29.2 | 18.25 | faces DOWN into cavity |
| Terminal block (dual) | 5.5…16.0 | −15.8…0 | 0…15.8 | 13.8 | faces DOWN |
| SMD blocks ×2 | ±7.2…±16.5 | −49.4…−37.0 | 37.0…49.4 | 7.0 | faces DOWN |
| Small SMDs | 1.6…6.0 | −53.8…−50.5 | 50.5…53.8 | 2.8 | faces DOWN |
| Far-end SMDs ×2 | ±5…±9.8 | −85.7…−78.9 | 78.9…85.7 | 1.5 | faces DOWN |
| Stacking header sockets ×2 | ±14.0…±16.5 | −94.7…−54.0 | 54.0…94.7 | 8.1 | faces UP (jumper access) |
| Far-end low parts | −8…8 | −94.3…−87.0 | 87.0…94.3 | 2.0 | faces UP |

The only ≥7 mm window of bare laminate common to both u = ±3.5 strips is
**v 31.0–50.5** — this is where all four support pads sit (v 34.5 / 42.0),
additionally biased away from the removal slide path (pads top out below
v 46.9, the swept floor of the v 50.5–53.8 SMDs during board removal).

## Discrepancies & confidence notes

1. **A7670 STEP vs DXF**: hole Ø differs by 0.03 mm (1.700 vs 1.7296) — the
   DXF callout is the plated-hole spec; both round to M1.6. No other deltas.
2. **A7670 STEP models optional 16 mm stacking-header pins** below the PCB.
   Default standoffs assume they are NOT soldered (this project wires the
   boards with jumpers, never stacked). Set `A7670_STANDOFF_H = 21.0` in
   `cad/parameters.py` if your board has them.
3. **T-SimHat PCB thickness 1.0 mm** is STEP-derived and unusual (1.6 is
   common); the cage's 0.2 mm vertical clearances accept either, but verify.
4. The T-SimHat STEP is a fused single solid (no part tree); relay identity
   was inferred from envelope size/position, consistent with the repo's
   pinout photo (single G5LE-14, relay at IO32).

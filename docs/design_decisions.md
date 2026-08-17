# Design decisions

Rationale for the load-bearing choices. Dimensions live in
`cad/parameters.py`; measurements in `docs/reference_geometry.md`.

## Layout: side-by-side, long edges parallel

- A7670X 33.07 × 110.54 + SimHat 33.0 × 94.8 stacked end-to-end would exceed
  205 mm in Y — too long. Side-by-side with a 12 mm wiring channel:
  129.1 × 127.5 mm footprint, fits the 175 mm A1-mini safety envelope with
  >45 mm margin, and both boards stay serviceable from above.
- A7670X on +X, SimHat on −X; clip end of the SimHat faces the frame
  centerline so release tabs are between the boards (reachable, and jumper
  wires from the up-facing headers drop straight into the channel).

## A7670X mounting: M1.6 screws into printed pilots

- PCB holes are Ø1.73 mm (DXF-verified) → M1.6 is the honest fit. M2/M3
  would ream the board. Cross-checked STEP (Ø1.70 cylinders) vs DXF
  (Ø1.7296 callouts) — same centers.
- Pilot Ø1.30 × 8.5 mm deep in Ø4.6 bosses: self-tapping PETG thread,
  ~1.65 mm wall around the pilot. Blind pilots (1.5 mm floor) so screws
  never touch the enclosure below.
- Standoff height 13 mm: base 3.2 + bottom shield 8.5 + ~1.3 mm air. The
  parameter exists because boards with soldered 16 mm stacking headers need
  21 mm — one-line change.
- Board located by its 4 screws (not rails): no XY clearance fights, and
  unscrew → lift free is unobstructed (validated).

## T-SimHat: flipped, laminate-supported, snap-retained

Why flipped (relay down, headers up): the project wires the boards with
jumpers — headers must face up; relay/terminal side is the tall side that
benefits from a cavity; terminal-block screws face down but are only
touched at install time (mount carrier on enclosure screws AFTER wiring, or
leave relay-side access; see assembly doc).

Retention concept per requirements — open frame, no tray:

- **4 support pads** (6×6 mm) on bare laminate at v 34.5/42.0, u ±3.5 — the
  only ≥7 mm free window on both strips when checked against **all 77**
  component solids (first attempt used top-10 zones and validation caught
  real SMD collisions — kept the full-solid check).
- **Fixed capture lip** at the far end (v=94.8), 2 segments at u −13.5…−9
  and 9…13.5, engaging 2.6 mm over the PCB top. Segmented to keep the
  up-facing far-end SMDs (v 78.9–85.7) and header sockets (v 54–94.7,
  u ±14…16.5) clear; the two chosen windows are bare edge laminate.
- **2 corner clips** at the near end engage the PCB edge 1.0 mm over the
  top face. Flexure is **in the XY plane** (arm bends about Z): printed
  layers stay in-plane → maximum layer adhesion, no Z-axis peeling.
- **3 fences** (u sides at v 16/45/74 staggered) + lip + corner hooks give
  positive XY location and rotation lock; the board cannot translate or
  rotate (validated: seated interference zero against real STEP geometry).

## Snap-fit sizing (PETG, 0.4 mm nozzle)

- Arm: 14 mm long × 2.0 mm thick × 6 mm deep, tip deflection needed
  1.05 mm (per side) → ε ≈ 1.6 %, well under PETG's elastic envelope
  (~2–3 % design ceiling for repeated snapping). Long-gentle beats
  short-stiff: no brittle hooks anywhere.
- 0.8 mm plan-view lead-in chamfer on the hook inner corner: insertion
  ramps the arm outward instead of corner-on-corner scraping; the same
  ramp acts during release so tabs need only light finger pressure.
- Release: 2× fins (7 mm tall, 2 mm thick) standing at the arm roots,
  angled inward between the boards — thumb+finger squeeze or individual
  presses both work.
- Coupon-first strategy: 4 variants (0.20/0.30/0.40/0.50 mm XY clearance),
  notch-counted 1–4, before committing to the full print. Default 0.30 mm
  is the mid FDM-tolerance guess, not a claim.

## Structure & printability

- Base 3.2 mm rails/ribs (≥2 mm minimum per requirements; 3.2 = 8×0.4
  nozzle passes), open frame, cross ribs at ~28–56 mm pitch. Flat on plate,
  zero supports: every feature either grows from the plate (pads, fences,
  lip walls, standoff bosses) or is a horizontal ledge printed as bridging
  ≤2.6 mm wide (lip/clip ledges bridge in 2 perimeter passes).
- Rounded 6 mm outer corners; ears are the only outward features.
- Walls/ledges that touch PCBs: 0.2 mm vertical clearance everywhere
  (except the designed laminate contacts).

## Carrier↔enclosure interface (parametric, two options)

1. **4 M3 slotted ears** (16 mm wide, 7.5 mm slots) at the frame corners —
   positions/extent/slot orientation are parameters (`EARS`, `EAR_EXT`,
   `EAR_SLOT_*`); slotted = tolerant to unknown boss spacing. Ears sit at
   the frame extremes, not over any board → removal paths stay clear.
2. **VHB tape pads**: two 24×24 mm flat, unperforated landings under each
   board's centerline, deliberately kept hole-free.
No shell drilling required by either method.

## Wiring

- 8 cable-tie slots (3.6 × 7 mm) through both gap rails; jumpers from the
  SimHat headers cross the 12 mm channel to the A7670 edge pins without
  passing under any board.
- Nothing routes beneath the SimHat; the cavity is component space only.

## LTE sticker-antenna tray

- LILYGO publishes no CAD for the bundled full-band FPC sticker (web
  research: Quectel YF0006-class family, ~50×25 to ~60×45 mm), so the tray
  is parametric (`ANT_SLIDE`/`ANT_W`) with caliper-confirm defaults.
- Placement: −Y end, the only zone free of the SimHat clip anchors (+Y,
  x −5.7..0.3) and USB-C (+Y, x 13–31). Channels start outside the ring
  rail so the slide path never crosses base structure; a 5 mm coax notch
  passes the cable through the rail.
- Slide orientation: sticker slides along its SHORTER dimension — worst
  case 60×45 sticker still yields ≤175 mm total Y (default 45 → 173.5).
- Retention: friction channels + end stop + optional adhesive (sticker is
  self-adhesive; tray floor is the "keep it flat" guarantee). Flared
  mouths (1.5 mm) self-guide insertion; prints flat, no supports.
- Antenna sits ~80–100 mm from the modem's SMAs — beyond the near-field
  of the RF jacks; coax jump crosses the frame over the 3.2 mm rails.

## Port-access audit (validated, not assumed)

All tall structure (cage fences z→27.6, clip anchors z→40.4) lives on the
SimHat half; the A7670 half has only 3.2 mm rails below board level
(z 13+). Service envelopes — USB-C plug body (extends 12 mm past the +Y
edge), both SMA antenna connectors (16 mm past the +X edge), SIM-tray
swap zone, battery-JST headroom — are checked against the carrier solid
in validation: zero interference. Envelope coordinates derive from the
measured STEP component islands.

## A7670X rotation (180°) and battery lift

- Rotating the A7670X 180° about Z puts its 2×16 pin-header rails at the
  −Y end — the same end as the SimHat's up-facing sockets. Jumper length
  drops from ~120 mm to ~15–25 mm across the 16 mm channel. The SMA jacks
  then face the channel, feeding the antenna coax straight from the tray
  through the tie-slot row. The gap widened 12 → 16 mm for SMA plug
  bodies (~10 mm) facing each other.
- Envelope/hole positions derive programmatically
  (`_a7670_local_to_carrier`), never hand-rotated — the service envelopes
  and mounting holes follow `A7670_ROT_180` automatically.
- The 18650 + holder under the board sets standoff height: 25 mm =
  base 3.2 + cell/holder ~20.5 + air. Validated keep-out: 20 × 71 mm
  center strip under the board, zero carrier intersection. Without the
  holder, 13 mm; the fit-check template uses 9 mm.
- Rotating the SimHat instead was rejected: its pad/lip/fence placement is
  tied to component zones that don't survive a mirror (free laminate
  windows are asymmetric), while the A7670X is screw-located and rotates
  freely.

## Low-profile fit-check template + sections

- `CARRIER_PROFILE=low` builds a 9 mm open-frame template: bosses tall
  enough for a real M1.6 screw-fit, cage walls for outline/lip/fence
  position checks, cross ribs only at ±53.5 (outside every board
  underhang), no clips (the coupon covers snap feel), no tray/tape pads.
  Doubles as a flat wall-mount bracket via its 4 M3 ear slots.
- Sections (`exports/sections/`) are an exact volume partition of the
  finished carrier (validated: section volumes sum to the whole) for
  cheap per-region iteration. Not for reassembly — the full carrier is
  the assembly part.

## Gridfinity fit-check tray (ecosystem compatibility)

- Researched standards: **Gridfinity** (42 mm grid — the dominant open
  standard, full spec available), ToolGrid (newer, wedge interface, thinner
  adoption), honeycomb wall storage (wall-mounted, not desk). Chose
  Gridfinity for adoption + exact public numbers.
- Geometry per the canonical `kennetek/gridfinity-rebuilt-openscad`
  constants: 41.5 per-unit top (0.5 gap), dovetail base profile
  (35.6-wide bottom, 45°→vertical→45° to full width at z=4.75, corner radii
  0.8/3.75), built as a ruled ThruSections loft.
- Deliberate deviations (allowed by spec, documented): no stacking lip, no
  magnet holes, 1.2 mm walls, boards sit proud of the 7 mm rim — it's a
  gauge first, tray second.
- **Gauge-pin pattern**: when under-board parts (18650 holder 20.5 mm,
  relay 18.25 mm) exceed any printable pocket, seat the board on its
  lowest part and verify the hole pattern with drop-over pins instead of
  seat-on bosses. Pins Ø1.25 because the STEP models ~Ø1.35 drills (the
  Ø1.73 DXF figure is the plated spec) — pins gauge POSITION; diameter
  stays a caliper check.
- Layout conflict caught by slide-path validation: the compressed antenna
  channel initially crossed the gauge pins; boards shifted −14 mm and the
  channel moved to the +Y end. Relative gauge geometry unchanged.

## Mounting-ecosystem research (v0.4)

- **Gridfinity (42 mm)**: adopted for the fit-check tray. Python library
  `cq-gridfinity` (michaelgale, CadQuery-native) exists; we keep the
  ~40-line spec-exact base (boolean-validated against the canonical
  constants) — no new dependency, same geometry. Revisit the library if
  we ever generate baseplates/bins.
- **DIN-35 rail**: the classic shed/solar pattern (all charge controllers
  DIN-mount). Deferred: the unit's stated homes are a waterproof box or a
  wall box, both served by the M3 slotted ears/tabs + VHB pads. If the
  shed cabinet turns out DIN-rail-equipped, a clip-on ear pair is a
  parameter-level addition (TH35 top-hat profile, ~2 printed hooks),
  not a redesign.
- **19" rack / honeycomb wall**: rejected — wrong scale for a 133 mm
  carrier / wall-storage ecosystem is for tools, not wired electronics.

## Calibration strategy (v0.4)

Printer-dependent numbers (self-tap pilot Ø, PCB thickness, sticker
width, snap feel) are calibrated on a ~21 g throwaway coupon BEFORE the
17 g fit tray or the full carrier — see `docs/print_settings.md`. The
coupon's clip bay uses the production flip orientation and the shared
`_clip_arm_pts` profile, so what you feel there is what the carrier
does.

## Trade-offs accepted

- SimHat must slide 3.6 mm toward the clips during removal — pads are
  biased (v ≤ 42+3 = 45 < 46.9 sweep floor) so the down-facing SMDs never
  sweep into a pad; validated stage-by-stage.
- Ear flanges add 11 mm per side; total 129.1 mm still ≪ 175 mm.
- M1.6 fasteners are small to handle; alternative was reaming PCB holes —
  rejected.

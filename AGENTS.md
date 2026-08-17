# AGENTS.md — LLM-driven CAD for PCB carriers: lessons & skills

Working notes distilled from this project's iterations (v0.1 → v0.2).
Audience: any coding agent (or human) doing parametric mechanical design
around measured electronics in this repo — and the pattern generalizes to
the next board-carrier project. Review this file before extending the CAD.

## Process rules that paid for themselves

1. **Measure first, model second.** Never type a dimension that exists in
   manufacturer CAD. Pipeline: clone fork → `analyze_step.py`/`analyze_dxf.py`
   → `analysis/*.json` → `cad/parameters.py` loads measured values; only
   *design decisions* are literals. DXF `DIMENSION` measurements and STEP
   cylinder radii can disagree (Ø1.7296 vs Ø1.700) — take the tighter for
   fastener sizing, cross-check both, document the delta.
2. **Validation is the design review.** Every geometric claim gets a boolean
   check (`scripts/validate.py`): seated interference, removal kinematics,
   keep-outs, feature presence, watertight STL, deterministic rebuild. A
   render is never evidence. Keep the check list growing with the design.
3. **Boolean volume overlap vs real reference geometry is the pass gate.**
   Bbox-distance checks are advisory only: bbox granularity produces both
   false alarms (0.3 mm "violations" that are designed clearances) and false
   comfort. Zero mm³ common volume is the criterion.
4. **Derive placement transforms from measured slab data, never assumptions.**
   Both real bugs in v0.1 were transform bugs: (a) SimHat placed 18 mm high
   because tz used the flipped bbox z-min (relay tip) instead of the PCB slab
   face; (b) an A7670 tz used PCB thickness instead of slab z-bottom. Rule:
   the plane that *contacts* the support feature must be the plane you
   transform by.
5. **A 180° flip mirrors X, not just Y.** Rotating "about the long axis"
   maps (x,y,z)→(−x,y,−z): left-strip free windows become right-strip
   windows. A pad that was safe landed inside the relay. Always re-run the
   full-solid keep-out scan after any board reorientation.
6. **Keep-out scans must use ALL component solids, not the top-N.** The
   first pad placement used the 10 largest zones and collided with a 3 mm
   SMD at v 50.5–53.8. Component count on a hat-class PCB: ~80.
7. **Simulate removal as staged kinematics, and sanity-check the stages
   against physics.** Two v0.1 mistakes: tilt-sign inverted (dipped the relay
   into the base), and tilt-at-all is wrong for a 95 mm board over an 18 mm
   relay (real motion: lift 0.15 mm, slide, lift). Components SWEEP volumes
   during removal — pads must clear the swept path, not just the seat.
8. **One geometry source of truth.** When the carrier clip gained a lead-in
   chamfer, the test coupon kept the old square profile (duplicated inline
   point list) — the coupon would have validated the wrong geometry. Coupon
   bays now call the carrier's `_clip_arm_pts()` directly. Any derived
   variant (coupon, low profile, sections) must consume the same builder
   functions as the production part.
9. **When OCC fillets fail on fused prisms, move the feature into the 2D
   profile.** Plan-view polygon chamfers/tapers print better anyway
   (no support, no scorching). Flexure-root relief = tapered root polygon.
10. **Metadata lists that drive BOTH builds and cuts need a kind tag.** The
    ear list grew antenna-tab entries and `build_ears` materialized them as
    corner ears 8 mm off-position. `kind: corner|stop_tab` now filters.
11. **Fused single-solid STEP boards are normal.** Don't wait for a part
    tree: cross-section area sweeps (PCB slab), horizontal planar-face
    clustering (slab z-planes), cylindrical-face enumeration (holes),
    island maps at several z (component layout). Filter cylinders within
    one radius of the outline bbox — corner fillets masquerade as big holes.
12. **GitHub renders STL blobs in-browser; GLB covers everything else.**
    Link both from the README. A contact sheet of 8-9 labeled views catches
    what a single iso hides (relay side, tray mouth, clip detail).
13. **pip-audit every added dependency; keep the set minimal.** cadquery,
    ezdxf, trimesh, numpy, (pillow, lxml for images/3MF). No more.
14. **Camera framing:** assemblies read badly at whole-model scale. Render
    full views AND per-board close-ups (zoom + focus params on the camera).

15. **Fit-check with drop-over gauge pins when under-board parts exceed
    pocket depth.** Battery holders (20.5 mm) and relays (18.25 mm) make
    "seated on bosses" impossible in a thin tray: seat the board on its
    lowest part, run pins through the holes. Pin Ø follows the MODELLED
    drill (STEP corner holes ≈ Ø1.35), not the plated spec (DXF Ø1.73) —
    pins gauge position, calipers gauge diameter.
16. **Attach prototypes to an ecosystem standard when one exists.**
    Gridfinity (42 mm, exact public constants from the canonical
    gridfinity-rebuilt repo) turns a throwaway test print into a permanent
    desk asset and forces disciplined footprint numbers. Research
    competitors (ToolGrid, honeycomb) but pick by adoption + spec quality.
17. **Compressing a layout into a smaller footprint re-collides features
    that were fine at full size.** The antenna channel (outside the frame
    on the carrier) crossed the gauge pins once folded inside the tray.
    Slide-path validation must re-run after ANY layout compression or shift.

18. **The Y-flip mirrors u: STEP-native x is NOT board-local u.** After
    rotating a board 180° about Y, a part at STEP x −16.5..0 lands at
    u +0..+16.5. This bit THREE times in one session (carrier pads,
    fitcheck channel, calicheck bay). Rule: immediately after defining a
    board placement, print the mapped zone of every tall component in the
    new frame and re-derive free windows there — never carry zone tables
    across a flip or mirror.
19. **A mirrored placement is not a real placement.** "RotZ 180" to fix a
    handedness problem flips the board along its length and makes the
    scene physically unrealizable. If a sub-assembly needs the board the
    other way round, mirror the FIXTURE features (bay y = oy − v), keep
    the board transform a pure translation.
20. **Calibration coupon before any large print: hole-gauge ladder (Ø
    steps), thickness/width U-slit stairs, one real clip bay.** Probes:
    through-holes Ø±0.10 find the self-tap pilot; slits find the actual
    part dimensions; the bay (at production support height, production
    flip, production profile via the shared builder) finds snap feel.
    Validate the coupon itself: enumerate hole radii from model faces,
    probe every slit void, seat the reference STEP board in the bay.
21. **Library research verdict for Gridfinity-in-Python:** cq-gridfinity
    (michaelgale) exists and is CadQuery-native; we keep our ~40-line
    spec-exact base because it is already boolean-validated against the
    canonical constants and adds no dependency. Adopt-a-library criteria:
    spec fidelity provable, dependency audited, replaces >100 lines, or
    we need ecosystem features we won't hand-roll (baseplates, bins).
22. **Render verification needs zoom.** A vision model cannot resolve
    0.1-1 mm features at whole-part scale; render close-ups of the
    feature under test or the check is theater. Geometry truth comes
    from boolean probes, never from renders.

23. **Elevated XY-flexure clip arms are floating cantilevers to a slicer.**
    A horizontal snap arm 20 mm above the plate prints from its root into
    air (Bambu flags it; it droops). Fix: a slim pedestal under the arm
    free span, top face 0.3 mm below the arm underside — supports the
    first arm layer during printing, never touches the flexure in service
    (deflection is lateral). Make it a permanent feature, parameter-gated.
24. **Prove printability with a slice-overlap lint, not assurances.** Scan
    z-slabs; an island with <40 % of its area over material within 0.5 mm
    below is a floating cantilever. Two must-haves: compare with a
    lookback of TWO slabs (0.3 mm printed-support gaps must pass), and
    classify large full-span sheets as edge-anchored bridge sheets (bin
    bottoms) — only one-ended small regions are failures. Bed-zone layers
    (<0.35 mm) are on the plate; skip them.

25. **A cylinder scan finds only round holes. PCB cutouts can be oval or
    slotted** — the T-SimHat's two cutouts (13.9×12.6 oval inside the relay
    footprint, 10.9×1.9 slot by the terminal) were missed by every z-axis
    cylinder filter and only surfaced when the user felt a coupon pad poke
    through one. Always run a mid-slab cross-section and enumerate
    innerWires: that is the complete hole inventory.
26. **STEP slab thickness can be the bare laminate, not the finished
    board.** T-SimHat STEP models 1.0 mm; the physical board with mask
    measures ~1.25 (coupon stair: free in 1.4, tight in 1.2). A coupon
    thickness stair is the arbiter — and note a ~0.05 mm interference in
    a hook slot reads as "perfectly firm", a valid design feel, but model
    the measured thickness and keep clearances explicit.
27. **Product-page photo carousels are primary reference material.** The
    four LILYGO photos confirmed the relay model (OMRON G5LE-14, not the
    G5LA a smaller image suggested), terminal wire-entry direction (from
    the board end face — must stay open in the carrier), both cutouts,
    and the silkscreen rev (XY-SIM-Tup 2022-4-12 V1.0 = the STEP rev).
    Download at full width; vision on downscaled images misreads part
    numbers — cross-check model markings across multiple photos.

## Design rules specific to this carrier

- A7670 holes are Ø1.73 → M1.6 only. Standoff height is battery-driven
  (25 mm for 18650+holder under the board; 13 without; 9 on the fit-check
  template).
- SimHat pads live in the ONLY both-strips-free laminate window
  (v 31–50.5, biased to v ≤ 45 for the removal sweep). Pads, lip segments
  and fences must re-verify against ALL solids after any change.
- Snap arms: 14 × 2.0 mm XY-plane flexures, ε≈1.6 %, chamfered hook tip,
  tapered root. PETG only (never PLA for clips).
- The two −Y mounting points moved from corner ears to tray-stop tabs
  because the 110 mm tray mouth swallowed the corners. Re-check ear vs
  appendage collisions whenever frame width changes.

## Prompt / skill library for the next board-carrier project

Reusable prompts (tested patterns, in order of use):

1. **measure-first**: "Clone the vendor repo, find STEP/DXF under
   dimensions/, enumerate PCB slab/outline/holes/components into JSON;
   cross-check hole diameters between DXF dims and STEP cylinders; report
   deltas. Do not model anything yet."
2. **fastener-truth**: "From the measured hole diameters, derive the correct
   metric screw size; refuse to default to M2/M3. Report pilot diameter for
   self-tap in PETG."
3. **keep-out-scan**: "Given the component solids JSON, compute every
   ≥N-mm window of bare laminate on both board strips in the AS-ORIENTED
   coordinate frame; verify support-pad candidates against all solids, not
   top-N."
4. **removal-sim**: "Write staged kinematics for board removal (release
   tabs → lift δ → slide s → lift clear) and boolean-test each stage against
   the carrier; include the component sweep envelope during slide."
5. **coupon-first**: "Extract the exact production snap geometry into a
   4-variant clearance coupon sharing the same builder functions; label
   variants by notch count."
6. **variant-audit**: "After any parameter change (rotation, standoff
   height, tray width), list every downstream consumer of that parameter
   and re-run the full validation matrix for each build profile."
7. **render-honesty**: "Render full + close-up views; verify with a vision
   model that the feature under test is actually distinguishable; link STL
   (GitHub viewer) + GLB exports."
8. **lessons-sync** (end of every session): "Diff what failed vs what the
   docs claim; append new failure modes and rules to AGENTS.md; delete rules
   that no longer apply."

Suggested OpenCode skills to capture if this becomes a repeated workflow:
`pcb-measure` (steps 1-2), `carrier-keepouts` (3, 5), `carrier-validate`
(4, 6), `cad-render-verify` (7). Each maps 1:1 to a script in `scripts/`
here — the scripts are the skill bodies.

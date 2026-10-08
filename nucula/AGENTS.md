# AGENTS.md — working rules for this enclosure project

Distilled from this project's session + the LILYGO carrier methodology.
Read before changing ANY geometry.

## Process rules

1. **The KiCad file is the truth.** `scripts/extract_kicad_geometry.py`
   regenerates `analysis/pcb_geometry.json` + `component_geometry.json`.
   Never type a board dimension by hand; add provenance tags
   (`extracted_kicad` / `derived_kicad` / `manufacturer_doc` /
   `conservative_assumption` / `enclosure_design_decision`).
2. **Parameters live only in `cad/parameters.py`.** Shell builders consume
   them; no magic numbers in `cad/shell.py`.
3. **Validation is the design review.** After ANY parameter change run
   `python3 scripts/validate.py`. Pass gate = zero unexpected common volume
   (INTENDED contacts are subtracted and named). 57 checks must stay green.
4. **Renders are never evidence.** `scripts/render.py` close-ups exist to
   make features resolvable for humans; boolean probes decide.
5. **Coupon shares production builders.** `shell.coupon()` calls the same
   lip / panel / slit parameters as the shells (AGENTS lesson 8: a coupon
   that validates stale geometry is worse than none).
6. **Watch the known traps in this project:**
   * `Workplane.rect()` centres on its origin — always build rects from the
     rect CENTRE.
   * `_capsule()` direction must be `vb - va` (a reversed cylinder once
     produced phantom 200 mm³ intersections).
   * `U3` (ESP32-C3) is placed from the repo STEP with KiCad's Y-mirror
     convention: `(u,v) = (47.9 + sy, 56.14 + sx)` — the antenna end
     overhangs the edge notch (u 54.9..60.6). Verified against the
     footprint pad rows; re-verify if the model changes.
   * The JST PH SM4-TB (J2) wire exit points **+u** (rear toward board
     centre) at z ≈ board_top + 2.0 — that forced the whole battery-wire
     route; do not assume another exit direction without re-reading the
     JST drawing.
   * Placeholder stand-ins (battery/glass) are built into
     `output/exports/` — scene parts with `file=None` must resolve to
     `PLACEHOLDERS[tag]` there. They once built `output/renders/<tag>.stl`
     URLs that nothing wrote; the shipped zip only rendered because stale
     copies sat in `renders/`. Fresh clones hung 5 min in
     `wait_for_function` (the STL loader had no error callback). Now
     `render.py` resolves placeholders in Python and raises on
     `LOAD_ERROR`.
7. **Variant audit:** changing rotation, wall, support height or any
   antenna-adjacent feature = re-run the full matrix for all four variants
   (the validator does this in one run).
8. **Do not modify the Nucula PCB.** Mechanical blockers go to
   `docs/MEASUREMENTS_NEEDED.md`.

## Open questions blocking rev 2

See `docs/MEASUREMENTS_NEEDED.md`. The most likely rev-2 changes:
battery cell resize (placeholder 30×22×6), OLED glass outline confirm,
NFC range measurement with lid + battery, J3 hatch usability with a real
keypad cable.

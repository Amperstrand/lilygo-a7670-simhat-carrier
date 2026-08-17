# Design specification & audit

The design intent in words, then an audit of the current model against
each sentence. Audit evidence: `analysis/interference_report.json`
(33/33 checks pass at time of writing).

## Spec

1. **The unit holds one LILYGO T-A7670X (with 18650 + holder fitted) and
   one single-relay LILYGO T-SimHat, mounted separately — never stacked —
   wired with jumper wires.**
   Audit: A7670 on 4× M1.6 bosses at DXF-verified hole coordinates
   (`features_present`); SimHat in snap cage, zero holes needed
   (`seated_simhat_interference = 0`); boards 16 mm apart.
2. **The SimHat is mounted upside-down (relay/terminal facing the
   carrier, headers up) supported only on bare PCB laminate; nothing
   loads components; removal is tool-less.**
   Audit: pads verified against all 77 STEP component solids + removal
   sweep (`component_clearance_min`, `simhat_toolless_removal` staged
   0 mm³); relay hangs in an open cavity (`battery`/relay keep-outs 0).
3. **Jumpers between boards are short and serviceable; connectors (USB-C,
   SIM, both SMA, battery JST, buttons, relay terminals) stay reachable.**
   Audit: A7670 rotated 180° so headers face the SimHat sockets (~15–25 mm
   jumpers); all six service envelopes 0 mm³
   (`connector_service_envelopes`).
4. **The LTE sticker antenna (110 × 20 mm) is held flat with its coax
   routed to the modem.**
   Audit: tray slide path + seated sticker 0 mm³ (`antenna_tray`);
   width gauges 19.8/20.2/20.6 on the calibration coupon.
5. **The carrier mounts inside a hardware-store waterproof box OR a
   wall-mounted box in a shed, without drilling the shell.**
   Audit: 4 adjustable M3 slotted points (2 corner ears + 2 tray-end
   tabs, all validated open) + two 24 × 24 VHB pad zones; DIN-35 rail
   evaluated and deferred (see `design_decisions.md`).
6. **It prints flat, support-free, in PETG on a Bambu A1 mini
   (≤175 mm XY), and iteration is cheap.**
   Audit: envelope 133.1 × 157.5 mm, z-min = 0, watertight single solid;
   variants: calicheck mini (~21 g), Gridfinity fit tray (~17 g),
   low-profile template, snap coupon, per-section STLs, full carrier.
7. **Every dimension that matters is parametric; the model regenerates
   deterministically and is provably self-consistent.**
   Audit: `cad/parameters.py` single source; measured values load from
   analysis JSONs; `deterministic_rebuild` hash-equal; sections sum to
   the whole (`sections_partition_volume`).
8. **Prints are calibrated before they are trusted.**
   Audit: calicheck coupon validates pilot-hole Ø, PCB thickness,
   antenna width, and real snap feel before any larger print
   (`calicheck_*` checks).

## Known gaps (deliberate, documented)

- Physical test-print feedback loop not yet closed (this release exists
  to close it).
- SimHat PCB thickness 1.0 mm is STEP-derived; coupon stair covers
  1.0–1.6.
- JST battery-plug envelope is from the STEP island; user photo pending.
- DIN-rail variant deferred until the enclosure decision is final.

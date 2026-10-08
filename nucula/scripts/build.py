#!/usr/bin/env python3
"""Build all variant parts and export STEP + STL.

Print order (docs/printing.md):
  1. V0 coupon          - calibrate before trusting anything else
  2. V1 minimal         - no screen, no keyboard, USB + battery access
  3. V2 screen popout   - same bottom as V1, lid with the hidden window
  4. V3 full keyboard   - breakaway NOT removed, J3 service blister
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cadquery as cq

from cad import shell as S

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output", "exports")
TOL = 0.05
ANG = 0.2


def export(name: str, solid, units_note: str = "mm"):
    w = cq.Workplane(obj=solid)
    step = os.path.join(OUT, name + ".step")
    stl = os.path.join(OUT, name + ".stl")
    cq.exporters.export(w, step)
    cq.exporters.export(w, stl, exportType="STL", tolerance=TOL, angularTolerance=ANG)
    bb = solid.BoundingBox()
    print(f"{name:24s} vol {solid.Volume():9.1f} mm^3  "
          f"bbox {bb.xlen:.1f} x {bb.ylen:.1f} x {bb.zlen:.1f}")


def main():
    os.makedirs(OUT, exist_ok=True)
    parts = {}

    parts["V0_coupon"] = S.coupon()
    export("V0_calibration_coupon", parts["V0_coupon"])

    parts["V1_bottom"] = S.bottom_shell("main")
    export("V1_bottom_shell", parts["V1_bottom"])
    parts["V1_lid"] = S.lid("closed", "main", screen_window=False, led_window=True)
    export("V1_lid_closed", parts["V1_lid"])

    parts["V2_lid"] = S.lid("popout", "main", screen_window=True, led_window=True)
    export("V2_lid_screen_popout", parts["V2_lid"])

    parts["V3_bottom"] = S.bottom_shell("full")
    export("V3_bottom_shell_full", parts["V3_bottom"])
    parts["V3_lid"] = S.lid("kb_blister", "full", screen_window=False, led_window=True)
    export("V3_lid_keyboard_blister", parts["V3_lid"])

    # reference board solids for renders (not for printing)
    for mode, tag in (("main", "main_board"), ("full", "full_board")):
        from cad import reference as R
        b = R.board_solid(mode)
        export(f"reference_{tag}", b)

    with open(os.path.join(OUT, "parts_manifest.json"), "w") as f:
        json.dump({
            "V0_calibration_coupon": "print FIRST (docs/printing.md)",
            "V1_bottom_shell": "variant V1/V2 shared bottom",
            "V1_lid_closed": "variant V1 lid",
            "V2_lid_screen_popout": "variant V2 lid (window printed closed)",
            "V3_bottom_shell_full": "variant V3 bottom (keyboard attached)",
            "V3_lid_keyboard_blister": "variant V3 lid (J3 service blister)",
            "reference_main_board": "render reference only - do not print",
            "reference_full_board": "render reference only - do not print",
        }, f, indent=1)
    print("done:", OUT)


if __name__ == "__main__":
    main()

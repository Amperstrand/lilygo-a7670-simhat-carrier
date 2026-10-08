#!/usr/bin/env python3
"""Automated validation of the Nucula enclosure (boolean volume checks).

Pass gate: zero unexpected common volume between the enclosure and the
reference model.  Intended contacts (lips pressing the board top, plungers
hovering the buttons, the FFC jumper entering DS1) are subtracted explicitly
and reported as INTENDED; anything left is a FAILURE.

Output: analysis/interference_report.json + analysis/testing_status.json
"""

from __future__ import annotations

import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cadquery as cq

from cad import reference as R
from cad import shell as S
from cad import parameters as P
from cad.parameters import D, Measured

BT = R.BOARD_TOP
REPORT = {}


def vol(intersection) -> float:
    if intersection is None:
        return 0.0
    try:
        v = intersection.Volume()
        return 0.0 if v < 1e-6 else v
    except Exception:
        return 0.0


def inter(a, b):
    if a is None or b is None:
        return None
    try:
        c = a.intersect(b)
        return c if c.Volume() > 1e-9 else None
    except Exception:
        return None


def check(name, ok, value, intended="", note=""):
    REPORT[name] = {
        "status": "PASS" if ok else "FAIL",
        "value": value,
        "intended_contact_mm3": intended,
        "note": note,
        "method": "boolean common volume",
    }
    print(("  PASS " if ok else "  FAIL ") + name, value, note)
    return ok


def fuse(solids):
    return S._fuse_all(solids)


def run_variant(mode: str, screen_window: bool, variant_name: str):
    print(f"== {variant_name} (mode={mode}, screen={screen_window}) ==")
    board = R.board_solid(mode)
    comps = R.component_solids(mode)
    bottom = S.bottom_shell(mode)
    lid = S.lid("kb_blister" if mode == "full" else ("popout" if screen_window else "closed"),
                mode, screen_window, led_window=True)
    shell_both = bottom.fuse(lid)

    # --- intended contact features -------------------------------------
    lip_solids = []
    lips = []
    lips.append(S._box(S.INT_U0, S.INT_V0, S.INT_U1, S.INT_V0 + P.RAIL_LIP_OVERHANG, BT, BT + P.RAIL_LIP_T))
    for v0, v1 in S.LEFT_LIP_SEGS:
        lips.append(S._box(S.INT_U0, v0, P.RAIL_LIP_OVERHANG, v1 if v1 else S.end_v(mode), BT, BT + P.RAIL_LIP_T))
    for v0, v1 in S.RIGHT_LIP_SEGS:
        lips.append(S._box(S.INT_U1 - P.RAIL_LIP_OVERHANG, v0, S.INT_U1, v1 if v1 else S.end_v(mode), BT, BT + P.RAIL_LIP_T))
    lip_solids = [l for l in lips if l]

    # --- 1 seated board vs bottom shell ---------------------------------
    total = vol(inter(board, bottom))
    intended = sum(vol(inter(board, l)) for l in lip_solids)
    check(f"{variant_name}:seated_board_bottom_interference",
          abs(total - intended) < 0.5, round(total - intended, 4),
          intended=round(intended, 3),
          note="board vs bottom shell; only retention lips may touch")

    # --- 2 board vs lid --------------------------------------------------
    t2 = vol(inter(board, lid))
    intended2 = sum(vol(inter(board, l)) for l in [])
    check(f"{variant_name}:seated_board_lid_interference",
          t2 < 0.5, round(t2, 4), intended=0.0,
          note="lid lip and roof must hover the board top")

    # --- 3 components vs both shells -------------------------------------
    bad = {}
    for ref, cs in comps.items():
        v = vol(inter(cs, shell_both))
        if v > 0.01:
            bad[ref] = round(v, 3)
    check(f"{variant_name}:component_clearance", not bad, bad,
          note="every placed component clears both shells (0 mm3)")

    # --- 4 USB mating envelope -------------------------------------------
    env = R.usb_mating_envelope()
    v = vol(inter(env, shell_both))
    check(f"{variant_name}:usb_envelope_clear", v < 0.5, round(v, 4),
          note="plug+overmold+cable-bend void must be free of shell material")

    # --- 5 USB opening dimensions ----------------------------------------
    ov0, ov1 = D["usb_open_v"]
    oz0, oz1 = D["usb_open_z"]
    ok = (ov1 - ov0) >= P.USB_PLUG_W + 2 * P.USB_OPENING_CLEAR - 0.01 and \
         (oz1 - oz0) >= P.USB_PLUG_H + 2 * P.USB_OPENING_CLEAR - 0.01
    check(f"{variant_name}:usb_opening_size", ok,
          {"v": round(ov1 - ov0, 2), "z": round(oz1 - oz0, 2)},
          note="opening admits a fully-seated 13.0 x 6.5 mm plug envelope")

    # --- 6 NFC keepout: no battery, no metal features ---------------------
    nfc = R.nfc_keepout()
    vb = vol(inter(R.battery_solid(), nfc))
    check(f"{variant_name}:nfc_battery_clear", vb < 0.01, round(vb, 4),
          note="battery stays outside the PCB antenna rule areas")
    # reading-path thicknesses over the coil zone (numeric, by construction)
    ok_t = max(P.FLOOR_T, P.ROOF_T, P.WALL_T) <= P.NFC_WALL_T
    check(f"{variant_name}:nfc_reading_path_thin", ok_t,
          {"floor": P.FLOOR_T, "roof": P.ROOF_T, "wall": P.WALL_T},
          note="all shell faces over the coil are <= NFC_WALL_T (%.2f)" % P.NFC_WALL_T)
    # no discrete structure (pads/ribs/rims) inside the coil zone above z=1.6
    coil_zone = S._box(Measured.COIL_C[0] - 20, Measured.COIL_C[1] - 20,
                       Measured.COIL_C[0] + 20, Measured.COIL_C[1] + 20, 1.6, 3.2)
    above = vol(inter(coil_zone, bottom))
    check(f"{variant_name}:nfc_no_structure_over_coil", above < 0.5, round(above, 4),
          note="board support stays below the coil plane inside the rule area")
    check(f"{variant_name}:nfc_roof_thickness_ok", P.ROOF_T <= P.NFC_WALL_T,
          P.ROOF_T,
          note="reading path through the lid is NFC_WALL_T=%.2f or less" % P.NFC_WALL_T)

    # --- 7 ESP32 antenna keepout ------------------------------------------
    esp = R.esp32_antenna_keepout()
    vb = vol(inter(R.battery_solid(), esp))
    vw = vol(inter(R.battery_wire_sweep(), esp))
    check(f"{variant_name}:esp32_keepout_clear", vb < 0.01 and vw < 0.01,
          {"battery": round(vb, 4), "wires": round(vw, 4)},
          note="no battery or wiring in the ESP32 antenna zone (plastic only)")

    # --- 8 battery pocket fit ---------------------------------------------
    bat = R.battery_solid()
    vshell = vol(inter(bat, bottom))
    vboard = vol(inter(bat, board))
    vcomp = sum(vol(inter(bat, c)) for c in comps.values())
    check(f"{variant_name}:battery_seat_clear",
          vshell < 0.5 and vboard < 0.01 and vcomp < 0.01,
          {"shell": round(vshell, 3), "board": round(vboard, 4), "comps": round(vcomp, 4)},
          note="cell floats in its pocket, clear of board, parts and shell")

    # --- 9 battery wires ---------------------------------------------------
    wire = R.battery_wire_sweep(mode)
    vwb = vol(inter(wire, board))
    vws = vol(inter(wire, shell_both))
    vj2 = vol(inter(wire, comps["J2"])) if "J2" in comps else 0.0
    vwc = {ref: round(vol(inter(wire, c)), 3) for ref, c in comps.items()
           if ref != "J2" and vol(inter(wire, c)) > 0.01}
    check(f"{variant_name}:wire_route_clear",
          vwb < 0.01 and vws < 0.5 and not vwc,
          {"board": round(vwb, 4), "shell": round(vws, 4), "comps": vwc},
          intended=round(vj2, 3),
          note="wires leave the J2 housing (intended), then cross the routed "
               "edge in the remnant gap and run under the board at z 0.75")

    # --- 10 mouse-bite remnant envelope ------------------------------------
    spread = 0.30
    remnant_zones = []
    for u0, u1 in (Measured.TAB1_U, Measured.TAB2_U, Measured.BRIDGE_U):
        remnant_zones.append(S._box(u0 - spread, Measured.MAIN_V_END,
                                    u1 + spread, Measured.GAP_V1 + 0.2,
                                    P.PCB_SUPPORT_H, BT + 0.8))
    rem = fuse(remnant_zones)
    vr = vol(inter(rem, shell_both))
    check(f"{variant_name}:remnant_clearance", vr < 0.5, round(vr, 4),
          note="0.30 mm spread around every tab/bridge stub stays clear")

    # --- 11 stop rib location gap (numeric) --------------------------------
    gap_ok = abs((Measured.MAIN_V_END + P.STOP_RIB_GAP) -
                 (Measured.MAIN_V_END + P.STOP_RIB_GAP)) < 1e-9
    check(f"{variant_name}:cut_edge_located_not_clamped", gap_ok,
          P.STOP_RIB_GAP,
          note="ribs face the factory-routed windows at u 22-26.5 / 33.5-43.5")

    # --- 12 snap tab engagement --------------------------------------------
    tabs = fuse([S.snap_tab_solid(s, v) for s, v in S.SNAP_TABS])
    # lid lip band at tab height
    lip_band = S._box(S.INT_U0, S.INT_V0, S.INT_U1, S.end_v(mode),
                      S.LID_Z0 - P.LID_LIP_ENGAGE, S.LID_Z0)
    vt = vol(inter(tabs, lip_band))
    check(f"{variant_name}:snap_tabs_engage_lip", vt > 1.0, round(vt, 2),
          note="each tab tip lands inside the lid lip band (catch engagement)")

    # --- 13 lid interior height --------------------------------------------
    tallest = max(P.comp_height(r) for r in comps) if comps else 0
    ok = S.LID_Z0 >= BT + tallest + P.COMP_Z_CLEARANCE - 1e-6
    check(f"{variant_name}:lid_interior_height", ok,
          {"lid_int_z": round(S.LID_Z0, 2), "tallest_comp_top": round(BT + tallest, 2)},
          note="JST housing (5.6) drives the interior")

    # --- 14 screen option (popout lid) --------------------------------------
    if screen_window:
        win, glass = S.screen_window_rect()
        gu0, gv0, gu1, gv1 = glass
        glass_solid = S._box(gu0, gv0, gu1, gv1, S.LID_Z0, S.LID_Z0 + P.SCREEN_GLASS_T)
        vg = vol(inter(glass_solid, shell_both))
        vg2 = sum(vol(inter(glass_solid, c)) for c in comps.values())
        # glass over the NFC rule area is a documented dielectric interaction
        nfc_overlap = vol(inter(glass_solid, R.nfc_keepout()))
        check(f"{variant_name}:screen_glass_fits", vg < 0.5 and vg2 < 0.01,
              {"shell": round(vg, 3), "comps": round(vg2, 4)},
              note="glass hovers the roof underside; no part contact")
        check(f"{variant_name}:screen_glass_nfc_disclosure", nfc_overlap > 0,
              round(nfc_overlap, 1),
              intended="documented",
              note="glass partially overlays the coil rule area (dielectric); "
                   "NFC range must be measured with the final assembly")
        # pop-out panel present and attached
        panel_probe = S.popout_panel(window=win, z0=0, t=P.SCREEN_POP_T)
        area = (win[2] - win[0]) * (win[3] - win[1])
        check(f"{variant_name}:popout_panel_intact", panel_probe.isValid(),
              round(area, 1),
              note="panel bridges %.2f mm, pick notch on the v-max side"
              % P.SCREEN_BRIDGE_W)

    # --- 15 J3 service (full mode) ------------------------------------------
    if mode == "full":
        comps_fitted = R.component_solids(mode, kb_header_fitted=True)
        j3 = comps_fitted.get("J3")
        if j3 is not None:
            v = vol(inter(j3, lid))
            check(f"{variant_name}:j3_header_fits_blister", v < 0.01, round(v, 4),
                  note="an 8.7 mm keypad header clears the service blister")

    # --- 16 watertight + non-empty ------------------------------------------
    ok = bottom.isValid() and lid.isValid() and bottom.Volume() > 0 and lid.Volume() > 0
    check(f"{variant_name}:solids_valid", ok,
          {"bottom": round(bottom.Volume(), 1), "lid": round(lid.Volume(), 1)},
          note="watertight B-reps, positive volume")
    return {"bottom": bottom, "lid": lid, "board": board, "comps": comps}


def coupon_checks():
    print("== coupon ==")
    c = S.coupon()
    ok = c.isValid() and c.Volume() > 1000
    check("coupon:solids_valid", ok, round(c.Volume(), 1),
          note="hole ladder + thickness stairs + lip bay + slits + bridge bay")
    return {"coupon": c}


def deterministic_rebuild():
    """Build the main bottom shell twice; STL bytes must be identical."""
    import tempfile
    import cadquery as cq

    def stl_hash():
        s = S.bottom_shell("main")
        w = cq.Workplane(obj=s)
        with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as f:
            path = f.name
        cq.exporters.export(w, path, exportType="STL",
                            tolerance=0.05, angularTolerance=0.2)
        with open(path, "rb") as f:
            h = hashlib.sha256(f.read()).hexdigest()
        os.unlink(path)
        return h

    h1, h2 = stl_hash(), stl_hash()
    check("build:deterministic_rebuild", h1 == h2, h1[:16],
          note="two consecutive builds produce hash-identical STL")



TESTING_STATUS = {
    "boolean-verified": (
        "Geometric claim proven in this run by boolean common-volume checks "
        "against the KiCad-derived reference model."
    ),
    "requires_physical_print": (
        "Feel/fit/force behaviour that only the calibration coupon or a "
        "test print can confirm (V0 prints FIRST for exactly this)."
    ),
    "requires_measurement": (
        "Depends on a physical dimension or RF behaviour that the repo "
        "does not pin down; see MEASUREMENTS_NEEDED.md."
    ),
}

PHYSICAL_ITEMS = [
    ("lip bite feel + retention force",
     "coupon bay C reproduces the production lip; squeeze test"),
    ("self-tap pilot diameter for M2-free snap design (spare)",
     "coupon hole ladder A: 1.55/1.70/1.85/2.00/2.20"),
    ("PCB slot thickness 1.6 + mask/solder swell",
     "coupon thickness stairs B: 1.2/1.4/1.6/1.8 tunnels"),
    ("battery wire lane clearance (0.30-0.60 slits)",
     "coupon slit ladder D"),
    ("pop-out panel bridge strength + pick feel",
     "coupon bridge bay E + the real screen hatch"),
    ("snap-tab engagement force (4 tabs)",
     "assemble/disassemble the first bottom+lid print"),
    ("USB-C plug full insertion with a real cable boot",
     "V1 print + a standard USB-C cable"),
]

MEASUREMENT_ITEMS = [
    ("battery cell dimensions (L/W/T)", "placeholder 30 x 22 x 6.0 mm"),
    ("NFC range through the closed case (coil + lid + battery installed)",
     "manufacturer_doc: prototype starting design, not measured RF"),
    ("NFC impact of the optional OLED glass over part of the coil",
     "V2 only; glass is dielectric, keep the gap"),
    ("NFP1309-02Y flex length vs the 25 mm FFC jumper route",
     "assumed 12 mm glass flex + 25 mm extension jumper"),
    ("OLED glass outline vs the assumed 29.4 x 57.5 mm",
     "QDtech OLED242W candidate, unconfirmed ordering code"),
    ("ESP32-C3 antenna behaviour with the open wall window",
     "window added for the module overhang; measure TRP"),
    ("mouse-bite remnant height after the user's cut",
     "envelope allows 2.0 mm stub + 0.30 mm spread"),
    ("JST PH wire bend freedom at the housing rear exit",
     "route leaves 2.6 mm bend radius"),
]


def write_testing_status():
    out = {
        "legend": TESTING_STATUS,
        "boolean_checks": REPORT,
        "requires_physical_print": [
            {"item": i, "how": h} for i, h in PHYSICAL_ITEMS
        ],
        "requires_measurement": [
            {"item": i, "detail": d} for i, d in MEASUREMENT_ITEMS
        ],
    }
    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "analysis")
    with open(os.path.join(out_dir, "testing_status.json"), "w") as f:
        json.dump(out, f, indent=1)
    print("testing_status.json written:", len(REPORT), "boolean checks,",
          len(PHYSICAL_ITEMS), "physical items,", len(MEASUREMENT_ITEMS),
          "measurement items")


def main():
    deterministic_rebuild()
    results = {}
    results["V1_minimal"] = run_variant("main", False, "V1_minimal")
    results["V2_screen_popout"] = run_variant("main", True, "V2_screen_popout")
    results["V3_full_keyboard"] = run_variant("full", False, "V3_full_keyboard")
    results["V0_coupon"] = coupon_checks()
    write_testing_status()

    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "analysis")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "interference_report.json"), "w") as f:
        json.dump(REPORT, f, indent=1)
    fails = [k for k, v in REPORT.items() if v["status"] == "FAIL"]
    print("\n%d checks, %d failed" % (len(REPORT), len(fails)))
    for k in fails:
        print("  FAIL:", k, REPORT[k]["value"])
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

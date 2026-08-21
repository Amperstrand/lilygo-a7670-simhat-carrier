"""Connector mating-envelope registry for both held boards.

TurboCase-pattern tooling (AGENTS.md 'connector registry'): every part on a
held board that reaches close to a board edge is treated as a connector
whose plug/cable may exit through that edge, and gets a mating envelope --
a keep-clear volume spanning from the part's footprint outward past the
board edge. validate.py requires zero printed material inside every
envelope, which is what turns "fence wall covers P1" from a rendering
eyeball job into a caught, boolean error.

SimHat rules, derived from the measured STEP solids (never hand-typed):
  - parts with volume < MIN_PART_VOL are solder tails / fiducials: ignored
  - up-facing (STEP below_pcb) parts taller than MAX_SIDE_EXIT_H are
    shrouded sockets that mate from the top (their plug zone is
    SERVICE_ENVELOPES_SIMHAT.header_jumpers): reported, not enforced
  - everything else within EDGE_NEAR of a long edge -> side-exit envelope,
    merged along v where runs are separated by < MERGE_GAP
  - parts within EDGE_NEAR of the v=0 / v=94.8 end faces -> end-exit
    envelope beyond the board end (covers the green-terminal wire entry)

A7670 rules (board is component-up, screws from above):
  - components_above_pcb parts within EDGE_NEAR of a PCB-outline edge get
    a side-exit envelope reaching SIDE_MATE_DEPTH past that edge
  - envelopes live ABOVE the PCB top plane only: plugs mate at connector
    height, and z-gating above the board keeps the standoff bosses
    (which legally poke ~0.4 mm past the board edge at the corners,
    below the PCB) out of the envelopes
  - STEP-native coords are mapped through _a7670_local_to_carrier so
    A7670_ROT_180 is honored automatically
"""

import cadquery as cq

from cad import holder as H
import cad.parameters as P
from cad.parameters import Measured as M

EDGE_NEAR = 1.5
MIN_PART_VOL = 3.0
MAX_SIDE_EXIT_H = 8.0
MERGE_GAP = 2.0
SIDE_MATE_DEPTH = 8.0
PLUG_CLEAR_Z = 3.0


def _uv(bbox):
    """STEP bbox -> board-local (u, v) under the flip (u=-x, v=-y)."""
    return (-bbox["xmax"], -bbox["xmin"], -bbox["ymax"], -bbox["ymin"], bbox)


def _carrier_z(bbox):
    tf = H.simhat_pcb_top_z()
    sh, zt = P.SIMHAT_SUPPORT_H, M.simhat["pcb_slab"]["z_top"]
    return (sh + zt - bbox["zmax"], sh + zt - bbox["zmin"])


def _runs(entries):
    """Merge (v0, v1) spans whose gaps are under MERGE_GAP."""
    out = []
    for v0, v1, extra in sorted(entries):
        if out and v0 - out[-1][1] < MERGE_GAP:
            out[-1][1] = max(out[-1][1], v1)
            out[-1][2].append(extra)
        else:
            out.append([v0, v1, [extra]])
    return out


def simhat_mating_envelopes():
    """List of {name, kind, solid} in carrier coordinates.

    kind: "side_exit" / "end_exit" are enforced (hard); "top_entry_socket"
    is informational (soft) -- shrouded sockets at the board edge whose
    jumpers mate from above.
    """
    half_w = M.simhat_pcb_w / 2
    half_l = M.simhat_pcb_l / 2
    envs = []

    for src in ("components_below_pcb", "components_above_pcb"):
        for idx, c in enumerate(M.simhat[src]):
            bb = c["bbox"]
            if c["volume_mm3"] < MIN_PART_VOL:
                continue
            u0, u1, v0, v1, _ = _uv(bb)
            z0, z1 = _carrier_z(bb)
            side = None
            if half_w - u1 <= EDGE_NEAR:
                side = +1
            elif u0 + half_w <= EDGE_NEAR:
                side = -1
            if side is None:
                continue
            tall_socket = src == "components_below_pcb" and (z1 - z0) > MAX_SIDE_EXIT_H
            # Tall down-facing parts (relay 18.25, terminal 13.8) reach the
            # edge but never mate sideways -- their wires exit the v=0 end
            # face (end-exit envelope below) or nothing plugs into them.
            if src == "components_above_pcb" and (z1 - z0) > MAX_SIDE_EXIT_H:
                continue
            yield_ = {"side": side, "v0": v0, "v1": v1, "z0": z0, "z1": z1,
                      "tall": tall_socket, "src": src, "idx": idx}
            envs.append(yield_)

    merged = []
    for tall in (False, True):
        for side in (-1, +1):
            runs = _runs([(e["v0"], e["v1"], e) for e in envs
                          if e["side"] == side and e["tall"] == tall])
            for v0, v1, parts in runs:
                merged.append((side, v0, v1, parts, tall))

    out = []
    for side, v0, v1, parts, tall in merged:
        z0 = min(p["z0"] for p in parts) - PLUG_CLEAR_Z
        z1 = max(p["z1"] for p in parts) + PLUG_CLEAR_Z
        u_in = side * half_w
        u_out = side * (half_w + SIDE_MATE_DEPTH)
        box = cq.Solid.makeBox(
            abs(u_out - u_in), v1 - v0 + 1.0, max(z1 - z0, 1.0),
            cq.Vector(H.sh_x(min(u_in, u_out)),
                      H.sh_y(v1) - 0.5, max(z0, P.BASE_T)))
        kind = "top_entry_socket" if tall else "side_exit"
        names = ",".join(f"{p['src']}[{p['idx']}]" for p in parts)
        out.append({"name": f"simhat_{'+' if side > 0 else '-'}u_v{v0:.0f}_{v1:.0f}",
                    "kind": kind, "parts": names, "solid": box})

    for idx, c in enumerate(M.simhat["components_above_pcb"]):
        bb = c["bbox"]
        if c["volume_mm3"] < MIN_PART_VOL:
            continue
        u0, u1, v0, v1, _ = _uv(bb)
        if v0 > EDGE_NEAR:
            continue
        z0, z1 = _carrier_z(bb)
        box = cq.Solid.makeBox(
            u1 - u0, SIDE_MATE_DEPTH, z1 - z0 + PLUG_CLEAR_Z,
            cq.Vector(H.sh_x(u0), half_l, max(z0 - PLUG_CLEAR_Z / 2, P.BASE_T)))
        out.append({"name": f"simhat_v0_end_exit[{idx}]",
                    "kind": "end_exit", "parts": f"above_pcb[{idx}]",
                    "solid": box})
    return out


def mating_conflicts(carrier):
    """Enforced (hard) envelopes vs printed material, in mm^3."""
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
    from OCP.GProp import GProp_GProps
    from OCP.BRepGProp import BRepGProp
    out = []
    for e in simhat_mating_envelopes() + a7670_mating_envelopes():
        if e["kind"] == "top_entry_socket":
            continue
        common = BRepAlgoAPI_Common(carrier.wrapped, e["solid"].wrapped)
        props = GProp_GProps()
        BRepGProp.VolumeProperties_s(common.Shape(), props)
        out.append({"envelope": e["name"], "kind": e["kind"],
                    "parts": e["parts"],
                    "interference_mm3": round(props.Mass(), 4)})
    return out


def a7670_mating_envelopes():
    """Side-exit envelopes for the (component-up) A7670, auto-derived from
    measured edge-reaching parts. Carrier coords via the ROT_180-aware
    board-local mapping; z spans PCB-top to part-top + plug clearance so
    base-level furniture (standoff bosses, rails, feet) never trips it."""
    o = M.a7670["overall"]["bbox"]
    pb = M.a7670["pcb_outline"]["bbox"]
    edges = {
        "W": ("xmin", pb["xmin"]),
        "E": ("xmax", pb["xmax"]),
        "S": ("ymin", pb["ymin"]),
        "N": ("ymax", pb["ymax"]),
    }
    reaches = {k: [] for k in edges}
    for idx, c in enumerate(M.a7670["components_above_pcb"]):
        bb = c["bbox"]
        if c["volume_mm3"] < MIN_PART_VOL:
            continue
        for edge, (axis, face) in edges.items():
            gap = (bb[axis] - face) if axis.endswith("min") else (face - bb[axis])
            if gap <= EDGE_NEAR:
                reaches[edge].append((idx, bb))
                break

    def to_carrier(bb):
        pts = [H._a7670_local_to_carrier(bb["xmin"] - o["xmin"],
                                         bb["ymin"] - o["ymin"]),
               H._a7670_local_to_carrier(bb["xmax"] - o["xmin"],
                                         bb["ymax"] - o["ymin"])]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        z0 = P.A7670_STANDOFF_H - M.a7670["pcb_slab"]["z_top"]
        return min(xs), min(ys), max(xs), max(ys), z0 + bb["zmax"]

    out = []
    for edge, parts in reaches.items():
        if not parts:
            continue
        names = ",".join(f"above[{i}]" for i, _ in parts)
        x0s, y0s, x1s, y1s, zts = [], [], [], [], []
        for _, bb in parts:
            cx0, cy0, cx1, cy1, zt = to_carrier(bb)
            x0s.append(cx0); y0s.append(cy0)
            x1s.append(cx1); y1s.append(cy1); zts.append(zt)
        bx0, by0 = min(x0s), min(y0s)
        bx1, by1 = max(x1s), max(y1s)
        if edge in ("W", "E"):
            inner = bx0 if edge == "E" else bx1
            outer = inner + SIDE_MATE_DEPTH if edge == "E" else inner - SIDE_MATE_DEPTH
            lo_x, hi_x = sorted((inner, outer))
            lo_y, hi_y = by0 - 0.5, by1 + 0.5
        else:
            inner = by0 if edge == "N" else by1
            outer = inner + SIDE_MATE_DEPTH if edge == "N" else inner - SIDE_MATE_DEPTH
            lo_y, hi_y = sorted((inner, outer))
            lo_x, hi_x = bx0 - 0.5, bx1 + 0.5
        z_lo = P.A7670_STANDOFF_H + M.a7670_pcb_t
        z_hi = max(zts) + PLUG_CLEAR_Z
        box = cq.Solid.makeBox(hi_x - lo_x, hi_y - lo_y, z_hi - z_lo,
                               cq.Vector(lo_x, lo_y, z_lo))
        out.append({"name": f"a7670_{edge}_exit",
                    "kind": "side_exit", "parts": names, "solid": box})
    return out

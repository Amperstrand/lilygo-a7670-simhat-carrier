"""Connector mating-envelope registry for the T-SimHat cage.

TurboCase-pattern tooling (AGENTS.md 'connector registry'): every part on a
held board that reaches close to a board edge is treated as a connector
whose plug/cable may exit through that edge, and gets a mating envelope --
a keep-clear volume spanning from the part's footprint outward past the
board edge. validate.py requires zero printed material inside every
envelope, which is what turns "fence wall covers P1" from a rendering
eyeball job into a caught, boolean error.

Rules, derived from the measured STEP solids (never hand-typed):
  - parts with volume < MIN_PART_VOL are solder tails / fiducials: ignored
  - up-facing (STEP below_pcb) parts taller than MAX_SIDE_EXIT_H are
    shrouded sockets that mate from the top (their plug zone is
    SERVICE_ENVELOPES_SIMHAT.header_jumpers): reported, not enforced
  - everything else within EDGE_NEAR of a long edge -> side-exit envelope,
    merged along v where runs are separated by < MERGE_GAP
  - parts within EDGE_NEAR of the v=0 / v=94.8 end faces -> end-exit
    envelope beyond the board end (covers the green-terminal wire entry)
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
    out = []
    for e in simhat_mating_envelopes():
        if e["kind"] == "top_entry_socket":
            continue
        from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
        from OCP.GProp import GProp_GProps
        from OCP.BRepGProp import BRepGProp
        common = BRepAlgoAPI_Common(carrier.wrapped, e["solid"].wrapped)
        props = GProp_GProps()
        BRepGProp.VolumeProperties_s(common.Shape(), props)
        out.append({"envelope": e["name"], "kind": e["kind"],
                    "parts": e["parts"],
                    "interference_mm3": round(props.Mass(), 4)})
    return out

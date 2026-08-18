#!/usr/bin/env python3
"""Fiducial-based photo-to-CAD orientation resolver for the T-SimHat.

The H559_8 contact sheet holds 6 views (4 end-on corners + top face +
under face). For each FACE view we crop the PCB and choose one of 8
orientations (4 rotations x mirror) by scoring landmark placement against
CAD truth on the flipped board (carrier u rightward, v from clip end):

  component (relay) face, which points DOWN on the carrier:
    - green terminal block centroid: u ~ -10.8, v ~ 7.9 (left, near clips)
    - relay (dark mass) centroid:    u ~ +8.3, v ~ 17.9 (right, mid-near)
  socket (solder) face, which points UP on the carrier:
    - two silver socket rows occupy u ~ +/-15, v 54..94.7 (far half)

Writes the oriented textures to /tmp/opencode/tex_{down,up}.png plus a
landmark evidence JSON to analysis/hybrid_fiducials.json.
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from cad.parameters import Measured as M

SHEET = "/tmp/opencode/H559_8_full.jpg"
FRONT = "/tmp/opencode/T-SimHat.jpg"
PHOTO_URLS = {
    FRONT: "https://lilygo.cc/cdn/shop/products/T-SimHat.jpg?v=1657769776&width=1206",
    SHEET: "https://lilygo.cc/cdn/shop/products/H559_8.jpg?v=1657769774&width=1946",
}
FACE_CELLS = {"CT": "down", "CB": "up"}
TRANSFORMS = ["", "FLIP_LEFT_RIGHT", "FLIP_TOP_BOTTOM", "ROTATE_180",
              "ROTATE_90", "ROTATE_270", "TRANSPOSE", "TRANSPOSE_FLIP"]


def fetch_photos():
    import urllib.request
    for path, url in PHOTO_URLS.items():
        if not os.path.exists(path):
            urllib.request.urlretrieve(url, path)


def largest_dark_region_mask(mask):
    """Keep the largest 8-connected dark component (drops inset modules,
    logos, background junk)."""
    from scipy import ndimage
    lab, n = ndimage.label(mask)
    if n <= 1:
        return mask
    sizes = ndimage.sum(mask, lab, range(1, n + 1))
    return lab == (int(np.argmax(sizes)) + 1)


def board_corners(mask):
    """Four extreme-sum/difference points of the dark mask = perspective
    quadrilateral corners for a near-axis photo of a rectangle."""
    ys, xs = np.where(mask)
    s = xs + ys
    d = xs - ys
    pts = {
        "tl": (xs[np.argmin(s)], ys[np.argmin(s)]),
        "br": (xs[np.argmax(s)], ys[np.argmax(s)]),
        "tr": (xs[np.argmax(d)], ys[np.argmax(d)]),
        "bl": (xs[np.argmin(d)], ys[np.argmin(d)]),
    }
    return pts


def find_coeffs(target, source):
    A = []
    for (tx, ty), (sx, sy) in zip(target, source):
        A.append([sx, sy, 1, 0, 0, 0, -tx * sx, -tx * sy])
        A.append([0, 0, 0, sx, sy, 1, -ty * sx, -ty * sy])
    A = np.array(A, dtype=np.float64)
    b = np.array([c for pt in target for c in pt], dtype=np.float64).reshape(-1)
    x = np.linalg.lstsq(A, b, rcond=None)[0]
    return x


def rectify_perspective(img, dark_thresh=110, out_w=660, out_h=1896):
    """Perspective-rectify the photographed PCB to its true 33:94.8
    aspect using detected board corners. Returns image + corner points."""
    a = np.asarray(img.convert("RGB")).astype(float)
    lum = a.mean(axis=2)
    mask = lum < dark_thresh
    mask = largest_dark_region_mask(mask)
    pts = board_corners(mask)
    src = [pts["tl"], pts["tr"], pts["br"], pts["bl"]]
    dst = [(0, 0), (out_w - 1, 0), (out_w - 1, out_h - 1), (0, out_h - 1)]
    coeffs = find_coeffs(dst, src)
    return img.transform((out_w, out_h), Image.PERSPECTIVE, coeffs,
                         resample=Image.BICUBIC), pts


def crop_board(img, dark_thresh=110):
    a = np.asarray(img.convert("RGB")).astype(float)
    lum = a.mean(axis=2)
    mask = largest_dark_region_mask(lum < dark_thresh)
    rows = np.where(mask.any(axis=1))[0]
    cols = np.where(mask.any(axis=0))[0]
    if len(rows) == 0:
        return None, None
    box = (int(cols[0]), int(rows[0]), int(cols[-1] + 1), int(rows[-1] + 1))
    return img.crop(box), box


def landmarks(arr):
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    lum = arr.mean(axis=2)
    green = (g > 80) & (g > r + 25) & (g > b + 25)
    silver = (arr.min(axis=2) > 120) & (arr.max(axis=2) - arr.min(axis=2) < 60)
    dark = lum < 55
    H, W = lum.shape
    out = {}
    for name, m in (("green", green), ("silver", silver), ("dark", dark)):
        n = m.sum()
        if n < 30:
            out[name] = None
            continue
        ys, xs = np.where(m)
        out[name] = {"n": int(n),
                     "cu": float(xs.mean() / W), "cv": float(ys.mean() / H)}
    return out


def score_down(lm):
    """Component face. Texture convention: image top = far/socket end
    (v 94.8), image bottom = clip end (v 0), left = u -16.5.
    Strongest fiducial: the 2x16 header sockets at the far half ->
    silver centroid ~(0.5, 0.21). Tiebreak: green terminal bottom-left
    (0.17, 0.9); relay is black-on-black and NOT usable as a threshold
    fiducial (whole PCB is black)."""
    if not lm["silver"]:
        return -1e9
    su, sv = lm["silver"]["cu"], lm["silver"]["cv"]
    s = -(abs(sv - 0.21) * 5.0 + abs(su - 0.5) * 2.0)
    if lm["green"]:
        s -= abs(lm["green"]["cv"] - 0.917) * 1.0
        s -= abs(lm["green"]["cu"] - 0.174) * 1.0
    return s


def score_up(lm):
    """Socket face, same convention: socket solder/pin rows occupy the
    far half at u ~ +/-15 -> silver centroid (0.5, 0.22)."""
    if not lm["silver"]:
        return -1e9
    su, sv = lm["silver"]["cu"], lm["silver"]["cv"]
    return -(abs(sv - 0.22) * 5.0 + abs(su - 0.5) * 2.0)


def apply_transform(img, t):
    if t == "":
        return img
    if t == "TRANSPOSE_FLIP":
        return img.transpose(Image.TRANSPOSE).transpose(Image.ROTATE_180)
    return img.transpose(getattr(Image, t))


def main():
    fetch_photos()
    sheet = Image.open(SHEET).convert("RGB")
    cb_cell = sheet.crop((187, 287, 800, 929))
    cb_right = cb_cell.crop((cb_cell.width // 2 + 10, 0, cb_cell.width,
                             cb_cell.height))
    sources = {
        "down": Image.open("/tmp/opencode/T-SimHat.jpg").convert("RGB"),
        "up": cb_right,
    }
    report = {}
    for face, img in sources.items():
        rect, corner_pts = rectify_perspective(img)
        best = None
        for t in TRANSFORMS:
            tex = apply_transform(rect, t)
            lm = landmarks(np.asarray(tex).astype(float))
            s = score_down(lm) if face == "down" else score_up(lm)
            if best is None or s > best[0]:
                best = (s, t, lm)
        s, t, lm = best
        tex = apply_transform(rect, t)
        out = f"/tmp/opencode/tex_{face}.png"
        tex.save(out)
        report[face] = {
            "source": ("T-SimHat.jpg (largest dark region)"
                       if face == "down" else "H559_8 CB right half (under)"),
            "perspective_corners_tl_tr_br_bl": [[int(v) for v in corner_pts[k]]
                                                for k in ("tl", "tr", "br", "bl")],
            "chosen_transform": t, "score": round(s, 3),
            "landmarks_cu_cv_n": {k: (None if v is None else
                                      (round(v["cu"], 2), round(v["cv"], 2), v["n"]))
                                  for k, v in lm.items()},
            "target_aspect_w_over_h": round(M.simhat_pcb_w / M.simhat_pcb_l, 4),
            "rectified_px": [tex.width, tex.height],
        }
        print(f"{face}: {t} score={s:.3f} landmarks={report[face]['landmarks_cu_cv_n']}")
    with open("analysis/hybrid_fiducials.json", "w") as f:
        json.dump(report, f, indent=2)
    print("wrote analysis/hybrid_fiducials.json + textures")


if __name__ == "__main__":
    main()

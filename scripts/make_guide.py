#!/usr/bin/env python3
"""Generate the annotated calibration-coupon feedback guide (PNG).

Left panel: scale schematic of the coupon drawn directly from
cad/calicheck.py constants (single source of truth — no drift).
Right panel: the four tests + secondary checks, as text.
Output: renders/calicheck_guide.png (+ copy into exports/ for LAN serving).
"""

from __future__ import annotations

import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from PIL import Image, ImageDraw, ImageFont
from cad import calicheck as CC
from cad import holder
from cad.parameters import Measured as M

S = 11.0
OX, OY = 46, 110
PANEL_W = 1180
W, H = 1880, 1220


def px(x, y):
    return (OX + (x + 50) * S, OY + (34 - y) * S)


def font(sz, bold=True):
    path = ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
            else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    try:
        return ImageFont.truetype(path, sz)
    except OSError:
        return ImageFont.load_default()


def main():
    im = Image.new("RGB", (W, H), (250, 250, 252))
    d = ImageDraw.Draw(im)
    ink = (25, 28, 34)
    faint = (150, 155, 165)

    d.text((40, 22), "LILYGO CARRIER — CALIBRATION COUPON: WHAT TO CHECK",
           font=font(34), fill=ink)
    d.text((40, 66), "print v0.4.1  ·  plate should measure ~92 × 64 mm  ·  "
           "fill in the numbers, send back with photos",
           font=font(20, bold=False), fill=faint)

    d.rectangle([PANEL_W - 10, 20, PANEL_W - 4, H - 20], fill=(210, 214, 222))

    # ---- schematic panel ----
    d.text((40, 96), "TOP VIEW (true scale, mm)", font=font(20), fill=faint)

    x0, y0 = px(-CC.PLATE_W / 2, CC.PLATE_L / 2)
    x1, y1 = px(CC.PLATE_W / 2, -CC.PLATE_L / 2)
    d.rectangle([x0, y0, x1, y1], outline=ink, width=3, fill=(238, 238, 240))

    # 1) hole ladder
    for i, dia in enumerate(CC.HOLE_DIAMS):
        cx, cy = px(CC.HOLE_ROW_X0 + i * CC.HOLE_PITCH, CC.HOLE_ROW_Y)
        r = dia / 2 * S
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=ink, width=2,
                  fill=(255, 255, 255))
        d.text((cx - 16, cy - 34), f"{dia:.2f}", font=font(15), fill=ink)
    badge(d, px(CC.HOLE_ROW_X0 + 2 * CC.HOLE_PITCH, CC.HOLE_ROW_Y + 7), 1)

    # 2) thickness stair
    for i, t in enumerate(CC.PCB_SLIT_HEIGHTS):
        y_c = CC.PCB_Y0 + i * CC.PCB_SLIT_PITCH
        c1 = px(CC.PCB_X_IN - CC.WALL_T,
                y_c + CC.PCB_SLIT_WIDTH / 2 + CC.WALL_T)
        c2 = px(CC.PCB_X_IN + CC.SLIT_TRAVEL + CC.WALL_T,
                y_c - CC.PCB_SLIT_WIDTH / 2 - CC.WALL_T)
        bx0, by0, bx1, by1 = min(c1[0], c2[0]), min(c1[1], c2[1]), \
            max(c1[0], c2[0]), max(c1[1], c2[1])
        d.rectangle([bx0, by0, bx1, by1], outline=ink, width=2, fill=(228, 230, 234))
        sy0, sy1 = px(CC.PCB_X_IN + CC.SLIT_TRAVEL, y_c + CC.PCB_SLIT_WIDTH / 2), \
            px(CC.PCB_X_IN + CC.SLIT_TRAVEL, y_c - CC.PCB_SLIT_WIDTH / 2)
        d.rectangle([sy0[0] - 2, min(sy0[1], sy1[1]),
                     sy0[0] + 2, max(sy0[1], sy1[1])], fill=(255, 120, 90))
        d.text((bx1 + 8, (by0 + by1) / 2 - 10), f"{t:.1f}", font=font(17), fill=ink)
    badge(d, px(CC.PCB_X_IN + 5, CC.PCB_Y0 + 1.5 * CC.PCB_SLIT_PITCH), 2)
    d.text(px(CC.PCB_X_IN + 14, CC.PCB_Y0 + 3.6 * CC.PCB_SLIT_PITCH),
           "slide SimHat\nedge in →", font=font(15, bold=False), fill=faint)

    # 3) antenna slits
    for i, wdt in enumerate(CC.ANT_SLIT_WIDTHS):
        x_c = CC.ANT_X0 + i * CC.ANT_X_PITCH
        c1 = px(x_c - CC.SLIT_TRAVEL / 2 - CC.WALL_T,
                CC.ANT_Y_C + wdt / 2 + CC.WALL_T)
        c2 = px(x_c + CC.SLIT_TRAVEL / 2 + CC.WALL_T,
                CC.ANT_Y_C - wdt / 2 - CC.WALL_T)
        bx0, by0, bx1, by1 = min(c1[0], c2[0]), min(c1[1], c2[1]), \
            max(c1[0], c2[0]), max(c1[1], c2[1])
        d.rectangle([bx0, by0, bx1, by1], outline=ink, width=2, fill=(228, 230, 234))
        sw0, sw1 = px(x_c, CC.ANT_Y_C - wdt / 2), px(x_c, CC.ANT_Y_C + wdt / 2)
        d.rectangle([min(sw0[0], sw1[0]) - 2, min(sw0[1], sw1[1]),
                     max(sw0[0], sw1[0]) + 2, max(sw0[1], sw1[1])],
                    fill=(255, 120, 90))
        d.text((bx1 + 8, (by0 + by1) / 2 - 10), f"{wdt:.1f}", font=font(17), fill=ink)
    badge(d, px(CC.ANT_X0 + CC.ANT_X_PITCH, CC.ANT_Y_C + 14), 3)
    d.text(px(CC.ANT_X0 + CC.ANT_X_PITCH - 4, CC.ANT_Y_C + 18.5),
           "sticker slides ↓ through", font=font(15, bold=False), fill=faint)

    # 4) snap bay
    bx = CC.BAY_OX
    for (u_pad, v_pad) in CC.BAY_PADS_UV:
        cx, cy = px(bx + u_pad, CC.BAY_OY - v_pad)
        r = CC.BAY_PAD_SIZE / 2 * S
        d.rectangle([cx - r, cy - r, cx + r, cy + r], outline=ink, width=2,
                    fill=(210, 232, 210))
    half = M.simhat_pcb_w / 2 + CC.BAY_CLEAR
    for side in (-1, 1):
        pts = [(u, -v) for u, v in holder._clip_arm_pts(CC.BAY_CLEAR, side)]
        poly = [px(bx + u, CC.BAY_OY + v) for u, v in pts]
        d.polygon(poly, outline=ink, fill=(255, 244, 200))
    board_x0, _ = px(bx - M.simhat_pcb_w / 2, 0)
    board_x1, _ = px(bx + M.simhat_pcb_w / 2, 0)
    by_top, _ = px(0, CC.BAY_OY)
    dashed_v(d, board_x0, by_top, H - 60)
    dashed_v(d, board_x1, by_top, H - 60)
    dashed_h(d, board_x0, board_x1, by_top)
    d.text((board_x0 + 6, by_top + 10), "SimHat board end goes here\n(relay DOWN, terminals facing you)",
           font=font(15, bold=False), fill=(90, 100, 110))
    badge(d, px(bx, CC.BAY_OY - 8), 4)

    # scale bar
    sx0, sy = px(-40, -34.5)
    sx1, _ = px(-30, -34.5)
    d.line([sx0, sy, sx1, sy], fill=ink, width=3)
    d.text((sx0 + 10, sy + 6), "10 mm", font=font(15), fill=ink)

    # ---- right panel: instructions ----
    X = PANEL_W + 20
    y = 96
    steps = [
        ("1  ·  M1.6 HOLE LADDER  (top right)",
         ["Try an M1.6 screw in each hole, left (1.20) to right (1.60).",
          "Report the SMALLEST hole where the screw BITES",
          "instead of spinning freely. That number +0.1 → pilot Ø.",
          "Maps to: A7670_PILOT_D"]),
        ("2  ·  PCB THICKNESS STAIR  (left wall)",
         ["Slide the T-SimHat short edge into each slit, bottom (1.0)",
          "to top (1.6). Report the FIRST slit it enters freely.",
          "Even better: caliper the board edge and report mm.",
          "Maps to: SimHat PCB thickness assumption"]),
        ("3  ·  ANTENNA WIDTH SLITS  (3 tall blocks)",
         ["Push the antenna sticker through each wide slit:",
          "bottom 19.8 / middle 20.2 / top 20.6. Report which is",
          "'light drag' (slides, but you feel it). Also caliper the",
          "sticker. Maps to: ANT_W / ANT_SIDE_CLEAR"]),
        ("4  ·  SNAP CLIP BAY  (bottom right)",
         ["Hold the board UPRIGHT, relay facing DOWN, at the bay.",
          "Lower the board end between the two yellow hook arms",
          "until it CLICKS under both hooks (pads take the weight).",
          "Then pinch both fins outward to release. Report:",
          "clicked? force? release easy? white marks at arm roots",
          "after 5-10 cycles? Maps to: SIMHAT_PCB_XY_CLEAR"]),
        ("5-8  ·  SECONDARY",
         ["5: Caliper the plate: expect 92.0 x 64.0 mm (report both).",
          "6: First layer flat? corners lifting? elephant foot?",
          "7: Are the 1.20 holes round and open (not clogged)?",
          "8: Stringing in slits? delamination on the tall pads?"]),
    ]
    for title, lines in steps:
        d.text((X, y), title, font=font(21), fill=(160, 40, 40))
        y += 32
        for ln in lines:
            d.text((X + 14, y), ln, font=font(17, bold=False), fill=ink)
            y += 26
        y += 18

    d.text((X, y + 6), "Then paste the feedback template from",
           font=font(17, bold=False), fill=ink)
    d.text((X, y + 30), "docs/calibration_guide.md back to me.",
           font=font(17, bold=False), fill=ink)

    im.save("renders/calicheck_guide.png")
    shutil.copy("renders/calicheck_guide.png", "exports/lilygo_calicheck_guide.png")
    print("wrote renders/calicheck_guide.png + exports/lilygo_calicheck_guide.png")


def badge(d, xy, n):
    x, y = xy
    r = 17
    d.ellipse([x - r, y - r, x + r, y + r], fill=(200, 40, 40),
              outline=(255, 255, 255), width=2)
    cx, cy = d.textbbox((0, 0), str(n), font=font(19))[2:]
    d.text((x - cx / 2, y - cy / 2 - 2), str(n), font=font(19),
           fill=(255, 255, 255))


def dashed_v(d, x, y0, y1, dash=8, gap=6):
    y = y0
    while y < y1:
        d.line([x, y, x, min(y + dash, y1)], fill=(120, 128, 140), width=2)
        y += dash + gap


def dashed_h(d, x0, x1, y, dash=8, gap=6):
    x = x0
    while x < x1:
        d.line([x, y, min(x + dash, x1), y], fill=(120, 128, 140), width=2)
        x += dash + gap


if __name__ == "__main__":
    main()

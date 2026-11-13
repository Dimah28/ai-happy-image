#!/usr/bin/env python3
"""The Happiest Morning -- one image made to make the AI judge happy.

A deterministic generative program for the make.fun bounty
"Make the AI judge happy" (ai-happy-01).

What it draws
------------
One original 1024x1024 picture, entirely procedural with the Python
standard library only: a big smiling sun rising over rolling green hills
on the happiest morning -- a rainbow arcing across a warm dawn sky,
hot-air balloons drifting, birds and butterflies, and a meadow full of
daisies. The idea is a specific moment (the first morning light, the
whole world waking up smiling) rather than a stock smiley or a generic
sunny scene: one huge warm sun as the hero, so the picture still lands
at ~300 pixels across.

The morning is a little party, not just a sky: the sun wears a daisy
flower crown and has long happy eyelashes, a white bunny sits on the
hill waving at it with a carrot beside it, a red-and-yellow kite with
its own tiny smiley face dances under the rainbow, a red-checked picnic
blanket waits with a teapot and two cups, and gold sparkles drift in
the dawn light. Every character is placed on purpose, so the judge
sees a scene with a story instead of a stock smiley face.

There is no network access, no randomness that is not seeded, and no
external asset: the same run always writes the same bytes, so the two
sandbox runs required by the bounty produce identical files.

Output
------
Writes ``entry.png`` into ``$MAKEFUN_OUTPUT_DIR`` (the sandbox's /output),
or into ``/output`` when the variable is not set. The PNG is encoded by
hand with zlib (colour type 2, 8-bit RGB, per-row filter choice), so the
program needs nothing beyond the standard library.

Run locally:
    mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
"""

import hashlib
import math
import os
import random
import struct
import sys
import zlib

# ---------------------------------------------------------------- canvas ---
W = 1024
H = 1024
SEED = 20261113  # fixed seed: every run draws the same picture

canvas = bytearray(W * H * 3)
rng = random.Random(SEED)

# --------------------------------------------------------------- palette ---
SKY_TOP = (110, 186, 232)
SKY_MID = (168, 214, 240)
SKY_LOW = (255, 214, 168)
SUN = (255, 208, 80)
SUN_DEEP = (255, 178, 44)
SUN_GLOW = (255, 226, 130)
FACE = (122, 72, 20)
CHEEK = (255, 140, 130)
HILL_FAR = (110, 190, 110)
HILL_NEAR = (72, 168, 88)
LEAF = (46, 140, 70)
RAINBOW = [(235, 80, 80), (250, 150, 60), (252, 214, 80),
           (110, 205, 110), (90, 160, 235), (150, 110, 210)]
CLOUD = (255, 255, 255)
BALLOON_A = (235, 90, 90)
BALLOON_B = (90, 160, 235)
BALLOON_C = (252, 190, 60)
WHITE = (250, 250, 246)


# ------------------------------------------------------------ primitives ---
def hline(x0, x1, y, color):
    """Fill a horizontal span of pixels (clipped)."""
    if y < 0 or y >= H:
        return
    x0 = max(0, int(x0))
    x1 = min(W - 1, int(x1))
    if x1 < x0:
        return
    n = x1 - x0 + 1
    i = (y * W + x0) * 3
    canvas[i:i + n * 3] = bytes(color) * n


def rect(x, y, w, h, color):
    """Fill an axis-aligned rectangle (floats allowed)."""
    y0 = max(0, int(math.floor(y)))
    y1 = min(H - 1, int(math.ceil(y + h)) - 1)
    for yy in range(y0, y1 + 1):
        hline(x, x + w - 1, yy, color)


def blend_px(x, y, color, alpha):
    """Alpha-blend one pixel over the canvas."""
    if 0 <= x < W and 0 <= y < H and alpha > 0:
        i = (y * W + x) * 3
        a = alpha
        canvas[i] = int(color[0] * a + canvas[i] * (1 - a) + 0.5)
        canvas[i + 1] = int(color[1] * a + canvas[i + 1] * (1 - a) + 0.5)
        canvas[i + 2] = int(color[2] * a + canvas[i + 2] * (1 - a) + 0.5)


def fill_poly(pts, color):
    """Scanline-fill a polygon given as [(x, y), ...]."""
    ys = [p[1] for p in pts]
    y0 = max(0, int(math.floor(min(ys))))
    y1 = min(H - 1, int(math.ceil(max(ys))))
    n = len(pts)
    for y in range(y0, y1 + 1):
        yc = y + 0.5
        xs = []
        for i in range(n):
            x0, ya = pts[i]
            x1, yb = pts[(i + 1) % n]
            if ya == yb:
                continue
            lo, hi = (ya, yb) if ya < yb else (yb, ya)
            if lo <= yc < hi:
                t = (yc - ya) / (yb - ya)
                xs.append(x0 + t * (x1 - x0))
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            xa = int(math.ceil(xs[k] - 0.5))
            xb = int(math.floor(xs[k + 1] - 0.5))
            hline(xa, xb, y, color)


def fill_circle(cx, cy, r, color):
    """Fill a disc (float centre/radius allowed)."""
    r = float(r)
    y0 = max(0, int(math.floor(cy - r)))
    y1 = min(H - 1, int(math.ceil(cy + r)))
    for y in range(y0, y1 + 1):
        dy = (y + 0.5) - cy
        d2 = r * r - dy * dy
        if d2 < 0:
            continue
        dx = math.sqrt(d2)
        hline(cx - dx, cx + dx, y, color)


def fill_circle_alpha(cx, cy, r, color, alpha):
    """Fill a disc with a constant alpha over the canvas."""
    r = float(r)
    y0 = max(0, int(math.floor(cy - r)))
    y1 = min(H - 1, int(math.ceil(cy + r)))
    for y in range(y0, y1 + 1):
        dy = (y + 0.5) - cy
        d2 = r * r - dy * dy
        if d2 < 0:
            continue
        dx = math.sqrt(d2)
        for x in range(max(0, int(cx - dx)), min(W - 1, int(cx + dx)) + 1):
            blend_px(x, y, color, alpha)


def ring(cx, cy, r, w, color):
    """Draw a circle outline of width w."""
    ro = r + w / 2.0
    ri = r - w / 2.0
    y0 = max(0, int(math.floor(cy - ro)))
    y1 = min(H - 1, int(math.ceil(cy + ro)))
    for y in range(y0, y1 + 1):
        dy = (y + 0.5) - cy
        d2o = ro * ro - dy * dy
        if d2o < 0:
            continue
        xo = math.sqrt(d2o)
        d2i = ri * ri - dy * dy
        xi = math.sqrt(d2i) if d2i > 0 else 0.0
        hline(cx - xo, cx - xi, y, color)
        hline(cx + xi, cx + xo, y, color)


def line(x0, y0, x1, y1, w, color, alpha=1.0):
    """Draw a thick line by stamping discs along it."""
    dist = math.hypot(x1 - x0, y1 - y0)
    steps = max(1, int(dist / max(1.0, w * 0.35)))
    for i in range(steps + 1):
        t = i / steps
        x = x0 + (x1 - x0) * t
        y = y0 + (y1 - y0) * t
        if alpha >= 1.0:
            fill_circle(x, y, w / 2.0, color)
        else:
            fill_circle_alpha(x, y, w / 2.0, color, alpha)


def arc(cx, cy, r, a0, a1, w, color):
    """Draw an arc (angles in radians, 0 = east, positive clockwise
    because y grows downwards) by stamping discs along it."""
    steps = max(8, int(abs(a1 - a0) * r / 4))
    for i in range(steps + 1):
        a = a0 + (a1 - a0) * i / steps
        fill_circle(cx + r * math.cos(a), cy + r * math.sin(a), w / 2.0, color)


def soft_disc(cx, cy, r, color, strength):
    """Radial glow: colour fading smoothly to nothing at radius r."""
    r = float(r)
    x0 = max(0, int(cx - r))
    x1 = min(W - 1, int(cx + r))
    y0 = max(0, int(cy - r))
    y1 = min(H - 1, int(cy + r))
    for y in range(y0, y1 + 1):
        dy = (y + 0.5 - cy) / r
        for x in range(x0, x1 + 1):
            dx = (x + 0.5 - cx) / r
            d2 = dx * dx + dy * dy
            if d2 < 1.0:
                a = strength * (1.0 - d2) * (1.0 - d2)
                blend_px(x, y, color, a)


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t + 0.5) for i in range(3))


# ------------------------------------------------------------- the scene ---
SUN_C = (512, 330)
SUN_R = 150


def draw_sky():
    """Warm dawn gradient: soft blue above, peach at the horizon."""
    for y in range(H):
        t = y / (H - 1)
        if t < 0.6:
            c = lerp(SKY_TOP, SKY_MID, t / 0.6)
        else:
            c = lerp(SKY_MID, SKY_LOW, (t - 0.6) / 0.4)
        hline(0, W - 1, y, c)


def draw_rainbow():
    """Six-colour arc across the sky, centred below the horizon so only
    the arc shows; the hills drawn later cover its feet."""
    cx, cy = 512, 980
    for i, col in enumerate(RAINBOW):
        ring(cx, cy, 560 - i * 22, 20, col)


def draw_sun():
    """The hero: a huge smiling sun with rays, closed happy eyes, a big
    smile and rosy cheeks -- wearing a daisy flower crown, with long
    happy eyelashes, so it reads as a character, not a stock smiley."""
    soft_disc(SUN_C[0], SUN_C[1], 260, SUN_GLOW, 0.55)
    # rays: alternating long and short triangles
    for k in range(16):
        a = k * math.pi / 8
        long = (k % 2 == 0)
        r0 = SUN_R + 12
        r1 = SUN_R + (64 if long else 36)
        tip = (SUN_C[0] + r1 * math.cos(a), SUN_C[1] + r1 * math.sin(a))
        base1 = (SUN_C[0] + r0 * math.cos(a - 0.09),
                 SUN_C[1] + r0 * math.sin(a - 0.09))
        base2 = (SUN_C[0] + r0 * math.cos(a + 0.09),
                 SUN_C[1] + r0 * math.sin(a + 0.09))
        fill_poly([base1, tip, base2], SUN_DEEP)
    fill_circle(SUN_C[0], SUN_C[1], SUN_R, SUN)
    # warm shading on the lower rim
    arc(SUN_C[0], SUN_C[1], SUN_R - 8, math.pi * 0.15, math.pi * 0.85,
        10, SUN_DEEP)
    # closed happy eyes: upward-curving arcs
    arc(SUN_C[0] - 58, SUN_C[1] - 28, 26, math.pi * 1.15, math.pi * 1.85,
        9, FACE)
    arc(SUN_C[0] + 58, SUN_C[1] - 28, 26, math.pi * 1.15, math.pi * 1.85,
        9, FACE)
    # long eyelashes fanning off the outer end of each closed eye
    for (ex, ey, sgn) in ((SUN_C[0] - 58, SUN_C[1] - 28, -1),
                          (SUN_C[0] + 58, SUN_C[1] - 28, 1)):
        # outer tip of the eye arc
        tx = ex + sgn * 24
        ty = ey - 8
        for (dx, dy, ln) in ((14, -16, 15), (20, -6, 14), (22, 4, 12)):
            line(tx, ty, tx + sgn * dx, ty + dy, 4, FACE)
    # big open smile
    arc(SUN_C[0], SUN_C[1] + 8, 62, math.pi * 0.15, math.pi * 0.85, 10, FACE)
    # rosy cheeks
    fill_circle_alpha(SUN_C[0] - 102, SUN_C[1] + 18, 22, CHEEK, 0.75)
    fill_circle_alpha(SUN_C[0] + 102, SUN_C[1] + 18, 22, CHEEK, 0.75)
    # daisy flower crown across the top of the sun's head
    for k in range(5):
        ang = math.radians(212 + k * 17)
        dx = SUN_C[0] + (SUN_R - 6) * math.cos(ang)
        dy = SUN_C[1] + (SUN_R - 6) * math.sin(ang)
        # five white petals around a yellow centre
        for p in range(5):
            pa = p * math.pi * 2 / 5 - math.pi / 2
            fill_circle(dx + 8 * math.cos(pa), dy + 8 * math.sin(pa),
                        5.5, WHITE)
        fill_circle(dx, dy, 5, (252, 200, 60))
        fill_circle(dx - 14, dy + 10, 4, LEAF)
        fill_circle(dx + 14, dy + 10, 4, LEAF)


def cloud(cx, cy, s):
    """One fluffy cloud from overlapping soft discs."""
    for dx, dy, r in ((-46, 8, 30), (-14, -12, 38), (22, -6, 34),
                      (52, 8, 28), (0, 12, 36)):
        fill_circle_alpha(cx + dx * s, cy + dy * s, r * s, CLOUD, 0.92)


def draw_clouds():
    cloud(150, 150, 0.9)
    cloud(880, 120, 1.05)
    cloud(830, 560, 0.7)
    cloud(120, 520, 0.65)


def draw_hills():
    """Two rolling hills; the near one carries the flower meadow."""
    # far hill: a gentle dome, crest near y=650 at the centre
    pts = []
    for x in range(0, W + 1, 16):
        t = x / W
        pts.append((x, 760 - 110 * math.sin(math.pi * t) ** 1.5))
    pts.append((W, H))
    pts.append((0, H))
    fill_poly(pts, HILL_FAR)
    # near hill (a big low ellipse of green across the bottom)
    cy = 940
    for y in range(700, H):
        dy = (y + 0.5 - cy) / 280.0
        d2 = 1.0 - dy * dy
        if d2 < 0:
            continue
        dx = 760 * math.sqrt(d2)
        hline(512 - dx, 512 + dx, y, HILL_NEAR)
    # soft light on the near hill
    soft_disc(512, 830, 320, (140, 220, 130), 0.25)


def draw_flowers():
    """A seeded meadow of daisies on the near hill."""
    for _ in range(90):
        x = rng.uniform(20, W - 20)
        y = rng.uniform(760, 1010)
        s = rng.uniform(0.7, 1.5)
        # stem
        line(x, y, x + rng.uniform(-4, 4), y - 16 * s, 2.5, LEAF)
        # petals
        for k in range(6):
            a = k * math.pi / 3
            fill_circle(x + 7 * s * math.cos(a), y - 18 * s + 7 * s * math.sin(a),
                        4.5 * s, WHITE)
        fill_circle(x, y - 18 * s, 4.5 * s, (252, 200, 60))
    # a few red poppies among the daisies
    for _ in range(14):
        x = rng.uniform(30, W - 30)
        y = rng.uniform(800, 1000)
        s = rng.uniform(0.8, 1.3)
        line(x, y, x, y - 14 * s, 2.5, LEAF)
        fill_circle(x, y - 16 * s, 6 * s, (235, 70, 70))
        fill_circle(x, y - 16 * s, 2.5 * s, (60, 30, 30))


def balloon(cx, cy, s, col):
    """One hot-air balloon: striped envelope, basket, ropes."""
    r = 34 * s
    fill_circle(cx, cy, r, col)
    fill_poly([(cx - r, cy), (cx, cy - r), (cx + r, cy)], (255, 255, 255))
    fill_circle(cx, cy, r * 0.55, col)
    line(cx - r * 0.55, cy + r * 0.7, cx - 10 * s, cy + 62 * s, 2.5, FACE)
    line(cx + r * 0.55, cy + r * 0.7, cx + 10 * s, cy + 62 * s, 2.5, FACE)
    rect(cx - 11 * s, cy + 62 * s, 22 * s, 16 * s, (120, 80, 40))


def draw_balloons():
    balloon(180, 300, 0.9, BALLOON_A)
    balloon(850, 330, 0.75, BALLOON_B)
    balloon(760, 180, 0.55, BALLOON_C)


def bird(cx, cy, s):
    """One distant bird: two short curved strokes."""
    line(cx - 12 * s, cy, cx, cy - 6 * s, 3, FACE)
    line(cx, cy - 6 * s, cx + 12 * s, cy, 3, FACE)


def butterfly(cx, cy, s, col):
    """One tiny butterfly: two wing discs and a body."""
    fill_circle(cx - 6 * s, cy - 3 * s, 6 * s, col)
    fill_circle(cx + 6 * s, cy - 3 * s, 6 * s, col)
    fill_circle(cx - 6 * s, cy + 4 * s, 4.5 * s, col)
    fill_circle(cx + 6 * s, cy + 4 * s, 4.5 * s, col)
    line(cx, cy - 6 * s, cx, cy + 7 * s, 2.5, FACE)


def draw_sparkles():
    """Gold four-point sparkles drifting in the dawn light."""
    spots = [(240, 90), (640, 80), (920, 260), (90, 380), (420, 130),
             (960, 430), (700, 90), (180, 470)]
    for (x, y) in spots:
        s = 10
        line(x - s, y, x + s, y, 3, (255, 220, 120))
        line(x, y - s, x, y + s, 3, (255, 220, 120))
        fill_circle(x, y, 3, (255, 240, 170))


def kite(cx, cy, s):
    """A red-and-yellow diamond kite with its own tiny smiley face,
    a string curving down and three bows on its tail."""
    # diamond sail
    fill_poly([(cx, cy - 46 * s), (cx + 34 * s, cy),
               (cx, cy + 46 * s), (cx - 34 * s, cy)], (235, 90, 90))
    fill_poly([(cx, cy - 46 * s), (cx + 34 * s, cy),
               (cx, cy), (cx, cy - 46 * s)], (252, 200, 60))
    # cross sticks
    line(cx, cy - 46 * s, cx, cy + 46 * s, 3, FACE)
    line(cx - 34 * s, cy, cx + 34 * s, cy, 3, FACE)
    # tiny smiley face on the sail
    fill_circle(cx - 9 * s, cy - 8 * s, 2.5, FACE)
    fill_circle(cx + 9 * s, cy - 8 * s, 2.5, FACE)
    arc(cx, cy - 2 * s, 10 * s, math.pi * 0.15, math.pi * 0.85, 3, FACE)
    # tail with bows, curving down to the RIGHT so it never crosses
    # the sun's face
    tx, ty = cx - 4 * s, cy + 46 * s
    for k in range(3):
        nx, ny = tx + 14 * s, ty + 34 * s
        line(tx, ty, nx, ny, 2.5, FACE)
        fill_circle(nx - 7 * s, ny, 5 * s, BALLOON_B)
        fill_circle(nx + 7 * s, ny, 5 * s, BALLOON_B)
        tx, ty = nx, ny
    # string trailing off toward the hill (the flyer is out of frame)
    line(tx, ty, tx + 60 * s, ty + 90 * s, 2, FACE, alpha=0.7)


def bunny(cx, cy, s):
    """A little white bunny sitting on the hill, waving one paw at
    the sun, a carrot beside it."""
    # tail and body
    fill_circle(cx - 26 * s, cy - 6 * s, 10 * s, WHITE)
    fill_circle(cx, cy, 26 * s, WHITE)
    fill_circle(cx + 6 * s, cy - 6 * s, 20 * s, WHITE)
    # long ears (one flopping)
    fill_poly([(cx - 12 * s, cy - 34 * s), (cx - 4 * s, cy - 34 * s),
               (cx - 2 * s, cy - 66 * s), (cx - 12 * s, cy - 66 * s)],
              WHITE)
    fill_poly([(cx + 8 * s, cy - 34 * s), (cx + 18 * s, cy - 34 * s),
               (cx + 30 * s, cy - 58 * s), (cx + 20 * s, cy - 60 * s)],
              WHITE)
    fill_circle(cx - 7 * s, cy - 50 * s, 3.5 * s, (255, 170, 190))
    fill_circle(cx + 19 * s, cy - 47 * s, 3.5 * s, (255, 170, 190))
    # head
    fill_circle(cx + 4 * s, cy - 30 * s, 18 * s, WHITE)
    # face: eyes, pink nose, smile
    fill_circle(cx - 3 * s, cy - 34 * s, 2.5, FACE)
    fill_circle(cx + 11 * s, cy - 34 * s, 2.5, FACE)
    fill_circle(cx + 4 * s, cy - 26 * s, 3 * s, (255, 130, 160))
    arc(cx + 4 * s, cy - 26 * s, 7 * s, math.pi * 0.2, math.pi * 0.8,
        2.5, FACE)
    # waving paw, raised high, with motion ticks
    fill_circle(cx + 30 * s, cy - 34 * s, 7 * s, WHITE)
    line(cx + 38 * s, cy - 44 * s, cx + 44 * s, cy - 50 * s, 2.5, FACE)
    line(cx + 40 * s, cy - 36 * s, cx + 48 * s, cy - 38 * s, 2.5, FACE)
    # carrot on the grass
    fill_poly([(cx + 52 * s, cy + 2 * s), (cx + 62 * s, cy + 2 * s),
               (cx + 57 * s, cy + 20 * s)], (250, 130, 50))
    line(cx + 57 * s, cy + 2 * s, cx + 52 * s, cy - 8 * s, 2.5, LEAF)
    line(cx + 57 * s, cy + 2 * s, cx + 62 * s, cy - 8 * s, 2.5, LEAF)


def picnic(cx, cy, s):
    """A red-checked picnic blanket with a teapot and two cups,
    waiting for the sun to come up properly."""
    # blanket: 8 x 5 checkerboard
    cell = 14 * s
    for r in range(5):
        for c in range(8):
            col = (235, 90, 90) if (r + c) % 2 == 0 else (255, 250, 240)
            rect(cx + c * cell, cy + r * cell, cell, cell, col)
    # teapot: round body, spout, handle, lid
    px, py = cx + 34 * s, cy + 8 * s
    fill_circle(px, py, 13 * s, (90, 160, 235))
    fill_poly([(px - 12 * s, py - 2 * s), (px - 24 * s, py - 10 * s),
               (px - 22 * s, py + 2 * s)], (90, 160, 235))
    arc(px + 12 * s, py, 9 * s, -math.pi / 2, math.pi / 2, 3, FACE)
    fill_circle(px, py - 14 * s, 4 * s, (250, 250, 246))
    # two cups with steam curls
    for ox in (70 * s, 92 * s):
        rect(cx + ox, cy + 22 * s, 12 * s, 12 * s, (255, 250, 240))
        arc(cx + ox + 13 * s, cy + 28 * s, 5 * s, -math.pi / 2,
            math.pi / 2, 2.5, FACE)
        line(cx + ox + 3 * s, cy + 18 * s, cx + ox + 6 * s, cy + 10 * s,
             2, (200, 200, 200))
    # steam over the teapot
    line(px - 2 * s, py - 20 * s, px + 2 * s, py - 28 * s, 2,
         (220, 220, 220))


def snail(cx, cy, s):
    """A garden snail with a smiling spiral shell, crawling along
    the bottom of the hill."""
    # body: a low slug curve
    fill_circle(cx - 6 * s, cy, 12 * s, (150, 110, 80))
    fill_circle(cx + 12 * s, cy, 10 * s, (150, 110, 80))
    fill_circle(cx + 22 * s, cy - 4 * s, 9 * s, (150, 110, 80))
    # head with two eye stalks
    fill_circle(cx + 28 * s, cy - 10 * s, 7 * s, (150, 110, 80))
    line(cx + 26 * s, cy - 14 * s, cx + 24 * s, cy - 24 * s, 2.5,
         (150, 110, 80))
    line(cx + 30 * s, cy - 14 * s, cx + 32 * s, cy - 24 * s, 2.5,
         (150, 110, 80))
    fill_circle(cx + 24 * s, cy - 25 * s, 2.5, FACE)
    fill_circle(cx + 32 * s, cy - 25 * s, 2.5, FACE)
    # smile
    arc(cx + 28 * s, cy - 10 * s, 4 * s, math.pi * 0.2, math.pi * 0.8,
        2, FACE)
    # spiral shell: concentric arcs in warm brown
    fill_circle(cx - 8 * s, cy - 12 * s, 16 * s, (190, 130, 70))
    ring(cx - 8 * s, cy - 12 * s, 11, 3, (120, 80, 40))
    ring(cx - 8 * s, cy - 12 * s, 6, 3, (120, 80, 40))
    fill_circle(cx - 8 * s, cy - 12 * s, 2.5, (120, 80, 40))


def ladybug(cx, cy, s):
    """A tiny ladybug resting on a daisy petal."""
    fill_circle(cx, cy, 7 * s, (220, 60, 60))
    line(cx, cy - 7 * s, cx, cy + 7 * s, 2, FACE)
    fill_circle(cx - 3 * s, cy - 3 * s, 1.8, FACE)
    fill_circle(cx + 3 * s, cy - 3 * s, 1.8, FACE)
    fill_circle(cx - 3 * s, cy + 3 * s, 1.8, FACE)
    fill_circle(cx + 3 * s, cy + 3 * s, 1.8, FACE)
    fill_circle(cx, cy - 8 * s, 2.5, FACE)


def draw_dew():
    """Morning dew: tiny bright dots scattered on the meadow grass."""
    for _ in range(60):
        x = rng.uniform(15, W - 15)
        y = rng.uniform(770, 1015)
        fill_circle(x, y, 1.8, (255, 255, 255))


def draw():
    draw_sky()
    draw_rainbow()
    draw_sparkles()
    draw_sun()
    draw_clouds()
    kite(640, 150, 1.0)
    draw_hills()
    draw_flowers()
    draw_dew()
    snail(520, 985, 1.0)
    ladybug(248, 806, 1.0)
    picnic(680, 895, 1.25)
    bunny(320, 885, 1.25)
    draw_balloons()
    bird(300, 200, 1.0)
    bird(350, 170, 0.8)
    bird(700, 240, 0.9)
    butterfly(250, 700, 1.0, (250, 130, 180))
    butterfly(790, 780, 1.1, (150, 130, 240))


# -------------------------------------------------------------------- png ---
def png_chunk(kind, data):
    chunk = struct.pack(">I", len(data)) + kind + data
    chunk += struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return chunk


def encode_png():
    """Encode the RGB canvas as a PNG (colour type 2, 8-bit).

    Each row gets the smallest of filters None/Sub/Up/Average/Paeth
    by the usual sum-of-absolute-values heuristic, then one zlib
    stream at level 9. Fully deterministic for a fixed canvas.
    """
    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    raw = bytearray()
    prev = bytes(W * 3)
    for y in range(H):
        row = bytes(canvas[y * W * 3:(y + 1) * W * 3])
        cands = []
        cands.append((0, row))
        sub = bytearray(row)
        for i in range(3, len(sub)):
            sub[i] = (sub[i] - row[i - 3]) & 0xFF
        cands.append((1, bytes(sub)))
        up = bytearray(row)
        for i in range(len(up)):
            up[i] = (up[i] - prev[i]) & 0xFF
        cands.append((2, bytes(up)))
        avg = bytearray(row)
        for i in range(len(avg)):
            left = row[i - 3] if i >= 3 else 0
            avg[i] = (avg[i] - ((left + prev[i]) // 2)) & 0xFF
        cands.append((3, bytes(avg)))
        paeth = bytearray(row)
        for i in range(len(paeth)):
            a = row[i - 3] if i >= 3 else 0
            b = prev[i]
            c = prev[i - 3] if i >= 3 else 0
            p = a + b - c
            pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
            pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
            paeth[i] = (paeth[i] - pr) & 0xFF
        cands.append((4, bytes(paeth)))

        def cost(b):
            return sum(v if v < 128 else 256 - v for v in b)

        ftype, fdata = min(cands, key=lambda c: cost(c[1]))
        raw.append(ftype)
        raw.extend(fdata)
        prev = row
    idat = zlib.compress(bytes(raw), 9)
    png = b"\x89PNG\r\n\x1a\n"
    png += png_chunk(b"IHDR", ihdr)
    png += png_chunk(b"IDAT", idat)
    png += png_chunk(b"IEND", b"")
    return png


def main():
    draw()
    png = encode_png()
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "entry.png")
    with open(path, "wb") as f:
        f.write(png)
    digest = hashlib.sha256(png).hexdigest()
    print(f"wrote {path} ({len(png)} bytes, {W}x{H}, sha256={digest})")
    if len(png) > 1048576:
        print("WARNING: over the 1 MiB limit", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

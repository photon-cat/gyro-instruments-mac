# /// script
# requires-python = ">=3.10"
# dependencies = ["pygame-ce"]
# ///
"""Draw the instrument art into assets/. The PNGs are committed; rerun this after editing.

Each part is its own layer, centred on the dial, so the instruments just rotate,
slide and stack them. Drawn at 4x and smooth-scaled down for antialiasing.

    case.png      instrument case (shared)                       392 x 392
    dg_card.png   compass card, rotates with heading              294 x 294
    dg_bug.png    heading bug at the top, rotates                 294 x 294
    dg_face.png   lubber line, plane, bezel, knobs                392 x 392
    ai_tape.png   sky/ground + pitch ladder, slides with pitch    294 x (294 + 180 * PX_PER_DEG)
    ai_card.png   bank card with a hole for the tape, rolls       294 x 294
    ai_plane.png  miniature plane, moved by the adjust knob       392 x 392
    ai_face.png   bank pointer, shroud, bezel, knob               392 x 392

Run:  uv run make_assets.py
"""

import json
import math
import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame

OUT = Path(__file__).resolve().parent / "assets"
S = 4  # supersampling

BOX, CARD_R, BEZEL_R, KNOB_R = 392, 147, 184, 33
HOLE_R = 104          # bank card hole the pitch tape shows through
PX_PER_DEG = 2.5      # pitch tape scale
TAPE_H = 2 * CARD_R + round(180 * PX_PER_DEG)
KNOBS = {"dg_card": (-158, 158), "dg_bug": (158, 158), "ai_adjust": (-158, 158)}

WHITE = (240, 240, 236)
BLACK = (16, 16, 18)
ORANGE = (255, 122, 24)
SKY_HIGH, SKY_LOW = (36, 98, 178), (92, 168, 224)
GROUND_HIGH, GROUND_LOW = (128, 86, 54), (78, 52, 32)
CASE = (30, 31, 34)
BEZEL = (24, 24, 27)
SHROUD = (38, 38, 42)
STEM = (112, 74, 48)


# ---- drawing in 1x units on a 4x canvas

def canvas(w, h):
    return pygame.Surface((w * S, h * S), pygame.SRCALPHA)


def save(surf, name):
    w, h = surf.get_width() // S, surf.get_height() // S
    pygame.image.save(pygame.transform.smoothscale(surf, (w, h)), str(OUT / name))


def sc(p):
    return p[0] * S, p[1] * S


def line(surf, color, a, b, width):
    pygame.draw.line(surf, color, sc(a), sc(b), round(width * S))


def circle(surf, color, center, r, width=0):
    pygame.draw.circle(surf, color, sc(center), r * S, round(width * S))


def poly(surf, color, points):
    pygame.draw.polygon(surf, color, [sc(p) for p in points])


def rect(surf, color, r, radius=0):
    pygame.draw.rect(surf, color, [v * S for v in r], border_radius=radius * S)


def label(surf, text, size, color, center, angle=0):
    t = pygame.font.Font(None, size * S).render(text, True, color)
    t = pygame.transform.rotate(t, angle)
    surf.blit(t, t.get_rect(center=sc(center)))


def polar(center, r, deg):
    """Point at a compass angle (0 = up, clockwise)."""
    a = math.radians(deg)
    return center[0] + r * math.sin(a), center[1] - r * math.cos(a)


def keep_circle(surf, center, r_out, r_in=0):
    mask = canvas(surf.get_width() // S, surf.get_height() // S)
    circle(mask, (255, 255, 255, 255), center, r_out)
    if r_in:
        circle(mask, (0, 0, 0, 0), center, r_in)
    surf.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)


def gradient(surf, top, bottom, y0, y1, w):
    for y in range(y0 * S, y1 * S):
        f = (y - y0 * S) / max(1, (y1 - y0) * S - 1)
        pygame.draw.line(surf, [round(a + (b - a) * f) for a, b in zip(top, bottom)], (0, y), (w * S, y))


# ---- shared parts

C = (BOX // 2, BOX // 2)  # centre of instrument-sized layers
K = (CARD_R, CARD_R)      # centre of card-sized layers


def bezel(surf):
    circle(surf, BEZEL, C, BEZEL_R)
    circle(surf, (52, 52, 56), C, BEZEL_R, 3)       # outer highlight
    circle(surf, (0, 0, 0, 0), C, CARD_R)          # window
    circle(surf, (6, 6, 8), C, CARD_R + 4, 5)      # inner shadow


def knob(surf, offset, text="", color=WHITE):
    at = (C[0] + offset[0], C[1] + offset[1])
    circle(surf, (20, 20, 22), at, KNOB_R)
    circle(surf, (48, 48, 52), at, KNOB_R - 3)
    circle(surf, (70, 70, 74), at, KNOB_R - 3, 2)
    if text:
        label(surf, text, 18, color, at)


def case():
    surf = canvas(BOX, BOX)
    rect(surf, CASE, (0, 0, BOX, BOX), 36)
    for sx in (-1, 1):
        for sy in (-1, 1):
            circle(surf, (16, 16, 18), (C[0] + sx * 170, C[1] + sy * 170), 6)
    save(surf, "case.png")


# ---- directional gyro

def dg_card():
    surf = canvas(2 * CARD_R, 2 * CARD_R)
    circle(surf, BLACK, K, CARD_R)
    for deg in range(0, 360, 5):
        major = deg % 10 == 0
        line(surf, WHITE, polar(K, CARD_R - 3, deg), polar(K, CARD_R - (19 if major else 11), deg), 2.6 if major else 1.6)
    for deg in range(0, 360, 30):
        text = {0: "N", 90: "E", 180: "S", 270: "W"}.get(deg, str(deg // 10))
        label(surf, text, 40 if deg % 90 == 0 else 34, WHITE, polar(K, CARD_R - 42, deg), -deg)
    save(surf, "dg_card.png")


def dg_bug():
    surf = canvas(2 * CARD_R, 2 * CARD_R)
    x = CARD_R
    poly(surf, ORANGE, [(x - 15, 2), (x + 15, 2), (x + 15, 20), (x + 6, 20), (x, 11), (x - 6, 20), (x - 15, 20)])
    save(surf, "dg_bug.png")


def dg_face():
    surf = canvas(BOX, BOX)
    bezel(surf)  # first: it's a filled disc with the window cut out
    x, y = C
    poly(surf, WHITE, [(x, y - CARD_R + 4), (x + 5, y - 62), (x - 5, y - 62)])  # lubber line, top
    line(surf, WHITE, (x, y + 96), (x, y + CARD_R - 2), 3)                     # lubber line, bottom
    rect(surf, WHITE, (x - 5, y - 32, 10, 70), 5)                              # fuselage
    rect(surf, WHITE, (x - 52, y - 8, 104, 13), 6)                             # wings
    rect(surf, WHITE, (x - 19, y + 28, 38, 9), 4)                              # tail
    knob(surf, KNOBS["dg_card"], "PUSH")
    knob(surf, KNOBS["dg_bug"], "HDG", ORANGE)
    save(surf, "dg_face.png")


# ---- attitude indicator

def ai_tape():
    surf = canvas(2 * CARD_R, TAPE_H)
    h = TAPE_H // 2
    gradient(surf, SKY_HIGH, SKY_LOW, 0, h, 2 * CARD_R)
    gradient(surf, GROUND_HIGH, GROUND_LOW, h, TAPE_H, 2 * CARD_R)
    line(surf, WHITE, (0, h), (2 * CARD_R, h), 2.5)
    for pitch in range(5, 31, 5):
        half = 38 if pitch % 10 == 0 else 18
        for y in (h - pitch * PX_PER_DEG, h + pitch * PX_PER_DEG):
            line(surf, WHITE, (CARD_R - half, y), (CARD_R + half, y), 2)
            if pitch % 10 == 0:
                for side in (-1, 1):
                    label(surf, str(pitch), 18, WHITE, (CARD_R + side * (half + 14), y))
    save(surf, "ai_tape.png")


def ai_card():
    surf = canvas(2 * CARD_R, 2 * CARD_R)
    rect(surf, SKY_LOW, (0, 0, 2 * CARD_R, CARD_R))
    rect(surf, GROUND_HIGH, (0, CARD_R, 2 * CARD_R, CARD_R))
    line(surf, WHITE, (0, CARD_R), (2 * CARD_R, CARD_R), 3)
    for deg, length in ((10, 10), (20, 10), (30, 20), (60, 20)):
        for side in (-1, 1):
            line(surf, WHITE, polar(K, CARD_R - 3, side * deg), polar(K, CARD_R - 3 - length, side * deg), 3)
    for side in (-1, 1):  # 45 deg marks
        a, b, c = polar(K, CARD_R - 4, side * 45), polar(K, CARD_R - 14, side * 42), polar(K, CARD_R - 14, side * 48)
        poly(surf, WHITE, [a, b, c])
    poly(surf, WHITE, [(CARD_R, 6), (CARD_R - 9, 22), (CARD_R + 9, 22)])  # zero mark
    keep_circle(surf, K, CARD_R, HOLE_R)
    circle(surf, (10, 10, 12), K, HOLE_R + 2, 3)  # hole edge
    save(surf, "ai_card.png")


def ai_plane():
    surf = canvas(BOX, BOX)
    x, y = C
    for side in (-1, 1):  # Y-shaped stem; long enough to stay in the shroud when adjusted
        line(surf, STEM, (x + side * 28, y + 2), (x, y + 42), 5)
    line(surf, STEM, (x, y + 40), (x, y + 92), 7)
    rect(surf, ORANGE, (x - 96, y - 3, 68, 7), 3)
    rect(surf, ORANGE, (x + 28, y - 3, 68, 7), 3)
    circle(surf, ORANGE, (x, y), 5)
    save(surf, "ai_plane.png")


def ai_face():
    surf = canvas(BOX, BOX)
    bezel(surf)
    x, y = C
    shroud = canvas(BOX, BOX)
    rect(shroud, SHROUD, (0, y + 100, BOX, BOX))
    poly(shroud, SHROUD, [(x - 26, y + 66), (x + 26, y + 66), (x + 58, y + 101), (x - 58, y + 101)])
    line(shroud, (62, 62, 68), (x - 26, y + 66), (x + 26, y + 66), 2)
    keep_circle(shroud, C, CARD_R + 2)
    surf.blit(shroud, (0, 0))
    label(surf, "ATTITUDE", 16, (190, 190, 196), (x, y + 116))
    poly(surf, ORANGE, [(x - 11, y - CARD_R - 2), (x + 11, y - CARD_R - 2), (x, y - CARD_R + 20)])  # bank pointer
    knob(surf, KNOBS["ai_adjust"])
    line(surf, WHITE, (C[0] - 158 - 14, C[1] + 158), (C[0] - 158 + 14, C[1] + 158), 3)  # knob index
    save(surf, "ai_face.png")


def main():
    pygame.init()
    OUT.mkdir(exist_ok=True)
    for draw in (case, dg_card, dg_bug, dg_face, ai_tape, ai_card, ai_plane, ai_face):
        draw()
    geometry = {"box": BOX, "card_r": CARD_R, "knob_r": KNOB_R, "knobs": KNOBS,
                "ai": {"px_per_deg": PX_PER_DEG, "horizon_row": TAPE_H // 2, "max_adjust": 5}}
    (OUT / "assets.json").write_text(json.dumps(geometry, indent=2) + "\n")
    print(f"wrote {len(list(OUT.glob('*.png')))} layers to {OUT}")


if __name__ == "__main__":
    main()

# /// script
# requires-python = ">=3.10"
# dependencies = ["pygame-ce", "pillow"]
# ///
"""Attitude indicator + directional gyro driven by the MacBook's Bosch gyro.

Starts ./dgyro -l as a child process and reads one CSV line per gyro sample:
    t,heading,rate_dps,ang_x,ang_y,ang_z,temp_c
heading comes from rotation about z, pitch from x (ang_x), roll from y (ang_y).
Status messages (calibrating, bias, warnings) arrive on its stderr.
Commands go back on its stdin: "<degrees>" set heading, "c" recalibrate,
"r" reverse heading direction, "l" level (zero pitch/roll), "q" quit.

Instrument art comes from X-Plane 12's Cessna 172 if it's installed (set
XPLANE_ROOT if it isn't at /Volumes/pny/xplane). It's converted once into
~/.cache/macbook-compass and never copied into this repo. Without it, simple
drawn instruments are used instead.

Run:  uv run compass.py
"""

import math
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pygame

HERE = Path(__file__).resolve().parent
CAL_SECS = 3

# Flip these if pitch or roll move the wrong way
PITCH_SIGN = 1
ROLL_SIGN = 1

XPLANE = Path(os.environ.get("XPLANE_ROOT", "/Volumes/pny/xplane"))
C172 = XPLANE / "Aircraft/Laminar Research/Cessna 172 SP/objects/instruments"
CACHE = Path.home() / ".cache/macbook-compass"

# Layout: two instruments side by side. All instrument geometry is in texture
# pixels (the X-Plane textures are 512x512 with the dial centred at 184,184).
BOX = 392            # instrument case size
CARD_R = 147         # radius of the moving card
BEZEL_R = 184        # outer radius of the bezel ring
W, H = 2 * BOX + 3 * 28, 700
CY = 150 + BOX // 2
AI_CENTER = (28 + BOX // 2, CY)
DG_CENTER = (2 * 28 + BOX + BOX // 2, CY)

BG = (18, 20, 24)
CASE = (30, 31, 34)
CARD = (34, 37, 44)
FG = (235, 235, 235)
DIM = (130, 135, 145)
ACCENT = (255, 165, 0)
SKY = (74, 150, 200)
GROUND = (115, 85, 70)
GOOD = (80, 200, 120)
WARN = (240, 190, 60)
BAD = (230, 80, 70)


class Gyro:
    """Runs dgyro and keeps its latest values. Two background threads read its output."""

    def __init__(self):
        self.proc = subprocess.Popen(
            [str(HERE / "dgyro"), "-l"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1,
        )
        self.heading = 0.0
        self.rate = 0.0
        self.pitch = 0.0
        self.roll = 0.0
        self.temp = 0.0
        self.calibrating = True
        self.cal_started = time.monotonic()
        self.cal_warning = False
        threading.Thread(target=self._read_samples, daemon=True).start()
        threading.Thread(target=self._read_status, daemon=True).start()

    def _read_samples(self):
        for line in self.proc.stdout:
            fields = line.strip().split(",")
            if fields[0] == "t":  # header
                continue
            _, heading, rate, ang_x, ang_y, _, temp = map(float, fields)
            self.heading, self.rate, self.temp = heading, rate, temp
            self.pitch = PITCH_SIGN * ang_x
            self.roll = (ROLL_SIGN * ang_y + 180) % 360 - 180

    def _read_status(self):
        for line in self.proc.stderr:
            line = line.strip()
            if line.startswith("calibrating"):
                self.calibrating = True
                self.cal_started = time.monotonic()
                self.cal_warning = False
            elif line.startswith("bias"):
                self.calibrating = False
                self.cal_warning = "WARNING" in line

    def send(self, command):
        try:
            self.proc.stdin.write(command + "\n")
            self.proc.stdin.flush()
        except BrokenPipeError:
            pass

    def set_heading(self, degrees):
        self.heading = degrees % 360
        self.send(f"{self.heading:.2f}")

    def level(self):
        self.pitch = self.roll = 0.0
        self.send("l")

    def close(self):
        self.send("q")
        try:
            self.proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            self.proc.terminate()


# ---------------------------------------------------------------- X-Plane art

def uv_triangles(obj_path):
    """UV triangles (in 512px texture coords) of every mesh in an X-Plane OBJ."""
    uvs, idx, tris = [], [], []
    for line in open(obj_path, encoding="latin-1"):
        p = line.split()
        if not p:
            continue
        if p[0] == "VT":
            uvs.append((float(p[7]) * 512, (1 - float(p[8])) * 512))
        elif p[0] in ("IDX", "IDX10"):
            idx += map(int, p[1:])
        elif p[0] == "TRIS":
            off, n = int(p[1]), int(p[2])
            tris += [[uvs[i] for i in idx[k:k + 3]] for k in range(off, off + n, 3)]
    return tris


def load_texture(folder, name):
    """Load an X-Plane instrument texture as a pygame surface, or None if X-Plane isn't there.

    X-Plane ships DDS (pygame can't read it) with no transparency: each part's
    outline comes from its mesh. So convert once to PNG, using the OBJ's UV
    triangles as the alpha channel to cut every part out cleanly.
    """
    cached = CACHE / f"{name}.png"
    if not cached.exists():
        dds, obj = C172 / folder / f"{name}.dds", C172 / folder / f"{name}.obj"
        if not (dds.exists() and obj.exists()):
            return None
        from PIL import Image, ImageDraw
        image = Image.open(dds).convert("RGBA")
        alpha = Image.new("L", image.size, 0)
        draw = ImageDraw.Draw(alpha)
        for tri in uv_triangles(obj):
            draw.polygon(tri, fill=255)
        image.putalpha(alpha)
        CACHE.mkdir(parents=True, exist_ok=True)
        image.save(cached)
    return pygame.image.load(str(cached)).convert_alpha()


def crop(texture, rect):
    surf = pygame.Surface(rect[2:], pygame.SRCALPHA)
    surf.blit(texture, (0, 0), rect)
    return surf


def keep_circle(surf, center, r_out, r_in=0):
    """Make everything outside the ring r_in..r_out transparent."""
    mask = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    pygame.draw.circle(mask, (255, 255, 255, 255), center, r_out)
    if r_in:
        pygame.draw.circle(mask, (0, 0, 0, 0), center, r_in)
    surf.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    return surf


def disc(texture, r_out, r_in=0):
    """Ring or disc around the dial centre (184,184) of an instrument texture."""
    surf = crop(texture, (184 - r_out, 184 - r_out, 2 * r_out, 2 * r_out))
    return keep_circle(surf, (r_out, r_out), r_out, r_in)


def place(layer, texture, rect, anchor, at, clip_r=None):
    """Blit part `rect` of the texture so texture point `anchor` lands at `at` on the layer
    (layer coords are relative to the instrument centre at BOX/2)."""
    part = crop(texture, rect)
    if clip_r:  # don't let the part stick out past the dial face
        keep_circle(part, (anchor[0] - rect[0], anchor[1] - rect[1]), clip_r)
    layer.blit(part, (BOX // 2 + at[0] - (anchor[0] - rect[0]), BOX // 2 + at[1] - (anchor[1] - rect[1])))


def case_layer():
    layer = pygame.Surface((BOX, BOX), pygame.SRCALPHA)
    pygame.draw.rect(layer, CASE, layer.get_rect(), border_radius=36)
    for sx in (-1, 1):
        for sy in (-1, 1):
            pygame.draw.circle(layer, (18, 18, 20), (BOX // 2 + sx * 170, BOX // 2 + sy * 170), 6)
    return layer


class DirectionalGyro:
    def __init__(self):
        self.tex = load_texture("directional_gyro", "dir_gyro_ga")
        if not self.tex:
            return
        self.case = case_layer()
        self.card = disc(self.tex, CARD_R)
        self.over = pygame.Surface((BOX, BOX), pygame.SRCALPHA)
        # plane symbol, lubber line and VACUUM label; wing root sits on the dial centre
        place(self.over, self.tex, (362, 160, 148, 350), (432, 332), (0, 0), clip_r=CARD_R)
        self.over.blit(disc(self.tex, BEZEL_R, CARD_R - 1), (BOX // 2 - BEZEL_R, BOX // 2 - BEZEL_R))
        place(self.over, self.tex, (234, 362, 66, 66), (267, 395), (-158, 158))  # PUSH knob
        place(self.over, self.tex, (302, 362, 66, 66), (335, 395), (158, 158))   # HDG knob

    def draw(self, screen, center, heading):
        if not self.tex:
            return draw_dg_fallback(screen, center, heading)
        box = self.case.get_rect(center=center)
        screen.blit(self.case, box)
        card = pygame.transform.rotozoom(self.card, heading, 1)  # higher headings come round from the right
        screen.blit(card, card.get_rect(center=center))
        screen.blit(self.over, box)


class AttitudeIndicator:
    PX_PER_DEG = 1.65              # pitch ladder spacing on the texture (10 deg = ~17 px)
    MAX_SHIFT = CARD_R             # px; past this the ladder is out of view anyway
    LADDER = (86, 131, 197, 106)   # pitch ladder oval on the texture
    LADDER_HORIZON = 52            # horizon line's distance down the ladder, px

    def __init__(self):
        self.tex = load_texture("horizon", "horizon_ga_vac")
        if not self.tex:
            return
        self.case = case_layer()
        self.card = disc(self.tex, CARD_R)  # sky/ground card with the bank scale; rolls

        # Pitch ladder oval (cut out by its mesh) and where it sits on the card at zero pitch
        self.ladder = crop(self.tex, self.LADDER)
        self.ladder_at = (self.LADDER[0] - (184 - CARD_R), self.LADDER[1] - (184 - CARD_R))
        self.sky = self.tex.get_at((184, 140))
        self.ground = self.tex.get_at((184, 232))

        self.over = pygame.Surface((BOX, BOX), pygame.SRCALPHA)
        place(self.over, self.tex, (180, 424, 330, 88), (346, 358), (0, 62), clip_r=CARD_R + 2)  # lower shroud
        place(self.over, self.tex, (290, 356, 112, 70), (346, 358), (0, 62))                       # VACUUM bump
        place(self.over, self.tex, (355, 14, 100, 66), (405, 9), (0, 0))                           # plane stem
        place(self.over, self.tex, (302, 0, 208, 15), (405, 9), (0, 0))                            # plane wings
        place(self.over, self.tex, (318, 18, 38, 28), (337, 20), (0, -CARD_R + 1))                 # bank pointer
        bezel_r = BEZEL_R - 5  # the knob strip sits just inside the bottom of the bezel on this texture
        self.over.blit(disc(self.tex, bezel_r, CARD_R - 1), (BOX // 2 - bezel_r, BOX // 2 - bezel_r))
        place(self.over, self.tex, (233, 354, 68, 68), (267, 388), (-158, 158), clip_r=33)          # adjust knob

    def draw(self, screen, center, pitch, roll):
        if not self.tex:
            return draw_ai_fallback(screen, center, pitch, roll)
        box = self.case.get_rect(center=center)
        screen.blit(self.case, box)

        # The ball behind the card: sky/ground plus the ladder, slid by pitch.
        # Nose up moves the horizon down.
        shift = max(-self.MAX_SHIFT, min(self.MAX_SHIFT, pitch * self.PX_PER_DEG))
        size = 2 * CARD_R
        horizon = int(self.ladder_at[1] + self.LADDER_HORIZON + shift)
        ball = pygame.Surface((size, size), pygame.SRCALPHA)
        ball.fill(self.sky, (0, 0, size, horizon))
        ball.fill(self.ground, (0, horizon, size, size))
        ball.blit(self.ladder, (self.ladder_at[0], self.ladder_at[1] + shift))
        ball.blit(self.card, (0, 0))  # the card has a hole in the middle that the ball shows through
        keep_circle(ball, (CARD_R, CARD_R), CARD_R)

        # Banking right turns the horizon the other way (counter-clockwise on screen)
        ball = pygame.transform.rotozoom(ball, roll, 1)
        screen.blit(ball, ball.get_rect(center=center))
        screen.blit(self.over, box)


# ------------------------------------------------------ fallback instruments

def polar(center, radius, angle_deg):
    """Point at a compass angle (0 = up, clockwise) from a centre."""
    a = math.radians(angle_deg)
    return center[0] + radius * math.sin(a), center[1] - radius * math.cos(a)


def draw_dg_fallback(screen, center, heading, fonts={}):
    if not fonts:
        fonts.update(cardinal=pygame.font.Font(None, 40), label=pygame.font.Font(None, 30))
    pygame.draw.circle(screen, CARD, center, CARD_R + 20)
    pygame.draw.circle(screen, DIM, center, CARD_R + 20, 2)
    r = CARD_R + 18
    for deg in range(0, 360, 5):
        angle = deg - heading
        major = deg % 10 == 0
        pygame.draw.line(screen, FG if major else DIM, polar(center, r, angle),
                         polar(center, r - (20 if major else 10), angle), 3 if major else 1)
        if deg % 30 == 0:
            text = {0: "N", 90: "E", 180: "S", 270: "W"}.get(deg, str(deg // 10))
            font = fonts["cardinal"] if deg % 90 == 0 else fonts["label"]
            label = pygame.transform.rotozoom(font.render(text, True, FG), -angle, 1)
            screen.blit(label, label.get_rect(center=polar(center, r - 45, angle)))
    cx, cy = center
    pygame.draw.polygon(screen, ACCENT, [(cx - 12, cy - r - 22), (cx + 12, cy - r - 22), (cx, cy - r + 4)])
    pygame.draw.line(screen, ACCENT, (cx, cy - r + 70), (cx, cy - 10), 3)
    pygame.draw.line(screen, ACCENT, (cx - 34, cy), (cx + 34, cy), 4)


def draw_ai_fallback(screen, center, pitch, roll):
    r = CARD_R + 20
    face = pygame.Surface((4 * r, 4 * r), pygame.SRCALPHA)
    horizon = 2 * r + max(-r, min(r, pitch * 3))
    face.fill(SKY, (0, 0, 4 * r, horizon))
    face.fill(GROUND, (0, horizon, 4 * r, 4 * r))
    pygame.draw.line(face, FG, (0, horizon), (4 * r, horizon), 3)
    face = pygame.transform.rotozoom(face, roll, 1)
    clip = pygame.Surface((2 * r, 2 * r), pygame.SRCALPHA)
    clip.blit(face, face.get_rect(center=(r, r)))
    keep_circle(clip, (r, r), r)
    screen.blit(clip, clip.get_rect(center=center))
    cx, cy = center
    pygame.draw.line(screen, ACCENT, (cx - 70, cy), (cx - 20, cy), 5)
    pygame.draw.line(screen, ACCENT, (cx + 20, cy), (cx + 70, cy), 5)
    pygame.draw.circle(screen, ACCENT, center, 5)
    pygame.draw.circle(screen, DIM, center, r, 2)


# ------------------------------------------------------------------- screen

def draw_calibrating(screen, fonts, gyro):
    shade = pygame.Surface((W, H), pygame.SRCALPHA)
    for center in (AI_CENTER, DG_CENTER):
        pygame.draw.circle(shade, (0, 0, 0, 200), center, CARD_R + 4)
    screen.blit(shade, (0, 0))
    progress = min(1.0, (time.monotonic() - gyro.cal_started) / CAL_SECS)
    for center in (AI_CENTER, DG_CENTER):
        ring = pygame.Rect(0, 0, 2 * CARD_R - 40, 2 * CARD_R - 40)
        ring.center = center
        pygame.draw.arc(screen, ACCENT, ring, math.pi / 2 - progress * 2 * math.pi, math.pi / 2, 8)
        for text, font, dy in (("Hold still", fonts["title"], -18), ("measuring gyro bias", fonts["small"], 22)):
            surf = font.render(text, True, FG)
            screen.blit(surf, surf.get_rect(center=(center[0], center[1] + dy)))


def signed(value, places):
    """+1.5 / -2.0 / +0.0, never -0.0"""
    return f"{round(value, places) + 0.0:+.{places}f}"


def draw_readouts(screen, fonts, gyro):
    points = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    for center, big, sub in (
        (AI_CENTER, f"{signed(gyro.pitch, 0)}° / {signed(gyro.roll, 0)}°",
         f"pitch {signed(gyro.pitch, 1)}°   ·   roll {signed(gyro.roll, 1)}°"),
        (DG_CENTER, f"{round(gyro.heading) % 360:03d}°",
         f"{points[int((gyro.heading + 22.5) // 45) % 8]}   ·   {round(gyro.heading, 1) % 360:05.1f}°"),
    ):
        surf = fonts["readout"].render(big, True, FG)
        screen.blit(surf, surf.get_rect(center=(center[0], 62)))
        surf = fonts["small"].render(sub, True, DIM)
        screen.blit(surf, surf.get_rect(center=(center[0], 112)))


def draw_status(screen, fonts, gyro, aligned_at):
    since = time.monotonic() - aligned_at
    if gyro.cal_warning:
        color, text = BAD, "Moved during calibration: press C and hold still"
    else:
        color = GOOD if since < 300 else WARN if since < 900 else BAD
        text = (f"aligned {int(since // 60)}m {int(since % 60):02d}s ago   ·   "
                f"turning {gyro.rate:+.1f}°/s   ·   gyro {gyro.temp:.1f}°C")
    surf = fonts["small"].render(text, True, FG)
    rect = surf.get_rect(center=(W // 2 + 10, H - 100))
    pygame.draw.circle(screen, color, (rect.left - 18, rect.centery), 7)
    screen.blit(surf, rect)
    hints = ("Set heading: drag the gyro dial, Left/Right keys (Shift = 10°), or N E S W",
             "L level attitude   ·   C recalibrate   ·   R reverse heading   ·   Q quit")
    for i, line in enumerate(hints):
        hint = fonts["hint"].render(line, True, DIM)
        screen.blit(hint, hint.get_rect(center=(W // 2, H - 52 + i * 24)))


def mouse_angle(pos):
    return math.degrees(math.atan2(pos[0] - DG_CENTER[0], DG_CENTER[1] - pos[1]))


def main():
    screenshot = sys.argv[sys.argv.index("--screenshot") + 1] if "--screenshot" in sys.argv else None

    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Attitude + Directional Gyro")
    fonts = {
        "readout": pygame.font.Font(None, 84),
        "title": pygame.font.Font(None, 44),
        "small": pygame.font.Font(None, 26),
        "hint": pygame.font.Font(None, 21),
    }
    ai, dg = AttitudeIndicator(), DirectionalGyro()
    clock = pygame.time.Clock()
    gyro = Gyro()
    aligned_at = time.monotonic()
    drag = None  # (mouse angle, heading) when a drag on the gyro dial started

    def align(degrees):
        nonlocal aligned_at
        gyro.set_heading(degrees)
        aligned_at = time.monotonic()

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                step = 10 if event.mod & pygame.KMOD_SHIFT else 1
                if event.key in (pygame.K_q, pygame.K_ESCAPE):
                    running = False
                elif event.key == pygame.K_LEFT:
                    align(gyro.heading - step)
                elif event.key == pygame.K_RIGHT:
                    align(gyro.heading + step)
                elif event.key in (pygame.K_n, pygame.K_e, pygame.K_s, pygame.K_w):
                    align({pygame.K_n: 0, pygame.K_e: 90, pygame.K_s: 180, pygame.K_w: 270}[event.key])
                elif event.key == pygame.K_l:
                    gyro.level()
                elif event.key == pygame.K_c:
                    gyro.send("c")
                elif event.key == pygame.K_r:
                    gyro.send("r")
            elif event.type == pygame.MOUSEBUTTONDOWN and math.dist(event.pos, DG_CENTER) <= CARD_R:
                drag = (mouse_angle(event.pos), gyro.heading)
            elif event.type == pygame.MOUSEBUTTONUP:
                drag = None
            elif event.type == pygame.MOUSEMOTION and drag:
                # Turning the card clockwise moves lower numbers under the pointer
                turned = (mouse_angle(event.pos) - drag[0] + 180) % 360 - 180
                align(drag[1] - turned)

        screen.fill(BG)
        draw_readouts(screen, fonts, gyro)
        ai.draw(screen, AI_CENTER, gyro.pitch, gyro.roll)
        dg.draw(screen, DG_CENTER, gyro.heading)
        if gyro.calibrating:
            draw_calibrating(screen, fonts, gyro)
        draw_status(screen, fonts, gyro, aligned_at)
        pygame.display.flip()
        clock.tick(60)

        if screenshot and not gyro.calibrating and time.monotonic() - gyro.cal_started > CAL_SECS + 1:
            pygame.image.save(screen, screenshot)
            running = False

    gyro.close()
    pygame.quit()


if __name__ == "__main__":
    main()

"""X-Plane 12 Cessna 172 instrument textures, cut into pygame layers.

The art is read from your X-Plane install (set XPLANE_ROOT if it isn't at
/Volumes/pny/xplane), converted once into ~/.cache/macbook-compass, and never
copied into this repo. Textures are 512x512 with the dial centred at (184, 184);
all instrument geometry below is in texture pixels.
"""

import os
from pathlib import Path

import pygame

XPLANE = Path(os.environ.get("XPLANE_ROOT", "/Volumes/pny/xplane"))
C172 = XPLANE / "Aircraft/Laminar Research/Cessna 172 SP/objects/instruments"
CACHE = Path.home() / ".cache/macbook-compass"

BOX = 392       # instrument case size
CARD_R = 147    # radius of the moving card
BEZEL_R = 184   # outer radius of the bezel ring
KNOB_R = 33
CASE = (30, 31, 34)


def uv_triangles(obj_path):
    """UV triangles (texture px) of every mesh in an X-Plane OBJ."""
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


def texture(folder, name):
    """Load an instrument texture as a pygame surface.

    X-Plane ships DDS (pygame can't read it) with no transparency: each part's
    outline comes from its mesh. So convert once to PNG, using the OBJ's UV
    triangles as the alpha channel to cut every part out cleanly.
    """
    cached = CACHE / f"{name}.png"
    if not cached.exists():
        dds, obj = C172 / folder / f"{name}.dds", C172 / folder / f"{name}.obj"
        if not (dds.exists() and obj.exists()):
            raise SystemExit(f"X-Plane instrument art not found at {dds}\nSet XPLANE_ROOT to your X-Plane 12 folder.")
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


def crop(tex, rect):
    surf = pygame.Surface(rect[2:], pygame.SRCALPHA)
    surf.blit(tex, (0, 0), rect)
    return surf


def keep_circle(surf, center, r_out, r_in=0):
    """Make everything outside the ring r_in..r_out transparent."""
    mask = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    pygame.draw.circle(mask, (255, 255, 255, 255), center, r_out)
    if r_in:
        pygame.draw.circle(mask, (0, 0, 0, 0), center, r_in)
    surf.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    return surf


def disc(tex, r_out, r_in=0):
    """Ring or disc around the dial centre."""
    surf = crop(tex, (184 - r_out, 184 - r_out, 2 * r_out, 2 * r_out))
    return keep_circle(surf, (r_out, r_out), r_out, r_in)


def layer():
    return pygame.Surface((BOX, BOX), pygame.SRCALPHA)


def place(dest, tex, rect, anchor, at, clip_r=None):
    """Blit part `rect` of the texture so texture point `anchor` lands at offset `at`
    from the centre of `dest` (an instrument-sized layer)."""
    part = crop(tex, rect)
    ax, ay = anchor[0] - rect[0], anchor[1] - rect[1]
    if clip_r:  # don't let the part stick out past the dial face
        keep_circle(part, (ax, ay), clip_r)
    w, h = dest.get_size()
    dest.blit(part, (w // 2 + at[0] - ax, h // 2 + at[1] - ay))


def bezel(tex, r_out=BEZEL_R):
    ring = layer()
    ring.blit(disc(tex, r_out, CARD_R - 1), (BOX // 2 - r_out, BOX // 2 - r_out))
    return ring


def case():
    surf = layer()
    pygame.draw.rect(surf, CASE, surf.get_rect(), border_radius=36)
    for sx in (-1, 1):
        for sy in (-1, 1):
            pygame.draw.circle(surf, (18, 18, 20), (BOX // 2 + sx * 170, BOX // 2 + sy * 170), 6)
    return surf

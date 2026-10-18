"""Instrument art: PNG layers and their geometry in assets/ (drawn by make_assets.py)."""

import json
from pathlib import Path

import pygame

ASSETS = Path(__file__).resolve().parent / "assets"
GEOMETRY = json.loads((ASSETS / "assets.json").read_text())
BOX, CARD_R, KNOB_R = GEOMETRY["box"], GEOMETRY["card_r"], GEOMETRY["knob_r"]


def load(name):
    return pygame.image.load(str(ASSETS / f"{name}.png")).convert_alpha()


def keep_circle(surf, center, r):
    """Make everything outside radius r transparent."""
    mask = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    pygame.draw.circle(mask, (255, 255, 255, 255), center, r)
    surf.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)

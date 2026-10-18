"""G meter (accelerometer), one per axis.

Sensor input: g        load factor along the axis (+1 G on z when lying flat)
User input:   reset()  PUSH knob, brings the min/max tattletale needles back to the needle
"""

import pygame

import art


class GMeter:
    KNOB = art.GEOMETRY["knobs"]["gm_reset"]

    def __init__(self, axis, scale=1.0):
        g = art.GEOMETRY["gm"]
        self.axis, self.scale = axis, scale
        self.range, self.deg_per_g = g["range"], g["deg_per_g"]
        self.g = self.min = self.max = 0.0
        self.case, self.face, self.needle, self.tattle = (
            pygame.transform.smoothscale_by(art.load(name), scale) for name in ("case", "gm_face", "gm_needle", "gm_tattle"))
        self.font = pygame.font.Font(None, round(34 * scale))

    def read(self, g):
        self.g = g
        self.min, self.max = min(self.min, g), max(self.max, g)

    def reset(self):
        self.min = self.max = self.g

    def knob_at(self, center):
        return center[0] + self.KNOB[0] * self.scale, center[1] + self.KNOB[1] * self.scale

    def draw(self, screen, center):
        box = self.case.get_rect(center=center)
        screen.blit(self.case, box)
        screen.blit(self.face, box)
        label = self.font.render(f"{self.axis}  {round(self.g, 2) + 0.0:+.2f} G", True, (235, 235, 235))
        screen.blit(label, label.get_rect(center=(center[0], center[1] + 84 * self.scale)))  # in the gap below the scale
        for value, layer in ((self.min, self.tattle), (self.max, self.tattle), (self.g, self.needle)):
            angle = max(-self.range - 0.1, min(self.range + 0.1, value)) * self.deg_per_g  # pegs just past full scale
            turned = pygame.transform.rotozoom(layer, -angle, 1)  # more G = clockwise
            screen.blit(turned, turned.get_rect(center=center))

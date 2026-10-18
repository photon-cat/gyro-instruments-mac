"""Directional gyro (heading indicator).

Sensor input:  heading
User inputs:   turn_card(+/-deg)  PUSH knob, lines the card up with a known heading
               turn_bug(+/-deg)   HDG knob, moves the heading bug
"""

import pygame

import art


class DirectionalGyro:
    KNOBS = {"card": art.GEOMETRY["knobs"]["dg_card"], "bug": art.GEOMETRY["knobs"]["dg_bug"]}

    def __init__(self):
        self.heading = 0.0   # from the sensors
        self.offset = 0.0    # PUSH knob correction
        self.bug = 0.0       # selected heading
        self.case, self.card, self.bug_layer, self.face = map(art.load, ("case", "dg_card", "dg_bug", "dg_face"))

    @property
    def indicated(self):
        """Heading shown under the lubber line."""
        return (self.heading + self.offset) % 360

    def turn_card(self, degrees):
        self.offset += degrees

    def turn_bug(self, degrees):
        self.bug = (self.bug + degrees) % 360

    def draw(self, screen, center):
        box = self.case.get_rect(center=center)
        screen.blit(self.case, box)
        # Higher headings come round from the right: the card turns counter-clockwise
        for layer, angle in ((self.card, self.indicated), (self.bug_layer, self.indicated - self.bug)):
            turned = pygame.transform.rotozoom(layer, angle, 1)
            screen.blit(turned, turned.get_rect(center=center))
        screen.blit(self.face, box)

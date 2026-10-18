"""Directional gyro (heading indicator).

Sensor input:  heading
User inputs:   turn_card(+/-deg)  HDG knob, lines the card up with a known heading
               turn_bug(+/-deg)   BUG knob, moves the heading bug
Each knob turns visibly; click its left/right half (arrows) to turn it.
"""

import pygame

import art


class DirectionalGyro:
    KNOBS = {"card": art.GEOMETRY["knobs"]["dg_card"], "bug": art.GEOMETRY["knobs"]["dg_bug"]}
    KNOB_GEAR = 4  # knob degrees per degree of heading, so small changes are visible

    def __init__(self):
        self.heading = 0.0   # from the sensors
        self.offset = 0.0    # PUSH knob correction
        self.bug = 0.0       # selected heading
        self.knob_angle = {"card": 0.0, "bug": 0.0}
        self.case, self.card, self.bug_layer, self.face, self.knob = map(
            art.load, ("case", "dg_card", "dg_bug", "dg_face", "knob"))

    @property
    def indicated(self):
        """Heading shown under the lubber line."""
        return (self.heading + self.offset) % 360

    def turn_card(self, degrees):
        self.offset += degrees
        self.knob_angle["card"] += degrees * self.KNOB_GEAR

    def turn_bug(self, degrees):
        self.bug = (self.bug + degrees) % 360
        self.knob_angle["bug"] += degrees * self.KNOB_GEAR

    def draw(self, screen, center):
        box = self.case.get_rect(center=center)
        screen.blit(self.case, box)
        # Higher headings come round from the right: the card turns counter-clockwise
        for layer, angle in ((self.card, self.indicated), (self.bug_layer, self.indicated - self.bug)):
            turned = pygame.transform.rotozoom(layer, angle, 1)
            screen.blit(turned, turned.get_rect(center=center))
        for name, (dx, dy) in self.KNOBS.items():  # turning right = clockwise
            grip = pygame.transform.rotozoom(self.knob, -self.knob_angle[name], 1)
            screen.blit(grip, grip.get_rect(center=(center[0] + dx, center[1] + dy)))
        screen.blit(self.face, box)  # includes each knob's label and arrows

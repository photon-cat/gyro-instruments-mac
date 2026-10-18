"""Directional gyro (heading indicator), Cessna 172 style.

Sensor input:  heading
User inputs:   turn_card(+/-deg)  PUSH knob, lines the card up with a known heading
               turn_bug(+/-deg)   HDG knob, moves the heading bug
"""

import pygame

import xplane as xp


class DirectionalGyro:
    KNOBS = {"card": (-158, 158), "bug": (158, 158)}  # knob centres, offset from the dial centre

    def __init__(self):
        tex = xp.texture("directional_gyro", "dir_gyro_ga")
        self.heading = 0.0   # from the sensors
        self.offset = 0.0    # PUSH knob correction
        self.bug = 0.0       # selected heading

        self.case = xp.case()
        self.card = xp.disc(tex, xp.CARD_R)
        self.bug_layer = pygame.Surface((2 * xp.CARD_R, 2 * xp.CARD_R), pygame.SRCALPHA)
        self.bug_layer.blit(xp.crop(tex, (318, 22, 38, 35)), (xp.CARD_R - 19, 0))  # bug at the top of the card
        self.over = xp.layer()
        # plane symbol, lubber line and VACUUM label; wing root on the dial centre
        xp.place(self.over, tex, (362, 160, 148, 350), (432, 332), (0, 0), clip_r=xp.CARD_R)
        self.over.blit(xp.bezel(tex), (0, 0))
        xp.place(self.over, tex, (234, 362, 66, 66), (267, 395), self.KNOBS["card"], clip_r=xp.KNOB_R)
        xp.place(self.over, tex, (302, 362, 66, 66), (335, 395), self.KNOBS["bug"], clip_r=xp.KNOB_R)

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
        card = pygame.transform.rotozoom(self.card, self.indicated, 1)
        screen.blit(card, card.get_rect(center=center))
        bug = pygame.transform.rotozoom(self.bug_layer, self.indicated - self.bug, 1)
        screen.blit(bug, bug.get_rect(center=center))
        screen.blit(self.over, box)

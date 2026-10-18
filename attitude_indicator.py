"""Attitude indicator.

Sensor inputs: pitch, roll
(The adjust knob and miniature plane are fixed for now.)
"""

import pygame

import art


class AttitudeIndicator:
    def __init__(self):
        g = art.GEOMETRY["ai"]
        self.px_per_deg, self.horizon_row = g["px_per_deg"], g["horizon_row"]
        self.pitch = self.roll = 0.0  # from the sensors
        self.case, self.tape, self.card, self.face = map(art.load, ("case", "ai_tape", "ai_card", "ai_face"))

    def draw(self, screen, center):
        box = self.case.get_rect(center=center)
        screen.blit(self.case, box)

        # Window onto the pitch tape: nose up shows more sky, so the horizon drops
        size = 2 * art.CARD_R
        pitch = max(-90, min(90, self.pitch))
        top = round(self.horizon_row - art.CARD_R - pitch * self.px_per_deg)
        ball = pygame.Surface((size, size), pygame.SRCALPHA)
        ball.blit(self.tape, (0, 0), (0, top, size, size))
        ball.blit(self.card, (0, 0))  # bank card, with a hole the tape shows through
        art.keep_circle(ball, (art.CARD_R, art.CARD_R), art.CARD_R)

        # Banking right turns the horizon counter-clockwise on screen
        ball = pygame.transform.rotozoom(ball, self.roll, 1)
        screen.blit(ball, ball.get_rect(center=center))
        screen.blit(self.face, box)  # miniature plane, shroud, bank pointer, bezel

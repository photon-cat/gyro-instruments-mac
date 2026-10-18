"""Attitude indicator.

Sensor inputs: pitch, roll
User input:    turn_adjust(+/-deg)  adjust knob, moves the miniature plane up/down
"""

import pygame

import art


class AttitudeIndicator:
    KNOBS = {"adjust": art.GEOMETRY["knobs"]["ai_adjust"]}

    def __init__(self):
        g = art.GEOMETRY["ai"]
        self.px_per_deg, self.horizon_row, self.max_adjust = g["px_per_deg"], g["horizon_row"], g["max_adjust"]
        self.pitch = self.roll = 0.0  # from the sensors
        self.adjust = 0.0             # miniature plane offset, degrees (up = positive)
        self.case, self.tape, self.card, self.plane, self.face = map(
            art.load, ("case", "ai_tape", "ai_card", "ai_plane", "ai_face"))

    def turn_adjust(self, degrees):
        self.adjust = max(-self.max_adjust, min(self.max_adjust, self.adjust + degrees))

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
        screen.blit(self.plane, box.move(0, -round(self.adjust * self.px_per_deg)))
        screen.blit(self.face, box)

"""Turn coordinator.

Sensor inputs: turn_rate  deg/s, + = turning right; the plane banks to the
                          L/R mark at standard rate (3 deg/s, a 2-minute turn)
               ball       deg along the tube, + = right; where apparent gravity
                          (gravity + sideways acceleration) holds the ball
"""

import math

import pygame

import art

STANDARD_RATE = 3.0  # deg/s


class TurnCoordinator:
    def __init__(self):
        g = art.GEOMETRY["tc"]
        self.std_bank, self.tube_c, self.tube_r, self.ball_max = g["std_rate_bank"], g["tube_c"], g["tube_r"], g["ball_max"]
        self.turn_rate = self.ball = 0.0  # from the sensors
        self.case, self.face, self.plane, self.ball_img, self.glass = map(
            art.load, ("case", "tc_face", "tc_plane", "tc_ball", "tc_glass"))

    def draw(self, screen, center):
        box = self.case.get_rect(center=center)
        screen.blit(self.case, box)
        screen.blit(self.face, box)

        # The ball rolls along an arc whose centre sits above the dial centre
        a = math.radians(max(-self.ball_max, min(self.ball_max, self.ball)))
        x = center[0] + self.tube_c[0] + self.tube_r * math.sin(a)
        y = center[1] + self.tube_c[1] + self.tube_r * math.cos(a)
        screen.blit(self.ball_img, self.ball_img.get_rect(center=(round(x), round(y))))
        screen.blit(self.glass, box)

        # Turning right banks the plane right (clockwise on screen)
        bank = max(-45, min(45, self.turn_rate / STANDARD_RATE * self.std_bank))
        plane = pygame.transform.rotozoom(self.plane, -bank, 1)
        screen.blit(plane, plane.get_rect(center=center))

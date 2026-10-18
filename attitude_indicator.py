"""Attitude indicator, Cessna 172 style.

Sensor inputs: pitch, roll
User input:    turn_adjust(+/-deg)  adjust knob, moves the miniature plane up/down
"""

import pygame

import xplane as xp


class AttitudeIndicator:
    KNOBS = {"adjust": (-158, 158)}
    PX_PER_DEG = 1.65               # pitch ladder spacing on the texture (10 deg = ~17 px)
    LADDER = (86, 131, 197, 106)    # pitch ladder oval on the texture
    LADDER_HORIZON = 52             # horizon line's distance down the ladder, px
    MAX_ADJUST = 5                  # degrees the miniature plane can move (more and its stem leaves the shroud)

    def __init__(self):
        tex = xp.texture("horizon", "horizon_ga_vac")
        self.pitch = self.roll = 0.0  # from the sensors
        self.adjust = 0.0             # miniature plane offset, degrees (up = positive)

        self.case = xp.case()
        self.card = xp.disc(tex, xp.CARD_R)  # sky/ground card with the bank scale; it has a hole the ball shows through
        self.ladder = xp.crop(tex, self.LADDER)
        self.ladder_at = (self.LADDER[0] - (184 - xp.CARD_R), self.LADDER[1] - (184 - xp.CARD_R))
        self.sky, self.ground = tex.get_at((184, 140)), tex.get_at((184, 232))

        self.plane = xp.layer()
        xp.place(self.plane, tex, (355, 14, 100, 66), (405, 9), (0, 0))   # stem
        xp.place(self.plane, tex, (302, 0, 208, 15), (405, 9), (0, 0))    # wings
        self.shroud = xp.layer()
        xp.place(self.shroud, tex, (180, 424, 330, 88), (346, 358), (0, 62), clip_r=xp.CARD_R + 2)
        xp.place(self.shroud, tex, (290, 356, 112, 70), (346, 358), (0, 62))  # VACUUM bump
        self.over = xp.layer()
        xp.place(self.over, tex, (318, 18, 38, 28), (337, 20), (0, -xp.CARD_R + 1))  # bank pointer
        self.over.blit(xp.bezel(tex, xp.BEZEL_R - 5), (0, 0))  # knob strip sits just inside the bezel on this texture
        xp.place(self.over, tex, (233, 354, 68, 68), (267, 388), self.KNOBS["adjust"], clip_r=xp.KNOB_R)

    def turn_adjust(self, degrees):
        self.adjust = max(-self.MAX_ADJUST, min(self.MAX_ADJUST, self.adjust + degrees))

    def draw(self, screen, center):
        box = self.case.get_rect(center=center)
        screen.blit(self.case, box)

        # The ball: sky/ground plus the ladder, slid by pitch (nose up moves the horizon down)
        shift = max(-xp.CARD_R, min(xp.CARD_R, self.pitch * self.PX_PER_DEG))
        size = 2 * xp.CARD_R
        horizon = int(self.ladder_at[1] + self.LADDER_HORIZON + shift)
        ball = pygame.Surface((size, size), pygame.SRCALPHA)
        ball.fill(self.sky, (0, 0, size, horizon))
        ball.fill(self.ground, (0, horizon, size, size))
        ball.blit(self.ladder, (self.ladder_at[0], self.ladder_at[1] + shift))
        ball.blit(self.card, (0, 0))
        xp.keep_circle(ball, (xp.CARD_R, xp.CARD_R), xp.CARD_R)

        # Banking right turns the horizon counter-clockwise on screen
        ball = pygame.transform.rotozoom(ball, self.roll, 1)
        screen.blit(ball, ball.get_rect(center=center))
        screen.blit(self.plane, box.move(0, -round(self.adjust * self.PX_PER_DEG)))
        screen.blit(self.shroud, box)
        screen.blit(self.over, box)

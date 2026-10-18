"""Sensor processing: gyro + accelerometer in, heading / pitch / roll out.

libimu.dylib (imu.c) streams the Bosch BMI282 samples; this module removes the
gyro bias and integrates the rates:
    heading  rotation about z
    pitch    rotation about x
    roll     rotation about y
Pitch and roll are gently pulled toward the accelerometer's gravity direction
so they don't drift; heading has no such reference (there's no magnetometer).
The inclinometer ball is the accelerometer's sideways pull: it settles where
apparent gravity (gravity plus any sideways acceleration) points.
"""

import atexit
import ctypes
import math
import time
from pathlib import Path

LIB = Path(__file__).resolve().parent / "libimu.dylib"
GYRO, ACCEL = 9, 3

# Flip a sign if that axis moves the wrong way on screen
HEADING_SIGN = -1
PITCH_SIGN = 1
ROLL_SIGN = 1

CAL_SECS = 3          # bias calibration time, keep still
GRAVITY_TAU = 2.0     # seconds for pitch/roll to settle onto the accelerometer
BALL_TAU = 0.15       # inclinometer ball damping, seconds
RATE_TAU = 0.3        # turn rate smoothing, seconds
MOVED_DPS = 0.2       # gyro noise above this during calibration means it moved


class Sample(ctypes.Structure):
    _fields_ = [("t", ctypes.c_double), ("sensor", ctypes.c_int32), ("seq", ctypes.c_uint32),
                ("x", ctypes.c_double), ("y", ctypes.c_double), ("z", ctypes.c_double),
                ("temp", ctypes.c_double)]


class Imu:
    """Heading, pitch and roll from the MacBook's gyro and accelerometer. Call update() often."""

    def __init__(self):
        self.lib = ctypes.CDLL(str(LIB))
        self.lib.imu_read.argtypes = [ctypes.POINTER(Sample), ctypes.c_int]
        if self.lib.imu_start() != 0:
            raise RuntimeError("gyro/accelerometer not found on this Mac")
        atexit.register(self.lib.imu_stop)  # streaming is a global driver setting: always turn it off
        self.buffer = (Sample * 512)()
        self.heading = self.pitch = self.roll = 0.0  # degrees
        self.turn_rate = 0.0                          # deg/s, positive = heading increasing (smoothed)
        self.ball = 0.0                               # inclinometer ball, deg along its tube, + = right
        self.temp = 0.0                               # IMU temperature, degC
        self.gravity = (0.0, 0.0, -1.0)               # latest accelerometer reading, g
        self.bias = (0.0, 0.0, 0.0)
        self.last_t = self.last_accel_t = None
        self.calibrate()

    def calibrate(self):
        """Start measuring gyro bias; keep the laptop still for CAL_SECS."""
        self.calibrating = True
        self.cal_started = time.monotonic()
        self.cal_warning = False
        self.cal_samples = []

    def close(self):
        self.lib.imu_stop()

    def update(self):
        n = self.lib.imu_read(self.buffer, len(self.buffer))
        for s in self.buffer[:n]:
            if s.sensor == ACCEL:
                self._accel(s)
            elif self.calibrating:
                self.cal_samples.append((s.x, s.y, s.z))
            else:
                self._integrate(s)
            self.temp = s.temp
        if self.calibrating and time.monotonic() - self.cal_started >= CAL_SECS:
            self._finish_calibration()

    def _finish_calibration(self):
        xs, ys, zs = zip(*self.cal_samples)
        self.bias = tuple(sum(v) / len(v) for v in (xs, ys, zs))
        noise = max(math.sqrt(sum((v - m) ** 2 for v in vs) / len(vs)) for vs, m in zip((xs, ys, zs), self.bias))
        self.cal_warning = noise > MOVED_DPS
        self.pitch, self.roll = self._gravity_angles()  # start level with the real horizon
        self.calibrating = False
        self.last_t = None

    def _gravity_angles(self):
        """Pitch and roll implied by the accelerometer (the gravity vector turns opposite to the laptop)."""
        ax, ay, az = self.gravity
        return (PITCH_SIGN * math.degrees(math.atan2(-ay, -az)),
                ROLL_SIGN * math.degrees(math.atan2(ax, -az)))

    def _accel(self, s):
        dt = s.t - self.last_accel_t if self.last_accel_t else 0.0
        self.last_accel_t = s.t
        self.gravity = (s.x, s.y, s.z)
        # A ball in a curved tube rests where the tube is perpendicular to apparent gravity
        target = ROLL_SIGN * math.degrees(math.atan2(s.x, -s.z))
        self.ball += min(1.0, dt / BALL_TAU) * (target - self.ball)

    def _integrate(self, s):
        dt = s.t - self.last_t if self.last_t else 0.0
        self.last_t = s.t
        if dt > 0.1:  # gap (sleep, stall): don't integrate across it
            dt = 0.0
        wx, wy, wz = (s.x - self.bias[0], s.y - self.bias[1], s.z - self.bias[2])
        rate = HEADING_SIGN * wz
        self.heading = (self.heading + rate * dt) % 360
        self.turn_rate += dt / (RATE_TAU + dt) * (rate - self.turn_rate)
        self.pitch += PITCH_SIGN * wx * dt
        self.roll += ROLL_SIGN * wy * dt

        # Only trust gravity when the laptop isn't accelerating (reading close to 1 g)
        if abs(math.dist((0, 0, 0), self.gravity) - 1) < 0.1:
            k = dt / (GRAVITY_TAU + dt)
            gp, gr = self._gravity_angles()
            self.pitch += k * (gp - self.pitch)
            self.roll += k * ((gr - self.roll + 180) % 360 - 180)
        self.roll = (self.roll + 180) % 360 - 180

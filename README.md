# macbook-compass

An attitude indicator, directional gyro and turn coordinator driven by the MacBook's own motion sensor.

## Reading the IMU

The MacBook has a Bosch BMI282 IMU on its always-on sensor hub, which macOS exposes as vendor HID devices. `imu.c` turns streaming on through the sensor's `AppleSPUHIDDriver` properties and queues every report. No root is needed. Python drains the queue through ctypes (`sensors.py`).

| Sensor | Rate | Values |
|---|---|---|
| Gyro | 100 Hz | rotation rate about x, y, z in °/s, plus IMU temperature |
| Accelerometer | 200 Hz | x, y, z in g (lying flat it reads about (0, 0, -1)) |

There's no magnetometer, so heading is relative: set it with the DG's PUSH knob. See [sensors.md](sensors.md) for everything found while probing the hardware.

## Computing pitch, roll and yaw

At startup the laptop has to sit still for 3 s while the gyro bias $b$ is measured. After that, each gyro sample updates the angles:

$$
\theta_k = \theta_{k-1} + s\,(\omega_k - b)\,\Delta t_k + \frac{\Delta t_k}{\tau + \Delta t_k}\left(\theta^{g}_k - \theta_{k-1}\right)
$$

- $\omega_k$ is the gyro rate about the axis: yaw about z, pitch about x, roll about y.
- $\Delta t_k$ is the integration period, the time between gyro samples (about 10 ms at 100 Hz). Gaps longer than 100 ms aren't integrated.
- $s = \pm 1$ is the axis sign: `HEADING_SIGN`, `PITCH_SIGN` and `ROLL_SIGN` in `sensors.py`.
- The last term pulls pitch and roll toward the gravity angles $\theta^g$ with a time constant $\tau = 2$ s. It's only applied when the accelerometer reads close to 1 g.
  - The gravity angles are pitch = `atan2(-ay, -az)` and roll = `atan2(ax, -az)`.
  - Yaw has no gravity reference, so it skips this term and drifts slowly. Recalibrate with `C`, or realign the card.

The turn coordinator uses two more values:
- **Turn rate:** the yaw rate $s\,(\omega_z - b)$, smoothed over 0.3 s. The plane symbol reaches the L/R mark at standard rate, 3°/s.
- **Ball:** the inclinometer ball rests where apparent gravity (gravity plus any sideways acceleration) holds it in its curved tube.
  - We project the accelerometer vector onto the sensor's X–Z plane (X across the keyboard, Z through the deck) and take its angle from straight down: `atan2(ax, -az)`. Lying flat the vector is (0, 0, −1) g, so the angle is 0° and the ball is centred.
  - Fore-aft acceleration (Y) is ignored, because a real tube lies across the aircraft, so pitching doesn't move the ball.
  - **Fluid damping, approximated:** a real ball is slowed by the fluid in its tube, roughly a damped pendulum. Here it's a first-order lag, `ball += (target − ball) · Δt / τ` with τ = 0.15 s, applied on every accelerometer sample (5 ms at 200 Hz). It never overshoots, whereas a real underdamped ball can swing past slightly.

## Requirements

- An Apple Silicon MacBook (developed on a 16" M1 Pro, MacBookPro18,1) running macOS.
- The Xcode command-line tools, to build `libimu.dylib`: `xcode-select --install`
- [uv](https://docs.astral.sh/uv/), which installs Python and `pygame-ce` on first run: `brew install uv`
  - Without uv: `pip install pygame-ce`, then `python compass.py`

## Run

```sh
make run
```

| Control | Mouse | Keys |
|---|---|---|
| Set heading (turn the DG card) | Click the arrows on the HDG knob (hold to repeat), or scroll over it | ← / → |
| Move the heading bug | Click the arrows on the BUG knob, or scroll over it | `[` / `]` |
| Recalibrate gyro bias | | `C` |
| Quit | | `Q` |

Hold Shift for 10° steps. The attitude indicator's pitch scale is fixed for now.

## Files

| File | Role |
|---|---|
| `imu.c` | Streams the gyro and accelerometer: `imu_start`, `imu_read`, `imu_stop` |
| `sensors.py` | Bias calibration and integration into heading, pitch and roll, plus turn rate and the ball |
| `attitude_indicator.py`, `directional_gyro.py`, `turn_coordinator.py` | The instruments: sensor inputs, plus the DG's knob inputs |
| `compass.py` | Window, layout, input |
| `art.py`, `assets/`, `make_assets.py` | Instrument art: loader, PNG layers and the script that draws them (`make assets`) |

# macbook-compass

A directional gyro and attitude indicator driven by the MacBook's own motion sensor.

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

## Requirements

- An Apple Silicon MacBook (developed on a 16" M1 Pro, MacBookPro18,1) running macOS.
- The Xcode command-line tools, to build `libimu.dylib`: `xcode-select --install`
- [uv](https://docs.astral.sh/uv/), which installs Python and `pygame-ce` on first run: `brew install uv`
  - Without uv: `pip install pygame-ce`, then `python compass.py`

## Run

```sh
make run
```

| Control | Keys | Or scroll over |
|---|---|---|
| Turn the DG card | ← / → | PUSH knob |
| Move the heading bug | `[` / `]` | HDG knob |
| Move the miniature plane | ↑ / ↓ | AI knob |
| Recalibrate gyro bias | `C` | |
| Quit | `Q` | |

Hold Shift for 10° steps.

## Files

| File | Role |
|---|---|
| `imu.c` | Streams the gyro and accelerometer: `imu_start`, `imu_read`, `imu_stop` |
| `sensors.py` | Bias calibration and integration into heading, pitch and roll |
| `directional_gyro.py`, `attitude_indicator.py` | The two instruments (sensor inputs and knob inputs) |
| `compass.py` | Window, layout, input |
| `art.py`, `assets/`, `make_assets.py` | Instrument art: loader, PNG layers and the script that draws them (`make assets`) |

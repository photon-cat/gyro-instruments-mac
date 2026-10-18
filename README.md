# gyro-instruments-mac

Turns your MacBook into half of a six-pack.

An attitude indicator, directional gyro, turn-and-slip indicator and per-axis G meters, all driven by the MacBook's inertial measurement unit (IMU).

![The app: attitude indicator, directional gyro and turn-and-slip indicator, with X/Y/Z G meters below](docs/screenshot.png)

## Reading the IMU

Apple Silicon MacBooks have a Bosch BMI282 IMU (gyro and accelerometer) on the always-on sensor hub, and macOS exposes it as vendor HID devices. It's silent until its `AppleSPUHIDDriver` gets `SensorPropertyReportingState`, `SensorPropertyPowerState` and a `ReportInterval`. Setting the interval back to 0 stops it. No root is needed.

`imu.c` does that and queues every report, and `sensors.py` drains the queue through ctypes. Each sample gives:
- gyro rates $\omega_x, \omega_y, \omega_z$ in °/s
- accelerations $a_x, a_y, a_z$ in g (lying flat, about (0, 0, −1))

Details of the hardware probing are in [sensors.md](sensors.md).

## How each value is computed

$\Delta t$ is the time between samples, $s = \pm1$ is the axis sign, and $\text{lag}_\tau(x)$ smooths toward $x$ with $y \leftarrow y + \frac{\Delta t}{\tau + \Delta t}(x - y)$.

**Rates.** $b$ is the gyro bias, measured over 3 s at startup.

$$
\dot\psi = s_\psi(\omega_z - b_z), \qquad
\dot\theta = s_\theta(\omega_x - b_x), \qquad
\dot\phi = s_\phi(\omega_y - b_y)
$$

**Turn rate.**

$$
r = \text{lag}_{\text{0.3 s}}(\dot\psi)
$$

**Heading.**

$$
\psi \leftarrow (\psi + \dot\psi \Delta t) \bmod 360°
$$

**Pitch and roll.** Integrate the gyro, then pull toward gravity (only while $\lVert a\rVert \approx 1$ g).

$$
\theta^g = s_\theta\mathrm{atan2}(-a_y, -a_z), \qquad
\phi^g = s_\phi\mathrm{atan2}(a_x, -a_z)
$$

$$
\theta \leftarrow \theta + \dot\theta \Delta t, \qquad
\theta \leftarrow \theta + \frac{\Delta t}{\text{2 s} + \Delta t}\left(\theta^g - \theta\right)
\qquad \text{(same for } \phi\text{)}
$$

**Ball.** Apparent gravity in the X–Z plane, with the lag standing in for fluid damping.

$$
\beta = \text{lag}_{\text{0.15 s}}\left(s_\phi\mathrm{atan2}(a_x, -a_z)\right)
$$

**G meters.** Load factor per axis.

$$
n_i = \text{lag}_{\text{0.1 s}}(-a_i), \qquad i \in \lbrace x, y, z \rbrace
$$

## Requirements

- An Apple Silicon MacBook running macOS
- The Xcode command-line tools: `xcode-select --install`
- [uv](https://docs.astral.sh/uv/): `brew install uv`. It installs Python and `pygame-ce` on first run. Without uv, use `pip install pygame-ce`.

## Run

```sh
make run
```

## Files

| File | Role |
|---|---|
| `imu.c` | Streams the gyro and accelerometer: `imu_start`, `imu_read`, `imu_stop` |
| `sensors.py` | Bias, rates, angles, ball and G per axis (the formulas above) |
| `attitude_indicator.py`, `directional_gyro.py`, `turn_coordinator.py`, `g_meter.py` | The instruments |
| `compass.py` | Window, layout, input |
| `art.py`, `assets/`, `make_assets.py` | Instrument art: loader, PNG layers, and the script that draws them |

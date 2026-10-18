# MacBook sensor findings

Machine: MacBookPro18,1 (16" M1 Pro, 2021), macOS 26.6.2. None of the sensors below need root.

## Magnetic sensing
- There's no magnetometer: no compass node on the sensor hub, and the IMU is 6-axis only.
- The only analogue magnetic sensor is the lid hinge angle sensor, a MagAlpha MA781 (chip_id 135).
- The hinge sensor reports a processed angle, not a field vector. Rotating the laptop to 0°, 90° and back moved it by less than its noise (±0.015° vs a 0.03° SD). Earth's field is invisible next to the hinge magnet.
- The SMC lid switch (key `MSLD`, ui8, 0 = open) is a 1-bit reading.

## Sensor hub layout
- Sensors sit on the AOP (always-on processor): `aop` → `AOPEndpointN` → `AppleSPU` → `AppleSPUHIDInterface` → `AppleSPUHIDDevice`.
- Endpoints: `accel` 2, `gyro` 3, `als` 4, `las` (lid angle) 5, `wakehint` 6, `devmotion6` 10, `cma` 11, `als-temp` 12.
- Each sensor is a vendor HID device (VID 0x05AC, PID 0x8104, Transport "SPU").
- Match on Transport "SPU" as well as the usage. The internal keyboard/trackpad (SPI) also has a page 0xFF00 / usage 3 interface.

## IMU: Bosch BMI282 (accel + gyro), the one this project uses
- Gyro: page 0xFF00, usage 9. Accel: page 0xFF00, usage 3. Supported rates are 50/100/200/400/800 Hz.
- Streaming is off by default. To start it, set `SensorPropertyReportingState` = 1, `SensorPropertyPowerState` = 1 and `ReportInterval` (µs) on the sensor's `AppleSPUHIDDriver`.
- To stop it, set `ReportInterval` to 0. Setting the state properties to 0 alone leaves it streaming.
- These are global driver settings: they persist after your process exits, and they're shared by every process.
- Asked for 100 Hz, the accel usually stays silent. At 200 Hz it streams reliably, so `imu.c` uses 200 Hz for the accel and 100 Hz for the gyro.
- Report format, 22 bytes, little-endian: bytes 0–3 u32 sample counter (+8 per sample), 4–5 always zero, 6–17 i32 x/y/z, 18–21 i32 temperature.
- All values are fixed point × 65536. The gyro is in °/s, with a step of 0.061°/s (the ±2000°/s range). The accel is in g. Temperature is in °C (about 42–46°C).
- Lying flat on a desk, the accel reads about (0.015, -0.007, -1.01) g.
- Resting gyro bias is about x -0.32, y +0.47, z -0.28 °/s, with about 0.07–0.09°/s noise. Uncorrected, the z bias would drift about 17°/min.
- With the bias removed, z drift was under 0.5° over 6.5 minutes at rest.
- The reports carry no device timestamp, so take the host time on arrival and use the counter to spot gaps.

## Other hub sensors (not used)
- `als`, ambient light ("Redbird", usage 4): 122-byte reports at about 10 Hz. They contain 5 u32 channels at offset 20 and a float at offset 40 that looks like lux. The lux reading is unverified.
- `als-temp`, TI TMP108 (usage 5): 14-byte reports at about 94 Hz. Bytes 2–5 are °C × 65536 (about 27°C).
- `las`, MagAlpha MA781 (page 0x20, usage 0x8A): polled with GetReport.
  - Report 1 is the angle in degrees (9 bits). Report 7 is the angle in 0.01° (u16).
  - Reports 2, 3 and 4 are hardware revision, serial and status. Report 6 is a writable output. Reports 5 and 8 are unknown.
  - The logger is on the `lid-angle` branch.
- `cma` (page 0xFF0C, usage 1): occasional 5-byte events, undecoded.
- `devmotion6` (page 0xFF0C, usage 5, 100 bytes): never streamed with the property method, even with the accel and gyro running.

## SMC
- There are about 2050 keys, readable through the AppleSMC user client (selector 2).
- Useful keys: `MSLD` lid switch, `F0Ac`/`F1Ac` fan RPM (float), plus many temperature, voltage and current keys.

## Instrument art
- The art in `assets/` is original. `make_assets.py` draws it as one PNG layer per moving part, and `assets.json` holds the geometry.
- An earlier version used X-Plane 12's Cessna 172 textures. It was dropped because that art is Laminar Research's and can't be redistributed.
- Useful if revisiting it: those textures have no alpha channel, so their OBJ UV triangles give each part's cut-out.

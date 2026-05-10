# Arduino Porting Guide (C Firmware from az1m0v Python)

This guide identifies which parts of the current repository can run on Arduino-class MCUs and provides C firmware artifacts for manual flashing.

## 1) What was ported now

Ported from Python control flow in `core/vehicle_controller.py`:

- drive mode multipliers and effective limit calculation
- throttle/brake shaping with clamping
- simplified speed integration
- regenerative braking current request
- communication mode selection for CAN/LoRaWAN fallback

Implemented files:

- `firmware/arduino/ev_drive_core.h`
- `firmware/arduino/ev_drive_core.c`
- `firmware/arduino/bench_mvp_controller.ino`

## 2) Why these are suitable for Arduino

These routines are:

- deterministic
- lightweight (no heavy dynamic allocation)
- independent from Linux networking/UI stack
- suitable for fixed-frequency control loops

## 3) What should stay on Raspberry Pi

- dashboard + web APIs
- rich diagnostics/log persistence
- orchestration across all subsystems
- AI/autopilot experiments and non-real-time logic
- deployment tooling and integration scripts

## 4) Flash workflow (manual)

For the full, detailed flash manual, use:

- [Arduino Flashing Manual](ARDUINO_FLASHING_MANUAL.md)

1. Open `firmware/arduino/bench_mvp_controller.ino` in Arduino IDE.
2. Keep `ev_drive_core.h` and `ev_drive_core.c` in the same sketch folder (or add as local library).
3. Select your board and USB port.
4. Build and upload.
5. Open serial monitor at `115200` baud and verify one-line JSON outputs.

The sketch supports manual commands over serial:

- `THROTTLE:35`
- `BRAKE:20`

These commands influence emitted JSON values used by Raspberry Pi `bench_mvp` bridge.

## 5) Suggested next firmware ports

Next Python modules to split toward MCU firmware:

- sensor pre-processing from `sensors/temperature.py` (filtering + thresholds)
- local safety latching primitives from `core/safety_system.py`
- compact CAN command encoder/decoder from `communication/can_bus.py`

## 6) Do you need more Arduinos?

Recommendation by stage:

- bench MVP: 1 Arduino is enough
- real-size prototype (without trolley): 2 MCUs recommended
- full-size prototype: 3+ MCU/ECU nodes recommended

Typical split:

- MCU-A: powertrain edge control
- MCU-B: body/auxiliary I/O
- MCU-C: safety/watchdog supervisor (optional but recommended for full-size stage)

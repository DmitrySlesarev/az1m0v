# Arduino Flashing Manual (Bench MVP Firmware)

This is a practical step-by-step manual to flash the Arduino firmware used by the az1m0v bench MVP bridge.

Firmware files in this repository:

- `firmware/arduino/bench_mvp_controller.ino`
- `firmware/arduino/ev_drive_core.c`
- `firmware/arduino/ev_drive_core.h`

---

## 1) Before you start

1. Ensure the Arduino is disconnected from any high-voltage bench section.
2. Use a known-good USB data cable (not charge-only).
3. Close any process that may already hold the serial port:
   - Arduino Serial Monitor
   - `screen`, `minicom`, `picocom`
   - Python scripts reading `/dev/ttyACM*` or `/dev/ttyUSB*`

---

## 2) Prepare sketch folder (required)

Arduino IDE expects the `.ino` file to be in a folder with matching name.

Create and copy files:

```bash
mkdir -p ~/Arduino/bench_mvp_controller
cp /workspace/firmware/arduino/bench_mvp_controller.ino ~/Arduino/bench_mvp_controller/
cp /workspace/firmware/arduino/ev_drive_core.c ~/Arduino/bench_mvp_controller/
cp /workspace/firmware/arduino/ev_drive_core.h ~/Arduino/bench_mvp_controller/
```

If your workspace path is different, replace `/workspace` accordingly.

---

## 3) Flash with Arduino IDE 2.x

1. Open **Arduino IDE**.
2. Open sketch:
   - `File -> Open...`
   - Select `~/Arduino/bench_mvp_controller/bench_mvp_controller.ino`
3. Select board:
   - `Tools -> Board -> <your board>`
4. Select port:
   - `Tools -> Port -> /dev/ttyACM0` (example)
5. For Arduino Nano (if needed):
   - `Tools -> Processor -> ATmega328P (Old Bootloader)`
6. Click **Verify** (checkmark).
7. Click **Upload** (arrow).
8. Wait for `Done uploading`.

---

## 4) Validate serial output

1. Open **Serial Monitor**.
2. Set baud to **115200**.
3. Set line ending to **Newline**.
4. Confirm periodic JSON lines appear (battery/motor/vehicle messages).

Manual control commands:

- `THROTTLE:35`
- `BRAKE:20`

These commands change generated status values and are used to test Raspberry Pi ingestion.

---

## 5) Connect with Raspberry Pi bench MVP bridge

On Raspberry Pi, configure `config/config.json`:

```json
{
  "bench_mvp": {
    "enabled": true,
    "simulation_mode": false,
    "arduino_port": "/dev/ttyACM0",
    "rak_port": "/dev/ttyACM1",
    "prefer_lorawan": true
  }
}
```

Then run the stack:

```bash
poetry run python main.py
```

In dashboard, verify the **Dual-Link Network** card:

- Operating mode (`dual_link`, `can_primary`, `can_only_safe`)
- Arduino link online/offline
- RAK4630 link online/offline
- CAN backbone online/offline

---

## 6) Troubleshooting

## 6.1 Port permission denied

```bash
sudo usermod -aG dialout "$USER"
```

Then log out/in (or reboot) and retry.

## 6.2 Port busy

Find process:

```bash
sudo lsof /dev/ttyACM0
```

Stop conflicting process and upload again.

## 6.3 Upload timeout / sync errors

- Replug USB cable
- Try another USB cable/port
- Re-select board/port in IDE
- For Nano, try old bootloader option

## 6.4 Build error for `ev_drive_core.h`

Ensure `.ino`, `.c`, and `.h` are all in the same sketch folder.

## 6.5 No serial output

- Confirm baud is 115200
- Confirm line ending is Newline
- Press board reset once after upload

---

## 7) Optional CLI flashing workflow (advanced)

If you prefer terminal-only flashing, use `arduino-cli`:

```bash
arduino-cli board list
arduino-cli compile --fqbn <fqbn> ~/Arduino/bench_mvp_controller
arduino-cli upload -p /dev/ttyACM0 --fqbn <fqbn> ~/Arduino/bench_mvp_controller
```

Replace `<fqbn>` with your board FQBN (for example `arduino:avr:uno`).

# Arduino as CAN peripheral (az1m0v)

## Role

The Raspberry Pi runs az1m0v and **SocketCAN** (`can0`). An **Arduino Uno** (or compatible) with a **CAN transceiver shield** (e.g. MCP2515 + MCP2551) is a practical **I/O coprocessor**:

- Read **digital inputs** (switches, contactors feedback).
- Read **analog inputs** (NTC thermistors, 0–5 V signals) with stable ADC.
- Drive **digital outputs** (relays, LEDs, enable lines) and one **PWM** channel (e.g. fan).

USB (`CH340`) is only for **flashing** the Arduino; on the vehicle, the Arduino participates **only on CAN** alongside the Pi.

## CAN identifiers (default)

| Direction        | ID (hex) | Name                          |
|------------------|----------|-------------------------------|
| Arduino → bus    | `310`    | `ARDUINO_PERIPHERAL_STATUS`   |
| Pi → Arduino     | `311`    | `ARDUINO_PERIPHERAL_COMMAND`  |

Override in `config.json` → `arduino_can.status_can_id` / `command_can_id` (decimal or hex in JSON as integer).

## Frame formats

See `communication/arduino_peripheral_can.py` for the authoritative layout.

### Status `0x310` (8 bytes)

- `0xA1` magic
- `digital_inputs` uint8 bitmask
- three `int16` analog values, **little-endian**  
  - With `analog_unit: "centi_c"` (default), value is °C × 100 (e.g. `2534` → 25.34 °C).

### Command `0x311` (8 bytes)

- `0xB1` magic
- `digital_outputs` uint8 bitmask
- `pwm_aux` uint8 (0–255)
- `flags` uint8 — **bit0 = listen-only**: when set, firmware should **not** apply outputs (Pi is observing only).

## Configuration (`config.json`)

```json
"arduino_can": {
  "enabled": true,
  "status_can_id": 784,
  "command_can_id": 785,
  "analog_unit": "centi_c",
  "listen_only_default": true,
  "resend_command_interval_s": 1.0,
  "inject_temperatures": [
    { "channel": 0, "sensor_id": "coolant_inlet" }
  ]
}
```

- `inject_temperatures`: maps analog channel index (0–2) to an existing `TemperatureSensorManager` sensor id so BMS/safety see those readings.

## Firmware

Example sketch: `firmware/arduino_az1m0v_peripheral.ino` (requires **MCP_CAN** or equivalent library; adjust CS/INT pins for your shield).

## Web UI

With `arduino_can.enabled` and CAN up, the dashboard shows an **Arduino peripheral** card: listen-only toggle, D0–D3 on/off, PWM, and a manual “Send CAN command” action.

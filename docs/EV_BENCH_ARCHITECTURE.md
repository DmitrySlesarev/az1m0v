# EV Bench Prototype Architecture (Raspberry Pi + Arduino + RAK4630)

This document defines a practical architecture for evolving the current bench setup into a real EV prototype in incremental steps.

## 1) Target principles

- Keep **CAN bus** as the deterministic legacy backbone (design for up to 127 logical nodes).
- Add **LoRaWAN (RAK4630)** as a parallel "neural" channel for supervisory telemetry/commands.
- Use **automatic fallback**: if LoRaWAN quality drops, continue all safety-critical operation over CAN.
- Keep control logic modular so components can move from Raspberry Pi Python to MCU firmware over time.

## 2) MVP bench architecture (current hardware only)

Current hardware:

- Raspberry Pi (main controller)
- RS485 CAN HAT on Raspberry Pi GPIO/SPI
- MCP2515 CAN node over twisted pair
- Arduino over USB 2.0
- RAK4630 WisBlock over USB 2.0

### 2.1 Logical roles

- **Raspberry Pi (orchestrator)**
  - Runs `az1m0v` core logic, safety checks, dashboard, and integration bridge.
  - Maintains global state and sends/receives CAN frames.
  - Ingests USB serial streams from Arduino and RAK4630.

- **Arduino (fast edge I/O worker)**
  - Handles deterministic sensor/actuator loops that do not require Linux.
  - Reports compact status frames to Raspberry Pi.
  - Executes low-latency local control primitives (mapped from Python to C firmware).

- **RAK4630 (LoRaWAN side-channel)**
  - Sends periodic telemetry uplinks (fleet/state snapshots).
  - Receives downlink supervisory commands (non-safety-critical).
  - Provides link health metrics used by failover policy.

- **CAN network (legacy robust backbone)**
  - Carries real-time operational state between ECUs.
  - Guarantees continuity when LoRaWAN is degraded.

### 2.2 Data path and fallback policy

1. Raspberry Pi computes state and publishes on CAN.
2. Raspberry Pi forwards selected summaries to RAK4630 for LoRaWAN uplink.
3. If LoRaWAN heartbeat or quality is below threshold, system state switches to `CAN_PRIMARY`.
4. When LoRaWAN health is restored and stable for a hold interval, system can return to `DUAL_LINK`.

Recommended link states:

- `DUAL_LINK` (normal): CAN + LoRaWAN available.
- `CAN_PRIMARY` (degraded): CAN only for critical operation, LoRaWAN optional.
- `CAN_ONLY_SAFE` (fault): force-safe profile and CAN-only operation.

### 2.3 Bench wiring summary

- Raspberry Pi GPIO/SPI -> RS485 CAN HAT -> twisted pair -> MCP2515 CAN segment.
- Raspberry Pi USB -> Arduino (CDC serial).
- Raspberry Pi USB -> RAK4630 (CDC serial).
- Common ground reference across low-voltage bench devices.

## 3) Extension path to real EV prototype

## 3.1 Stage A: Real-size prototype (without trolley)

- Add real traction inverter/motor interface, contactors, and real BMS.
- Keep Raspberry Pi as high-level supervisor.
- Move hard real-time loops to MCU firmware (Arduino-class or STM32).
- Keep CAN as mandatory transport for safety-relevant frames.

## 3.2 Stage B: Full-size prototype

- Introduce distributed ECU topology:
  - Safety ECU
  - Powertrain ECU
  - Body/auxiliary ECU
  - Telematics ECU
- Add gateway segmentation (powertrain CAN vs body CAN) if bus load rises.
- Add redundant power rails and watchdog reset strategy.

## 4) Control partitioning guidance

Keep on Raspberry Pi:

- Fleet telemetry orchestration
- Route-level AI/autopilot experiments
- Dashboard and diagnostics UI
- Non-deterministic analytics

Move to MCU firmware:

- Fast actuator command shaping
- Sensor filtering and debounce
- Emergency stop logic and watchdog-triggered fallbacks
- Minimal limp-home control profile

## 5) Validation milestones

Bench MVP exit criteria:

- Raspberry Pi receives Arduino + RAK serial traffic reliably.
- CAN status frames are generated continuously.
- Link-state transitions (`DUAL_LINK` <-> `CAN_PRIMARY`) are observable in logs/UI.
- Manual loss of LoRaWAN path does not break CAN control loop.

Real-size (no trolley) exit criteria:

- Stable operation under representative motor load and thermal cycle.
- Safety limits trigger deterministic fallback behavior.

Full-size exit criteria:

- End-to-end fault handling validated for communication and power faults.
- Multi-ECU CAN architecture validated under peak traffic.

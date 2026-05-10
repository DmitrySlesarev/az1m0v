# EV Prototype Roadmap and Shopping List

This document converts the architecture into phased implementation steps and purchasing priorities.

## 1) Step-by-step roadmap

## Phase 0 - Bench lab prototype (current setup)

Goal: functional MVP with Raspberry Pi + CAN + Arduino + RAK4630.

Deliverables:

- Bench communication bridge (USB serial + CAN publication)
- Dual-link policy (LoRaWAN preferred when healthy, CAN fallback otherwise)
- Updated dashboard with communication/link-state visibility
- Initial Arduino firmware for deterministic edge tasks

## Phase 1 - Real-size prototype (without trolley)

Goal: move from pure bench to full-scale subsystems without full vehicle integration.

Deliverables:

- Real motor controller and battery interfaces
- Contactor precharge/safety chain
- Deterministic control moved to MCU firmware
- Hardware-in-the-loop fault injections

## Phase 2 - Full-size prototype

Goal: integrate drivetrain, charging, safety, and telemetry into complete EV prototype.

Deliverables:

- Multi-ECU CAN topology
- Safety-compliant fault handling paths
- LoRaWAN remote diagnostics with strict CAN fallback
- Production-like wiring harness and enclosure strategy

---

## 2) Shopping list by iteration

## 2.1 Buy now (MVP on current bench)

| Item | Qty | Why now |
|---|---:|---|
| USB isolator (industrial grade) | 2 | Protect Raspberry Pi USB when connecting Arduino/RAK in noisy bench setups |
| CAN termination resistors (120 Ohm) | 4-8 | Ensure proper bus termination and quick replacements |
| Twisted-pair shielded cable (automotive grade) | 5-10 m | Stable CAN physical layer |
| DIN-rail or bench power supply 12V/5V | 1 | Clean and stable bench power distribution |
| Logic analyzer with CAN decode | 1 | Speeds up CAN timing/debug validation |
| Extra Arduino-compatible board | 1 | Spare and A/B firmware testing |
| RAK4630 debug/programming adapter | 1 | Reliable LoRa module development/debug |

## 2.2 Buy for next stage (real-size, no trolley)

| Item | Qty | Why in this phase |
|---|---:|---|
| STM32F407 development board (or automotive-grade STM32) | 1-2 | Deterministic real-time safety/control domain |
| Isolated CAN transceivers | 2-4 | Better EMC and fault containment |
| Automotive contactors + precharge resistor chain | 1 set | HV-safe switching logic validation |
| BMS with CAN output | 1 | Real battery integration path |
| Inverter/motor bench interface hardware | 1 set | Real powertrain integration without full vehicle |
| Emergency stop circuit hardware | 1 set | Hardwired safety layer independent from Linux |

## 2.3 Buy for full-size prototype

| Item | Qty | Why in this phase |
|---|---:|---|
| Additional ECU boards (Arduino/STM32 mix) | 2-4 | Separate powertrain, body, and safety domains |
| Automotive-grade wiring harness materials | as required | Reliability and maintainability at full scale |
| Sealed enclosures (IP-rated) | as required | Environmental protection |
| HV safety gear and isolation monitor | 1 set | Full-prototype safety validation |
| Redundant DC/DC converters and fused distribution | 1 set | Power redundancy and serviceability |

---

## 3) Do you need more Arduinos?

Short answer:

- **Bench MVP:** one Arduino is usually enough.
- **Real-size prototype:** usually two MCU nodes are better.
- **Full-size prototype:** three or more MCU/ECU nodes become practical.

Suggested split:

- MCU #1: fast actuator/sensor loops (powertrain edge logic)
- MCU #2: body/aux I/O and backup control channel
- MCU #3 (optional): dedicated safety monitor / watchdog supervisor

---

## 4) LoRaWAN-over-CAN operating model

CAN remains mandatory for:

- safety-critical control and interlock states
- deterministic local control under all network conditions

LoRaWAN adds:

- remote telemetry
- non-critical supervisory commands
- optional over-the-air maintenance workflows

Fallback behavior:

- If LoRaWAN heartbeat/quality degrades: switch to CAN-only operational mode.
- If LoRaWAN recovers and remains stable: return to dual-link mode.

This approach keeps backwards compatibility and robustness while allowing higher-level telemetry and remote operations.

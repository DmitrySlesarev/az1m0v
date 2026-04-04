"""CAN framing for an Arduino (or similar) peripheral coprocessor on the EV bus.

The Raspberry Pi runs az1m0v; the Arduino + MCP2515 (or equivalent) handles
low-speed digital I/O and ADC, publishing readings and accepting output/PWM.

Frame conventions (little-endian, 8 data bytes):

**0x310 — STATUS (Arduino → bus)**  
- byte0: magic 0xA1
- byte1: digital_inputs (bitmask, 8 lines)
- bytes2–3: analog0 as int16 (see unit)
- bytes4–5: analog1 as int16
- bytes6–7: analog2 as int16

Default unit for analog int16 is centi-degrees Celsius (e.g. 2550 → 25.50 °C).
Configure ``unit: "raw"`` in inject_temperatures to treat values as raw ADC.

**0x311 — COMMAND (Pi → Arduino)**  
- byte0: magic 0xB1
- byte1: digital_outputs (bitmask)
- byte2: pwm_aux (0–255)
- byte3: flags — bit0: listen_only on Arduino side (optional); reserved
- bytes4–7: reserved (0)
"""

from __future__ import annotations

import struct
import time
from typing import Any, Dict, List, Optional, Tuple

STATUS_MAGIC = 0xA1
COMMAND_MAGIC = 0xB1


def parse_arduino_status_frame(
    data: bytes,
    *,
    analog_unit: str = "centi_c",
) -> Optional[Dict[str, Any]]:
    """Parse 0x310 peripheral status payload."""
    if len(data) < 8 or data[0] != STATUS_MAGIC:
        return None
    digital_in = data[1]
    a0, a1, a2 = struct.unpack_from("<hhh", data, 2)
    analog_raw: List[int] = [a0, a1, a2]
    analog_c: List[Optional[float]] = []
    for raw in analog_raw:
        if analog_unit == "centi_c":
            analog_c.append(raw / 100.0)
        elif analog_unit == "raw":
            analog_c.append(float(raw))
        else:
            analog_c.append(raw / 100.0)
    return {
        "magic": STATUS_MAGIC,
        "digital_inputs": digital_in,
        "analog_raw": analog_raw,
        "analog_c": analog_c,
        "timestamp": time.time(),
    }


def build_arduino_command_frame(
    digital_outputs: int,
    pwm_aux: int = 0,
    flags: int = 0,
) -> bytes:
    """Build 8-byte payload for 0x311."""
    digital_outputs &= 0xFF
    pwm_aux = max(0, min(255, int(pwm_aux)))
    flags &= 0xFF
    return struct.pack(
        "<BBBB4s",
        COMMAND_MAGIC,
        digital_outputs,
        pwm_aux,
        flags,
        b"\x00\x00\x00\x00",
    )


def split_digital_mask(mask: int) -> Tuple[List[int], List[int]]:
    """Return (indices_of_set_bits, indices_of_clear_bits) for bits 0..7."""
    on = [b for b in range(8) if mask & (1 << b)]
    off = [b for b in range(8) if not (mask & (1 << b))]
    return on, off

"""UART/COM endpoint payloads for an Arduino-style peripheral controller.

The edge switch forwards EV application frames to this endpoint over a serial
stream. Payloads remain compact so they are easy to parse on an Arduino, but
the framing around them is handled by :class:`communication.ip_uart_transport.UARTFrameCodec`.
"""

from __future__ import annotations

import struct
import time
from typing import Any, Dict, List, Optional, Tuple

STATUS_MAGIC = 0xA1
COMMAND_MAGIC = 0xB1


def parse_arduino_status_payload(
    data: bytes,
    *,
    analog_unit: str = "centi_c",
) -> Optional[Dict[str, Any]]:
    """Parse the compact peripheral status payload from a UART endpoint."""

    if len(data) < 8 or data[0] != STATUS_MAGIC:
        return None
    digital_in = data[1]
    a0, a1, a2 = struct.unpack_from("<hhh", data, 2)
    analog_raw: List[int] = [a0, a1, a2]
    analog_c: List[Optional[float]] = []
    for raw in analog_raw:
        if analog_unit == "raw":
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


def build_arduino_command_payload(
    digital_outputs: int,
    pwm_aux: int = 0,
    flags: int = 0,
) -> bytes:
    """Build the compact command payload consumed by the Arduino endpoint."""

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


# Backwards-compatible names used by existing tests and imports.
parse_arduino_status_frame = parse_arduino_status_payload
build_arduino_command_frame = build_arduino_command_payload

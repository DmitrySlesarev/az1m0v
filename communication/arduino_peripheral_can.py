"""Compatibility imports for the Arduino UART peripheral payload helpers."""

from communication.uart_peripheral import (
    COMMAND_MAGIC,
    STATUS_MAGIC,
    build_arduino_command_frame,
    build_arduino_command_payload,
    parse_arduino_status_frame,
    parse_arduino_status_payload,
    split_digital_mask,
)

__all__ = [
    "COMMAND_MAGIC",
    "STATUS_MAGIC",
    "build_arduino_command_frame",
    "build_arduino_command_payload",
    "parse_arduino_status_frame",
    "parse_arduino_status_payload",
    "split_digital_mask",
]

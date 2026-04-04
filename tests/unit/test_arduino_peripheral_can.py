"""Tests for Arduino peripheral CAN framing."""

import struct

from communication.arduino_peripheral_can import (
    STATUS_MAGIC,
    COMMAND_MAGIC,
    parse_arduino_status_frame,
    build_arduino_command_frame,
)


def test_parse_status_centi_c():
    payload = struct.pack("<BBhhh", STATUS_MAGIC, 0b101, 2500, -50, 0)
    assert len(payload) == 8
    d = parse_arduino_status_frame(payload, analog_unit="centi_c")
    assert d is not None
    assert d["digital_inputs"] == 0b101
    assert d["analog_c"][0] == 25.0
    assert d["analog_c"][1] == -0.5
    assert d["analog_c"][2] == 0.0


def test_parse_status_wrong_magic():
    payload = bytes([0x00, 0, 0, 0, 0, 0, 0, 0])
    assert parse_arduino_status_frame(payload) is None


def test_build_command():
    b = build_arduino_command_frame(digital_outputs=0x0F, pwm_aux=128, flags=1)
    assert len(b) == 8
    assert b[0] == COMMAND_MAGIC
    assert b[1] == 0x0F
    assert b[2] == 128
    assert b[3] == 1
    assert b[4:8] == b"\x00\x00\x00\x00"

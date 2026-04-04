"""Tests for ArduinoPeripheralBridge."""

from unittest.mock import Mock

from communication.can_bus import CANBusInterface, EVCANProtocol
from communication.arduino_can_bridge import ArduinoPeripheralBridge
from communication.arduino_peripheral_can import STATUS_MAGIC, COMMAND_MAGIC
import struct


def test_bridge_registers_handler_and_parses_status():
    can_bus = Mock(spec=CANBusInterface)
    can_bus.register_message_handler = Mock()
    proto = EVCANProtocol(can_bus)

    tm = Mock()
    tm.sensors = {"coolant_inlet": Mock()}

    cfg = {
        "enabled": True,
        "status_can_id": 0x310,
        "command_can_id": 0x311,
        "inject_temperatures": [{"channel": 0, "sensor_id": "coolant_inlet"}],
    }
    bridge = ArduinoPeripheralBridge(can_bus, proto, cfg, temperature_manager=tm)

    assert can_bus.register_message_handler.called
    handler = can_bus.register_message_handler.call_args[0][1]

    payload = struct.pack("<BBhhh", STATUS_MAGIC, 3, 2000, 0, 0)
    frame = Mock()
    frame.can_id = 0x310
    frame.data = payload

    handler(frame)

    tm.sensors["coolant_inlet"].set_temperature.assert_called_once()
    args = tm.sensors["coolant_inlet"].set_temperature.call_args[0][0]
    assert abs(args - 20.0) < 1e-6


def test_send_command_builds_frame():
    can_bus = Mock(spec=CANBusInterface)
    can_bus.send_frame = Mock(return_value=True)
    can_bus.register_message_handler = Mock()
    proto = EVCANProtocol(can_bus)

    bridge = ArduinoPeripheralBridge(
        can_bus, proto, {"status_can_id": 0x310, "command_can_id": 0x311}, temperature_manager=None
    )
    bridge.set_digital_bit(0, True)
    bridge.set_listen_only(False)
    ok = bridge.send_command()
    assert ok is True
    assert can_bus.send_frame.called
    sent = can_bus.send_frame.call_args[0][0]
    assert sent.can_id == 0x311
    assert sent.data[0] == COMMAND_MAGIC
    assert sent.data[1] == 0x01
    assert sent.data[3] == 0

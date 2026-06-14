"""Unit tests for the self-written IP/UART vehicle transport."""

import struct

import pytest

from communication.ip_uart_transport import (
    EVTCPIPProtocol,
    EndpointSwitch,
    ITFrame,
    PacketCodec,
    TCPIPTransportInterface,
    UARTEndpoint,
    UARTFrameCodec,
)


class FakeSerial:
    def __init__(self):
        self.writes = []
        self.closed = False

    def write(self, data: bytes) -> int:
        self.writes.append(data)
        return len(data)

    def close(self) -> None:
        self.closed = True


def test_packet_codec_round_trip_and_crc_validation():
    frame = ITFrame(
        service_id=0x210,
        payload=struct.pack("<f", 1500.0),
        source="raspberry-pi",
        destination="engine",
        sequence=42,
        metadata={"command": "rpm"},
    )

    packet = PacketCodec.encode(frame)
    decoded = PacketCodec.decode(packet)

    assert decoded.service_id == frame.service_id
    assert decoded.payload == frame.payload
    assert decoded.source == "raspberry-pi"
    assert decoded.destination == "engine"
    assert decoded.metadata == {"command": "rpm"}

    corrupted = bytearray(packet)
    corrupted[-1] ^= 0x01
    with pytest.raises(ValueError, match="CRC"):
        PacketCodec.decode(bytes(corrupted))


def test_uart_frame_codec_handles_stream_boundaries():
    first = ITFrame(service_id=0x183, payload=b"battery", destination="battery")
    second = ITFrame(service_id=0x203, payload=b"engine", destination="engine")

    stream = UARTFrameCodec.encode(first) + UARTFrameCodec.encode(second)
    frames, remainder = UARTFrameCodec.decode_stream(stream)

    assert remainder == b""
    assert [frame.service_id for frame in frames] == [0x183, 0x203]
    assert [frame.payload for frame in frames] == [b"battery", b"engine"]

    partial = UARTFrameCodec.encode(first)[:-3]
    frames, remainder = UARTFrameCodec.decode_stream(partial)
    assert frames == []
    assert remainder


def test_virtual_transport_dispatches_registered_handlers():
    transport = TCPIPTransportInterface(mode="virtual")
    received = []
    transport.register_message_handler(0x203, received.append)

    assert transport.connect()
    frame = ITFrame(service_id=0x203, payload=b"motor", destination="engine")
    packet = PacketCodec.encode(frame)

    decoded = transport.process_incoming_packet(packet)

    assert decoded.payload == b"motor"
    assert received == [decoded]
    assert transport.get_statistics()["frames_received"] == 1


def test_endpoint_switch_converts_network_packet_to_uart_stream():
    fake_serial = FakeSerial()
    endpoint = UARTEndpoint("engine", "/dev/ttyUSB0", serial_instance=fake_serial)
    switch = EndpointSwitch({"engine": endpoint})
    frame = ITFrame(service_id=0x210, payload=struct.pack("<f", 3200.0), destination="engine")

    assert switch.route_network_packet(PacketCodec.encode(frame)) is True
    assert switch.get_statistics()["uart_frames_sent"] == 1
    assert len(fake_serial.writes) == 1

    decoded, remainder = UARTFrameCodec.decode_stream(fake_serial.writes[0])
    assert remainder == b""
    assert decoded[0].service_id == 0x210
    assert struct.unpack("<f", decoded[0].payload)[0] == pytest.approx(3200.0)


def test_ev_protocol_sends_full_length_application_payload():
    transport = TCPIPTransportInterface(mode="virtual")
    transport.connect()
    protocol = EVTCPIPProtocol(transport)

    assert protocol.send_vesc_status(1000.0, 10.0, 48.0, 31.5)
    assert len(transport.outbox) == 1

    frame = PacketCodec.decode(transport.outbox[0])
    assert frame.service_id == protocol.SERVICE_IDS["VESC_STATUS"]
    assert frame.destination == "engine"
    assert len(frame.payload) == 16
    assert protocol.parse_vesc_status(frame)["voltage"] == pytest.approx(48.0)

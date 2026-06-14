"""Self-written IP-to-UART transport for EV subsystems.

The Raspberry Pi side speaks application frames over the TCP/IP stack (UDP is
the preferred mode). At the physical edge, an :class:`EndpointSwitch` receives
those packets and forwards the same application frame through a UART/COM-safe
byte stream to engine, battery, charger, or peripheral controllers.
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
import socket
import struct
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple


MAX_UDP_PAYLOAD = 1400
PACKET_MAGIC = b"AZIP"
PACKET_VERSION = 1
_PACKET_HEADER = struct.Struct("!4sBI")
_CRC = struct.Struct("!I")

SLIP_END = 0xC0
SLIP_ESC = 0xDB
SLIP_ESC_END = 0xDC
SLIP_ESC_ESC = 0xDD


class TransportMode(Enum):
    """Supported host-side transport modes."""

    UDP = "udp"
    TCP = "tcp"
    VIRTUAL = "virtual"


class FrameType(Enum):
    """Application frame types used above IP and UART."""

    DATA = "data"
    CONTROL = "control"
    ACK = "ack"
    ERROR = "error"

    # Compatibility values for callers that still import the old enum.
    REMOTE = "remote"
    OVERLOAD = "overload"


@dataclass
class ITFrame:
    """Application frame independent of CAN addressing or 8-byte data limits."""

    service_id: int
    payload: bytes
    source: str = "raspberry-pi"
    destination: str = "edge-switch"
    timestamp: float = field(default_factory=time.time)
    frame_type: FrameType = FrameType.DATA
    qos: int = 0
    sequence: int = 0
    ttl: int = 16
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.service_id = int(self.service_id)
        if not 0 <= self.service_id <= 0xFFFF:
            raise ValueError("service_id must fit in an unsigned 16-bit service namespace")
        if not isinstance(self.payload, (bytes, bytearray)):
            raise TypeError("payload must be bytes")
        self.payload = bytes(self.payload)
        if len(self.payload) > MAX_UDP_PAYLOAD:
            raise ValueError(f"payload exceeds UDP-safe limit of {MAX_UDP_PAYLOAD} bytes")
        self.source = self._validate_endpoint(self.source, "source")
        self.destination = self._validate_endpoint(self.destination, "destination")
        if not isinstance(self.frame_type, FrameType):
            self.frame_type = FrameType(str(self.frame_type))
        self.qos = max(0, min(255, int(self.qos)))
        self.sequence = int(self.sequence) & 0xFFFFFFFF
        self.ttl = max(0, min(255, int(self.ttl)))

    @staticmethod
    def _validate_endpoint(value: str, field_name: str) -> str:
        encoded = str(value).encode("utf-8")
        if not encoded or len(encoded) > 64:
            raise ValueError(f"{field_name} must be 1..64 UTF-8 bytes")
        return str(value)

    @property
    def data(self) -> bytes:
        """Compatibility property for existing dashboard/protocol handlers."""

        return self.payload

    @property
    def can_id(self) -> int:
        """Compatibility alias while the codebase migrates to service_id."""

        return self.service_id

    @property
    def dlc(self) -> int:
        """Payload length; no CAN 8-byte ceiling is applied."""

        return len(self.payload)


@dataclass
class ITMessage:
    """Structured EV application message before serialization."""

    service_id: int
    name: str
    description: str
    data: Dict[str, Any]
    timestamp: float
    source: str
    destination: str = "edge-switch"
    priority: int = 0

    @property
    def message_id(self) -> int:
        """Compatibility alias for old CAN message naming."""

        return self.service_id


class PacketCodec:
    """Encode/decode application frames for UDP/TCP packets."""

    @staticmethod
    def encode(frame: ITFrame) -> bytes:
        body = {
            "version": PACKET_VERSION,
            "service_id": frame.service_id,
            "source": frame.source,
            "destination": frame.destination,
            "timestamp": frame.timestamp,
            "frame_type": frame.frame_type.value,
            "qos": frame.qos,
            "sequence": frame.sequence,
            "ttl": frame.ttl,
            "metadata": frame.metadata,
            "payload_b64": base64.b64encode(frame.payload).decode("ascii"),
        }
        body_bytes = json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")
        crc = binascii.crc32(body_bytes) & 0xFFFFFFFF
        return _PACKET_HEADER.pack(PACKET_MAGIC, PACKET_VERSION, len(body_bytes)) + body_bytes + _CRC.pack(crc)

    @staticmethod
    def decode(packet: bytes) -> ITFrame:
        if len(packet) < _PACKET_HEADER.size + _CRC.size:
            raise ValueError("packet is too short")
        magic, version, body_len = _PACKET_HEADER.unpack_from(packet, 0)
        if magic != PACKET_MAGIC:
            raise ValueError("invalid packet magic")
        if version != PACKET_VERSION:
            raise ValueError(f"unsupported packet version {version}")
        body_start = _PACKET_HEADER.size
        body_end = body_start + body_len
        if len(packet) != body_end + _CRC.size:
            raise ValueError("packet length does not match header")
        body_bytes = packet[body_start:body_end]
        expected_crc = _CRC.unpack_from(packet, body_end)[0]
        actual_crc = binascii.crc32(body_bytes) & 0xFFFFFFFF
        if actual_crc != expected_crc:
            raise ValueError("packet CRC mismatch")
        body = json.loads(body_bytes.decode("utf-8"))
        payload = base64.b64decode(body["payload_b64"].encode("ascii"))
        return ITFrame(
            service_id=int(body["service_id"]),
            payload=payload,
            source=str(body["source"]),
            destination=str(body["destination"]),
            timestamp=float(body["timestamp"]),
            frame_type=FrameType(body["frame_type"]),
            qos=int(body.get("qos", 0)),
            sequence=int(body.get("sequence", 0)),
            ttl=int(body.get("ttl", 16)),
            metadata=dict(body.get("metadata") or {}),
        )


class UARTFrameCodec:
    """SLIP framing for moving IP application frames over UART/COM streams."""

    @staticmethod
    def encode(frame: ITFrame) -> bytes:
        packet = PacketCodec.encode(frame)
        escaped = bytearray([SLIP_END])
        for byte in packet:
            if byte == SLIP_END:
                escaped.extend([SLIP_ESC, SLIP_ESC_END])
            elif byte == SLIP_ESC:
                escaped.extend([SLIP_ESC, SLIP_ESC_ESC])
            else:
                escaped.append(byte)
        escaped.append(SLIP_END)
        return bytes(escaped)

    @staticmethod
    def decode_stream(buffer: bytes) -> Tuple[List[ITFrame], bytes]:
        frames: List[ITFrame] = []
        current = bytearray()
        in_frame = False
        escape_next = False
        last_boundary = 0

        for index, byte in enumerate(buffer):
            if byte == SLIP_END:
                if in_frame and current:
                    frames.append(PacketCodec.decode(bytes(current)))
                    current.clear()
                in_frame = True
                escape_next = False
                last_boundary = index + 1
                continue
            if not in_frame:
                continue
            if escape_next:
                if byte == SLIP_ESC_END:
                    current.append(SLIP_END)
                elif byte == SLIP_ESC_ESC:
                    current.append(SLIP_ESC)
                else:
                    raise ValueError("invalid SLIP escape sequence")
                escape_next = False
                continue
            if byte == SLIP_ESC:
                escape_next = True
                continue
            current.append(byte)

        remainder = buffer[last_boundary:] if in_frame and current else b""
        return frames, remainder


class TCPIPTransportInterface:
    """UDP-preferred host-side transport to the edge switch."""

    def __init__(
        self,
        endpoint_id: str = "raspberry-pi",
        mode: str = TransportMode.UDP.value,
        bind_host: str = "0.0.0.0",
        bind_port: int = 0,
        switch_host: str = "127.0.0.1",
        switch_port: int = 9900,
        recv_timeout_s: float = 0.0,
    ):
        self.endpoint_id = endpoint_id
        self.mode = TransportMode(mode)
        self.bind_host = bind_host
        self.bind_port = int(bind_port)
        self.switch_host = switch_host
        self.switch_port = int(switch_port)
        self.recv_timeout_s = float(recv_timeout_s)
        self.is_connected = False
        self.message_handlers: Dict[int, List[Callable[[ITFrame], None]]] = {}
        self.outbox: List[bytes] = []
        self._socket: Optional[socket.socket] = None
        self.logger = logging.getLogger(f"IPUARTTransport_{endpoint_id}")
        self.stats = {
            "frames_sent": 0,
            "frames_received": 0,
            "errors": 0,
            "last_activity": 0.0,
        }

    def connect(self) -> bool:
        try:
            if self.mode == TransportMode.UDP:
                self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self._socket.bind((self.bind_host, self.bind_port))
                self._socket.settimeout(self.recv_timeout_s)
            elif self.mode == TransportMode.TCP:
                self._socket = socket.create_connection((self.switch_host, self.switch_port), timeout=2.0)
            self.is_connected = True
            self.logger.info("Connected IP/UART transport via %s", self.mode.value)
            return True
        except OSError as exc:
            self.logger.error("Failed to connect IP/UART transport: %s", exc)
            self.stats["errors"] += 1
            self.is_connected = False
            return False

    def disconnect(self) -> None:
        if self._socket:
            self._socket.close()
            self._socket = None
        self.is_connected = False
        self.logger.info("Disconnected IP/UART transport %s", self.endpoint_id)

    def send_frame(self, frame: ITFrame) -> bool:
        if not self.is_connected:
            self.logger.error("Cannot send frame: transport is not connected")
            return False
        try:
            packet = PacketCodec.encode(frame)
            if self.mode == TransportMode.UDP and self._socket:
                self._socket.sendto(packet, (self.switch_host, self.switch_port))
            elif self.mode == TransportMode.TCP and self._socket:
                self._socket.sendall(packet)
            else:
                self.outbox.append(packet)
            self.stats["frames_sent"] += 1
            self.stats["last_activity"] = time.time()
            return True
        except Exception as exc:
            self.logger.error("Failed to send IP/UART frame: %s", exc)
            self.stats["errors"] += 1
            return False

    def receive_once(self, max_bytes: int = 4096) -> Optional[ITFrame]:
        if not self.is_connected or not self._socket:
            return None
        try:
            packet = self._socket.recv(max_bytes)
            return self.process_incoming_packet(packet)
        except (BlockingIOError, socket.timeout):
            return None
        except Exception as exc:
            self.logger.error("Failed to receive IP/UART frame: %s", exc)
            self.stats["errors"] += 1
            return None

    def process_incoming_packet(self, packet: bytes) -> ITFrame:
        frame = PacketCodec.decode(packet)
        self.stats["frames_received"] += 1
        self.stats["last_activity"] = time.time()
        for handler in self.message_handlers.get(frame.service_id, []):
            handler(frame)
        return frame

    def register_message_handler(self, service_id: int, handler: Callable[[ITFrame], None]) -> None:
        self.message_handlers.setdefault(int(service_id), []).append(handler)
        self.logger.info("Registered handler for service 0x%04X", int(service_id))

    def get_statistics(self) -> Dict[str, Any]:
        return {
            "endpoint_id": self.endpoint_id,
            "mode": self.mode.value,
            "bind": f"{self.bind_host}:{self.bind_port}",
            "switch": f"{self.switch_host}:{self.switch_port}",
            "is_connected": self.is_connected,
            "frames_sent": self.stats["frames_sent"],
            "frames_received": self.stats["frames_received"],
            "errors": self.stats["errors"],
            "last_activity": self.stats["last_activity"],
        }


class UARTEndpoint:
    """UART/COM endpoint attached to the edge switch."""

    def __init__(
        self,
        name: str,
        port: str,
        baudrate: int = 115200,
        serial_instance: Optional[Any] = None,
        serial_factory: Optional[Callable[..., Any]] = None,
    ):
        self.name = name
        self.port = port
        self.baudrate = int(baudrate)
        self.serial = serial_instance
        self.serial_factory = serial_factory
        self.is_connected = serial_instance is not None
        self.logger = logging.getLogger(f"UARTEndpoint_{name}")
        self.frames_written = 0

    def connect(self) -> bool:
        if self.serial:
            self.is_connected = True
            return True
        try:
            factory = self.serial_factory
            if factory is None:
                import serial  # type: ignore

                factory = serial.Serial
            self.serial = factory(self.port, self.baudrate, timeout=0.05)
            self.is_connected = True
            return True
        except Exception as exc:
            self.logger.error("Failed to open UART endpoint %s on %s: %s", self.name, self.port, exc)
            self.is_connected = False
            return False

    def disconnect(self) -> None:
        if self.serial and hasattr(self.serial, "close"):
            self.serial.close()
        self.is_connected = False

    def send_frame(self, frame: ITFrame) -> bool:
        if not self.is_connected and not self.connect():
            return False
        encoded = UARTFrameCodec.encode(frame)
        written = self.serial.write(encoded)
        self.frames_written += 1
        return written == len(encoded)


class EndpointSwitch:
    """Routes UDP/TCP application packets to UART/COM endpoint streams."""

    def __init__(self, endpoints: Optional[Dict[str, UARTEndpoint]] = None):
        self.endpoints: Dict[str, UARTEndpoint] = dict(endpoints or {})
        self.logger = logging.getLogger("EndpointSwitch")
        self.stats = {
            "packets_received": 0,
            "uart_frames_sent": 0,
            "unknown_destinations": 0,
            "errors": 0,
        }

    def register_endpoint(self, destination: str, endpoint: UARTEndpoint) -> None:
        self.endpoints[destination] = endpoint

    def route_network_packet(self, packet: bytes) -> bool:
        try:
            return self.route_frame(PacketCodec.decode(packet))
        except Exception as exc:
            self.logger.error("Failed to route network packet: %s", exc)
            self.stats["errors"] += 1
            return False

    def route_frame(self, frame: ITFrame) -> bool:
        self.stats["packets_received"] += 1
        endpoint = self.endpoints.get(frame.destination) or self.endpoints.get("default")
        if not endpoint:
            self.stats["unknown_destinations"] += 1
            self.logger.warning("No UART endpoint registered for destination %s", frame.destination)
            return False
        if endpoint.send_frame(frame):
            self.stats["uart_frames_sent"] += 1
            return True
        self.stats["errors"] += 1
        return False

    def get_statistics(self) -> Dict[str, Any]:
        return dict(self.stats)


class EVTCPIPProtocol:
    """EV service protocol carried by IP packets and UART endpoint streams."""

    SERVICE_IDS = {
        "BMS_VOLTAGE": 0x0180,
        "BMS_CURRENT": 0x0181,
        "BMS_TEMPERATURE": 0x0182,
        "BMS_STATUS": 0x0183,
        "BMS_SOC": 0x0184,
        "MOTOR_SPEED": 0x0200,
        "MOTOR_TORQUE": 0x0201,
        "MOTOR_TEMPERATURE": 0x0202,
        "MOTOR_STATUS": 0x0203,
        "VESC_SET_RPM": 0x0210,
        "VESC_SET_CURRENT": 0x0211,
        "VESC_SET_DUTY": 0x0212,
        "VESC_STATUS": 0x0213,
        "VESC_VALUES": 0x0214,
        "CHARGER_STATUS": 0x0280,
        "CHARGER_VOLTAGE": 0x0281,
        "CHARGER_CURRENT": 0x0282,
        "VEHICLE_SPEED": 0x0300,
        "VEHICLE_ACCELERATION": 0x0301,
        "VEHICLE_STATUS": 0x0303,
        "BRAKE_STATUS": 0x0380,
        "STEERING_ANGLE": 0x0381,
        "TEMPERATURE_BATTERY_CELL_GROUP": 0x0400,
        "TEMPERATURE_COOLANT_INLET": 0x0401,
        "TEMPERATURE_COOLANT_OUTLET": 0x0402,
        "TEMPERATURE_MOTOR_STATOR": 0x0403,
        "TEMPERATURE_CHARGING_PORT": 0x0404,
        "TEMPERATURE_CHARGING_CONNECTOR": 0x0405,
        "TEMPERATURE_GENERIC": 0x0406,
        "ARDUINO_PERIPHERAL_STATUS": 0x0310,
        "ARDUINO_PERIPHERAL_COMMAND": 0x0311,
    }

    CAN_IDS = SERVICE_IDS

    def __init__(
        self,
        transport: TCPIPTransportInterface,
        source: str = "raspberry-pi",
        default_destination: str = "engine",
    ):
        self.transport = transport
        self.can_bus = transport
        self.source = source
        self.default_destination = default_destination
        self.logger = logging.getLogger("EVTCPIPProtocol")

    def send_battery_status(self, voltage: float, current: float, temperature: float, soc: float) -> bool:
        return self._send_service(
            "BMS_STATUS",
            "Battery Management System Status",
            {"voltage": voltage, "current": current, "temperature": temperature, "soc": soc},
            source="BMS",
            destination="battery",
        )

    def send_motor_status(self, speed: float, torque: float, temperature: float) -> bool:
        return self._send_service(
            "MOTOR_STATUS",
            "Motor Controller Status",
            {"speed": speed, "torque": torque, "temperature": temperature},
            source="MotorController",
            destination="engine",
        )

    def send_charger_status(self, voltage: float, current: float, state: str) -> bool:
        return self._send_service(
            "CHARGER_STATUS",
            "Charging System Status",
            {"voltage": voltage, "current": current, "state": state},
            source="ChargingSystem",
            destination="charger",
        )

    def send_vehicle_status(self, speed: float, acceleration: float, mode: str, state: str = "active") -> bool:
        return self._send_service(
            "VEHICLE_STATUS",
            "Vehicle Controller Status",
            {"speed": speed, "acceleration": acceleration, "mode": mode, "state": state},
            source="VehicleController",
            destination="engine",
        )

    def send_vesc_command_rpm(self, rpm: float) -> bool:
        return self._send_service("VESC_SET_RPM", "VESC Set RPM Command", {"rpm": rpm}, source="VehicleController")

    def send_vesc_command_current(self, current_a: float) -> bool:
        return self._send_service(
            "VESC_SET_CURRENT",
            "VESC Set Current Command",
            {"current": current_a},
            source="VehicleController",
        )

    def send_vesc_command_duty(self, duty_cycle: float) -> bool:
        return self._send_service(
            "VESC_SET_DUTY",
            "VESC Set Duty Cycle Command",
            {"duty_cycle": duty_cycle},
            source="VehicleController",
        )

    def send_vesc_status(self, rpm: float, current: float, voltage: float, temperature: float) -> bool:
        return self._send_service(
            "VESC_STATUS",
            "VESC Status Information",
            {"rpm": rpm, "current": current, "voltage": voltage, "temperature": temperature},
            source="VESC",
            destination="engine",
        )

    def send_temperature_data(self, sensor_type: str, sensor_id: str, temperature: float) -> bool:
        service_id_map = {
            "battery_cell_group": self.SERVICE_IDS["TEMPERATURE_BATTERY_CELL_GROUP"],
            "coolant_inlet": self.SERVICE_IDS["TEMPERATURE_COOLANT_INLET"],
            "coolant_outlet": self.SERVICE_IDS["TEMPERATURE_COOLANT_OUTLET"],
            "motor_stator": self.SERVICE_IDS["TEMPERATURE_MOTOR_STATOR"],
            "charging_port": self.SERVICE_IDS["TEMPERATURE_CHARGING_PORT"],
            "charging_connector": self.SERVICE_IDS["TEMPERATURE_CHARGING_CONNECTOR"],
        }
        service_id = service_id_map.get(sensor_type, self.SERVICE_IDS["TEMPERATURE_GENERIC"])
        message = ITMessage(
            service_id=service_id,
            name=f"TEMPERATURE_{sensor_type.upper()}",
            description=f"Temperature sensor data: {sensor_id}",
            data={"sensor_id": sensor_id, "temperature": temperature, "sensor_type": sensor_type},
            timestamp=time.time(),
            source="TemperatureSensor",
            destination="engine",
        )
        return self._send_message(message)

    def parse_vesc_command(self, frame: ITFrame) -> Optional[Dict[str, Any]]:
        mapping = {
            self.SERVICE_IDS["VESC_SET_RPM"]: "set_rpm",
            self.SERVICE_IDS["VESC_SET_CURRENT"]: "set_current",
            self.SERVICE_IDS["VESC_SET_DUTY"]: "set_duty",
        }
        command = mapping.get(frame.service_id)
        if not command:
            return None
        try:
            return {"command": command, "value": struct.unpack("<f", frame.payload[:4])[0]}
        except struct.error:
            return None

    def parse_vesc_status(self, frame: ITFrame) -> Optional[Dict[str, Any]]:
        if frame.service_id != self.SERVICE_IDS["VESC_STATUS"]:
            return None
        try:
            values = struct.unpack("<ffff", frame.payload[:16])
        except struct.error:
            return None
        return {"rpm": values[0], "current": values[1], "voltage": values[2], "temperature": values[3]}

    def parse_temperature_data(self, frame: ITFrame) -> Optional[Dict[str, Any]]:
        service_to_type = {
            self.SERVICE_IDS["TEMPERATURE_BATTERY_CELL_GROUP"]: "battery_cell_group",
            self.SERVICE_IDS["TEMPERATURE_COOLANT_INLET"]: "coolant_inlet",
            self.SERVICE_IDS["TEMPERATURE_COOLANT_OUTLET"]: "coolant_outlet",
            self.SERVICE_IDS["TEMPERATURE_MOTOR_STATOR"]: "motor_stator",
            self.SERVICE_IDS["TEMPERATURE_CHARGING_PORT"]: "charging_port",
            self.SERVICE_IDS["TEMPERATURE_CHARGING_CONNECTOR"]: "charging_connector",
            self.SERVICE_IDS["TEMPERATURE_GENERIC"]: "generic",
        }
        sensor_type = service_to_type.get(frame.service_id)
        if not sensor_type:
            return None
        try:
            temperature = struct.unpack("<f", frame.payload[:4])[0]
        except struct.error:
            return None
        return {
            "temperature": temperature,
            "sensor_type": frame.metadata.get("sensor_type", sensor_type),
            "sensor_id": frame.metadata.get("sensor_id", "unknown"),
        }

    def _send_service(
        self,
        service_name: str,
        description: str,
        data: Dict[str, Any],
        *,
        source: str,
        destination: Optional[str] = None,
    ) -> bool:
        message = ITMessage(
            service_id=self.SERVICE_IDS[service_name],
            name=service_name,
            description=description,
            data=data,
            timestamp=time.time(),
            source=source,
            destination=destination or self.default_destination,
        )
        return self._send_message(message)

    def _send_message(self, message: ITMessage) -> bool:
        frame = ITFrame(
            service_id=message.service_id,
            payload=self._serialize_data(message.data),
            source=message.source,
            destination=message.destination,
            timestamp=message.timestamp,
            qos=message.priority,
            metadata={k: v for k, v in message.data.items() if not isinstance(v, (int, float))},
        )
        return self.transport.send_frame(frame)

    def _serialize_data(self, data: Dict[str, Any]) -> bytes:
        result = bytearray()
        for value in data.values():
            if isinstance(value, (int, float)):
                result.extend(struct.pack("<f", float(value)))
        if not result:
            result.extend(json.dumps(data, separators=(",", ":"), sort_keys=True).encode("utf-8"))
        return bytes(result)

"""CAN Bus communication module for EV systems with industry best practices."""

import time
import threading
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from enum import Enum
import struct
import logging


class CANFrameType(Enum):
    """CAN frame types."""
    DATA = "data"
    REMOTE = "remote"
    ERROR = "error"
    OVERLOAD = "overload"


@dataclass
class CANFrame:
    """CAN frame data structure."""
    can_id: int
    data: bytes
    timestamp: float
    frame_type: CANFrameType = CANFrameType.DATA
    is_extended: bool = False
    is_remote: bool = False
    dlc: int = 8  # Data Length Code (0-8 bytes)
    
    def __post_init__(self):
        """Validate frame data after initialization."""
        if self.dlc > 8:
            raise ValueError("DLC cannot exceed 8 bytes")
        if len(self.data) != self.dlc:
            raise ValueError(f"Data length ({len(self.data)}) must match DLC ({self.dlc})")


@dataclass
class CANMessage:
    """Standardized CAN message with EV-specific data."""
    message_id: int
    name: str
    description: str
    data: Dict[str, Any]
    timestamp: float
    source: str  # ECU/subsystem name
    priority: int = 0  # 0=highest, 255=lowest


class CANBusInterface:
    """Generic CAN bus interface following industry standards."""
    
    def __init__(self, channel: str, bitrate: int = 500000, interface: str = "socketcan"):
        """Initialize CAN bus interface."""
        self.channel = channel
        self.bitrate = bitrate
        self.interface = interface
        self.is_connected = False
        self.logger = logging.getLogger(f"CANBus_{channel}")
        
        # Message handlers
        self.message_handlers: Dict[int, List[Callable]] = {}
        
        # Statistics
        self.stats = {
            'frames_sent': 0,
            'frames_received': 0,
            'errors': 0,
            'last_activity': 0.0
        }
    
    def connect(self) -> bool:
        """Connect to CAN bus."""
        try:
            self.is_connected = True
            self.logger.info(f"Connected to CAN bus {self.channel} at {self.bitrate} bps")
            return True
        except Exception as e:
            self.logger.error(f"Failed to connect to CAN bus: {e}")
            return False
    
    def disconnect(self) -> None:
        """Disconnect from CAN bus."""
        self.is_connected = False
        self.logger.info(f"Disconnected from CAN bus {self.channel}")
    
    def send_frame(self, frame: CANFrame) -> bool:
        """Send a CAN frame."""
        if not self.is_connected:
            self.logger.error("Cannot send frame: not connected to CAN bus")
            return False
        
        try:
            self.stats['frames_sent'] += 1
            self.stats['last_activity'] = time.time()
            self.logger.debug(f"Sent frame: ID={frame.can_id:03X}, Data={frame.data.hex()}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to send frame: {e}")
            self.stats['errors'] += 1
            return False
    
    def register_message_handler(self, can_id: int, handler: Callable[[CANFrame], None]) -> None:
        """Register a handler for specific CAN ID."""
        if can_id not in self.message_handlers:
            self.message_handlers[can_id] = []
        self.message_handlers[can_id].append(handler)
        self.logger.info(f"Registered handler for CAN ID {can_id:03X}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get CAN bus statistics."""
        return {
            'channel': self.channel,
            'bitrate': self.bitrate,
            'is_connected': self.is_connected,
            'frames_sent': self.stats['frames_sent'],
            'frames_received': self.stats['frames_received'],
            'errors': self.stats['errors'],
            'last_activity': self.stats['last_activity']
        }


class EVCANProtocol:
    """EV-specific CAN protocol implementation following industry standards."""
    
    # Standard EV CAN IDs (following ISO 11898 and industry conventions)
    CAN_IDS = {
        # Battery Management System
        'BMS_VOLTAGE': 0x180,
        'BMS_CURRENT': 0x181,
        'BMS_TEMPERATURE': 0x182,
        'BMS_STATUS': 0x183,
        'BMS_SOC': 0x184,
        
        # Motor Controller
        'MOTOR_SPEED': 0x200,
        'MOTOR_TORQUE': 0x201,
        'MOTOR_TEMPERATURE': 0x202,
        'MOTOR_STATUS': 0x203,
        
        # VESC-specific commands and status
        'VESC_SET_RPM': 0x210,
        'VESC_SET_CURRENT': 0x211,
        'VESC_SET_DUTY': 0x212,
        'VESC_STATUS': 0x213,
        'VESC_VALUES': 0x214,
        
        # Charging System
        'CHARGER_STATUS': 0x280,
        'CHARGER_VOLTAGE': 0x281,
        'CHARGER_CURRENT': 0x282,
        
        # Vehicle Controller
        'VEHICLE_SPEED': 0x300,
        'VEHICLE_ACCELERATION': 0x301,
        'VEHICLE_STATUS': 0x303,
        
        # Safety Systems
        'BRAKE_STATUS': 0x380,
        'STEERING_ANGLE': 0x381,
    }
    
    def __init__(self, can_bus: CANBusInterface):
        """Initialize EV CAN protocol."""
        self.can_bus = can_bus
        self.logger = logging.getLogger("EVCANProtocol")
    
    def send_battery_status(self, voltage: float, current: float, temperature: float, soc: float) -> bool:
        """Send battery status information."""
        message = CANMessage(
            message_id=self.CAN_IDS['BMS_STATUS'],
            name="BMS_STATUS",
            description="Battery Management System Status",
            data={
                'voltage': voltage,
                'current': current,
                'temperature': temperature,
                'soc': soc
            },
            timestamp=time.time(),
            source="BMS"
        )
        return self._send_message(message)
    
    def send_motor_status(self, speed: float, torque: float, temperature: float) -> bool:
        """Send motor status information."""
        message = CANMessage(
            message_id=self.CAN_IDS['MOTOR_STATUS'],
            name="MOTOR_STATUS",
            description="Motor Controller Status",
            data={
                'speed': speed,
                'torque': torque,
                'temperature': temperature
            },
            timestamp=time.time(),
            source="MotorController"
        )
        return self._send_message(message)
    
    def _send_message(self, message: CANMessage) -> bool:
        """Send a CAN message."""
        # Convert message to frame and send
        frame = CANFrame(
            can_id=message.message_id,
            data=self._serialize_data(message.data),
            timestamp=message.timestamp,
            dlc=8
        )
        return self.can_bus.send_frame(frame)
    
    def send_vesc_command_rpm(self, rpm: float) -> bool:
        """Send VESC RPM command via CAN."""
        message = CANMessage(
            message_id=self.CAN_IDS['VESC_SET_RPM'],
            name="VESC_SET_RPM",
            description="VESC Set RPM Command",
            data={'rpm': rpm},
            timestamp=time.time(),
            source="VehicleController"
        )
        return self._send_message(message)
    
    def send_vesc_command_current(self, current_a: float) -> bool:
        """Send VESC current command via CAN."""
        message = CANMessage(
            message_id=self.CAN_IDS['VESC_SET_CURRENT'],
            name="VESC_SET_CURRENT",
            description="VESC Set Current Command",
            data={'current': current_a},
            timestamp=time.time(),
            source="VehicleController"
        )
        return self._send_message(message)
    
    def send_vesc_command_duty(self, duty_cycle: float) -> bool:
        """Send VESC duty cycle command via CAN."""
        message = CANMessage(
            message_id=self.CAN_IDS['VESC_SET_DUTY'],
            name="VESC_SET_DUTY",
            description="VESC Set Duty Cycle Command",
            data={'duty_cycle': duty_cycle},
            timestamp=time.time(),
            source="VehicleController"
        )
        return self._send_message(message)
    
    def send_vesc_status(self, rpm: float, current: float, voltage: float, temperature: float) -> bool:
        """Send VESC status information via CAN."""
        message = CANMessage(
            message_id=self.CAN_IDS['VESC_STATUS'],
            name="VESC_STATUS",
            description="VESC Status Information",
            data={
                'rpm': rpm,
                'current': current,
                'voltage': voltage,
                'temperature': temperature
            },
            timestamp=time.time(),
            source="VESC"
        )
        return self._send_message(message)
    
    def parse_vesc_command(self, frame: CANFrame) -> Optional[Dict[str, Any]]:
        """
        Parse VESC command from CAN frame.
        
        Args:
            frame: CAN frame containing VESC command
        
        Returns:
            Dictionary with command type and value, or None if invalid
        """
        if frame.can_id == self.CAN_IDS['VESC_SET_RPM']:
            try:
                rpm = struct.unpack('<f', frame.data[:4])[0]
                return {'command': 'set_rpm', 'value': rpm}
            except struct.error:
                return None
        elif frame.can_id == self.CAN_IDS['VESC_SET_CURRENT']:
            try:
                current = struct.unpack('<f', frame.data[:4])[0]
                return {'command': 'set_current', 'value': current}
            except struct.error:
                return None
        elif frame.can_id == self.CAN_IDS['VESC_SET_DUTY']:
            try:
                duty = struct.unpack('<f', frame.data[:4])[0]
                return {'command': 'set_duty', 'value': duty}
            except struct.error:
                return None
        return None
    
    def parse_vesc_status(self, frame: CANFrame) -> Optional[Dict[str, Any]]:
        """
        Parse VESC status from CAN frame.
        
        Args:
            frame: CAN frame containing VESC status
        
        Returns:
            Dictionary with status values, or None if invalid
        """
        if frame.can_id == self.CAN_IDS['VESC_STATUS']:
            try:
                if len(frame.data) >= 8:  # At least 2 floats = 8 bytes (CAN max)
                    rpm = struct.unpack('<f', frame.data[0:4])[0]
                    current = struct.unpack('<f', frame.data[4:8])[0]
                    # If we have more data, parse voltage and temperature
                    voltage = 0.0
                    temperature = 0.0
                    if len(frame.data) >= 12:
                        voltage = struct.unpack('<f', frame.data[8:12])[0]
                    if len(frame.data) >= 16:
                        temperature = struct.unpack('<f', frame.data[12:16])[0]
                    return {
                        'rpm': rpm,
                        'current': current,
                        'voltage': voltage,
                        'temperature': temperature
                    }
            except struct.error:
                return None
        return None
    
    def _send_message(self, message: CANMessage) -> bool:
        """Send a CAN message."""
        # Convert message to frame and send
        frame = CANFrame(
            can_id=message.message_id,
            data=self._serialize_data(message.data),
            timestamp=message.timestamp,
            dlc=8
        )
        return self.can_bus.send_frame(frame)
    
    def _serialize_data(self, data: Dict[str, Any]) -> bytes:
        """Serialize message data to bytes."""
        result = bytearray()
        for key, value in data.items():
            if isinstance(value, (int, float)):
                result.extend(struct.pack('<f', float(value)))
        # Pad to 8 bytes if needed, limit to 8 bytes if too long
        if len(result) < 8:
            result.extend(b'\x00' * (8 - len(result)))
        return bytes(result[:8])  # Limit to 8 bytes for CAN

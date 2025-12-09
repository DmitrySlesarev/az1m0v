"""Telemetry module for the EV project.
Provides remote data transmission and monitoring using Quectel cellular modules.
"""

import time
import json
import logging
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, asdict
from enum import Enum


class TelemetryState(Enum):
    """Telemetry system states."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    SENDING = "sending"
    ERROR = "error"
    SIMULATION = "simulation"


@dataclass
class TelemetryData:
    """Telemetry data packet structure."""
    timestamp: float
    vehicle_id: str
    battery_soc: float
    battery_voltage: float
    battery_current: float
    motor_speed_rpm: float
    motor_current: float
    vehicle_speed_kmh: float
    charging_power_kw: float
    temperature: float
    location: Optional[Dict[str, float]] = None  # GPS coordinates
    state: str = "unknown"
    errors: List[str] = None

    def __post_init__(self):
        """Initialize optional fields."""
        if self.errors is None:
            self.errors = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())


class TelemetryConfig:
    """Configuration for telemetry system."""

    def __init__(
        self,
        enabled: bool = True,
        server_url: str = "",
        server_port: int = 443,
        api_key: str = "",
        update_interval_s: float = 10.0,
        connection_timeout_s: float = 30.0,
        retry_attempts: int = 3,
        retry_delay_s: float = 5.0,
        use_ssl: bool = True,
        cellular_apn: str = "",
        cellular_username: str = "",
        cellular_password: str = "",
        simulation_mode: bool = False
    ):
        """Initialize telemetry configuration."""
        self.enabled = enabled
        self.server_url = server_url
        self.server_port = server_port
        self.api_key = api_key
        self.update_interval_s = update_interval_s
        self.connection_timeout_s = connection_timeout_s
        self.retry_attempts = retry_attempts
        self.retry_delay_s = retry_delay_s
        self.use_ssl = use_ssl
        self.cellular_apn = cellular_apn
        self.cellular_username = cellular_username
        self.cellular_password = cellular_password
        self.simulation_mode = simulation_mode


class TelemetrySystem:
    """
    Telemetry system for remote data transmission using Quectel cellular modules.
    Supports both real hardware and simulation mode.
    """

    def __init__(
        self,
        config: Dict[str, Any],
        vehicle_id: str = "EV001"
    ):
        """
        Initialize telemetry system.

        Args:
            config: Configuration dictionary with telemetry parameters
            vehicle_id: Unique vehicle identifier
        """
        self.config = TelemetryConfig(
            enabled=config.get('enabled', True),
            server_url=config.get('server_url', ''),
            server_port=config.get('server_port', 443),
            api_key=config.get('api_key', ''),
            update_interval_s=config.get('update_interval_s', 10.0),
            connection_timeout_s=config.get('connection_timeout_s', 30.0),
            retry_attempts=config.get('retry_attempts', 3),
            retry_delay_s=config.get('retry_delay_s', 5.0),
            use_ssl=config.get('use_ssl', True),
            cellular_apn=config.get('cellular_apn', ''),
            cellular_username=config.get('cellular_username', ''),
            cellular_password=config.get('cellular_password', ''),
            simulation_mode=config.get('simulation_mode', False)
        )

        self.vehicle_id = vehicle_id
        self.logger = logging.getLogger(__name__)
        self.state = TelemetryState.DISCONNECTED

        # Quectel module (optional, for real hardware)
        self.quectel_module = None
        self._init_quectel()

        # Statistics
        self.stats = {
            'packets_sent': 0,
            'packets_failed': 0,
            'bytes_sent': 0,
            'connection_errors': 0,
            'last_send_time': 0.0,
            'last_successful_send': 0.0
        }

        # Last telemetry data
        self.last_data: Optional[TelemetryData] = None

        self.logger.info(
            f"Telemetry system initialized: enabled={self.config.enabled}, "
            f"simulation={self.config.simulation_mode}"
        )

    def _init_quectel(self) -> None:
        """Initialize Quectel module if available."""
        if self.config.simulation_mode:
            self.state = TelemetryState.SIMULATION
            self.logger.info("Telemetry running in simulation mode")
            return

        try:
            import quecpython
            self.quectel_module = quecpython
            self.logger.info("Quectel module loaded successfully")
        except ImportError:
            self.config.simulation_mode = True
            self.state = TelemetryState.SIMULATION
            self.logger.warning(
                "Quectel module not available, running in simulation mode"
            )

    def connect(self) -> bool:
        """
        Connect to cellular network and telemetry server.

        Returns:
            True if connection successful, False otherwise
        """
        if not self.config.enabled:
            self.logger.info("Telemetry is disabled")
            return False

        if self.config.simulation_mode:
            self.state = TelemetryState.CONNECTED
            self.logger.info("Telemetry connected (simulation mode)")
            return True

        try:
            self.state = TelemetryState.CONNECTING
            self.logger.info("Connecting to cellular network...")

            # In real implementation, this would:
            # 1. Initialize cellular module
            # 2. Configure APN
            # 3. Establish network connection
            # 4. Connect to telemetry server

            # For now, simulate connection
            time.sleep(0.1)  # Simulate connection delay
            self.state = TelemetryState.CONNECTED
            self.logger.info("Telemetry connected successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to connect telemetry: {e}")
            self.state = TelemetryState.ERROR
            self.stats['connection_errors'] += 1
            return False

    def disconnect(self) -> None:
        """Disconnect from telemetry server and cellular network."""
        if self.state == TelemetryState.DISCONNECTED:
            return

        self.logger.info("Disconnecting telemetry...")
        self.state = TelemetryState.DISCONNECTED

    def send_data(
        self,
        battery_soc: float = 0.0,
        battery_voltage: float = 0.0,
        battery_current: float = 0.0,
        motor_speed_rpm: float = 0.0,
        motor_current: float = 0.0,
        vehicle_speed_kmh: float = 0.0,
        charging_power_kw: float = 0.0,
        temperature: float = 0.0,
        location: Optional[Dict[str, float]] = None,
        state: str = "unknown",
        errors: Optional[List[str]] = None
    ) -> bool:
        """
        Send telemetry data to remote server.

        Args:
            battery_soc: Battery state of charge (0-100)
            battery_voltage: Battery voltage (V)
            battery_current: Battery current (A)
            motor_speed_rpm: Motor speed (RPM)
            motor_current: Motor current (A)
            vehicle_speed_kmh: Vehicle speed (km/h)
            charging_power_kw: Charging power (kW)
            temperature: System temperature (°C)
            location: GPS coordinates (optional)
            state: Vehicle state string
            errors: List of error messages (optional)

        Returns:
            True if data sent successfully, False otherwise
        """
        if not self.config.enabled:
            return False

        if self.state not in [TelemetryState.CONNECTED, TelemetryState.SIMULATION]:
            if not self.connect():
                return False

        # Create telemetry data packet
        telemetry_data = TelemetryData(
            timestamp=time.time(),
            vehicle_id=self.vehicle_id,
            battery_soc=battery_soc,
            battery_voltage=battery_voltage,
            battery_current=battery_current,
            motor_speed_rpm=motor_speed_rpm,
            motor_current=motor_current,
            vehicle_speed_kmh=vehicle_speed_kmh,
            charging_power_kw=charging_power_kw,
            temperature=temperature,
            location=location,
            state=state,
            errors=errors or []
        )

        self.last_data = telemetry_data

        # Send data
        try:
            self.state = TelemetryState.SENDING
            success = self._send_packet(telemetry_data)

            if success:
                self.stats['packets_sent'] += 1
                self.stats['bytes_sent'] += len(telemetry_data.to_json())
                self.stats['last_successful_send'] = time.time()
                self.state = TelemetryState.CONNECTED
                self.logger.debug(f"Telemetry data sent: {telemetry_data.to_json()}")
            else:
                self.stats['packets_failed'] += 1
                self.state = TelemetryState.ERROR
                self.logger.warning("Failed to send telemetry data")

            self.stats['last_send_time'] = time.time()
            return success

        except Exception as e:
            self.logger.error(f"Error sending telemetry data: {e}")
            self.stats['packets_failed'] += 1
            self.state = TelemetryState.ERROR
            return False

    def _send_packet(self, data: TelemetryData) -> bool:
        """
        Send a telemetry packet to the server.

        Args:
            data: Telemetry data packet

        Returns:
            True if successful, False otherwise
        """
        if self.config.simulation_mode:
            # In simulation mode, just log the data
            self.logger.debug(f"Simulated telemetry send: {data.to_json()}")
            return True

        # Real implementation would use Quectel module to send HTTP/HTTPS request
        # For now, simulate sending
        try:
            # In real implementation:
            # 1. Serialize data to JSON
            # 2. Create HTTP/HTTPS request
            # 3. Send via cellular connection
            # 4. Handle response

            json_data = data.to_json()
            self.logger.debug(f"Sending telemetry packet: {len(json_data)} bytes")
            return True

        except Exception as e:
            self.logger.error(f"Failed to send packet: {e}")
            return False

    def get_status(self) -> Dict[str, Any]:
        """
        Get telemetry system status.

        Returns:
            Dictionary with status information
        """
        return {
            'state': self.state.value,
            'enabled': self.config.enabled,
            'simulation_mode': self.config.simulation_mode,
            'connected': self.state in [TelemetryState.CONNECTED, TelemetryState.SIMULATION],
            'stats': self.stats.copy(),
            'last_data': self.last_data.to_dict() if self.last_data else None
        }

    def is_connected(self) -> bool:
        """Check if telemetry is connected."""
        return self.state in [TelemetryState.CONNECTED, TelemetryState.SIMULATION]

    def is_enabled(self) -> bool:
        """Check if telemetry is enabled."""
        return self.config.enabled

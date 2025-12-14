"""Charging system module for the EV project.
Implements high-level interface for EV charging compatible with VESC and SimpBMS.
Supports AC and DC charging with multiple connector types.
"""

import time
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum


class ChargingState(Enum):
    """Charging system states."""
    DISCONNECTED = "disconnected"
    IDLE = "idle"
    CONNECTED = "connected"
    CHARGING = "charging"
    CHARGING_AC = "charging_ac"
    CHARGING_DC = "charging_dc"
    PAUSED = "paused"
    COMPLETE = "complete"
    ERROR = "error"
    FAULT = "fault"


class ConnectorType(Enum):
    """Charging connector types."""
    CCS1 = "CCS1"
    CCS2 = "CCS2"
    CHADEMO = "CHAdeMO"
    TESLA = "Tesla"
    TYPE2 = "Type2"  # AC charging


@dataclass
class ChargingStatus:
    """Charging status information."""
    state: ChargingState = ChargingState.DISCONNECTED
    voltage_v: float = 0.0
    current_a: float = 0.0
    power_kw: float = 0.0
    energy_charged_kwh: float = 0.0
    charging_time_s: float = 0.0
    connector_type: Optional[ConnectorType] = None
    is_fast_charge: bool = False
    temperature_c: float = 0.0
    error_code: Optional[str] = None
    timestamp: float = 0.0
    port_temperature: Optional[float] = None  # Charging port temperature in °C
    connector_temperature: Optional[float] = None  # Charging connector temperature in °C


class ChargingSystem:
    """
    High-level charging system manager.
    Compatible with VESC motor controller and SimpBMS battery management.
    """

    def __init__(
        self,
        config: Dict[str, Any],
        bms: Optional[Any] = None,
        motor_controller: Optional[Any] = None,
        can_protocol: Optional[Any] = None,
        temperature_sensor_manager: Optional[Any] = None
    ):
        """
        Initialize charging system.
        
        Args:
            config: Configuration dictionary with charging parameters
            bms: Battery Management System instance (for charge authorization)
            motor_controller: Motor controller instance (VESC, for safety checks)
            can_protocol: EV CAN protocol instance (optional)
            temperature_sensor_manager: Optional TemperatureSensorManager instance for port/connector temperature readings
        """
        self.config = config
        self.bms = bms
        self.motor_controller = motor_controller
        self.can_protocol = can_protocol
        self.temperature_sensor_manager = temperature_sensor_manager

        self.logger = logging.getLogger(__name__)
        self.current_status = ChargingStatus()

        # Charging limits from config
        self.ac_max_power_kw = config.get('ac_max_power_kw', 11.0)
        self.dc_max_power_kw = config.get('dc_max_power_kw', 150.0)
        self.connector_type = ConnectorType(config.get('connector_type', 'CCS2'))
        self.fast_charge_enabled = config.get('fast_charge_enabled', True)

        # Safety limits
        self.max_temperature_c = config.get('max_temperature_c', 60.0)
        self.max_voltage_v = config.get('max_voltage_v', 500.0)
        self.min_voltage_v = config.get('min_voltage_v', 300.0)

        # Charging state
        self.charging_start_time: Optional[float] = None
        self.target_soc: float = 100.0  # Default to full charge

        self.logger.info(f"Charging system initialized: AC={self.ac_max_power_kw}kW, DC={self.dc_max_power_kw}kW")

    def connect_charger(self, connector_type: Optional[ConnectorType] = None) -> bool:
        """
        Connect to charging station.
        
        Args:
            connector_type: Connector type (uses config if not provided)
        
        Returns:
            True if connection successful, False otherwise
        """
        if self.current_status.state == ChargingState.CHARGING:
            self.logger.warning("Already charging, cannot connect new charger")
            return False

        # Check if motor is running (safety check)
        if self.motor_controller and self.motor_controller.is_connected:
            motor_status = self.motor_controller.get_status()
            if motor_status.state.value in ['running', 'braking']:
                self.logger.error("Cannot connect charger while motor is running")
                return False

        connector = connector_type or self.connector_type
        self.current_status.connector_type = connector
        self.current_status.state = ChargingState.CONNECTED
        self.current_status.timestamp = time.time()

        self.logger.info(f"Charger connected: {connector.value}")
        return True

    def disconnect_charger(self) -> None:
        """Disconnect from charging station."""
        if self.current_status.state == ChargingState.CHARGING:
            self.stop_charging()

        self.current_status.state = ChargingState.DISCONNECTED
        self.current_status.connector_type = None
        self.current_status.timestamp = time.time()

        self.logger.info("Charger disconnected")

    def start_charging(
        self,
        power_kw: Optional[float] = None,
        target_soc: float = 100.0,
        use_fast_charge: Optional[bool] = None
    ) -> bool:
        """
        Start charging process.
        
        Args:
            power_kw: Requested charging power (None = use max available)
            target_soc: Target state of charge (0-100%)
            use_fast_charge: Use fast charging if available (None = use config)
        
        Returns:
            True if charging started, False otherwise
        """
        # Check connection (allow resuming from paused state)
        if self.current_status.state not in [ChargingState.CONNECTED, ChargingState.IDLE, ChargingState.PAUSED]:
            self.logger.error("Charger not connected")
            return False

        # Check BMS authorization
        if self.bms:
            # Determine max power
            if power_kw is None:
                # Use fast charge if enabled and connector supports it
                if use_fast_charge is None:
                    use_fast_charge = self.fast_charge_enabled

                if use_fast_charge and self._supports_fast_charge():
                    max_power = min(self.dc_max_power_kw, self.bms.config.max_charge_rate_kw)
                else:
                    max_power = min(self.ac_max_power_kw, self.bms.config.max_charge_rate_kw)
            else:
                max_power = power_kw

            # Check if BMS allows charging
            if not self.bms.can_charge(max_power):
                self.logger.error(f"BMS does not allow charging at {max_power}kW")
                self.current_status.state = ChargingState.ERROR
                self.current_status.error_code = "BMS_REJECTED"
                return False

            # Check battery SOC
            bms_state = self.bms.get_state()
            if bms_state.soc >= target_soc:
                self.logger.info(f"Battery already at target SOC: {bms_state.soc:.1f}%")
                self.current_status.state = ChargingState.COMPLETE
                return False
        else:
            # No BMS, use defaults
            if power_kw is None:
                if use_fast_charge is None:
                    use_fast_charge = self.fast_charge_enabled
                max_power = self.dc_max_power_kw if use_fast_charge and self._supports_fast_charge() else self.ac_max_power_kw
            else:
                max_power = power_kw

        # Check motor controller safety
        if self.motor_controller and self.motor_controller.is_connected:
            if not self.motor_controller.is_healthy():
                self.logger.error("Motor controller not healthy, cannot start charging")
                self.current_status.state = ChargingState.ERROR
                self.current_status.error_code = "MOTOR_FAULT"
                return False

        # Start charging
        self.current_status.power_kw = max_power
        self.target_soc = target_soc
        self.charging_start_time = time.time()
        self.current_status.energy_charged_kwh = 0.0
        self.current_status.charging_time_s = 0.0

        # Determine charging type
        if use_fast_charge and self._supports_fast_charge():
            self.current_status.state = ChargingState.CHARGING_DC
            self.current_status.is_fast_charge = True
        else:
            self.current_status.state = ChargingState.CHARGING_AC
            self.current_status.is_fast_charge = False

        self.current_status.timestamp = time.time()
        self.logger.info(f"Charging started: {max_power}kW, target SOC: {target_soc}%")

        return True

    def stop_charging(self) -> bool:
        """
        Stop charging process.
        
        Returns:
            True if stopped successfully, False otherwise
        """
        if self.current_status.state not in [ChargingState.CHARGING, ChargingState.CHARGING_AC, ChargingState.CHARGING_DC]:
            self.logger.warning("Not currently charging")
            return False

        # Calculate final statistics
        if self.charging_start_time:
            self.current_status.charging_time_s = time.time() - self.charging_start_time

        self.current_status.state = ChargingState.CONNECTED
        self.charging_start_time = None
        self.current_status.power_kw = 0.0
        self.current_status.current_a = 0.0
        self.current_status.timestamp = time.time()

        self.logger.info("Charging stopped")
        return True

    def pause_charging(self) -> bool:
        """
        Pause charging (temporary stop, can be resumed).
        
        Returns:
            True if paused successfully, False otherwise
        """
        if self.current_status.state not in [ChargingState.CHARGING, ChargingState.CHARGING_AC, ChargingState.CHARGING_DC]:
            return False

        self.current_status.state = ChargingState.PAUSED
        self.current_status.timestamp = time.time()
        self.logger.info("Charging paused")
        return True

    def resume_charging(self) -> bool:
        """
        Resume paused charging.
        
        Returns:
            True if resumed successfully, False otherwise
        """
        if self.current_status.state != ChargingState.PAUSED:
            return False

        # Restart with same parameters
        return self.start_charging(
            power_kw=self.current_status.power_kw,
            target_soc=self.target_soc,
            use_fast_charge=self.current_status.is_fast_charge
        )

    def update_status(
        self,
        voltage_v: Optional[float] = None,
        current_a: Optional[float] = None,
        temperature_c: Optional[float] = None
    ) -> ChargingStatus:
        """
        Update charging status from charger or BMS.
        
        Args:
            voltage_v: Charging voltage
            current_a: Charging current
            temperature_c: Charging temperature
        
        Returns:
            Updated ChargingStatus
        """
        # Update from parameters if provided
        if voltage_v is not None:
            self.current_status.voltage_v = voltage_v
        if current_a is not None:
            self.current_status.current_a = current_a
        if temperature_c is not None:
            self.current_status.temperature_c = temperature_c

        # Get data from BMS if available
        if self.bms:
            bms_state = self.bms.get_state()
            if voltage_v is None:
                self.current_status.voltage_v = bms_state.voltage
            if current_a is None:
                self.current_status.current_a = bms_state.current
            if temperature_c is None:
                self.current_status.temperature_c = bms_state.temperature

        # Update port and connector temperatures from temperature sensor manager if available
        if self.temperature_sensor_manager:
            charging_temps = self.temperature_sensor_manager.get_charging_temperatures()
            if 'port' in charging_temps:
                self.current_status.port_temperature = charging_temps['port']
            if 'connector' in charging_temps:
                self.current_status.connector_temperature = charging_temps['connector']
            # Use port temperature as main temperature if not set
            if temperature_c is None and self.current_status.port_temperature is not None:
                self.current_status.temperature_c = self.current_status.port_temperature

        # Calculate power
        self.current_status.power_kw = (
            abs(self.current_status.voltage_v * self.current_status.current_a) / 1000.0
        )

        # Update charging statistics if charging
        if self.current_status.state in [ChargingState.CHARGING, ChargingState.CHARGING_AC, ChargingState.CHARGING_DC]:
            if self.charging_start_time:
                dt = time.time() - self.current_status.timestamp
                if dt > 0:
                    # Calculate energy charged
                    energy_kwh = (self.current_status.power_kw * dt) / 3600.0
                    self.current_status.energy_charged_kwh += energy_kwh
                    self.current_status.charging_time_s = time.time() - self.charging_start_time

            # Check if target SOC reached
            if self.bms:
                bms_state = self.bms.get_state()
                if bms_state.soc >= self.target_soc:
                    self.current_status.state = ChargingState.COMPLETE
                    self.logger.info(f"Charging complete: SOC={bms_state.soc:.1f}%")
                    if self.charging_start_time:
                        self.current_status.charging_time_s = time.time() - self.charging_start_time
                    self.charging_start_time = None

            # Check safety limits
            # Check port temperature
            if self.current_status.port_temperature and self.current_status.port_temperature > self.max_temperature_c:
                self.current_status.state = ChargingState.ERROR
                self.current_status.error_code = "PORT_OVERTEMPERATURE"
                self.logger.error(f"Charging stopped: port temperature {self.current_status.port_temperature}°C exceeds limit")
                self.stop_charging()
            # Check connector temperature
            elif self.current_status.connector_temperature and self.current_status.connector_temperature > self.max_temperature_c:
                self.current_status.state = ChargingState.ERROR
                self.current_status.error_code = "CONNECTOR_OVERTEMPERATURE"
                self.logger.error(f"Charging stopped: connector temperature {self.current_status.connector_temperature}°C exceeds limit")
                self.stop_charging()
            # Check general temperature
            elif self.current_status.temperature_c > self.max_temperature_c:
                self.current_status.state = ChargingState.ERROR
                self.current_status.error_code = "OVERTEMPERATURE"
                self.logger.error(f"Charging stopped: temperature {self.current_status.temperature_c}°C exceeds limit")
                self.stop_charging()

            if self.current_status.voltage_v > self.max_voltage_v:
                self.current_status.state = ChargingState.ERROR
                self.current_status.error_code = "OVERVOLTAGE"
                self.logger.error(f"Charging stopped: voltage {self.current_status.voltage_v}V exceeds limit")
                self.stop_charging()

            if self.current_status.voltage_v < self.min_voltage_v and self.current_status.voltage_v > 0:
                self.current_status.state = ChargingState.ERROR
                self.current_status.error_code = "UNDERVOLTAGE"
                self.logger.error(f"Charging stopped: voltage {self.current_status.voltage_v}V below minimum")
                self.stop_charging()

        self.current_status.timestamp = time.time()

        # Send status to CAN bus
        if self.can_protocol:
            self._send_status_to_can()

        return self.current_status

    def get_status(self) -> ChargingStatus:
        """
        Get current charging status.
        
        Returns:
            Current ChargingStatus
        """
        return self.update_status()

    def _supports_fast_charge(self) -> bool:
        """Check if current connector supports fast charging."""
        return self.current_status.connector_type in [
            ConnectorType.CCS1,
            ConnectorType.CCS2,
            ConnectorType.CHADEMO,
            ConnectorType.TESLA
        ]

    def _send_status_to_can(self) -> None:
        """Send charging status to CAN bus."""
        if not self.can_protocol:
            return

        try:
            # Send charger status
            if hasattr(self.can_protocol, 'send_charger_status'):
                self.can_protocol.send_charger_status(
                    voltage=self.current_status.voltage_v,
                    current=self.current_status.current_a,
                    state=self.current_status.state.value
                )
            # Send port and connector temperatures if available
            if hasattr(self.can_protocol, 'send_temperature_data'):
                if self.current_status.port_temperature is not None:
                    self.can_protocol.send_temperature_data(
                        sensor_type='charging_port',
                        sensor_id='charging_port',
                        temperature=self.current_status.port_temperature
                    )
                if self.current_status.connector_temperature is not None:
                    self.can_protocol.send_temperature_data(
                        sensor_type='charging_connector',
                        sensor_id='charging_connector',
                        temperature=self.current_status.connector_temperature
                    )
        except Exception as e:
            self.logger.warning(f"Failed to send charging status to CAN: {e}")

    def is_charging(self) -> bool:
        """
        Check if currently charging.
        
        Returns:
            True if charging, False otherwise
        """
        return self.current_status.state in [
            ChargingState.CHARGING,
            ChargingState.CHARGING_AC,
            ChargingState.CHARGING_DC
        ]

    def is_connected(self) -> bool:
        """
        Check if charger is connected.
        
        Returns:
            True if connected, False otherwise
        """
        return self.current_status.state != ChargingState.DISCONNECTED

    def is_healthy(self) -> bool:
        """
        Check if charging system is healthy.
        
        Returns:
            True if healthy, False otherwise
        """
        if self.current_status.state in [ChargingState.ERROR, ChargingState.FAULT]:
            return False

        if self.current_status.temperature_c > self.max_temperature_c:
            return False

        if self.current_status.voltage_v > self.max_voltage_v:
            return False

        return True

    def get_estimated_time_remaining(self) -> Optional[float]:
        """
        Estimate time remaining to reach target SOC.
        
        Returns:
            Estimated time in seconds, or None if cannot estimate
        """
        if not self.is_charging() or not self.bms:
            return None

        if self.current_status.power_kw <= 0:
            return None

        bms_state = self.bms.get_state()
        soc_remaining = self.target_soc - bms_state.soc

        if soc_remaining <= 0:
            return 0.0

        # Estimate: energy needed / current power
        energy_needed_kwh = (soc_remaining / 100.0) * self.bms.config.capacity_kwh
        time_hours = energy_needed_kwh / self.current_status.power_kw
        time_seconds = time_hours * 3600.0

        return time_seconds

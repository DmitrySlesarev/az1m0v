"""Temperature sensor module for the EV project.
Provides comprehensive temperature monitoring for battery cells, coolant, motor, and charging system.
"""

import time
import logging
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum


class TemperatureSensorType(Enum):
    """Types of temperature sensors."""
    BATTERY_CELL_GROUP = "battery_cell_group"
    COOLANT_INLET = "coolant_inlet"
    COOLANT_OUTLET = "coolant_outlet"
    MOTOR_STATOR = "motor_stator"
    CHARGING_PORT = "charging_port"
    CHARGING_CONNECTOR = "charging_connector"


class SensorStatus(Enum):
    """Temperature sensor status."""
    HEALTHY = "healthy"
    WARNING = "warning"
    FAULT = "fault"
    DISCONNECTED = "disconnected"


@dataclass
class TemperatureReading:
    """Single temperature reading from a sensor."""
    sensor_id: str
    sensor_type: TemperatureSensorType
    temperature_c: float
    timestamp: float
    status: SensorStatus = SensorStatus.HEALTHY
    location: Optional[str] = None  # e.g., "cell_group_1", "stator_phase_a"


@dataclass
class TemperatureSensorConfig:
    """Configuration for a temperature sensor."""
    sensor_id: str
    sensor_type: TemperatureSensorType
    location: str
    min_temperature: float = -40.0
    max_temperature: float = 150.0
    warning_threshold_low: float = 0.0
    warning_threshold_high: float = 60.0
    fault_threshold_low: float = -50.0
    fault_threshold_high: float = 100.0
    update_interval_s: float = 0.1
    enabled: bool = True


class TemperatureSensor:
    """Individual temperature sensor interface."""

    def __init__(self, config: TemperatureSensorConfig):
        """Initialize temperature sensor.
        
        Args:
            config: Sensor configuration
        """
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{config.sensor_id}")
        self.last_reading: Optional[TemperatureReading] = None
        self.last_update_time = 0.0
        self.reading_count = 0
        self.fault_count = 0

    def read_temperature(self) -> Optional[TemperatureReading]:
        """Read current temperature from sensor.
        
        Returns:
            TemperatureReading if successful, None otherwise
        """
        if not self.config.enabled:
            return None

        current_time = time.time()
        
        # Check if enough time has passed since last reading
        if current_time - self.last_update_time < self.config.update_interval_s:
            return self.last_reading

        try:
            # In real implementation, this would read from hardware
            # For now, simulate reading with a default value
            temp = self._read_hardware()
            
            if temp is None:
                status = SensorStatus.DISCONNECTED
            elif temp < self.config.fault_threshold_low or temp > self.config.fault_threshold_high:
                status = SensorStatus.FAULT
                self.fault_count += 1
            elif temp < self.config.warning_threshold_low or temp > self.config.warning_threshold_high:
                status = SensorStatus.WARNING
            else:
                status = SensorStatus.HEALTHY

            reading = TemperatureReading(
                sensor_id=self.config.sensor_id,
                sensor_type=self.config.sensor_type,
                temperature_c=temp if temp is not None else 0.0,
                timestamp=current_time,
                status=status,
                location=self.config.location
            )

            self.last_reading = reading
            self.last_update_time = current_time
            self.reading_count += 1

            return reading

        except Exception as e:
            self.logger.error(f"Error reading sensor {self.config.sensor_id}: {e}")
            self.fault_count += 1
            return None

    def _read_hardware(self) -> Optional[float]:
        """Read temperature from hardware sensor.
        
        Returns:
            Temperature in Celsius, or None if sensor is disconnected
        """
        # Placeholder for actual hardware interface
        # In real implementation, this would interface with I2C/SPI sensors
        # For simulation, return a default temperature
        return 25.0

    def get_status(self) -> Dict:
        """Get sensor status information.
        
        Returns:
            Dictionary with sensor status
        """
        return {
            'sensor_id': self.config.sensor_id,
            'sensor_type': self.config.sensor_type.value,
            'location': self.config.location,
            'enabled': self.config.enabled,
            'last_reading': self.last_reading.temperature_c if self.last_reading else None,
            'last_update': self.last_update_time,
            'reading_count': self.reading_count,
            'fault_count': self.fault_count,
            'status': self.last_reading.status.value if self.last_reading else SensorStatus.DISCONNECTED.value
        }

    def set_temperature(self, temperature: float) -> None:
        """Set temperature value (for simulation/testing).
        
        Args:
            temperature: Temperature value to set
        """
        current_time = time.time()
        status = SensorStatus.HEALTHY
        
        if temperature < self.config.fault_threshold_low or temperature > self.config.fault_threshold_high:
            status = SensorStatus.FAULT
            self.fault_count += 1
        elif temperature < self.config.warning_threshold_low or temperature > self.config.warning_threshold_high:
            status = SensorStatus.WARNING

        self.last_reading = TemperatureReading(
            sensor_id=self.config.sensor_id,
            sensor_type=self.config.sensor_type,
            temperature_c=temperature,
            timestamp=current_time,
            status=status,
            location=self.config.location
        )
        self.last_update_time = current_time
        self.reading_count += 1


class TemperatureSensorManager:
    """Manager for multiple temperature sensors across the EV system."""

    def __init__(self, config: Dict):
        """Initialize temperature sensor manager.
        
        Args:
            config: Configuration dictionary with sensor parameters
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.sensors: Dict[str, TemperatureSensor] = {}
        self.sensor_groups: Dict[str, List[str]] = {}  # Group name -> list of sensor IDs

        # Initialize sensors from config
        self._initialize_sensors()

    def _initialize_sensors(self) -> None:
        """Initialize all sensors from configuration."""
        # Battery cell group sensors
        cell_count = self.config.get('battery', {}).get('cell_count', 96)
        cells_per_group = self.config.get('temperature_sensors', {}).get('cells_per_group', 12)
        num_cell_groups = max(1, (cell_count + cells_per_group - 1) // cells_per_group)

        for i in range(num_cell_groups):
            sensor_id = f"battery_cell_group_{i+1}"
            sensor_config = TemperatureSensorConfig(
                sensor_id=sensor_id,
                sensor_type=TemperatureSensorType.BATTERY_CELL_GROUP,
                location=f"cell_group_{i+1}",
                min_temperature=self.config.get('battery', {}).get('min_temperature', 0.0),
                max_temperature=self.config.get('battery', {}).get('max_temperature', 45.0),
                warning_threshold_low=5.0,
                warning_threshold_high=40.0,
                fault_threshold_low=-10.0,
                fault_threshold_high=50.0,
                update_interval_s=self.config.get('temperature_sensors', {}).get('update_interval_s', 0.1)
            )
            self.sensors[sensor_id] = TemperatureSensor(sensor_config)

        # Coolant sensors
        if self.config.get('temperature_sensors', {}).get('coolant_enabled', True):
            inlet_config = TemperatureSensorConfig(
                sensor_id="coolant_inlet",
                sensor_type=TemperatureSensorType.COOLANT_INLET,
                location="coolant_inlet",
                min_temperature=-20.0,
                max_temperature=80.0,
                warning_threshold_low=0.0,
                warning_threshold_high=60.0,
                fault_threshold_low=-30.0,
                fault_threshold_high=90.0,
                update_interval_s=self.config.get('temperature_sensors', {}).get('update_interval_s', 0.1)
            )
            self.sensors["coolant_inlet"] = TemperatureSensor(inlet_config)

            outlet_config = TemperatureSensorConfig(
                sensor_id="coolant_outlet",
                sensor_type=TemperatureSensorType.COOLANT_OUTLET,
                location="coolant_outlet",
                min_temperature=-20.0,
                max_temperature=80.0,
                warning_threshold_low=0.0,
                warning_threshold_high=60.0,
                fault_threshold_low=-30.0,
                fault_threshold_high=90.0,
                update_interval_s=self.config.get('temperature_sensors', {}).get('update_interval_s', 0.1)
            )
            self.sensors["coolant_outlet"] = TemperatureSensor(outlet_config)

        # Motor stator sensors
        if self.config.get('temperature_sensors', {}).get('motor_stator_enabled', True):
            num_stator_sensors = self.config.get('temperature_sensors', {}).get('motor_stator_sensors', 3)
            for i in range(num_stator_sensors):
                sensor_id = f"motor_stator_{i+1}"
                sensor_config = TemperatureSensorConfig(
                    sensor_id=sensor_id,
                    sensor_type=TemperatureSensorType.MOTOR_STATOR,
                    location=f"stator_phase_{chr(65+i)}",  # A, B, C
                    min_temperature=-20.0,
                    max_temperature=120.0,
                    warning_threshold_low=0.0,
                    warning_threshold_high=80.0,
                    fault_threshold_low=-30.0,
                    fault_threshold_high=150.0,
                    update_interval_s=self.config.get('temperature_sensors', {}).get('update_interval_s', 0.1)
                )
                self.sensors[sensor_id] = TemperatureSensor(sensor_config)

        # Charging port/connector sensors
        if self.config.get('temperature_sensors', {}).get('charging_enabled', True):
            port_config = TemperatureSensorConfig(
                sensor_id="charging_port",
                sensor_type=TemperatureSensorType.CHARGING_PORT,
                location="charging_port",
                min_temperature=-20.0,
                max_temperature=80.0,
                warning_threshold_low=0.0,
                warning_threshold_high=60.0,
                fault_threshold_low=-30.0,
                fault_threshold_high=100.0,
                update_interval_s=self.config.get('temperature_sensors', {}).get('update_interval_s', 0.1)
            )
            self.sensors["charging_port"] = TemperatureSensor(port_config)

            connector_config = TemperatureSensorConfig(
                sensor_id="charging_connector",
                sensor_type=TemperatureSensorType.CHARGING_CONNECTOR,
                location="charging_connector",
                min_temperature=-20.0,
                max_temperature=80.0,
                warning_threshold_low=0.0,
                warning_threshold_high=60.0,
                fault_threshold_low=-30.0,
                fault_threshold_high=100.0,
                update_interval_s=self.config.get('temperature_sensors', {}).get('update_interval_s', 0.1)
            )
            self.sensors["charging_connector"] = TemperatureSensor(connector_config)

        # Organize sensors into groups
        self.sensor_groups['battery_cell_groups'] = [
            sid for sid in self.sensors.keys() if sid.startswith('battery_cell_group_')
        ]
        self.sensor_groups['coolant'] = [
            sid for sid in self.sensors.keys() if 'coolant' in sid
        ]
        self.sensor_groups['motor'] = [
            sid for sid in self.sensors.keys() if 'motor_stator' in sid
        ]
        self.sensor_groups['charging'] = [
            sid for sid in self.sensors.keys() if 'charging' in sid
        ]

        self.logger.info(f"Initialized {len(self.sensors)} temperature sensors")

    def read_all_sensors(self) -> Dict[str, TemperatureReading]:
        """Read all enabled sensors.
        
        Returns:
            Dictionary mapping sensor_id to TemperatureReading
        """
        readings = {}
        for sensor_id, sensor in self.sensors.items():
            reading = sensor.read_temperature()
            if reading:
                readings[sensor_id] = reading
        return readings

    def read_sensor(self, sensor_id: str) -> Optional[TemperatureReading]:
        """Read a specific sensor.
        
        Args:
            sensor_id: ID of the sensor to read
            
        Returns:
            TemperatureReading if successful, None otherwise
        """
        if sensor_id not in self.sensors:
            self.logger.warning(f"Sensor {sensor_id} not found")
            return None
        return self.sensors[sensor_id].read_temperature()

    def read_sensor_group(self, group_name: str) -> Dict[str, TemperatureReading]:
        """Read all sensors in a group.
        
        Args:
            group_name: Name of the sensor group
            
        Returns:
            Dictionary mapping sensor_id to TemperatureReading
        """
        if group_name not in self.sensor_groups:
            self.logger.warning(f"Sensor group {group_name} not found")
            return {}

        readings = {}
        for sensor_id in self.sensor_groups[group_name]:
            reading = self.read_sensor(sensor_id)
            if reading:
                readings[sensor_id] = reading
        return readings

    def get_battery_cell_temperatures(self) -> List[float]:
        """Get temperatures from all battery cell group sensors.
        
        Returns:
            List of temperatures in Celsius
        """
        readings = self.read_sensor_group('battery_cell_groups')
        return [r.temperature_c for r in readings.values()]

    def get_coolant_temperatures(self) -> Dict[str, float]:
        """Get coolant inlet and outlet temperatures.
        
        Returns:
            Dictionary with 'inlet' and 'outlet' temperatures
        """
        readings = self.read_sensor_group('coolant')
        result = {}
        for sensor_id, reading in readings.items():
            if 'inlet' in sensor_id:
                result['inlet'] = reading.temperature_c
            elif 'outlet' in sensor_id:
                result['outlet'] = reading.temperature_c
        return result

    def get_motor_stator_temperatures(self) -> List[float]:
        """Get temperatures from all motor stator sensors.
        
        Returns:
            List of stator temperatures in Celsius
        """
        readings = self.read_sensor_group('motor')
        return [r.temperature_c for r in readings.values()]

    def get_charging_temperatures(self) -> Dict[str, float]:
        """Get charging port and connector temperatures.
        
        Returns:
            Dictionary with 'port' and 'connector' temperatures
        """
        readings = self.read_sensor_group('charging')
        result = {}
        for sensor_id, reading in readings.items():
            if 'port' in sensor_id:
                result['port'] = reading.temperature_c
            elif 'connector' in sensor_id:
                result['connector'] = reading.temperature_c
        return result

    def get_sensor(self, sensor_id: str) -> Optional[TemperatureSensor]:
        """Get a sensor instance by ID.
        
        Args:
            sensor_id: ID of the sensor
            
        Returns:
            TemperatureSensor instance or None
        """
        return self.sensors.get(sensor_id)

    def get_all_sensors_status(self) -> Dict[str, Dict]:
        """Get status of all sensors.
        
        Returns:
            Dictionary mapping sensor_id to status dictionary
        """
        return {sensor_id: sensor.get_status() for sensor_id, sensor in self.sensors.items()}

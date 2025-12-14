"""Unit tests for Temperature Sensor module."""

import pytest
import time
from unittest.mock import Mock, patch
from sensors.temperature import (
    TemperatureSensor,
    TemperatureSensorManager,
    TemperatureSensorConfig,
    TemperatureSensorType,
    SensorStatus,
    TemperatureReading
)


class TestTemperatureSensorConfig:
    """Test TemperatureSensorConfig dataclass."""

    def test_config_creation(self):
        """Test creating a TemperatureSensorConfig."""
        config = TemperatureSensorConfig(
            sensor_id="test_sensor",
            sensor_type=TemperatureSensorType.BATTERY_CELL_GROUP,
            location="cell_group_1"
        )
        assert config.sensor_id == "test_sensor"
        assert config.sensor_type == TemperatureSensorType.BATTERY_CELL_GROUP
        assert config.location == "cell_group_1"
        assert config.min_temperature == -40.0
        assert config.max_temperature == 150.0

    def test_config_custom_limits(self):
        """Test TemperatureSensorConfig with custom limits."""
        config = TemperatureSensorConfig(
            sensor_id="test_sensor",
            sensor_type=TemperatureSensorType.BATTERY_CELL_GROUP,
            location="cell_group_1",
            min_temperature=0.0,
            max_temperature=50.0,
            warning_threshold_low=5.0,
            warning_threshold_high=45.0
        )
        assert config.min_temperature == 0.0
        assert config.max_temperature == 50.0
        assert config.warning_threshold_low == 5.0
        assert config.warning_threshold_high == 45.0


class TestTemperatureSensor:
    """Test TemperatureSensor class."""

    def test_sensor_creation(self):
        """Test creating a TemperatureSensor."""
        config = TemperatureSensorConfig(
            sensor_id="test_sensor",
            sensor_type=TemperatureSensorType.BATTERY_CELL_GROUP,
            location="cell_group_1"
        )
        sensor = TemperatureSensor(config)
        assert sensor.config == config
        assert sensor.last_reading is None
        assert sensor.reading_count == 0

    def test_read_temperature_simulation(self):
        """Test reading temperature in simulation mode."""
        config = TemperatureSensorConfig(
            sensor_id="test_sensor",
            sensor_type=TemperatureSensorType.BATTERY_CELL_GROUP,
            location="cell_group_1",
            update_interval_s=0.01
        )
        sensor = TemperatureSensor(config)
        
        reading = sensor.read_temperature()
        assert reading is not None
        assert reading.sensor_id == "test_sensor"
        assert reading.temperature_c == 25.0  # Default simulation value
        assert reading.status == SensorStatus.HEALTHY
        assert sensor.reading_count == 1

    def test_set_temperature(self):
        """Test setting temperature manually."""
        config = TemperatureSensorConfig(
            sensor_id="test_sensor",
            sensor_type=TemperatureSensorType.BATTERY_CELL_GROUP,
            location="cell_group_1"
        )
        sensor = TemperatureSensor(config)
        
        sensor.set_temperature(30.0)
        assert sensor.last_reading is not None
        assert sensor.last_reading.temperature_c == 30.0
        assert sensor.last_reading.status == SensorStatus.HEALTHY
        assert sensor.reading_count == 1

    def test_temperature_warning(self):
        """Test temperature warning status."""
        config = TemperatureSensorConfig(
            sensor_id="test_sensor",
            sensor_type=TemperatureSensorType.BATTERY_CELL_GROUP,
            location="cell_group_1",
            warning_threshold_high=30.0
        )
        sensor = TemperatureSensor(config)
        
        sensor.set_temperature(35.0)
        assert sensor.last_reading.status == SensorStatus.WARNING

    def test_temperature_fault(self):
        """Test temperature fault status."""
        config = TemperatureSensorConfig(
            sensor_id="test_sensor",
            sensor_type=TemperatureSensorType.BATTERY_CELL_GROUP,
            location="cell_group_1",
            fault_threshold_high=50.0
        )
        sensor = TemperatureSensor(config)
        
        sensor.set_temperature(60.0)
        assert sensor.last_reading.status == SensorStatus.FAULT
        assert sensor.fault_count == 1

    def test_sensor_disabled(self):
        """Test reading from disabled sensor."""
        config = TemperatureSensorConfig(
            sensor_id="test_sensor",
            sensor_type=TemperatureSensorType.BATTERY_CELL_GROUP,
            location="cell_group_1",
            enabled=False
        )
        sensor = TemperatureSensor(config)
        
        reading = sensor.read_temperature()
        assert reading is None

    def test_update_interval(self):
        """Test sensor update interval."""
        config = TemperatureSensorConfig(
            sensor_id="test_sensor",
            sensor_type=TemperatureSensorType.BATTERY_CELL_GROUP,
            location="cell_group_1",
            update_interval_s=0.1
        )
        sensor = TemperatureSensor(config)
        
        reading1 = sensor.read_temperature()
        time.sleep(0.05)  # Less than interval
        reading2 = sensor.read_temperature()
        
        # Should return same reading due to interval
        assert reading1 == reading2

    def test_get_status(self):
        """Test getting sensor status."""
        config = TemperatureSensorConfig(
            sensor_id="test_sensor",
            sensor_type=TemperatureSensorType.BATTERY_CELL_GROUP,
            location="cell_group_1"
        )
        sensor = TemperatureSensor(config)
        sensor.set_temperature(25.0)
        
        status = sensor.get_status()
        assert status['sensor_id'] == "test_sensor"
        assert status['last_reading'] == 25.0
        assert status['reading_count'] == 1
        assert status['enabled'] is True


class TestTemperatureSensorManager:
    """Test TemperatureSensorManager class."""

    def test_manager_creation(self):
        """Test creating a TemperatureSensorManager."""
        config = {
            'battery': {
                'cell_count': 96
            },
            'temperature_sensors': {
                'cells_per_group': 12,
                'coolant_enabled': True,
                'motor_stator_enabled': True,
                'motor_stator_sensors': 3,
                'charging_enabled': True,
                'update_interval_s': 0.1
            }
        }
        manager = TemperatureSensorManager(config)
        assert len(manager.sensors) > 0

    def test_battery_cell_group_sensors(self):
        """Test battery cell group sensors initialization."""
        config = {
            'battery': {
                'cell_count': 96
            },
            'temperature_sensors': {
                'cells_per_group': 12,
                'coolant_enabled': False,
                'motor_stator_enabled': False,
                'charging_enabled': False
            }
        }
        manager = TemperatureSensorManager(config)
        
        # Should have 8 cell group sensors (96 cells / 12 per group)
        cell_group_sensors = [sid for sid in manager.sensors.keys() if 'battery_cell_group' in sid]
        assert len(cell_group_sensors) == 8

    def test_coolant_sensors(self):
        """Test coolant sensors initialization."""
        config = {
            'battery': {
                'cell_count': 96
            },
            'temperature_sensors': {
                'cells_per_group': 12,
                'coolant_enabled': True,
                'motor_stator_enabled': False,
                'charging_enabled': False
            }
        }
        manager = TemperatureSensorManager(config)
        
        assert "coolant_inlet" in manager.sensors
        assert "coolant_outlet" in manager.sensors

    def test_motor_stator_sensors(self):
        """Test motor stator sensors initialization."""
        config = {
            'battery': {
                'cell_count': 96
            },
            'temperature_sensors': {
                'cells_per_group': 12,
                'coolant_enabled': False,
                'motor_stator_enabled': True,
                'motor_stator_sensors': 3,
                'charging_enabled': False
            }
        }
        manager = TemperatureSensorManager(config)
        
        stator_sensors = [sid for sid in manager.sensors.keys() if 'motor_stator' in sid]
        assert len(stator_sensors) == 3

    def test_charging_sensors(self):
        """Test charging port/connector sensors initialization."""
        config = {
            'battery': {
                'cell_count': 96
            },
            'temperature_sensors': {
                'cells_per_group': 12,
                'coolant_enabled': False,
                'motor_stator_enabled': False,
                'charging_enabled': True
            }
        }
        manager = TemperatureSensorManager(config)
        
        assert "charging_port" in manager.sensors
        assert "charging_connector" in manager.sensors

    def test_read_all_sensors(self):
        """Test reading all sensors."""
        config = {
            'battery': {
                'cell_count': 96
            },
            'temperature_sensors': {
                'cells_per_group': 12,
                'coolant_enabled': True,
                'motor_stator_enabled': True,
                'motor_stator_sensors': 3,
                'charging_enabled': True,
                'update_interval_s': 0.01
            }
        }
        manager = TemperatureSensorManager(config)
        
        readings = manager.read_all_sensors()
        assert len(readings) > 0
        for sensor_id, reading in readings.items():
            assert isinstance(reading, TemperatureReading)
            assert reading.sensor_id == sensor_id

    def test_read_sensor(self):
        """Test reading a specific sensor."""
        config = {
            'battery': {
                'cell_count': 96
            },
            'temperature_sensors': {
                'cells_per_group': 12,
                'coolant_enabled': True
            }
        }
        manager = TemperatureSensorManager(config)
        
        reading = manager.read_sensor("coolant_inlet")
        assert reading is not None
        assert reading.sensor_id == "coolant_inlet"
        
        reading = manager.read_sensor("nonexistent")
        assert reading is None

    def test_read_sensor_group(self):
        """Test reading sensor groups."""
        config = {
            'battery': {
                'cell_count': 96
            },
            'temperature_sensors': {
                'cells_per_group': 12,
                'coolant_enabled': True
            }
        }
        manager = TemperatureSensorManager(config)
        
        readings = manager.read_sensor_group('coolant')
        assert len(readings) == 2
        assert "coolant_inlet" in readings
        assert "coolant_outlet" in readings

    def test_get_battery_cell_temperatures(self):
        """Test getting battery cell temperatures."""
        config = {
            'battery': {
                'cell_count': 96
            },
            'temperature_sensors': {
                'cells_per_group': 12
            }
        }
        manager = TemperatureSensorManager(config)
        
        temps = manager.get_battery_cell_temperatures()
        assert len(temps) == 8  # 8 cell groups
        assert all(isinstance(t, float) for t in temps)

    def test_get_coolant_temperatures(self):
        """Test getting coolant temperatures."""
        config = {
            'battery': {
                'cell_count': 96
            },
            'temperature_sensors': {
                'cells_per_group': 12,
                'coolant_enabled': True
            }
        }
        manager = TemperatureSensorManager(config)
        
        # Set temperatures manually
        manager.get_sensor("coolant_inlet").set_temperature(25.0)
        manager.get_sensor("coolant_outlet").set_temperature(30.0)
        
        temps = manager.get_coolant_temperatures()
        assert 'inlet' in temps
        assert 'outlet' in temps
        assert temps['inlet'] == 25.0
        assert temps['outlet'] == 30.0

    def test_get_motor_stator_temperatures(self):
        """Test getting motor stator temperatures."""
        config = {
            'battery': {
                'cell_count': 96
            },
            'temperature_sensors': {
                'cells_per_group': 12,
                'motor_stator_enabled': True,
                'motor_stator_sensors': 3
            }
        }
        manager = TemperatureSensorManager(config)
        
        temps = manager.get_motor_stator_temperatures()
        assert len(temps) == 3
        assert all(isinstance(t, float) for t in temps)

    def test_get_charging_temperatures(self):
        """Test getting charging temperatures."""
        config = {
            'battery': {
                'cell_count': 96
            },
            'temperature_sensors': {
                'cells_per_group': 12,
                'charging_enabled': True
            }
        }
        manager = TemperatureSensorManager(config)
        
        # Set temperatures manually
        manager.get_sensor("charging_port").set_temperature(35.0)
        manager.get_sensor("charging_connector").set_temperature(40.0)
        
        temps = manager.get_charging_temperatures()
        assert 'port' in temps
        assert 'connector' in temps
        assert temps['port'] == 35.0
        assert temps['connector'] == 40.0

    def test_get_sensor(self):
        """Test getting a sensor instance."""
        config = {
            'battery': {
                'cell_count': 96
            },
            'temperature_sensors': {
                'cells_per_group': 12,
                'coolant_enabled': True
            }
        }
        manager = TemperatureSensorManager(config)
        
        sensor = manager.get_sensor("coolant_inlet")
        assert sensor is not None
        assert isinstance(sensor, TemperatureSensor)
        
        sensor = manager.get_sensor("nonexistent")
        assert sensor is None

    def test_get_all_sensors_status(self):
        """Test getting all sensors status."""
        config = {
            'battery': {
                'cell_count': 96
            },
            'temperature_sensors': {
                'cells_per_group': 12,
                'coolant_enabled': True
            }
        }
        manager = TemperatureSensorManager(config)
        
        status = manager.get_all_sensors_status()
        assert len(status) > 0
        assert "coolant_inlet" in status
        assert status["coolant_inlet"]["sensor_type"] == TemperatureSensorType.COOLANT_INLET.value


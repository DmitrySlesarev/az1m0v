"""Unit tests for telemetry system."""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from communication.telemetry import (
    TelemetryState,
    TelemetryData,
    TelemetryConfig,
    TelemetrySystem
)


class TestTelemetryData:
    """Test TelemetryData dataclass."""

    def test_telemetry_data_creation(self):
        """Test creating telemetry data."""
        data = TelemetryData(
            timestamp=time.time(),
            vehicle_id="EV001",
            battery_soc=85.5,
            battery_voltage=400.0,
            battery_current=50.0,
            motor_speed_rpm=3000.0,
            motor_current=100.0,
            vehicle_speed_kmh=60.0,
            charging_power_kw=0.0,
            temperature=25.0
        )

        assert data.vehicle_id == "EV001"
        assert data.battery_soc == 85.5
        assert data.battery_voltage == 400.0
        assert data.motor_speed_rpm == 3000.0
        assert data.errors == []

    def test_telemetry_data_to_dict(self):
        """Test converting telemetry data to dictionary."""
        data = TelemetryData(
            timestamp=1000.0,
            vehicle_id="EV001",
            battery_soc=50.0,
            battery_voltage=380.0,
            battery_current=30.0,
            motor_speed_rpm=2000.0,
            motor_current=80.0,
            vehicle_speed_kmh=40.0,
            charging_power_kw=0.0,
            temperature=20.0,
            state="driving"
        )

        data_dict = data.to_dict()
        assert isinstance(data_dict, dict)
        assert data_dict['vehicle_id'] == "EV001"
        assert data_dict['battery_soc'] == 50.0
        assert data_dict['state'] == "driving"

    def test_telemetry_data_to_json(self):
        """Test converting telemetry data to JSON."""
        data = TelemetryData(
            timestamp=1000.0,
            vehicle_id="EV001",
            battery_soc=75.0,
            battery_voltage=390.0,
            battery_current=40.0,
            motor_speed_rpm=2500.0,
            motor_current=90.0,
            vehicle_speed_kmh=50.0,
            charging_power_kw=0.0,
            temperature=22.0
        )

        json_str = data.to_json()
        assert isinstance(json_str, str)
        assert "EV001" in json_str
        assert "75.0" in json_str

    def test_telemetry_data_with_location(self):
        """Test telemetry data with GPS location."""
        location = {"latitude": 37.7749, "longitude": -122.4194}
        data = TelemetryData(
            timestamp=time.time(),
            vehicle_id="EV001",
            battery_soc=80.0,
            battery_voltage=395.0,
            battery_current=45.0,
            motor_speed_rpm=2800.0,
            motor_current=95.0,
            vehicle_speed_kmh=55.0,
            charging_power_kw=0.0,
            temperature=23.0,
            location=location
        )

        assert data.location == location
        data_dict = data.to_dict()
        assert data_dict['location'] == location

    def test_telemetry_data_with_errors(self):
        """Test telemetry data with error list."""
        errors = ["Low battery", "High temperature"]
        data = TelemetryData(
            timestamp=time.time(),
            vehicle_id="EV001",
            battery_soc=20.0,
            battery_voltage=350.0,
            battery_current=10.0,
            motor_speed_rpm=0.0,
            motor_current=0.0,
            vehicle_speed_kmh=0.0,
            charging_power_kw=0.0,
            temperature=35.0,
            errors=errors
        )

        assert data.errors == errors
        assert len(data.errors) == 2


class TestTelemetryConfig:
    """Test TelemetryConfig class."""

    def test_telemetry_config_defaults(self):
        """Test telemetry config with default values."""
        config = TelemetryConfig()

        assert config.enabled is True
        assert config.server_url == ""
        assert config.server_port == 443
        assert config.update_interval_s == 10.0
        assert config.simulation_mode is False

    def test_telemetry_config_custom(self):
        """Test telemetry config with custom values."""
        config = TelemetryConfig(
            enabled=False,
            server_url="https://example.com",
            server_port=8080,
            update_interval_s=5.0,
            simulation_mode=True
        )

        assert config.enabled is False
        assert config.server_url == "https://example.com"
        assert config.server_port == 8080
        assert config.update_interval_s == 5.0
        assert config.simulation_mode is True


class TestTelemetrySystem:
    """Test TelemetrySystem class."""

    @pytest.fixture
    def telemetry_config(self):
        """Create a telemetry configuration for testing."""
        return {
            'enabled': True,
            'server_url': 'https://telemetry.example.com',
            'server_port': 443,
            'api_key': 'test_key',
            'update_interval_s': 10.0,
            'simulation_mode': True
        }

    @pytest.fixture
    def telemetry_system(self, telemetry_config):
        """Create a TelemetrySystem instance for testing."""
        return TelemetrySystem(config=telemetry_config, vehicle_id="TEST001")

    def test_telemetry_system_initialization(self, telemetry_config):
        """Test telemetry system initialization."""
        system = TelemetrySystem(config=telemetry_config, vehicle_id="EV001")

        assert system.vehicle_id == "EV001"
        assert system.config.enabled is True
        assert system.state == TelemetryState.SIMULATION

    def test_telemetry_system_disabled(self):
        """Test telemetry system when disabled."""
        config = {'enabled': False, 'simulation_mode': True}
        system = TelemetrySystem(config=config)

        assert system.config.enabled is False
        assert not system.is_enabled()

    def test_telemetry_connect_simulation(self, telemetry_system):
        """Test connecting telemetry in simulation mode."""
        result = telemetry_system.connect()

        assert result is True
        assert telemetry_system.state == TelemetryState.CONNECTED
        assert telemetry_system.is_connected()

    def test_telemetry_connect_disabled(self):
        """Test connecting telemetry when disabled."""
        config = {'enabled': False, 'simulation_mode': True}
        system = TelemetrySystem(config=config)

        result = system.connect()
        assert result is False

    def test_telemetry_disconnect(self, telemetry_system):
        """Test disconnecting telemetry."""
        telemetry_system.connect()
        assert telemetry_system.is_connected()

        telemetry_system.disconnect()
        assert telemetry_system.state == TelemetryState.DISCONNECTED
        assert not telemetry_system.is_connected()

    def test_send_data_success(self, telemetry_system):
        """Test sending telemetry data successfully."""
        telemetry_system.connect()

        result = telemetry_system.send_data(
            battery_soc=85.0,
            battery_voltage=400.0,
            battery_current=50.0,
            motor_speed_rpm=3000.0,
            motor_current=100.0,
            vehicle_speed_kmh=60.0,
            charging_power_kw=0.0,
            temperature=25.0,
            state="driving"
        )

        assert result is True
        assert telemetry_system.stats['packets_sent'] == 1
        assert telemetry_system.last_data is not None
        assert telemetry_system.last_data.battery_soc == 85.0

    def test_send_data_disabled(self):
        """Test sending data when telemetry is disabled."""
        config = {'enabled': False, 'simulation_mode': True}
        system = TelemetrySystem(config=config)

        result = system.send_data(battery_soc=50.0)
        assert result is False

    def test_send_data_auto_connect(self, telemetry_system):
        """Test that send_data automatically connects if needed."""
        assert telemetry_system.state == TelemetryState.SIMULATION

        result = telemetry_system.send_data(battery_soc=75.0)
        assert result is True
        assert telemetry_system.is_connected()

    def test_send_data_with_location(self, telemetry_system):
        """Test sending data with GPS location."""
        telemetry_system.connect()

        location = {"latitude": 37.7749, "longitude": -122.4194}
        result = telemetry_system.send_data(
            battery_soc=80.0,
            battery_voltage=395.0,
            battery_current=45.0,
            motor_speed_rpm=2800.0,
            motor_current=95.0,
            vehicle_speed_kmh=55.0,
            charging_power_kw=0.0,
            temperature=23.0,
            location=location
        )

        assert result is True
        assert telemetry_system.last_data.location == location

    def test_send_data_with_errors(self, telemetry_system):
        """Test sending data with error list."""
        telemetry_system.connect()

        errors = ["Low battery warning"]
        result = telemetry_system.send_data(
            battery_soc=20.0,
            battery_voltage=350.0,
            battery_current=10.0,
            motor_speed_rpm=0.0,
            motor_current=0.0,
            vehicle_speed_kmh=0.0,
            charging_power_kw=0.0,
            temperature=30.0,
            errors=errors
        )

        assert result is True
        assert telemetry_system.last_data.errors == errors

    def test_get_status(self, telemetry_system):
        """Test getting telemetry status."""
        telemetry_system.connect()
        telemetry_system.send_data(battery_soc=75.0)

        status = telemetry_system.get_status()

        assert status['state'] == TelemetryState.CONNECTED.value
        assert status['enabled'] is True
        assert status['simulation_mode'] is True
        assert status['connected'] is True
        assert 'stats' in status
        assert status['stats']['packets_sent'] == 1
        assert status['last_data'] is not None

    def test_statistics_tracking(self, telemetry_system):
        """Test that statistics are tracked correctly."""
        telemetry_system.connect()

        # Send multiple packets
        for i in range(3):
            telemetry_system.send_data(battery_soc=50.0 + i)

        stats = telemetry_system.stats
        assert stats['packets_sent'] == 3
        assert stats['last_send_time'] > 0
        assert stats['last_successful_send'] > 0

    def test_quectel_module_import_failure(self):
        """Test handling of missing Quectel module."""
        config = {'enabled': True, 'simulation_mode': False}
        system = TelemetrySystem(config=config)

        # Should fall back to simulation mode
        assert system.config.simulation_mode is True
        assert system.state == TelemetryState.SIMULATION

    @patch('communication.telemetry.time.time')
    def test_send_packet_timestamp(self, mock_time, telemetry_system):
        """Test that packets include correct timestamp."""
        mock_time.return_value = 1234.567
        telemetry_system.connect()

        telemetry_system.send_data(battery_soc=75.0)

        assert telemetry_system.last_data.timestamp == 1234.567


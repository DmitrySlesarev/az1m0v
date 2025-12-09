"""Functional tests for telemetry system integration."""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from communication.telemetry import TelemetrySystem, TelemetryState
from core.battery_management import BatteryManagementSystem
from core.motor_controller import VESCManager
from core.charging_system import ChargingSystem


class TestTelemetryIntegration:
    """Integration tests for telemetry system."""

    @pytest.fixture
    def telemetry_config(self):
        """Create telemetry configuration for testing."""
        return {
            'enabled': True,
            'server_url': 'https://telemetry.example.com',
            'server_port': 443,
            'api_key': 'test_key',
            'update_interval_s': 1.0,
            'simulation_mode': True
        }

    @pytest.fixture
    def telemetry_system(self, telemetry_config):
        """Create telemetry system instance."""
        return TelemetrySystem(config=telemetry_config, vehicle_id="TEST001")

    @pytest.fixture
    def mock_bms(self):
        """Create mock BMS for testing."""
        bms = Mock(spec=BatteryManagementSystem)
        bms_state = Mock()
        bms_state.soc = 85.0
        bms_state.voltage = 400.0
        bms_state.current = 50.0
        bms_state.temperatures = [25.0, 26.0, 24.0]
        bms.get_state.return_value = bms_state
        return bms

    @pytest.fixture
    def mock_motor_controller(self):
        """Create mock motor controller for testing."""
        motor = Mock(spec=VESCManager)
        motor.is_connected = True
        motor_status = Mock()
        motor_status.speed_rpm = 3000.0
        motor_status.current_a = 100.0
        motor.get_status.return_value = motor_status
        return motor

    @pytest.fixture
    def mock_charging_system(self):
        """Create mock charging system for testing."""
        charging = Mock(spec=ChargingSystem)
        charging.is_connected.return_value = True
        charging.is_charging.return_value = False
        charging_status = Mock()
        charging_status.power_kw = 0.0
        charging_status.state.value = "idle"
        charging.get_status.return_value = charging_status
        return charging

    def test_telemetry_with_bms_integration(self, telemetry_system, mock_bms):
        """Test telemetry integration with BMS."""
        telemetry_system.connect()

        bms_state = mock_bms.get_state()
        result = telemetry_system.send_data(
            battery_soc=bms_state.soc,
            battery_voltage=bms_state.voltage,
            battery_current=bms_state.current,
            temperature=sum(bms_state.temperatures) / len(bms_state.temperatures),
            motor_speed_rpm=0.0,
            motor_current=0.0,
            vehicle_speed_kmh=0.0,
            charging_power_kw=0.0
        )

        assert result is True
        assert telemetry_system.last_data.battery_soc == 85.0
        assert telemetry_system.last_data.battery_voltage == 400.0

    def test_telemetry_with_motor_controller_integration(
        self, telemetry_system, mock_motor_controller
    ):
        """Test telemetry integration with motor controller."""
        telemetry_system.connect()

        motor_status = mock_motor_controller.get_status()
        result = telemetry_system.send_data(
            battery_soc=80.0,
            battery_voltage=395.0,
            battery_current=45.0,
            motor_speed_rpm=motor_status.speed_rpm,
            motor_current=motor_status.current_a,
            vehicle_speed_kmh=60.0,
            charging_power_kw=0.0,
            temperature=25.0
        )

        assert result is True
        assert telemetry_system.last_data.motor_speed_rpm == 3000.0
        assert telemetry_system.last_data.motor_current == 100.0

    def test_telemetry_with_charging_system_integration(
        self, telemetry_system, mock_charging_system
    ):
        """Test telemetry integration with charging system."""
        telemetry_system.connect()

        charging_status = mock_charging_system.get_status()
        result = telemetry_system.send_data(
            battery_soc=50.0,
            battery_voltage=380.0,
            battery_current=30.0,
            motor_speed_rpm=0.0,
            motor_current=0.0,
            vehicle_speed_kmh=0.0,
            charging_power_kw=charging_status.power_kw,
            temperature=22.0,
            state=charging_status.state.value
        )

        assert result is True
        assert telemetry_system.last_data.charging_power_kw == 0.0
        assert telemetry_system.last_data.state == "idle"

    def test_telemetry_full_system_integration(
        self, telemetry_system, mock_bms, mock_motor_controller, mock_charging_system
    ):
        """Test telemetry with all systems integrated."""
        telemetry_system.connect()

        bms_state = mock_bms.get_state()
        motor_status = mock_motor_controller.get_status()
        charging_status = mock_charging_system.get_status()

        result = telemetry_system.send_data(
            battery_soc=bms_state.soc,
            battery_voltage=bms_state.voltage,
            battery_current=bms_state.current,
            motor_speed_rpm=motor_status.speed_rpm,
            motor_current=motor_status.current_a,
            vehicle_speed_kmh=60.0,
            charging_power_kw=charging_status.power_kw,
            temperature=sum(bms_state.temperatures) / len(bms_state.temperatures),
            state="driving"
        )

        assert result is True
        assert telemetry_system.last_data.battery_soc == 85.0
        assert telemetry_system.last_data.motor_speed_rpm == 3000.0
        assert telemetry_system.last_data.vehicle_speed_kmh == 60.0

    def test_telemetry_continuous_data_stream(self, telemetry_system):
        """Test continuous telemetry data streaming."""
        telemetry_system.connect()

        # Simulate multiple data sends
        for i in range(5):
            telemetry_system.send_data(
                battery_soc=80.0 - i,
                battery_voltage=400.0 - i * 2,
                battery_current=50.0,
                motor_speed_rpm=3000.0,
                motor_current=100.0,
                vehicle_speed_kmh=60.0,
                charging_power_kw=0.0,
                temperature=25.0
            )
            time.sleep(0.01)  # Small delay

        assert telemetry_system.stats['packets_sent'] == 5
        assert telemetry_system.stats['last_send_time'] > 0

    def test_telemetry_error_handling(self, telemetry_system):
        """Test telemetry error handling."""
        telemetry_system.connect()

        # Send data with errors
        errors = ["Low battery", "High temperature warning"]
        result = telemetry_system.send_data(
            battery_soc=15.0,
            battery_voltage=350.0,
            battery_current=5.0,
            motor_speed_rpm=0.0,
            motor_current=0.0,
            vehicle_speed_kmh=0.0,
            charging_power_kw=0.0,
            temperature=40.0,
            errors=errors
        )

        assert result is True
        assert len(telemetry_system.last_data.errors) == 2
        assert "Low battery" in telemetry_system.last_data.errors

    def test_telemetry_with_gps_location(self, telemetry_system):
        """Test telemetry with GPS location data."""
        telemetry_system.connect()

        location = {"latitude": 37.7749, "longitude": -122.4194, "altitude": 10.0}
        result = telemetry_system.send_data(
            battery_soc=75.0,
            battery_voltage=390.0,
            battery_current=40.0,
            motor_speed_rpm=2500.0,
            motor_current=90.0,
            vehicle_speed_kmh=50.0,
            charging_power_kw=0.0,
            temperature=23.0,
            location=location
        )

        assert result is True
        assert telemetry_system.last_data.location == location
        assert telemetry_system.last_data.location['latitude'] == 37.7749

    def test_telemetry_status_monitoring(self, telemetry_system):
        """Test telemetry status monitoring."""
        telemetry_system.connect()

        # Send some data
        telemetry_system.send_data(battery_soc=80.0, battery_voltage=395.0,
                                   battery_current=45.0, motor_speed_rpm=2800.0,
                                   motor_current=95.0, vehicle_speed_kmh=55.0,
                                   charging_power_kw=0.0, temperature=24.0)

        status = telemetry_system.get_status()
        assert status['connected'] is True
        assert status['stats']['packets_sent'] == 1
        assert status['last_data'] is not None

    def test_telemetry_disconnect_cleanup(self, telemetry_system):
        """Test telemetry disconnect and cleanup."""
        telemetry_system.connect()
        telemetry_system.send_data(battery_soc=75.0, battery_voltage=390.0,
                                   battery_current=40.0, motor_speed_rpm=2500.0,
                                   motor_current=90.0, vehicle_speed_kmh=50.0,
                                   charging_power_kw=0.0, temperature=23.0)

        assert telemetry_system.is_connected()

        telemetry_system.disconnect()
        assert telemetry_system.state == TelemetryState.DISCONNECTED
        assert not telemetry_system.is_connected()

    def test_telemetry_configuration_variations(self):
        """Test telemetry with different configurations."""
        # Test with SSL disabled
        config1 = {
            'enabled': True,
            'server_url': 'http://example.com',
            'use_ssl': False,
            'simulation_mode': True
        }
        system1 = TelemetrySystem(config=config1)
        assert system1.config.use_ssl is False

        # Test with custom retry settings
        config2 = {
            'enabled': True,
            'retry_attempts': 5,
            'retry_delay_s': 10.0,
            'simulation_mode': True
        }
        system2 = TelemetrySystem(config=config2)
        assert system2.config.retry_attempts == 5
        assert system2.config.retry_delay_s == 10.0


"""Functional tests for charging system integration scenarios."""

import pytest
import time
from unittest.mock import Mock, patch
from core.charging_system import (
    ChargingSystem, ChargingState, ConnectorType
)
from core.battery_management import BatteryManagementSystem
from core.motor_controller import VESCManager, MotorState
from communication.can_bus import CANBusInterface, EVCANProtocol


class TestChargingSystemIntegration:
    """Integration tests for charging system."""

    @pytest.fixture
    def can_interface(self):
        """Create a CANBusInterface instance for integration testing."""
        interface = CANBusInterface("can0", 500000)
        interface.connect()
        return interface

    @pytest.fixture
    def can_protocol(self, can_interface):
        """Create an EVCANProtocol instance for integration testing."""
        protocol = EVCANProtocol(can_interface)
        protocol.send_charger_status = Mock(return_value=True)
        return protocol

    @pytest.fixture
    def bms_config(self):
        """Create BMS configuration."""
        return {
            'capacity_kwh': 75.0,
            'max_charge_rate_kw': 150.0,
            'max_discharge_rate_kw': 200.0,
            'nominal_voltage': 400.0,
            'cell_count': 96
        }

    @pytest.fixture
    def bms(self, bms_config, can_protocol):
        """Create a BatteryManagementSystem instance."""
        return BatteryManagementSystem(bms_config, can_protocol=can_protocol)

    @pytest.fixture
    def motor_config(self):
        """Create motor controller configuration."""
        return {
            'max_power_kw': 150.0,
            'max_torque_nm': 320.0,
            'max_current_a': 200.0,
            'max_rpm': 10000.0,
            'max_temperature_c': 80.0,
            'min_voltage_v': 300.0,
            'max_voltage_v': 500.0
        }

    @pytest.fixture
    def motor_controller(self, motor_config, can_protocol):
        """Create a VESCManager instance."""
        return VESCManager(
            serial_port="/dev/ttyUSB0",
            can_protocol=can_protocol,
            config=motor_config
        )

    @pytest.fixture
    def charging_config(self):
        """Create charging system configuration."""
        return {
            'ac_max_power_kw': 11.0,
            'dc_max_power_kw': 150.0,
            'connector_type': 'CCS2',
            'fast_charge_enabled': True
        }

    @pytest.fixture
    def charging_system(self, charging_config, bms, motor_controller, can_protocol):
        """Create a ChargingSystem instance for integration testing."""
        return ChargingSystem(
            config=charging_config,
            bms=bms,
            motor_controller=motor_controller,
            can_protocol=can_protocol
        )

    @patch('core.motor_controller.VESC_AVAILABLE', False)
    def test_full_charging_workflow(self, charging_system, bms):
        """Test complete charging workflow."""
        # Connect charger
        connect_result = charging_system.connect_charger()
        assert connect_result is True
        assert charging_system.is_connected()

        # Update BMS state to allow charging
        # Use nominal voltage and set SOC manually to ensure healthy state
        bms.update_state(voltage=400.0, current=0.0, temperature=25.0)
        bms.state.soc = 50.0  # Set SOC manually for test
        bms.state.status = bms._determine_status()  # Update status based on state
        bms_state = bms.get_state()
        assert bms_state.soc < 100.0
        assert bms.can_charge(11.0)  # Verify BMS allows charging

        # Start charging with AC power (lower than DC max)
        start_result = charging_system.start_charging(power_kw=11.0, target_soc=90.0, use_fast_charge=False)
        assert start_result is True
        assert charging_system.is_charging()

        # Update charging status
        status = charging_system.update_status(
            voltage_v=400.0,
            current_a=50.0,
            temperature_c=30.0
        )
        assert status.state in [ChargingState.CHARGING, ChargingState.CHARGING_AC, ChargingState.CHARGING_DC]
        assert status.power_kw > 0

        # Stop charging
        stop_result = charging_system.stop_charging()
        assert stop_result is True
        assert not charging_system.is_charging()

        # Disconnect
        charging_system.disconnect_charger()
        assert not charging_system.is_connected()

    @patch('core.motor_controller.VESC_AVAILABLE', False)
    def test_charging_with_bms_integration(self, charging_system, bms):
        """Test charging system integration with BMS."""
        # Connect charger
        charging_system.connect_charger()

        # Set BMS to allow charging
        bms.update_state(voltage=400.0, current=0.0, temperature=25.0)
        bms.state.soc = 50.0  # Set SOC manually for test
        bms.state.status = bms._determine_status()  # Update status

        # Start charging
        result = charging_system.start_charging(power_kw=50.0)
        assert result is True

        # Update BMS state during charging
        bms.update_state(voltage=400.0, current=50.0, temperature=30.0)

        # Update charging status (should get data from BMS)
        status = charging_system.update_status()
        assert status.voltage_v == 400.0
        assert status.current_a == 50.0
        assert status.temperature_c == 30.0

    @patch('core.motor_controller.VESC_AVAILABLE', False)
    def test_charging_bms_rejection(self, charging_system, bms):
        """Test charging when BMS rejects."""
        charging_system.connect_charger()

        # Set BMS to reject charging (full battery)
        bms.update_state(voltage=400.0, current=0.0, temperature=25.0)
        bms.state.soc = 100.0  # Full battery
        bms.state.status = bms._determine_status()  # Update status

        # Try to start charging
        result = charging_system.start_charging()
        assert result is False
        assert charging_system.current_status.state == ChargingState.ERROR

    @patch('core.motor_controller.VESC_AVAILABLE', False)
    def test_charging_motor_safety_check(self, charging_system, motor_controller):
        """Test charging safety check with motor controller."""
        # Connect motor controller
        motor_controller.connect()
        motor_controller.set_rpm(1000.0)  # Motor running
        # Update status to ensure state is RUNNING
        motor_controller.get_status()
        # In simulation mode, state might be RUNNING or IDLE depending on current
        # Force it to RUNNING for test
        motor_controller.current_status.state = MotorState.RUNNING
        motor_controller.current_status.speed_rpm = 1000.0

        # Try to connect charger while motor is running
        result = charging_system.connect_charger()
        assert result is False

        # Stop motor and update state
        motor_controller.stop()
        motor_controller.current_status.state = MotorState.IDLE
        motor_controller.current_status.speed_rpm = 0.0
        motor_controller.current_status.current_a = 0.0

        # Now should be able to connect
        result = charging_system.connect_charger()
        assert result is True

    @patch('core.motor_controller.VESC_AVAILABLE', False)
    def test_ac_vs_dc_charging(self, charging_system, bms):
        """Test AC vs DC charging selection."""
        charging_system.connect_charger()
        bms.update_state(voltage=400.0, current=0.0, temperature=25.0)
        bms.state.soc = 50.0
        bms.state.status = bms._determine_status()

        # Start AC charging
        result = charging_system.start_charging(use_fast_charge=False)
        assert result is True
        assert charging_system.current_status.state == ChargingState.CHARGING_AC
        assert charging_system.current_status.is_fast_charge is False

        charging_system.stop_charging()

        # Start DC fast charging
        result = charging_system.start_charging(use_fast_charge=True)
        assert result is True
        assert charging_system.current_status.state == ChargingState.CHARGING_DC
        assert charging_system.current_status.is_fast_charge is True

    @patch('core.motor_controller.VESC_AVAILABLE', False)
    def test_charging_pause_resume(self, charging_system, bms):
        """Test charging pause and resume."""
        charging_system.connect_charger()
        bms.update_state(voltage=400.0, current=0.0, temperature=25.0)
        bms.state.soc = 50.0
        bms.state.status = bms._determine_status()

        # Start charging
        charging_system.start_charging(power_kw=50.0)
        assert charging_system.is_charging()

        # Pause
        result = charging_system.pause_charging()
        assert result is True
        assert charging_system.current_status.state == ChargingState.PAUSED

        # Resume
        result = charging_system.resume_charging()
        assert result is True
        assert charging_system.is_charging()

    @patch('core.motor_controller.VESC_AVAILABLE', False)
    def test_charging_completion(self, charging_system, bms):
        """Test charging completion detection."""
        charging_system.connect_charger()
        bms.update_state(voltage=400.0, current=0.0, temperature=25.0)
        bms.state.soc = 50.0
        bms.state.status = bms._determine_status()

        # Start charging with target SOC
        charging_system.start_charging(target_soc=90.0)
        charging_system.charging_start_time = time.time()

        # Simulate charging progress by updating BMS state
        # SOC will be calculated, but we can manually set it for testing
        for soc in [60, 70, 80, 90]:
            bms.update_state(voltage=400.0, current=50.0, temperature=30.0)
            bms.state.soc = float(soc)  # Manually set SOC for test
            status = charging_system.update_status()

            if soc >= 90:
                assert status.state == ChargingState.COMPLETE
            else:
                assert status.state in [ChargingState.CHARGING, ChargingState.CHARGING_AC, ChargingState.CHARGING_DC]

    @patch('core.motor_controller.VESC_AVAILABLE', False)
    def test_charging_safety_limits(self, charging_system, bms):
        """Test charging safety limit enforcement."""
        charging_system.connect_charger()
        bms.update_state(voltage=400.0, current=0.0, temperature=25.0)
        bms.state.soc = 50.0
        bms.state.status = bms._determine_status()

        # Start charging
        charging_system.start_charging()
        charging_system.charging_start_time = time.time()

        # Test overtemperature
        status = charging_system.update_status(
            voltage_v=400.0,
            current_a=50.0,
            temperature_c=70.0  # Exceeds max
        )
        assert status.state == ChargingState.ERROR
        assert status.error_code == "OVERTEMPERATURE"

        # Reset and test overvoltage
        charging_system.current_status.state = ChargingState.CHARGING
        charging_system.stop_charging = Mock(return_value=True)

        status = charging_system.update_status(voltage_v=550.0)  # Exceeds max
        assert status.state == ChargingState.ERROR
        assert status.error_code == "OVERVOLTAGE"

    @patch('core.motor_controller.VESC_AVAILABLE', False)
    def test_charging_can_integration(self, charging_system, can_protocol, bms):
        """Test charging system CAN bus integration."""
        charging_system.connect_charger()
        bms.update_state(voltage=400.0, current=0.0, temperature=25.0)
        bms.state.soc = 50.0
        bms.state.status = bms._determine_status()

        # Start charging
        charging_system.start_charging()

        # Update status (should send to CAN)
        charging_system.update_status(
            voltage_v=400.0,
            current_a=50.0,
            temperature_c=30.0
        )

        # Verify CAN protocol was called
        assert can_protocol.send_charger_status.called

    @patch('core.motor_controller.VESC_AVAILABLE', False)
    def test_charging_connector_types(self, charging_system, bms):
        """Test different connector types."""
        bms.update_state(voltage=400.0, current=0.0, temperature=25.0)
        bms.state.soc = 50.0
        bms.state.status = bms._determine_status()

        # Test CCS1
        charging_system.connect_charger(ConnectorType.CCS1)
        assert charging_system.current_status.connector_type == ConnectorType.CCS1
        assert charging_system._supports_fast_charge() is True

        # Test Type2 (AC only)
        charging_system.connect_charger(ConnectorType.TYPE2)
        assert charging_system.current_status.connector_type == ConnectorType.TYPE2
        assert charging_system._supports_fast_charge() is False

    @patch('core.motor_controller.VESC_AVAILABLE', False)
    def test_charging_statistics(self, charging_system, bms):
        """Test charging statistics tracking."""
        charging_system.connect_charger()
        bms.update_state(voltage=400.0, current=0.0, temperature=25.0)
        bms.state.soc = 50.0
        bms.state.status = bms._determine_status()

        # Start charging
        charging_system.start_charging(power_kw=50.0)
        start_time = time.time()
        charging_system.charging_start_time = start_time

        # Simulate charging over time
        for i in range(5):
            time.sleep(0.01)  # Small delay
            status = charging_system.update_status(
                voltage_v=400.0,
                current_a=50.0,
                temperature_c=30.0
            )

        # Check statistics
        assert status.energy_charged_kwh > 0
        assert status.charging_time_s > 0

    @patch('core.motor_controller.VESC_AVAILABLE', False)
    def test_charging_time_estimation(self, charging_system, bms):
        """Test charging time estimation."""
        charging_system.connect_charger()
        bms.update_state(voltage=400.0, current=0.0, temperature=25.0)
        bms.state.soc = 50.0
        bms.state.status = bms._determine_status()

        # Start charging
        charging_system.start_charging(power_kw=50.0, target_soc=100.0)
        charging_system.current_status.power_kw = 50.0

        # Get time estimate
        time_remaining = charging_system.get_estimated_time_remaining()
        assert time_remaining is not None
        assert time_remaining > 0

    @patch('core.motor_controller.VESC_AVAILABLE', False)
    def test_charging_error_recovery(self, charging_system, bms):
        """Test charging error recovery."""
        charging_system.connect_charger()
        bms.update_state(voltage=400.0, current=0.0, temperature=25.0)
        bms.state.soc = 50.0
        bms.state.status = bms._determine_status()

        # Start charging
        charging_system.start_charging()
        charging_system.charging_start_time = time.time()

        # Trigger error (overtemperature)
        charging_system.update_status(temperature_c=70.0)
        assert charging_system.current_status.state == ChargingState.ERROR

        # Reset error state
        charging_system.current_status.state = ChargingState.CONNECTED
        charging_system.current_status.error_code = None

        # Should be able to start charging again
        result = charging_system.start_charging()
        assert result is True

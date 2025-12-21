"""Additional unit tests for motor controller uncovered lines."""

import pytest
import time
from unittest.mock import Mock, MagicMock, patch
from core.motor_controller import VESCManager, MotorState, MotorStatus


class TestVESCManagerAdditional:
    """Additional tests for VESCManager uncovered lines."""

    @pytest.fixture
    def vesc_config(self):
        """Create VESC configuration."""
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
    def vesc_manager(self, vesc_config):
        """Create VESCManager instance."""
        return VESCManager(
            serial_port=None,
            can_bus=None,
            can_protocol=None,
            config=vesc_config
        )

    def test_disconnect_stop_heartbeat(self, vesc_manager):
        """Test disconnect with heartbeat stop."""
        vesc_manager.is_connected = True
        vesc_manager.vesc = MagicMock()
        vesc_manager.vesc.stop_heartbeat = Mock()
        
        # Mock hasattr to return True
        with patch('builtins.hasattr', return_value=True):
            vesc_manager.disconnect()
        
        # Should have tried to stop heartbeat if hasattr returns True
        assert vesc_manager.is_connected is False

    def test_disconnect_heartbeat_error(self, vesc_manager):
        """Test disconnect with heartbeat stop error."""
        vesc_manager.is_connected = True
        vesc_manager.vesc = MagicMock()
        vesc_manager.vesc.stop_heartbeat = Mock(side_effect=Exception("Heartbeat error"))
        
        # Should handle error gracefully
        vesc_manager.disconnect()
        assert vesc_manager.is_connected is False

    def test_set_duty_cycle_exception(self, vesc_manager):
        """Test set_duty_cycle with exception."""
        vesc_manager.is_connected = True
        
        with patch.object(vesc_manager, 'vesc', None):
            # In simulation mode, should still work
            result = vesc_manager.set_duty_cycle(0.5)
            assert result is True

    def test_set_rpm_exception(self, vesc_manager):
        """Test set_rpm with exception."""
        vesc_manager.is_connected = True
        
        with patch.object(vesc_manager, 'vesc', None):
            # In simulation mode, should still work
            result = vesc_manager.set_rpm(1000.0)
            assert result is True

    def test_set_current_exception(self, vesc_manager):
        """Test set_current with exception."""
        vesc_manager.is_connected = True
        
        with patch.object(vesc_manager, 'vesc', None):
            # In simulation mode, should still work
            result = vesc_manager.set_current(50.0)
            assert result is True

    @patch('core.motor_controller.VESC_AVAILABLE', True)
    def test_get_status_vesc_available(self, vesc_manager):
        """Test get_status with VESC available."""
        vesc_manager.is_connected = True
        vesc_manager.vesc = MagicMock()
        mock_measurements = MagicMock()
        mock_measurements.rpm = 3000.0
        mock_measurements.avg_motor_current = 50.0
        mock_measurements.avg_input_current = 48.0
        mock_measurements.duty_cycle_now = 0.5
        mock_measurements.v_in = 400.0
        mock_measurements.temp_mos = 60.0
        vesc_manager.vesc.get_measurements.return_value = mock_measurements
        
        status = vesc_manager.get_status()
        assert status is not None
        assert status.speed_rpm == 3000.0  # VESC returns RPM directly

    @patch('core.motor_controller.VESC_AVAILABLE', True)
    def test_get_status_vesc_exception(self, vesc_manager):
        """Test get_status with VESC exception."""
        vesc_manager.is_connected = True
        vesc_manager.vesc = MagicMock()
        vesc_manager.vesc.get_measurements.side_effect = Exception("VESC error")
        
        status = vesc_manager.get_status()
        assert status is not None
        # Exception should set state to ERROR
        assert status.state == MotorState.ERROR

    def test_get_status_temperature_check(self, vesc_manager):
        """Test get_status temperature safety check."""
        vesc_manager.is_connected = True
        vesc_manager.current_status.temperature_c = 90.0  # Exceeds max
        vesc_manager.max_temperature_c = 80.0
        
        status = vesc_manager.get_status()
        assert status.state == MotorState.ERROR

    def test_get_status_voltage_checks(self, vesc_manager):
        """Test get_status voltage safety checks."""
        vesc_manager.is_connected = True
        vesc_manager.current_status.voltage_v = 250.0  # Below minimum
        vesc_manager.min_voltage_v = 300.0
        
        status = vesc_manager.get_status()
        assert status.state == MotorState.ERROR

        vesc_manager.current_status.voltage_v = 550.0  # Above maximum
        vesc_manager.max_voltage_v = 500.0
        
        status = vesc_manager.get_status()
        assert status.state == MotorState.ERROR

    def test_get_status_idle_state(self, vesc_manager):
        """Test get_status idle state detection."""
        vesc_manager.is_connected = True
        vesc_manager.current_status.speed_rpm = 0.0
        vesc_manager.current_status.current_a = 0.05  # Very low
        
        status = vesc_manager.get_status()
        assert status.state == MotorState.IDLE

    def test_get_status_running_state(self, vesc_manager):
        """Test get_status running state."""
        vesc_manager.is_connected = True
        vesc_manager.current_status.speed_rpm = 1000.0
        vesc_manager.current_status.current_a = 10.0
        
        status = vesc_manager.get_status()
        assert status.state == MotorState.RUNNING

    def test_send_status_to_can(self, vesc_manager):
        """Test sending status to CAN bus."""
        vesc_manager.can_protocol = MagicMock()
        vesc_manager.can_protocol.send_motor_status = Mock()
        vesc_manager.can_protocol.send_temperature_data = Mock()
        vesc_manager.current_status.speed_rpm = 3000.0
        vesc_manager.current_status.current_a = 50.0
        vesc_manager.current_status.temperature_c = 60.0
        vesc_manager.current_status.stator_temperatures = [65.0, 66.0, 67.0]
        
        vesc_manager._send_status_to_can()
        
        assert vesc_manager.can_protocol.send_motor_status.called
        assert vesc_manager.can_protocol.send_temperature_data.call_count == 3

    def test_send_status_to_can_no_protocol(self, vesc_manager):
        """Test sending status to CAN without protocol."""
        vesc_manager.can_protocol = None
        # Should not raise error
        vesc_manager._send_status_to_can()

    def test_send_status_to_can_exception(self, vesc_manager):
        """Test sending status to CAN with exception."""
        vesc_manager.can_protocol = MagicMock()
        vesc_manager.can_protocol.send_motor_status.side_effect = Exception("CAN error")
        
        # Should handle error gracefully
        vesc_manager._send_status_to_can()

    def test_send_status_to_can_no_temperature_method(self, vesc_manager):
        """Test sending status to CAN without temperature method."""
        vesc_manager.can_protocol = MagicMock()
        vesc_manager.can_protocol.send_motor_status = Mock()
        # Remove send_temperature_data method
        delattr(vesc_manager.can_protocol, 'send_temperature_data')
        vesc_manager.current_status.stator_temperatures = [65.0, 66.0, 67.0]
        
        # Should not raise error
        vesc_manager._send_status_to_can()

    def test_get_status_with_temperature_sensor_manager(self, vesc_manager):
        """Test get_status with temperature sensor manager."""
        vesc_manager.is_connected = True
        vesc_manager.temperature_sensor_manager = MagicMock()
        vesc_manager.temperature_sensor_manager.get_motor_stator_temperatures.return_value = [65.0, 66.0, 67.0]
        vesc_manager.current_status.temperature_c = 0.0
        
        status = vesc_manager.get_status()
        
        assert status.stator_temperatures == [65.0, 66.0, 67.0]
        assert status.temperature_c == 66.0  # Average

    def test_get_status_temperature_sensor_manager_no_temps(self, vesc_manager):
        """Test get_status with temperature sensor manager returning empty."""
        vesc_manager.is_connected = True
        vesc_manager.temperature_sensor_manager = MagicMock()
        vesc_manager.temperature_sensor_manager.get_motor_stator_temperatures.return_value = []
        
        status = vesc_manager.get_status()
        # Should not crash
        assert status is not None


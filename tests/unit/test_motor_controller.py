"""Unit tests for motor controller system."""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from core.motor_controller import (
    VESCManager, MotorStatus, MotorState
)


class TestMotorStatus:
    """Test MotorStatus dataclass."""
    
    def test_motor_status_creation(self):
        """Test creating a motor status."""
        status = MotorStatus(
            speed_rpm=3000.0,
            current_a=50.0,
            voltage_v=400.0,
            duty_cycle=0.5,
            temperature_c=60.0,
            power_w=20000.0,
            state=MotorState.RUNNING
        )
        
        assert status.speed_rpm == 3000.0
        assert status.current_a == 50.0
        assert status.voltage_v == 400.0
        assert status.duty_cycle == 0.5
        assert status.temperature_c == 60.0
        assert status.power_w == 20000.0
        assert status.state == MotorState.RUNNING
    
    def test_motor_status_defaults(self):
        """Test motor status with default values."""
        status = MotorStatus()
        
        assert status.speed_rpm == 0.0
        assert status.current_a == 0.0
        assert status.voltage_v == 0.0
        assert status.duty_cycle == 0.0
        assert status.temperature_c == 0.0
        assert status.power_w == 0.0
        assert status.state == MotorState.DISCONNECTED


class TestMotorState:
    """Test MotorState enum."""
    
    def test_motor_state_values(self):
        """Test that all expected motor states are present."""
        expected_states = ["disconnected", "idle", "running", "braking", "error"]
        
        for expected_state in expected_states:
            assert hasattr(MotorState, expected_state.upper()), f"Missing state: {expected_state}"
    
    def test_motor_state_enum_values(self):
        """Test that enum values match expected strings."""
        assert MotorState.DISCONNECTED.value == "disconnected"
        assert MotorState.IDLE.value == "idle"
        assert MotorState.RUNNING.value == "running"
        assert MotorState.BRAKING.value == "braking"
        assert MotorState.ERROR.value == "error"


class TestVESCManager:
    """Test VESCManager class."""
    
    @pytest.fixture
    def mock_can_bus(self):
        """Create a mock CAN bus interface."""
        return Mock()
    
    @pytest.fixture
    def mock_can_protocol(self, mock_can_bus):
        """Create a mock CAN protocol."""
        protocol = Mock()
        protocol.send_motor_status = Mock(return_value=True)
        return protocol
    
    @pytest.fixture
    def config(self):
        """Create a test configuration."""
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
    def vesc_manager(self, config, mock_can_bus, mock_can_protocol):
        """Create a VESCManager instance for testing."""
        return VESCManager(
            serial_port="/dev/ttyUSB0",
            can_bus=mock_can_bus,
            can_protocol=mock_can_protocol,
            config=config
        )
    
    def test_vesc_manager_initialization(self, vesc_manager, config):
        """Test VESCManager initialization."""
        assert vesc_manager.serial_port == "/dev/ttyUSB0"
        assert vesc_manager.config == config
        assert not vesc_manager.is_connected
        assert vesc_manager.max_power_kw == 150.0
        assert vesc_manager.max_torque_nm == 320.0
        assert vesc_manager.max_current_a == 200.0
        assert vesc_manager.max_rpm == 10000.0
    
    def test_vesc_manager_initialization_defaults(self):
        """Test VESCManager initialization with defaults."""
        manager = VESCManager()
        
        assert manager.serial_port is None
        assert manager.config == {}
        assert manager.max_power_kw == 150.0  # Default value
        assert manager.max_torque_nm == 320.0  # Default value
    
    @patch('core.motor_controller.VESC_AVAILABLE', False)
    def test_connect_simulation_mode(self, vesc_manager):
        """Test connecting in simulation mode (VESC not available)."""
        result = vesc_manager.connect()
        
        assert result is True
        assert vesc_manager.is_connected is True
        assert vesc_manager.current_status.state == MotorState.IDLE
    
    @patch('core.motor_controller.VESC_AVAILABLE', True)
    @patch('core.motor_controller.VESC')
    def test_connect_with_vesc(self, mock_vesc_class, vesc_manager):
        """Test connecting with VESC library available."""
        mock_vesc_instance = Mock()
        mock_vesc_class.return_value = mock_vesc_instance
        
        result = vesc_manager.connect("/dev/ttyUSB1")
        
        assert result is True
        assert vesc_manager.is_connected is True
        assert vesc_manager.serial_port == "/dev/ttyUSB1"
        assert vesc_manager.vesc == mock_vesc_instance
    
    def test_connect_no_port(self, vesc_manager):
        """Test connecting without specifying port."""
        vesc_manager.serial_port = None
        result = vesc_manager.connect()
        
        assert result is False
        assert not vesc_manager.is_connected
    
    @patch('core.motor_controller.VESC_AVAILABLE', True)
    @patch('core.motor_controller.VESC')
    def test_connect_failure(self, mock_vesc_class, vesc_manager):
        """Test connection failure."""
        mock_vesc_class.side_effect = Exception("Connection failed")
        
        result = vesc_manager.connect()
        
        assert result is False
        assert not vesc_manager.is_connected
    
    def test_disconnect(self, vesc_manager):
        """Test disconnecting from VESC."""
        vesc_manager.is_connected = True
        vesc_manager.vesc = Mock()
        vesc_manager.vesc.stop_heartbeat = Mock()
        
        vesc_manager.disconnect()
        
        assert not vesc_manager.is_connected
        assert vesc_manager.vesc is None
        assert vesc_manager.current_status.state == MotorState.DISCONNECTED
    
    def test_set_duty_cycle_not_connected(self, vesc_manager):
        """Test setting duty cycle when not connected."""
        result = vesc_manager.set_duty_cycle(0.5)
        
        assert result is False
    
    def test_set_duty_cycle_invalid(self, vesc_manager):
        """Test setting invalid duty cycle."""
        vesc_manager.is_connected = True
        
        result = vesc_manager.set_duty_cycle(1.5)
        assert result is False
        
        result = vesc_manager.set_duty_cycle(-1.5)
        assert result is False
    
    @patch('core.motor_controller.VESC_AVAILABLE', False)
    def test_set_duty_cycle_simulation(self, vesc_manager):
        """Test setting duty cycle in simulation mode."""
        vesc_manager.connect()
        
        result = vesc_manager.set_duty_cycle(0.5)
        
        assert result is True
        assert vesc_manager.current_status.duty_cycle == 0.5
        assert vesc_manager.current_status.state == MotorState.RUNNING
    
    @patch('core.motor_controller.VESC_AVAILABLE', True)
    def test_set_duty_cycle_with_vesc(self, vesc_manager):
        """Test setting duty cycle with VESC."""
        vesc_manager.is_connected = True
        vesc_manager.vesc = Mock()
        vesc_manager.vesc.set_duty_cycle = Mock()
        
        result = vesc_manager.set_duty_cycle(0.5)
        
        assert result is True
        vesc_manager.vesc.set_duty_cycle.assert_called_once_with(0.5)
    
    def test_set_rpm_not_connected(self, vesc_manager):
        """Test setting RPM when not connected."""
        result = vesc_manager.set_rpm(3000.0)
        
        assert result is False
    
    def test_set_rpm_exceeds_max(self, vesc_manager):
        """Test setting RPM that exceeds maximum."""
        vesc_manager.is_connected = True
        
        result = vesc_manager.set_rpm(15000.0)
        
        assert result is True
        assert vesc_manager.current_status.speed_rpm == 10000.0  # Clamped
    
    @patch('core.motor_controller.VESC_AVAILABLE', False)
    def test_set_rpm_simulation(self, vesc_manager):
        """Test setting RPM in simulation mode."""
        vesc_manager.connect()
        
        result = vesc_manager.set_rpm(3000.0)
        
        assert result is True
        assert vesc_manager.current_status.speed_rpm == 3000.0
        assert vesc_manager.current_status.state == MotorState.RUNNING
    
    @patch('core.motor_controller.VESC_AVAILABLE', True)
    def test_set_rpm_with_vesc(self, vesc_manager):
        """Test setting RPM with VESC."""
        vesc_manager.is_connected = True
        vesc_manager.vesc = Mock()
        vesc_manager.vesc.set_rpm = Mock()
        
        result = vesc_manager.set_rpm(3000.0)
        
        assert result is True
        vesc_manager.vesc.set_rpm.assert_called_once_with(3000)
    
    def test_set_current_not_connected(self, vesc_manager):
        """Test setting current when not connected."""
        result = vesc_manager.set_current(50.0)
        
        assert result is False
    
    def test_set_current_exceeds_max(self, vesc_manager):
        """Test setting current that exceeds maximum."""
        vesc_manager.is_connected = True
        
        result = vesc_manager.set_current(250.0)
        
        assert result is True
        assert vesc_manager.current_status.current_a == 200.0  # Clamped
    
    @patch('core.motor_controller.VESC_AVAILABLE', False)
    def test_set_current_braking(self, vesc_manager):
        """Test setting negative current (braking)."""
        vesc_manager.connect()
        
        result = vesc_manager.set_current(-50.0)
        
        assert result is True
        assert vesc_manager.current_status.current_a == -50.0
        assert vesc_manager.current_status.state == MotorState.BRAKING
    
    @patch('core.motor_controller.VESC_AVAILABLE', True)
    def test_set_current_with_vesc(self, vesc_manager):
        """Test setting current with VESC."""
        vesc_manager.is_connected = True
        vesc_manager.vesc = Mock()
        vesc_manager.vesc.set_current = Mock()
        
        result = vesc_manager.set_current(50.0)
        
        assert result is True
        vesc_manager.vesc.set_current.assert_called_once_with(50.0)
    
    def test_stop(self, vesc_manager):
        """Test stopping the motor."""
        vesc_manager.is_connected = True
        vesc_manager.set_current = Mock(return_value=True)
        
        result = vesc_manager.stop()
        
        assert result is True
        vesc_manager.set_current.assert_called_once_with(0.0)
    
    def test_get_status_not_connected(self, vesc_manager):
        """Test getting status when not connected."""
        status = vesc_manager.get_status()
        
        assert status.state == MotorState.DISCONNECTED
    
    @patch('core.motor_controller.VESC_AVAILABLE', False)
    def test_get_status_simulation(self, vesc_manager, mock_can_protocol):
        """Test getting status in simulation mode."""
        vesc_manager.connect()
        
        status = vesc_manager.get_status()
        
        assert status.state == MotorState.IDLE
        assert status.timestamp > 0
        mock_can_protocol.send_motor_status.assert_called()
    
    @patch('core.motor_controller.VESC_AVAILABLE', True)
    def test_get_status_with_vesc(self, vesc_manager, mock_can_protocol):
        """Test getting status with VESC."""
        vesc_manager.is_connected = True
        vesc_manager.vesc = Mock()
        
        # Mock measurements
        mock_measurements = Mock()
        mock_measurements.rpm = 3000.0
        mock_measurements.avg_motor_current = 50.0
        mock_measurements.v_in = 400.0
        mock_measurements.duty_cycle_now = 0.5
        mock_measurements.temp_mos = 60.0
        
        vesc_manager.vesc.get_measurements.return_value = mock_measurements
        
        status = vesc_manager.get_status()
        
        assert status.speed_rpm == 3000.0
        assert status.current_a == 50.0
        assert status.voltage_v == 400.0
        assert status.duty_cycle == 0.5
        assert status.temperature_c == 60.0
        assert status.power_w > 0
        mock_can_protocol.send_motor_status.assert_called()
    
    def test_get_status_temperature_error(self, vesc_manager):
        """Test status with temperature error."""
        vesc_manager.is_connected = True
        vesc_manager.current_status.temperature_c = 90.0  # Exceeds max
        vesc_manager.max_temperature_c = 80.0
        
        status = vesc_manager.get_status()
        
        assert status.state == MotorState.ERROR
    
    def test_get_status_voltage_error(self, vesc_manager):
        """Test status with voltage error."""
        vesc_manager.is_connected = True
        vesc_manager.current_status.voltage_v = 250.0  # Below minimum
        vesc_manager.min_voltage_v = 300.0
        
        status = vesc_manager.get_status()
        
        assert status.state == MotorState.ERROR
    
    def test_calculate_torque(self, vesc_manager):
        """Test torque calculation."""
        vesc_manager.current_status.speed_rpm = 3000.0
        vesc_manager.current_status.power_w = 20000.0
        
        torque = vesc_manager._calculate_torque()
        
        assert torque > 0
        assert torque <= vesc_manager.max_torque_nm
    
    def test_calculate_torque_zero_rpm(self, vesc_manager):
        """Test torque calculation with zero RPM."""
        vesc_manager.current_status.speed_rpm = 0.0
        
        torque = vesc_manager._calculate_torque()
        
        assert torque == 0.0
    
    def test_is_healthy_not_connected(self, vesc_manager):
        """Test health check when not connected."""
        assert vesc_manager.is_healthy() is False
    
    def test_is_healthy_connected(self, vesc_manager):
        """Test health check when connected and healthy."""
        vesc_manager.is_connected = True
        vesc_manager.current_status.state = MotorState.RUNNING
        vesc_manager.current_status.temperature_c = 60.0
        vesc_manager.current_status.voltage_v = 400.0
        
        assert vesc_manager.is_healthy() is True
    
    def test_is_healthy_error_state(self, vesc_manager):
        """Test health check with error state."""
        vesc_manager.is_connected = True
        vesc_manager.current_status.state = MotorState.ERROR
        
        assert vesc_manager.is_healthy() is False
    
    def test_is_healthy_high_temperature(self, vesc_manager):
        """Test health check with high temperature."""
        vesc_manager.is_connected = True
        vesc_manager.current_status.state = MotorState.RUNNING
        vesc_manager.current_status.temperature_c = 90.0  # Exceeds max
        vesc_manager.max_temperature_c = 80.0
        
        assert vesc_manager.is_healthy() is False
    
    def test_is_healthy_low_voltage(self, vesc_manager):
        """Test health check with low voltage."""
        vesc_manager.is_connected = True
        vesc_manager.current_status.state = MotorState.RUNNING
        vesc_manager.current_status.voltage_v = 250.0  # Below minimum
        vesc_manager.min_voltage_v = 300.0
        
        assert vesc_manager.is_healthy() is False


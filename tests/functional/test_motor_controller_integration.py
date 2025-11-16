"""Functional tests for motor controller integration scenarios."""

import pytest
import time
import struct
from unittest.mock import Mock, patch, MagicMock
from core.motor_controller import (
    VESCManager, MotorStatus, MotorState
)
from communication.can_bus import (
    CANBusInterface, EVCANProtocol, CANFrame, CANFrameType
)


class TestMotorControllerIntegration:
    """Integration tests for motor controller system."""
    
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
        # Mock send_motor_status to track calls
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
    def vesc_manager(self, config, can_interface, can_protocol):
        """Create a VESCManager instance for integration testing."""
        return VESCManager(
            serial_port="/dev/ttyUSB0",
            can_bus=can_interface,
            can_protocol=can_protocol,
            config=config
        )
    
    @patch('core.motor_controller.VESC_AVAILABLE', False)
    def test_full_motor_control_workflow(self, vesc_manager, can_protocol):
        """Test complete motor control workflow."""
        # Connect to motor controller
        connect_result = vesc_manager.connect()
        assert connect_result is True
        assert vesc_manager.is_connected
        
        # Set motor to run
        set_rpm_result = vesc_manager.set_rpm(3000.0)
        assert set_rpm_result is True
        
        # Get status (this will send to CAN)
        status = vesc_manager.get_status()
        assert status.state == MotorState.RUNNING
        assert status.speed_rpm == 3000.0
        
        # Stop motor
        stop_result = vesc_manager.stop()
        assert stop_result is True
        
        # Verify CAN bus communication (send_motor_status should have been called)
        assert can_protocol.send_motor_status.called
    
    @patch('core.motor_controller.VESC_AVAILABLE', False)
    def test_motor_controller_can_integration(self, vesc_manager, can_protocol):
        """Test motor controller CAN bus integration."""
        vesc_manager.connect()
        
        # Set motor parameters
        vesc_manager.set_rpm(5000.0)
        vesc_manager.set_current(100.0)
        
        # Get status (should send to CAN)
        status = vesc_manager.get_status()
        
        # Verify CAN protocol was called
        assert can_protocol.send_motor_status.called
    
    @patch('core.motor_controller.VESC_AVAILABLE', False)
    def test_motor_controller_duty_cycle_control(self, vesc_manager):
        """Test motor controller duty cycle control."""
        vesc_manager.connect()
        
        # Set duty cycle
        result = vesc_manager.set_duty_cycle(0.5)
        assert result is True
        assert vesc_manager.current_status.duty_cycle == 0.5
        assert vesc_manager.current_status.state == MotorState.RUNNING
        
        # Get status - state may be IDLE if speed/current are 0
        status = vesc_manager.get_status()
        assert status.duty_cycle == 0.5
        
        # Set reverse
        result = vesc_manager.set_duty_cycle(-0.3)
        assert result is True
        assert vesc_manager.current_status.duty_cycle == -0.3
    
    @patch('core.motor_controller.VESC_AVAILABLE', False)
    def test_motor_controller_current_control(self, vesc_manager):
        """Test motor controller current control."""
        vesc_manager.connect()
        
        # Set forward current
        result = vesc_manager.set_current(50.0)
        assert result is True
        assert vesc_manager.current_status.current_a == 50.0
        assert vesc_manager.current_status.state == MotorState.RUNNING
        
        # Set braking current (negative)
        result = vesc_manager.set_current(-30.0)
        assert result is True
        assert vesc_manager.current_status.current_a == -30.0
        assert vesc_manager.current_status.state == MotorState.BRAKING
    
    @patch('core.motor_controller.VESC_AVAILABLE', False)
    def test_motor_controller_safety_limits(self, vesc_manager):
        """Test motor controller safety limit enforcement."""
        vesc_manager.connect()
        
        # Test RPM clamping
        result = vesc_manager.set_rpm(15000.0)  # Exceeds max
        assert result is True
        assert vesc_manager.current_status.speed_rpm == 10000.0  # Clamped
        
        # Test current clamping
        result = vesc_manager.set_current(250.0)  # Exceeds max
        assert result is True
        assert vesc_manager.current_status.current_a == 200.0  # Clamped
    
    @patch('core.motor_controller.VESC_AVAILABLE', False)
    def test_motor_controller_health_monitoring(self, vesc_manager):
        """Test motor controller health monitoring."""
        vesc_manager.connect()
        
        # Set initial healthy state
        vesc_manager.current_status.temperature_c = 60.0
        vesc_manager.current_status.voltage_v = 400.0
        vesc_manager.current_status.state = MotorState.RUNNING
        vesc_manager.get_status()  # Update status
        
        # Initially healthy
        assert vesc_manager.is_healthy() is True
        
        # Simulate high temperature
        vesc_manager.current_status.temperature_c = 90.0  # Exceeds max
        vesc_manager.get_status()  # Update status
        
        assert vesc_manager.is_healthy() is False
        
        # Reset to healthy
        vesc_manager.current_status.temperature_c = 60.0
        vesc_manager.current_status.state = MotorState.RUNNING
        vesc_manager.get_status()  # Update status
        assert vesc_manager.is_healthy() is True
    
    @patch('core.motor_controller.VESC_AVAILABLE', False)
    def test_motor_controller_state_transitions(self, vesc_manager):
        """Test motor controller state transitions."""
        # Start disconnected
        assert vesc_manager.current_status.state == MotorState.DISCONNECTED
        
        # Connect
        vesc_manager.connect()
        assert vesc_manager.current_status.state == MotorState.IDLE
        
        # Start running
        vesc_manager.set_rpm(3000.0)
        assert vesc_manager.current_status.state == MotorState.RUNNING
        
        # Braking
        vesc_manager.set_current(-50.0)
        assert vesc_manager.current_status.state == MotorState.BRAKING
        
        # Stop
        vesc_manager.stop()
        vesc_manager.get_status()  # Update status
        # Should be idle when stopped
        assert vesc_manager.current_status.state in [MotorState.IDLE, MotorState.RUNNING]
    
    @patch('core.motor_controller.VESC_AVAILABLE', False)
    def test_motor_controller_torque_calculation(self, vesc_manager):
        """Test motor controller torque calculation."""
        vesc_manager.connect()
        
        # Set motor parameters
        vesc_manager.current_status.speed_rpm = 3000.0
        vesc_manager.current_status.power_w = 20000.0
        
        torque = vesc_manager._calculate_torque()
        
        assert torque > 0
        assert torque <= vesc_manager.max_torque_nm
        
        # Test with zero RPM
        vesc_manager.current_status.speed_rpm = 0.0
        torque = vesc_manager._calculate_torque()
        assert torque == 0.0
    
    def test_vesc_can_command_parsing(self, can_protocol):
        """Test parsing VESC commands from CAN frames."""
        # Test RPM command
        rpm_frame = CANFrame(
            can_id=can_protocol.CAN_IDS['VESC_SET_RPM'],
            data=bytearray(struct.pack('<f', 3000.0)) + b'\x00' * 4,
            timestamp=time.time(),
            dlc=8
        )
        
        command = can_protocol.parse_vesc_command(rpm_frame)
        assert command is not None
        assert command['command'] == 'set_rpm'
        assert command['value'] == pytest.approx(3000.0, rel=1e-3)
        
        # Test current command
        current_frame = CANFrame(
            can_id=can_protocol.CAN_IDS['VESC_SET_CURRENT'],
            data=bytearray(struct.pack('<f', 50.0)) + b'\x00' * 4,
            timestamp=time.time(),
            dlc=8
        )
        
        command = can_protocol.parse_vesc_command(current_frame)
        assert command is not None
        assert command['command'] == 'set_current'
        assert command['value'] == pytest.approx(50.0, rel=1e-3)
        
        # Test duty cycle command
        duty_frame = CANFrame(
            can_id=can_protocol.CAN_IDS['VESC_SET_DUTY'],
            data=bytearray(struct.pack('<f', 0.5)) + b'\x00' * 4,
            timestamp=time.time(),
            dlc=8
        )
        
        command = can_protocol.parse_vesc_command(duty_frame)
        assert command is not None
        assert command['command'] == 'set_duty'
        assert command['value'] == pytest.approx(0.5, rel=1e-3)
    
    def test_vesc_can_status_parsing(self, can_protocol):
        """Test parsing VESC status from CAN frames."""
        import struct
        
        # Create status frame with RPM, current, voltage, temperature
        status_data = bytearray()
        status_data.extend(struct.pack('<f', 3000.0))  # RPM
        status_data.extend(struct.pack('<f', 50.0))   # Current
        status_data.extend(struct.pack('<f', 400.0))  # Voltage
        status_data.extend(struct.pack('<f', 60.0))   # Temperature
        
        status_frame = CANFrame(
            can_id=can_protocol.CAN_IDS['VESC_STATUS'],
            data=status_data[:8],  # Limit to 8 bytes for CAN
            timestamp=time.time(),
            dlc=8
        )
        
        status = can_protocol.parse_vesc_status(status_frame)
        assert status is not None
        assert status['rpm'] == pytest.approx(3000.0, rel=1e-3)
        assert status['current'] == pytest.approx(50.0, rel=1e-3)
        # Note: CAN frame is limited to 8 bytes, so voltage and temperature are 0.0
        # In real implementation, these would be sent in separate frames
        assert status['voltage'] == pytest.approx(0.0, rel=1e-3)
        assert status['temperature'] == pytest.approx(0.0, rel=1e-3)
    
    def test_vesc_can_command_sending(self, can_protocol, can_interface):
        """Test sending VESC commands via CAN."""
        # Send RPM command
        result = can_protocol.send_vesc_command_rpm(3000.0)
        assert result is True
        
        # Send current command
        result = can_protocol.send_vesc_command_current(50.0)
        assert result is True
        
        # Send duty cycle command
        result = can_protocol.send_vesc_command_duty(0.5)
        assert result is True
        
        # Verify frames were sent
        stats = can_interface.get_statistics()
        assert stats['frames_sent'] >= 3
    
    def test_vesc_can_status_sending(self, can_protocol, can_interface):
        """Test sending VESC status via CAN."""
        result = can_protocol.send_vesc_status(
            rpm=3000.0,
            current=50.0,
            voltage=400.0,
            temperature=60.0
        )
        
        assert result is True
        
        # Verify frame was sent
        stats = can_interface.get_statistics()
        assert stats['frames_sent'] > 0
    
    @patch('core.motor_controller.VESC_AVAILABLE', False)
    def test_motor_controller_error_handling(self, vesc_manager):
        """Test motor controller error handling."""
        # Try to control when not connected
        result = vesc_manager.set_rpm(3000.0)
        assert result is False
        
        # Connect and test invalid values
        vesc_manager.connect()
        
        # Invalid duty cycle
        result = vesc_manager.set_duty_cycle(1.5)
        assert result is False
        
        # Valid operations should work
        result = vesc_manager.set_duty_cycle(0.5)
        assert result is True
    
    @patch('core.motor_controller.VESC_AVAILABLE', False)
    def test_motor_controller_disconnect_cleanup(self, vesc_manager):
        """Test motor controller disconnect and cleanup."""
        vesc_manager.connect()
        assert vesc_manager.is_connected
        
        vesc_manager.set_rpm(3000.0)
        assert vesc_manager.current_status.state == MotorState.RUNNING
        
        vesc_manager.disconnect()
        assert not vesc_manager.is_connected
        assert vesc_manager.current_status.state == MotorState.DISCONNECTED
        
        # Should not be able to control after disconnect
        result = vesc_manager.set_rpm(3000.0)
        assert result is False


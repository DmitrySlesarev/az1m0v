"""Tests for motor controller torque calculation."""

import pytest
from unittest.mock import Mock
from core.motor_controller import VESCManager, MotorStatus, MotorState


class TestMotorControllerTorque:
    """Test motor controller torque calculation."""

    @pytest.fixture
    def vesc_manager(self):
        """Create VESCManager instance."""
        return VESCManager(
            serial_port=None,
            can_bus=None,
            can_protocol=None,
            config={
                'max_power_kw': 150.0,
                'max_torque_nm': 320.0,
                'max_current_a': 200.0,
                'max_rpm': 10000.0
            }
        )

    def test_calculate_torque_zero_rpm(self, vesc_manager):
        """Test torque calculation with zero RPM."""
        vesc_manager.current_status.speed_rpm = 0.0
        vesc_manager.current_status.power_w = 10000.0
        
        torque = vesc_manager._calculate_torque()
        assert torque == 0.0

    def test_calculate_torque_zero_power(self, vesc_manager):
        """Test torque calculation with zero power."""
        vesc_manager.current_status.speed_rpm = 3000.0
        vesc_manager.current_status.power_w = 0.0
        
        torque = vesc_manager._calculate_torque()
        assert torque == 0.0

    def test_calculate_torque_negative_power(self, vesc_manager):
        """Test torque calculation with negative power."""
        vesc_manager.current_status.speed_rpm = 3000.0
        vesc_manager.current_status.power_w = -1000.0
        
        torque = vesc_manager._calculate_torque()
        assert torque == 0.0

    def test_calculate_torque_normal(self, vesc_manager):
        """Test normal torque calculation."""
        vesc_manager.current_status.speed_rpm = 3000.0
        vesc_manager.current_status.power_w = 50000.0  # 50kW
        
        torque = vesc_manager._calculate_torque()
        # T = P / ω, where ω = 2π * RPM / 60
        # Expected: 50000 / (2 * π * 3000 / 60) ≈ 159.15 N⋅m
        assert torque > 0
        assert torque < vesc_manager.max_torque_nm

    def test_calculate_torque_max_clamp(self, vesc_manager):
        """Test torque calculation clamping to maximum."""
        vesc_manager.current_status.speed_rpm = 100.0  # Low RPM
        vesc_manager.current_status.power_w = 1000000.0  # Very high power
        
        torque = vesc_manager._calculate_torque()
        assert torque == vesc_manager.max_torque_nm

    def test_calculate_torque_negative_clamp(self, vesc_manager):
        """Test torque calculation clamping to negative maximum."""
        vesc_manager.current_status.speed_rpm = -100.0  # Reverse
        vesc_manager.current_status.power_w = 1000000.0  # Very high power
        
        torque = vesc_manager._calculate_torque()
        assert torque == -vesc_manager.max_torque_nm


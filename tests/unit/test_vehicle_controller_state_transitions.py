"""Tests for vehicle controller state transitions."""

import pytest
from unittest.mock import Mock
from core.vehicle_controller import VehicleController, VehicleState, VehicleConfig


class TestVehicleControllerStateTransitions:
    """Test vehicle controller state transitions."""

    @pytest.fixture
    def vehicle_controller(self):
        """Create vehicle controller instance."""
        config = {
            'max_speed_kmh': 120.0,
            'max_acceleration_ms2': 3.0,
            'max_deceleration_ms2': -5.0,
            'max_power_kw': 150.0,
            'efficiency_wh_per_km': 200.0,
            'weight_kg': 1500.0
        }
        return VehicleController(config=config)

    def test_can_transition_to_error(self, vehicle_controller):
        """Test transition to ERROR state."""
        vehicle_controller.current_status.state = VehicleState.PARKED
        
        result = vehicle_controller._can_transition_to_state(
            VehicleState.PARKED,
            VehicleState.ERROR
        )
        assert result is True

    def test_can_transition_to_emergency(self, vehicle_controller):
        """Test transition to EMERGENCY state."""
        vehicle_controller.current_status.state = VehicleState.DRIVING
        
        result = vehicle_controller._can_transition_to_state(
            VehicleState.DRIVING,
            VehicleState.EMERGENCY
        )
        assert result is True

    def test_can_transition_from_error(self, vehicle_controller):
        """Test transition from ERROR state."""
        vehicle_controller.current_status.state = VehicleState.ERROR
        
        result = vehicle_controller._can_transition_to_state(
            VehicleState.ERROR,
            VehicleState.PARKED
        )
        assert result is True

    def test_can_transition_from_error_to_standby(self, vehicle_controller):
        """Test transition from ERROR to STANDBY."""
        result = vehicle_controller._can_transition_to_state(
            VehicleState.ERROR,
            VehicleState.STANDBY
        )
        assert result is True

    def test_cannot_drive_while_charging(self, vehicle_controller):
        """Test cannot transition to DRIVING while charging."""
        vehicle_controller.charging_system = Mock()
        vehicle_controller.charging_system.is_charging.return_value = True
        
        result = vehicle_controller._can_transition_to_state(
            VehicleState.READY,
            VehicleState.DRIVING
        )
        assert result is False

    def test_cannot_charge_while_driving(self, vehicle_controller):
        """Test cannot transition to CHARGING while driving."""
        vehicle_controller.current_status.state = VehicleState.DRIVING
        
        result = vehicle_controller._can_transition_to_state(
            VehicleState.DRIVING,
            VehicleState.CHARGING
        )
        assert result is False

    def test_valid_transition_parked_to_ready(self, vehicle_controller):
        """Test valid transition from PARKED to READY."""
        result = vehicle_controller._can_transition_to_state(
            VehicleState.PARKED,
            VehicleState.READY
        )
        assert result is True

    def test_valid_transition_ready_to_driving(self, vehicle_controller):
        """Test valid transition from READY to DRIVING."""
        vehicle_controller.charging_system = Mock()
        vehicle_controller.charging_system.is_charging.return_value = False
        
        result = vehicle_controller._can_transition_to_state(
            VehicleState.READY,
            VehicleState.DRIVING
        )
        assert result is True

    def test_invalid_transition_driving_to_charging(self, vehicle_controller):
        """Test invalid transition from DRIVING to CHARGING."""
        vehicle_controller.current_status.state = VehicleState.DRIVING
        
        result = vehicle_controller._can_transition_to_state(
            VehicleState.DRIVING,
            VehicleState.CHARGING
        )
        assert result is False

    def test_start_driving_bms_fault(self, vehicle_controller):
        """Test start_driving with BMS fault."""
        vehicle_controller.bms = Mock()
        bms_state = Mock()
        bms_state.status.value = 'fault'
        vehicle_controller.bms.get_state.return_value = bms_state
        
        result = vehicle_controller.start_driving()
        assert result is False
        assert vehicle_controller.current_status.state == VehicleState.ERROR

    def test_start_driving_low_soc(self, vehicle_controller):
        """Test start_driving with low SOC."""
        vehicle_controller.bms = Mock()
        bms_state = Mock()
        bms_state.status.value = 'healthy'
        bms_state.soc = 3.0  # Below 5%
        vehicle_controller.bms.get_state.return_value = bms_state
        
        result = vehicle_controller.start_driving()
        assert result is False
        assert vehicle_controller.current_status.state == VehicleState.ERROR


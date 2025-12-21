"""Additional tests for vehicle controller uncovered lines."""

import pytest
from unittest.mock import Mock, MagicMock
from core.vehicle_controller import VehicleController, VehicleState, VehicleConfig


class TestVehicleControllerAdditional:
    """Additional tests for vehicle controller."""

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

    def test_start_charging_no_charging_system(self, vehicle_controller):
        """Test start_charging without charging system."""
        vehicle_controller.charging_system = None
        
        result = vehicle_controller.start_charging()
        assert result is False

    def test_start_charging_connect_fails(self, vehicle_controller):
        """Test start_charging when connect fails."""
        vehicle_controller.charging_system = Mock()
        vehicle_controller.charging_system.is_connected.return_value = False
        vehicle_controller.charging_system.connect_charger.return_value = False
        
        result = vehicle_controller.start_charging()
        assert result is False

    def test_start_charging_start_fails(self, vehicle_controller):
        """Test start_charging when start fails."""
        vehicle_controller.charging_system = Mock()
        vehicle_controller.charging_system.is_connected.return_value = True
        vehicle_controller.charging_system.start_charging.return_value = False
        
        result = vehicle_controller.start_charging()
        assert result is False

    def test_stop_charging_no_charging_system(self, vehicle_controller):
        """Test stop_charging without charging system."""
        vehicle_controller.charging_system = None
        
        result = vehicle_controller.stop_charging()
        assert result is False

    def test_stop_charging_stop_fails(self, vehicle_controller):
        """Test stop_charging when stop fails."""
        vehicle_controller.charging_system = Mock()
        vehicle_controller.charging_system.stop_charging.return_value = False
        
        result = vehicle_controller.stop_charging()
        assert result is False

    def test_update_status_range_calculation(self, vehicle_controller):
        """Test update_status range calculation."""
        vehicle_controller.bms = Mock()
        bms_state = Mock()
        bms_state.soc = 80.0
        bms_state.status.value = 'healthy'
        vehicle_controller.bms.get_state.return_value = bms_state
        vehicle_controller.bms.config.capacity_kwh = 75.0
        
        status = vehicle_controller.update_status()
        
        assert status.range_km > 0

    def test_update_status_range_zero_soc(self, vehicle_controller):
        """Test update_status with zero SOC."""
        vehicle_controller.bms = Mock()
        bms_state = Mock()
        bms_state.soc = 0.0
        bms_state.status.value = 'healthy'
        vehicle_controller.bms.get_state.return_value = bms_state
        
        status = vehicle_controller.update_status()
        
        assert status.range_km == 0.0

    def test_update_status_bms_fault_driving(self, vehicle_controller):
        """Test update_status with BMS fault during driving."""
        vehicle_controller.current_status.state = VehicleState.DRIVING
        vehicle_controller.bms = Mock()
        # Configure BMS mock with config
        vehicle_controller.bms.config = Mock()
        vehicle_controller.bms.config.capacity_kwh = 50.0
        bms_state = Mock()
        bms_state.soc = 50.0
        bms_state.status.value = 'fault'
        vehicle_controller.bms.get_state.return_value = bms_state
        
        status = vehicle_controller.update_status()
        
        assert vehicle_controller.current_status.state == VehicleState.ERROR

    def test_update_status_charging_state_sync(self, vehicle_controller):
        """Test update_status charging state synchronization."""
        vehicle_controller.current_status.state = VehicleState.READY
        vehicle_controller.charging_system = Mock()
        charging_status = Mock()
        charging_status.state.value = 'charging'
        vehicle_controller.charging_system.get_status.return_value = charging_status
        
        status = vehicle_controller.update_status()
        
        assert vehicle_controller.current_status.state == VehicleState.CHARGING

    def test_update_status_charging_complete(self, vehicle_controller):
        """Test update_status when charging completes."""
        vehicle_controller.current_status.state = VehicleState.CHARGING
        vehicle_controller.charging_system = Mock()
        charging_status = Mock()
        charging_status.state.value = 'complete'
        vehicle_controller.charging_system.get_status.return_value = charging_status
        
        status = vehicle_controller.update_status()
        
        assert vehicle_controller.current_status.state == VehicleState.PARKED

    def test_update_status_charging_error(self, vehicle_controller):
        """Test update_status when charging has error."""
        vehicle_controller.current_status.state = VehicleState.CHARGING
        vehicle_controller.charging_system = Mock()
        charging_status = Mock()
        charging_status.state.value = 'error'
        vehicle_controller.charging_system.get_status.return_value = charging_status
        
        status = vehicle_controller.update_status()
        
        assert vehicle_controller.current_status.state == VehicleState.ERROR

    def test_send_status_to_can(self, vehicle_controller):
        """Test sending status to CAN bus."""
        vehicle_controller.can_protocol = Mock()
        vehicle_controller.can_protocol.send_vehicle_status = Mock()
        
        vehicle_controller._send_status_to_can()
        
        assert vehicle_controller.can_protocol.send_vehicle_status.called

    def test_send_status_to_can_no_protocol(self, vehicle_controller):
        """Test sending status to CAN without protocol."""
        vehicle_controller.can_protocol = None
        
        # Should not raise error
        vehicle_controller._send_status_to_can()

    def test_send_status_to_can_no_method(self, vehicle_controller):
        """Test sending status to CAN without method."""
        vehicle_controller.can_protocol = Mock()
        # Remove send_vehicle_status method
        delattr(vehicle_controller.can_protocol, 'send_vehicle_status')
        
        # Should not raise error
        vehicle_controller._send_status_to_can()

    def test_send_status_to_can_exception(self, vehicle_controller):
        """Test sending status to CAN with exception."""
        vehicle_controller.can_protocol = Mock()
        vehicle_controller.can_protocol.send_vehicle_status.side_effect = Exception("CAN error")
        
        # Should handle error gracefully
        vehicle_controller._send_status_to_can()


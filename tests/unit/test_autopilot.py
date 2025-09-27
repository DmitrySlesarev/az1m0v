"""Unit tests for autopilot system."""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from ai.autopilot import (
    AutopilotSystem, DrivingMode, VehicleState, EnvironmentState, DrivingCommand
)


class TestDrivingMode:
    """Test DrivingMode enum."""
    
    def test_driving_mode_values(self):
        """Test that all expected driving modes are present."""
        expected_modes = ["manual", "assist", "autopilot", "emergency"]
        
        for expected_mode in expected_modes:
            assert hasattr(DrivingMode, expected_mode.upper()), f"Missing driving mode: {expected_mode}"
    
    def test_driving_mode_enum_values(self):
        """Test that enum values match expected strings."""
        assert DrivingMode.MANUAL.value == "manual"
        assert DrivingMode.ASSIST.value == "assist"
        assert DrivingMode.AUTOPILOT.value == "autopilot"
        assert DrivingMode.EMERGENCY.value == "emergency"


class TestVehicleState:
    """Test VehicleState dataclass."""
    
    def test_vehicle_state_creation(self):
        """Test creating a vehicle state object."""
        state = VehicleState(
            position=(0.0, 0.0, 0.0),
            velocity=(10.0, 0.0, 0.0),
            heading=0.0,
            speed=10.0
        )
        
        assert state.position == (0.0, 0.0, 0.0)
        assert state.velocity == (10.0, 0.0, 0.0)
        assert state.heading == 0.0
        assert state.speed == 10.0


class TestEnvironmentState:
    """Test EnvironmentState dataclass."""
    
    def test_environment_state_creation(self):
        """Test creating an environment state object."""
        state = EnvironmentState(
            detected_objects=[{"class_name": "car", "distance": 50.0}],
            lane_info=[{"distance_to_lane": 0.5}],
            traffic_lights=[{"state": "green", "distance": 100.0}],
            road_conditions="dry"
        )
        
        assert len(state.detected_objects) == 1
        assert len(state.lane_info) == 1
        assert len(state.traffic_lights) == 1
        assert state.road_conditions == "dry"


class TestDrivingCommand:
    """Test DrivingCommand dataclass."""
    
    def test_driving_command_creation(self):
        """Test creating a driving command object."""
        command = DrivingCommand(
            steering_angle=0.1,
            throttle=0.5,
            brake=0.0,
            emergency_brake=False
        )
        
        assert command.steering_angle == 0.1
        assert command.throttle == 0.5
        assert command.brake == 0.0
        assert command.emergency_brake is False


class TestAutopilotSystem:
    """Test AutopilotSystem class."""
    
    @pytest.fixture
    def autopilot_config(self):
        """Create autopilot configuration for testing."""
        return {
            'min_following_distance': 2.0,
            'max_speed': 30.0,
            'emergency_brake_threshold': 1.5
        }
    
    @pytest.fixture
    def autopilot_system(self, autopilot_config):
        """Create an AutopilotSystem instance for testing."""
        return AutopilotSystem(autopilot_config)
    
    @pytest.fixture
    def vehicle_state(self):
        """Create a vehicle state for testing."""
        return VehicleState(
            position=(0.0, 0.0, 0.0),
            velocity=(10.0, 0.0, 0.0),
            heading=0.0,
            speed=10.0
        )
    
    @pytest.fixture
    def environment_state(self):
        """Create an environment state for testing."""
        return EnvironmentState(
            detected_objects=[],
            lane_info=[],
            traffic_lights=[],
            road_conditions="dry"
        )
    
    def test_autopilot_system_initialization(self, autopilot_system):
        """Test AutopilotSystem initialization."""
        assert autopilot_system.current_mode == DrivingMode.MANUAL
        assert not autopilot_system.is_active
        assert autopilot_system.vehicle_state is None
        assert autopilot_system.environment_state is None
        assert autopilot_system.min_following_distance == 2.0
        assert autopilot_system.max_speed == 30.0
        assert autopilot_system.emergency_brake_threshold == 1.5
    
    def test_activate_success(self, autopilot_system, vehicle_state, environment_state):
        """Test successful autopilot activation."""
        autopilot_system.update_sensor_data(vehicle_state, environment_state)
        
        result = autopilot_system.activate(DrivingMode.ASSIST)
        
        assert result is True
        assert autopilot_system.is_active
        assert autopilot_system.current_mode == DrivingMode.ASSIST
    
    def test_activate_failure_no_sensor_data(self, autopilot_system):
        """Test autopilot activation failure without sensor data."""
        result = autopilot_system.activate(DrivingMode.ASSIST)
        
        assert result is False
        assert not autopilot_system.is_active
        assert autopilot_system.current_mode == DrivingMode.MANUAL
    
    def test_activate_failure_high_speed_autopilot(self, autopilot_system, vehicle_state, environment_state):
        """Test autopilot activation failure at high speed."""
        # Set high speed
        vehicle_state.speed = 30.0
        autopilot_system.update_sensor_data(vehicle_state, environment_state)
        
        result = autopilot_system.activate(DrivingMode.AUTOPILOT)
        
        assert result is False
        assert not autopilot_system.is_active
    
    def test_activate_failure_bad_road_conditions(self, autopilot_system, vehicle_state, environment_state):
        """Test autopilot activation failure in bad road conditions."""
        environment_state.road_conditions = "ice"
        autopilot_system.update_sensor_data(vehicle_state, environment_state)
        
        result = autopilot_system.activate(DrivingMode.AUTOPILOT)
        
        assert result is False
        assert not autopilot_system.is_active
    
    def test_deactivate(self, autopilot_system, vehicle_state, environment_state):
        """Test autopilot deactivation."""
        autopilot_system.update_sensor_data(vehicle_state, environment_state)
        autopilot_system.activate(DrivingMode.ASSIST)
        
        autopilot_system.deactivate()
        
        assert not autopilot_system.is_active
        assert autopilot_system.current_mode == DrivingMode.MANUAL
    
    def test_update_sensor_data(self, autopilot_system, vehicle_state, environment_state):
        """Test sensor data update."""
        autopilot_system.update_sensor_data(vehicle_state, environment_state)
        
        assert autopilot_system.vehicle_state == vehicle_state
        assert autopilot_system.environment_state == environment_state
    
    def test_make_driving_decision_inactive(self, autopilot_system):
        """Test driving decision when system is inactive."""
        command = autopilot_system.make_driving_decision()
        
        assert isinstance(command, DrivingCommand)
        assert command.steering_angle == 0.0
        assert command.throttle == 0.0
        assert command.brake == 0.0
        assert not command.emergency_brake
    
    def test_make_driving_decision_emergency_mode(self, autopilot_system, vehicle_state, environment_state):
        """Test driving decision in emergency mode."""
        autopilot_system.update_sensor_data(vehicle_state, environment_state)
        autopilot_system.activate(DrivingMode.EMERGENCY)
        
        command = autopilot_system.make_driving_decision()
        
        assert command.steering_angle == 0.0
        assert command.throttle == 0.0
        assert command.brake == 1.0
        assert command.emergency_brake is True
    
    def test_emergency_conditions_detection(self, autopilot_system, vehicle_state, environment_state):
        """Test emergency conditions detection."""
        # Add object too close
        environment_state.detected_objects = [{"distance": 1.0}]
        autopilot_system.update_sensor_data(vehicle_state, environment_state)
        autopilot_system.activate(DrivingMode.ASSIST)
        
        command = autopilot_system.make_driving_decision()
        
        assert command.emergency_brake is True
        assert command.brake == 1.0
    
    def test_lane_keeping_steering_calculation(self, autopilot_system, vehicle_state, environment_state):
        """Test lane keeping steering calculation."""
        environment_state.lane_info = [{"distance_to_lane": 0.5}]
        autopilot_system.update_sensor_data(vehicle_state, environment_state)
        autopilot_system.activate(DrivingMode.ASSIST)
        
        steering_angle = autopilot_system._calculate_lane_keeping_steering()
        
        assert isinstance(steering_angle, float)
        assert steering_angle == -0.05  # -0.5 * 0.1
    
    def test_lane_keeping_steering_no_lanes(self, autopilot_system, vehicle_state, environment_state):
        """Test lane keeping steering with no lane information."""
        autopilot_system.update_sensor_data(vehicle_state, environment_state)
        autopilot_system.activate(DrivingMode.ASSIST)
        
        steering_angle = autopilot_system._calculate_lane_keeping_steering()
        
        assert steering_angle == 0.0
    
    def test_adaptive_cruise_control(self, autopilot_system, vehicle_state, environment_state):
        """Test adaptive cruise control."""
        # Add vehicle ahead
        environment_state.detected_objects = [{
            "class_name": "car",
            "distance": 5.0,
            "speed": 8.0
        }]
        autopilot_system.update_sensor_data(vehicle_state, environment_state)
        autopilot_system.activate(DrivingMode.ASSIST)
        
        throttle, brake = autopilot_system._calculate_adaptive_cruise()
        
        assert isinstance(throttle, float)
        assert isinstance(brake, float)
        assert 0.0 <= throttle <= 1.0
        assert 0.0 <= brake <= 1.0
    
    def test_speed_control_acceleration(self, autopilot_system, vehicle_state, environment_state):
        """Test speed control for acceleration."""
        vehicle_state.speed = 5.0
        autopilot_system.update_sensor_data(vehicle_state, environment_state)
        autopilot_system.activate(DrivingMode.ASSIST)
        
        throttle, brake = autopilot_system._calculate_speed_control(25.0)
        
        assert throttle > 0.0
        assert brake == 0.0
    
    def test_speed_control_deceleration(self, autopilot_system, vehicle_state, environment_state):
        """Test speed control for deceleration."""
        vehicle_state.speed = 30.0
        autopilot_system.update_sensor_data(vehicle_state, environment_state)
        autopilot_system.activate(DrivingMode.ASSIST)
        
        throttle, brake = autopilot_system._calculate_speed_control(10.0)
        
        assert throttle == 0.0
        assert brake > 0.0
    
    def test_speed_control_maintain(self, autopilot_system, vehicle_state, environment_state):
        """Test speed control for maintaining speed."""
        vehicle_state.speed = 25.0
        autopilot_system.update_sensor_data(vehicle_state, environment_state)
        autopilot_system.activate(DrivingMode.ASSIST)
        
        throttle, brake = autopilot_system._calculate_speed_control(25.0)
        
        assert throttle == 0.1
        assert brake == 0.0
    
    def test_get_system_status(self, autopilot_system, vehicle_state, environment_state):
        """Test system status retrieval."""
        autopilot_system.update_sensor_data(vehicle_state, environment_state)
        autopilot_system.activate(DrivingMode.ASSIST)
        
        status = autopilot_system.get_system_status()
        
        assert status['is_active'] is True
        assert status['current_mode'] == "assist"
        assert status['vehicle_state_available'] is True
        assert status['environment_state_available'] is True
        assert 'safety_parameters' in status
        assert status['safety_parameters']['min_following_distance'] == 2.0
        assert status['safety_parameters']['max_speed'] == 30.0
        assert status['safety_parameters']['emergency_brake_threshold'] == 1.5

"""Functional tests for autopilot system integration."""

import pytest
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from ai.autopilot import (
    AutopilotSystem, DrivingMode, VehicleState, EnvironmentState, DrivingCommand
)


class TestAutopilotIntegration:
    """Integration tests for autopilot system."""

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

    def test_full_assist_mode_workflow(self, autopilot_system):
        """Test complete assist mode workflow."""
        # Setup vehicle and environment
        vehicle_state = VehicleState(
            position=(0.0, 0.0, 0.0),
            velocity=(15.0, 0.0, 0.0),
            heading=0.0,
            speed=15.0
        )

        environment_state = EnvironmentState(
            detected_objects=[
                {"class_name": "car", "distance": 20.0, "speed": 12.0}
            ],
            lane_info=[
                {"distance_to_lane": 0.2}
            ],
            traffic_lights=[],
            road_conditions="dry"
        )

        # Update sensor data and activate
        autopilot_system.update_sensor_data(vehicle_state, environment_state)
        activation_result = autopilot_system.activate(DrivingMode.ASSIST)

        assert activation_result is True
        assert autopilot_system.is_active
        assert autopilot_system.current_mode == DrivingMode.ASSIST

        # Make driving decision
        command = autopilot_system.make_driving_decision()

        assert isinstance(command, DrivingCommand)
        assert not command.emergency_brake
        assert 0.0 <= command.throttle <= 1.0
        assert 0.0 <= command.brake <= 1.0

    def test_autopilot_mode_workflow(self, autopilot_system):
        """Test complete autopilot mode workflow."""
        # Setup vehicle and environment for autopilot
        vehicle_state = VehicleState(
            position=(0.0, 0.0, 0.0),
            velocity=(20.0, 0.0, 0.0),
            heading=0.0,
            speed=20.0
        )

        environment_state = EnvironmentState(
            detected_objects=[],
            lane_info=[
                {"distance_to_lane": 0.1}
            ],
            traffic_lights=[],
            road_conditions="dry"
        )

        # Update sensor data and activate
        autopilot_system.update_sensor_data(vehicle_state, environment_state)
        activation_result = autopilot_system.activate(DrivingMode.AUTOPILOT)

        assert activation_result is True
        assert autopilot_system.is_active
        assert autopilot_system.current_mode == DrivingMode.AUTOPILOT

        # Make driving decision
        command = autopilot_system.make_driving_decision()

        assert isinstance(command, DrivingCommand)
        assert not command.emergency_brake
        assert 0.0 <= command.throttle <= 1.0
        assert 0.0 <= command.brake <= 1.0

    def test_emergency_scenario_workflow(self, autopilot_system):
        """Test emergency scenario workflow."""
        # Setup vehicle and environment with emergency condition
        vehicle_state = VehicleState(
            position=(0.0, 0.0, 0.0),
            velocity=(25.0, 0.0, 0.0),
            heading=0.0,
            speed=25.0
        )

        environment_state = EnvironmentState(
            detected_objects=[
                {"class_name": "car", "distance": 1.0, "speed": 20.0}  # Too close!
            ],
            lane_info=[],
            traffic_lights=[],
            road_conditions="dry"
        )

        # Update sensor data and activate
        autopilot_system.update_sensor_data(vehicle_state, environment_state)
        autopilot_system.activate(DrivingMode.ASSIST)

        # Make driving decision - should trigger emergency
        command = autopilot_system.make_driving_decision()

        assert command.emergency_brake is True
        assert command.brake == 1.0
        assert command.throttle == 0.0
        assert command.steering_angle == 0.0

    def test_mode_transition_workflow(self, autopilot_system):
        """Test transitioning between different driving modes."""
        vehicle_state = VehicleState(
            position=(0.0, 0.0, 0.0),
            velocity=(10.0, 0.0, 0.0),
            heading=0.0,
            speed=10.0
        )

        environment_state = EnvironmentState(
            detected_objects=[],
            lane_info=[],
            traffic_lights=[],
            road_conditions="dry"
        )

        autopilot_system.update_sensor_data(vehicle_state, environment_state)

        # Test MANUAL -> ASSIST transition
        result = autopilot_system.activate(DrivingMode.ASSIST)
        assert result is True
        assert autopilot_system.current_mode == DrivingMode.ASSIST

        # Test ASSIST -> AUTOPILOT transition
        result = autopilot_system.activate(DrivingMode.AUTOPILOT)
        assert result is True
        assert autopilot_system.current_mode == DrivingMode.AUTOPILOT

        # Test AUTOPILOT -> EMERGENCY transition
        result = autopilot_system.activate(DrivingMode.EMERGENCY)
        assert result is True
        assert autopilot_system.current_mode == DrivingMode.EMERGENCY

        # Test deactivation
        autopilot_system.deactivate()
        assert autopilot_system.current_mode == DrivingMode.MANUAL
        assert not autopilot_system.is_active

    def test_road_conditions_adaptation(self, autopilot_system):
        """Test adaptation to different road conditions."""
        vehicle_state = VehicleState(
            position=(0.0, 0.0, 0.0),
            velocity=(15.0, 0.0, 0.0),
            heading=0.0,
            speed=15.0
        )

        # Test dry conditions
        dry_environment = EnvironmentState(
            detected_objects=[],
            lane_info=[],
            traffic_lights=[],
            road_conditions="dry"
        )

        autopilot_system.update_sensor_data(vehicle_state, dry_environment)
        dry_result = autopilot_system.activate(DrivingMode.AUTOPILOT)
        assert dry_result is True

        # Test wet conditions
        wet_environment = EnvironmentState(
            detected_objects=[],
            lane_info=[],
            traffic_lights=[],
            road_conditions="wet"
        )

        autopilot_system.update_sensor_data(vehicle_state, wet_environment)
        wet_result = autopilot_system.activate(DrivingMode.AUTOPILOT)
        assert wet_result is True

        # Test ice conditions - should fail for autopilot
        ice_environment = EnvironmentState(
            detected_objects=[],
            lane_info=[],
            traffic_lights=[],
            road_conditions="ice"
        )

        autopilot_system.update_sensor_data(vehicle_state, ice_environment)
        ice_result = autopilot_system.activate(DrivingMode.AUTOPILOT)
        assert ice_result is False  # Should fail in ice conditions

    def test_traffic_scenario_workflow(self, autopilot_system):
        """Test complex traffic scenario workflow."""
        # Setup complex traffic scenario
        vehicle_state = VehicleState(
            position=(0.0, 0.0, 0.0),
            velocity=(20.0, 0.0, 0.0),
            heading=0.0,
            speed=20.0
        )

        environment_state = EnvironmentState(
            detected_objects=[
                {"class_name": "car", "distance": 30.0, "speed": 18.0},  # Car ahead
                {"class_name": "truck", "distance": 50.0, "speed": 15.0},  # Truck ahead
                {"class_name": "person", "distance": 100.0, "speed": 0.0}  # Pedestrian
            ],
            lane_info=[
                {"distance_to_lane": 0.3}
            ],
            traffic_lights=[
                {"state": "green", "distance": 80.0}
            ],
            road_conditions="dry"
        )

        autopilot_system.update_sensor_data(vehicle_state, environment_state)
        autopilot_system.activate(DrivingMode.AUTOPILOT)

        # Make multiple driving decisions
        commands = []
        for _ in range(5):
            command = autopilot_system.make_driving_decision()
            commands.append(command)

        # Verify all commands are valid
        for command in commands:
            assert isinstance(command, DrivingCommand)
            assert 0.0 <= command.throttle <= 1.0
            assert 0.0 <= command.brake <= 1.0
            assert not command.emergency_brake

    def test_system_status_monitoring(self, autopilot_system):
        """Test system status monitoring throughout operation."""
        vehicle_state = VehicleState(
            position=(0.0, 0.0, 0.0),
            velocity=(15.0, 0.0, 0.0),
            heading=0.0,
            speed=15.0
        )

        environment_state = EnvironmentState(
            detected_objects=[],
            lane_info=[],
            traffic_lights=[],
            road_conditions="dry"
        )

        # Test status before activation
        status = autopilot_system.get_system_status()
        assert status['is_active'] is False
        assert status['current_mode'] == "manual"
        assert status['vehicle_state_available'] is False
        assert status['environment_state_available'] is False

        # Update sensor data
        autopilot_system.update_sensor_data(vehicle_state, environment_state)
        status = autopilot_system.get_system_status()
        assert status['vehicle_state_available'] is True
        assert status['environment_state_available'] is True

        # Activate and test status
        autopilot_system.activate(DrivingMode.ASSIST)
        status = autopilot_system.get_system_status()
        assert status['is_active'] is True
        assert status['current_mode'] == "assist"

        # Deactivate and test status
        autopilot_system.deactivate()
        status = autopilot_system.get_system_status()
        assert status['is_active'] is False
        assert status['current_mode'] == "manual"

    def test_error_handling_workflow(self, autopilot_system):
        """Test error handling in various scenarios."""
        # Test with None sensor data
        autopilot_system.update_sensor_data(None, None)
        result = autopilot_system.activate(DrivingMode.ASSIST)
        assert result is False

        # Test with partial sensor data
        vehicle_state = VehicleState(
            position=(0.0, 0.0, 0.0),
            velocity=(15.0, 0.0, 0.0),
            heading=0.0,
            speed=15.0
        )

        autopilot_system.update_sensor_data(vehicle_state, None)
        result = autopilot_system.activate(DrivingMode.ASSIST)
        assert result is False

        # Test driving decision with no sensor data
        command = autopilot_system.make_driving_decision()
        assert isinstance(command, DrivingCommand)
        assert command.steering_angle == 0.0
        assert command.throttle == 0.0
        assert command.brake == 0.0
        assert not command.emergency_brake

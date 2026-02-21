"""Functional tests for Alpamayo autopilot workflows."""

import sys
from pathlib import Path

import pytest

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from ai.autopilot import AutopilotSystem, DrivingMode, EnvironmentState, VehicleState


class _SequencePredictor:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    def predict(self, payload):
        self.calls += 1
        if self._responses:
            return self._responses.pop(0)
        return {"steering_angle": 0.0, "throttle": 0.1, "brake": 0.0}


@pytest.fixture
def vehicle_state():
    return VehicleState(
        position=(0.0, 0.0, 0.0),
        velocity=(15.0, 0.0, 0.0),
        heading=0.0,
        speed=15.0,
    )


def test_alpamayo_workflow_with_multiple_predictions(vehicle_state):
    predictor = _SequencePredictor(
        [
            {"steering_angle": 0.15, "throttle": 0.35, "brake": 0.0},
            {"steering_angle": -0.05, "throttle": 0.25, "brake": 0.0},
        ]
    )
    config = {
        "autonomy_provider": "alpamayo",
        "alpamayo_enabled": True,
        "alpamayo_fallback_to_rule_based": True,
    }
    autopilot = AutopilotSystem(config=config, alpamayo_predictor=predictor)
    environment = EnvironmentState(
        detected_objects=[],
        lane_info=[{"distance_to_lane": 0.1}],
        traffic_lights=[],
        road_conditions="dry",
    )

    autopilot.update_sensor_data(vehicle_state, environment)
    assert autopilot.activate(DrivingMode.AUTOPILOT) is True

    command_1 = autopilot.make_driving_decision()
    command_2 = autopilot.make_driving_decision()

    assert predictor.calls == 2
    assert command_1.throttle == 0.35
    assert command_2.steering_angle == -0.05
    assert command_1.emergency_brake is False
    assert command_2.emergency_brake is False


def test_emergency_object_still_overrides_alpamayo(vehicle_state):
    predictor = _SequencePredictor(
        [{"steering_angle": 0.2, "throttle": 0.7, "brake": 0.0}]
    )
    config = {
        "autonomy_provider": "alpamayo",
        "alpamayo_enabled": True,
    }
    autopilot = AutopilotSystem(config=config, alpamayo_predictor=predictor)
    environment = EnvironmentState(
        detected_objects=[{"class_name": "car", "distance": 0.8, "speed": 5.0}],
        lane_info=[{"distance_to_lane": 0.0}],
        traffic_lights=[],
        road_conditions="dry",
    )

    autopilot.update_sensor_data(vehicle_state, environment)
    assert autopilot.activate(DrivingMode.AUTOPILOT) is True

    command = autopilot.make_driving_decision()

    assert command.emergency_brake is True
    assert command.throttle == 0.0
    assert command.brake == 1.0
    # Predictor should not be used when emergency is detected first.
    assert predictor.calls == 0


def test_alpamayo_missing_backend_falls_back_to_rule_based(vehicle_state):
    config = {
        "autonomy_provider": "alpamayo",
        "alpamayo_enabled": True,
        "alpamayo_fallback_to_rule_based": True,
        "alpamayo_import_candidates": ["module_that_does_not_exist_123"],
    }
    autopilot = AutopilotSystem(config=config)
    environment = EnvironmentState(
        detected_objects=[],
        lane_info=[{"distance_to_lane": 0.5}],
        traffic_lights=[],
        road_conditions="dry",
    )

    autopilot.update_sensor_data(vehicle_state, environment)
    assert autopilot.activate(DrivingMode.AUTOPILOT) is True
    command = autopilot.make_driving_decision()
    status = autopilot.get_system_status()

    assert command.emergency_brake is False
    assert status["autonomy"]["alpamayo_fallback_active"] is True

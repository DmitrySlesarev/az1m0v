"""Unit tests for Alpamayo-enabled autopilot behavior."""

import sys
from pathlib import Path

import pytest

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from ai.autopilot import AutopilotSystem, DrivingMode, EnvironmentState, VehicleState


class _Predictor:
    def __init__(self, response):
        self.response = response
        self.last_payload = None

    def predict(self, payload):
        self.last_payload = payload
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


@pytest.fixture
def vehicle_state():
    return VehicleState(
        position=(0.0, 0.0, 0.0),
        velocity=(12.0, 0.0, 0.0),
        heading=0.0,
        speed=12.0,
    )


@pytest.fixture
def environment_state():
    return EnvironmentState(
        detected_objects=[],
        lane_info=[{"distance_to_lane": 0.2}],
        traffic_lights=[],
        road_conditions="dry",
    )


def test_alpamayo_predictor_is_used_and_commands_are_limited(vehicle_state, environment_state):
    predictor = _Predictor(
        {
            "steering_angle": 0.95,
            "throttle": 0.95,
            "brake": 0.0,
            "emergency_brake": False,
        }
    )
    config = {
        "autonomy_provider": "alpamayo",
        "alpamayo_enabled": True,
        "alpamayo_fallback_to_rule_based": True,
        "vehicle_profile": "truck",
        "max_steering_angle": 0.4,
        "max_throttle": 0.6,
        "max_brake": 1.0,
    }
    autopilot = AutopilotSystem(config=config, alpamayo_predictor=predictor)
    autopilot.update_sensor_data(vehicle_state, environment_state)
    assert autopilot.activate(DrivingMode.AUTOPILOT) is True

    command = autopilot.make_driving_decision()

    assert command.steering_angle == 0.4
    assert command.throttle == 0.6
    assert command.brake == 0.0
    assert command.emergency_brake is False
    assert predictor.last_payload["vehicle_profile"] == "truck"
    assert predictor.last_payload["ego_vehicle"]["speed"] == vehicle_state.speed


def test_alpamayo_invalid_prediction_falls_back_to_rule_based(vehicle_state, environment_state):
    predictor = _Predictor("invalid-payload")
    config = {
        "autonomy_provider": "alpamayo",
        "alpamayo_enabled": True,
        "alpamayo_fallback_to_rule_based": True,
        "lane_steering_gain": 0.1,
        "assist_target_speed": 25.0,
    }
    autopilot = AutopilotSystem(config=config, alpamayo_predictor=predictor)
    autopilot.update_sensor_data(vehicle_state, environment_state)
    assert autopilot.activate(DrivingMode.AUTOPILOT) is True

    command = autopilot.make_driving_decision()
    status = autopilot.get_system_status()

    assert command.emergency_brake is False
    assert status["autonomy"]["alpamayo_fallback_active"] is True
    assert status["autonomy"]["alpamayo_last_error"] == "invalid_prediction_type"


def test_alpamayo_without_fallback_returns_emergency(vehicle_state, environment_state):
    predictor = _Predictor(RuntimeError("predict-failed"))
    config = {
        "autonomy_provider": "alpamayo",
        "alpamayo_enabled": True,
        "alpamayo_fallback_to_rule_based": False,
    }
    autopilot = AutopilotSystem(config=config, alpamayo_predictor=predictor)
    autopilot.update_sensor_data(vehicle_state, environment_state)
    assert autopilot.activate(DrivingMode.AUTOPILOT) is True

    command = autopilot.make_driving_decision()

    assert command.emergency_brake is True
    assert command.throttle == 0.0
    assert command.brake == 1.0


def test_alpamayo_module_probe_exposes_backend_status():
    config = {
        "autonomy_provider": "alpamayo",
        "alpamayo_enabled": True,
        "alpamayo_import_candidates": ["json"],
    }
    autopilot = AutopilotSystem(config=config)
    status = autopilot.get_system_status()

    assert status["autonomy"]["provider"] == "alpamayo"
    assert status["autonomy"]["alpamayo_enabled"] is True
    assert status["autonomy"]["alpamayo_ready"] is False
    assert status["autonomy"]["alpamayo_backend_module"] == "json"

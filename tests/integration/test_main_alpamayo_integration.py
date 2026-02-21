"""Integration tests for EVSystem + Alpamayo autopilot wiring."""

import json
import tempfile
import types
from pathlib import Path
from unittest.mock import patch

from ai.autopilot import DrivingMode, EnvironmentState, VehicleState
from main import EVSystem


def _base_config():
    return {
        "vehicle": {"model": "test", "serial_number": "TEST001", "manufacturer": "test"},
        "battery": {
            "capacity_kwh": 50.0,
            "max_charge_rate_kw": 100.0,
            "max_discharge_rate_kw": 150.0,
            "nominal_voltage": 400.0,
            "cell_count": 96,
        },
        "motor": {
            "max_power_kw": 100.0,
            "max_torque_nm": 250.0,
            "efficiency": 0.9,
            "type": "permanent_magnet",
        },
        "motor_controller": {"type": "vesc", "serial_port": None, "can_enabled": False},
        "charging": {
            "ac_max_power_kw": 11.0,
            "dc_max_power_kw": 150.0,
            "connector_type": "CCS2",
            "fast_charge_enabled": True,
        },
        "sensors": {
            "imu_enabled": False,
            "gps_enabled": False,
            "temperature_sensors": 8,
            "sampling_rate_hz": 100,
        },
        "communication": {"can_bus_enabled": False, "update_interval_ms": 1000},
        "vehicle_controller": {"max_speed_kmh": 120.0, "max_power_kw": 150.0},
        "temperature_sensors": {"enabled": False},
        "ui": {"dashboard_enabled": False, "mobile_app_enabled": True, "theme": "dark"},
        "ai": {
            "autopilot_enabled": True,
            "computer_vision_enabled": False,
            "model_path": "/models/",
            "autonomy_provider": "alpamayo",
            "alpamayo_enabled": True,
            "alpamayo_fallback_to_rule_based": True,
            "alpamayo_import_candidates": ["module_that_does_not_exist_123"],
        },
        "logging": {
            "level": "INFO",
            "file_path": "/tmp/test.log",
            "max_file_size_mb": 100,
            "backup_count": 5,
        },
    }


def test_evsystem_initializes_alpamayo_autopilot_with_fallback():
    config = _base_config()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(config, f)
        config_path = f.name

    try:
        system = EVSystem(config_path=config_path)
        assert system.autopilot is not None

        status = system.autopilot.get_system_status()
        assert status["autonomy"]["provider"] == "alpamayo"
        assert status["autonomy"]["alpamayo_enabled"] is True
        assert status["autonomy"]["alpamayo_ready"] is False
    finally:
        Path(config_path).unlink()


def test_evsystem_loads_explicit_alpamayo_adapter_class():
    class FakePredictor:
        def __init__(self, config=None):
            self.config = config or {}

        def predict(self, payload):
            return {
                "steering_angle": 0.11,
                "throttle": 0.22,
                "brake": 0.0,
                "emergency_brake": False,
            }

    fake_module = types.SimpleNamespace(FakePredictor=FakePredictor)

    config = _base_config()
    config["ai"]["alpamayo_adapter_module"] = "fake_alpamayo_adapter"
    config["ai"]["alpamayo_adapter_class"] = "FakePredictor"
    config["ai"]["alpamayo_import_candidates"] = []

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(config, f)
        config_path = f.name

    try:
        with patch("ai.autopilot.importlib.import_module", return_value=fake_module):
            system = EVSystem(config_path=config_path)

        assert system.autopilot is not None
        status = system.autopilot.get_system_status()
        assert status["autonomy"]["alpamayo_ready"] is True
        assert status["autonomy"]["alpamayo_backend_module"] == "fake_alpamayo_adapter"

        vehicle_state = VehicleState(
            position=(0.0, 0.0, 0.0),
            velocity=(10.0, 0.0, 0.0),
            heading=0.0,
            speed=10.0,
        )
        environment_state = EnvironmentState(
            detected_objects=[],
            lane_info=[{"distance_to_lane": 0.1}],
            traffic_lights=[],
            road_conditions="dry",
        )

        system.autopilot.update_sensor_data(vehicle_state, environment_state)
        assert system.autopilot.activate(DrivingMode.AUTOPILOT) is True

        command = system.autopilot.make_driving_decision()
        assert command.steering_angle == 0.11
        assert command.throttle == 0.22
        assert command.emergency_brake is False
    finally:
        Path(config_path).unlink()

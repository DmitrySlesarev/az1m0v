"""Unit tests for dashboard REST API extensions."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple
from unittest.mock import Mock

from ui.dashboard import EVDashboard


class _FakeDeploymentManager:
    def __init__(self):
        self.started_with: Optional[Sequence[str]] = None
        self._status: Dict[str, Any] = {
            "state": "idle",
            "started_at": None,
            "finished_at": None,
            "progress": {"current": 0, "total": 0},
            "current_step": None,
            "error": None,
            "logs": [],
        }

    def start_deployment(self, integrations: Optional[Sequence[str]] = None) -> Tuple[bool, str]:
        self.started_with = integrations or []
        self._status["state"] = "running"
        self._status["progress"] = {"current": 0, "total": 1}
        self._status["logs"] = ["Deployment started"]
        return True, "Deployment started"

    def get_status(self) -> Dict[str, Any]:
        return dict(self._status)


def test_api_control_accepts_payload_alias():
    fake_deployment = _FakeDeploymentManager()
    dashboard = EVDashboard(host="127.0.0.1", port=5051, deployment_manager=fake_deployment)
    dashboard.vehicle_controller = Mock()
    dashboard.vehicle_controller.accelerate.return_value = True

    client = dashboard.app.test_client()
    response = client.post(
        "/api/control",
        json={"command": "accelerate", "payload": {"throttle_percent": 22.5}},
    )

    assert response.status_code == 200
    assert response.get_json()["success"] is True
    dashboard.vehicle_controller.accelerate.assert_called_once_with(22.5)


def test_api_deploy_start_and_status():
    fake_deployment = _FakeDeploymentManager()
    dashboard = EVDashboard(host="127.0.0.1", port=5052, deployment_manager=fake_deployment)
    client = dashboard.app.test_client()

    start_response = client.post(
        "/api/deploy/start",
        json={"integrations": ["VESC", "quectel"]},
    )
    assert start_response.status_code == 202
    body = start_response.get_json()
    assert body["success"] is True
    assert fake_deployment.started_with == ["vesc", "quectel"]

    status_response = client.get("/api/deploy/status")
    assert status_response.status_code == 200
    status = status_response.get_json()
    assert status["state"] == "running"
    assert status["logs"] == ["Deployment started"]


def test_api_deploy_start_rejects_invalid_integrations_payload():
    fake_deployment = _FakeDeploymentManager()
    dashboard = EVDashboard(host="127.0.0.1", port=5053, deployment_manager=fake_deployment)
    client = dashboard.app.test_client()

    response = client.post("/api/deploy/start", json={"integrations": "vesc"})
    assert response.status_code == 400
    assert response.get_json()["success"] is False


def test_api_status_serializes_enums():
    class State(Enum):
        OK = "ok"

    fake_deployment = _FakeDeploymentManager()
    dashboard = EVDashboard(host="127.0.0.1", port=5054, deployment_manager=fake_deployment)
    dashboard.autopilot = Mock()
    dashboard.autopilot.get_system_status.return_value = {
        "current_mode": State.OK,
        "autonomy": {
            "provider": "rule_based",
        },
    }
    dashboard.telemetry = Mock()
    dashboard.telemetry.get_status.return_value = {"state": State.OK}
    dashboard.safety_system = Mock()
    dashboard.safety_system.get_status.return_value = {
        "safety_states": {"thermal": State.OK},
    }
    dashboard._refresh_extended_status_data()

    client = dashboard.app.test_client()
    response = client.get("/api/status")
    assert response.status_code == 200
    payload = response.get_json()

    assert payload["autopilot"]["current_mode"] == "ok"
    assert payload["telemetry"]["state"] == "ok"
    assert payload["safety"]["safety_states"]["thermal"] == "ok"

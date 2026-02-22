"""Unit tests for dashboard deployment manager."""

from __future__ import annotations

import time
from pathlib import Path
from subprocess import CompletedProcess
from typing import Any, List

from ui.deployment import DeploymentManager


def _wait_for_terminal_state(manager: DeploymentManager, timeout_s: float = 5.0) -> dict:
    start = time.time()
    while time.time() - start < timeout_s:
        status = manager.get_status()
        if status["state"] in {"succeeded", "failed", "idle"}:
            return status
        time.sleep(0.05)
    raise AssertionError("Deployment did not finish in time")


def test_deployment_manager_successful_run(tmp_path: Path):
    calls: List[List[str]] = []

    def fake_runner(command: List[str], **_: Any) -> CompletedProcess[str]:
        calls.append(command)
        return CompletedProcess(command, 0, stdout="ok", stderr="")

    manager = DeploymentManager(project_root=tmp_path, command_runner=fake_runner)
    started, message = manager.start_deployment(integrations=["vesc", "quectel"])

    assert started is True
    assert message == "Deployment started"

    status = _wait_for_terminal_state(manager)
    assert status["state"] == "succeeded"
    assert calls[0] == ["bash", "scripts/setup.sh"]
    assert calls[1] == ["poetry", "run", "python", "scripts/integration/vesc_builder.py"]
    assert calls[2] == ["poetry", "run", "python", "scripts/integration/quectel_builder.py"]


def test_deployment_manager_rejects_unsupported_integrations(tmp_path: Path):
    manager = DeploymentManager(project_root=tmp_path)
    started, message = manager.start_deployment(integrations=["bad-module"])

    assert started is False
    assert "Unsupported integration" in message
    assert manager.get_status()["state"] == "idle"


def test_deployment_manager_reports_failed_step(tmp_path: Path):
    step_counter = {"count": 0}

    def fake_runner(command: List[str], **_: Any) -> CompletedProcess[str]:
        step_counter["count"] += 1
        if step_counter["count"] == 2:
            return CompletedProcess(command, 1, stdout="", stderr="failed")
        return CompletedProcess(command, 0, stdout="ok", stderr="")

    manager = DeploymentManager(project_root=tmp_path, command_runner=fake_runner)
    started, _ = manager.start_deployment(integrations=["vesc"])
    assert started is True

    status = _wait_for_terminal_state(manager)
    assert status["state"] == "failed"
    assert "exit code 1" in (status["error"] or "")
    assert any("failed" in line for line in status["logs"])


def test_deployment_manager_blocks_parallel_runs(tmp_path: Path):
    def slow_runner(command: List[str], **_: Any) -> CompletedProcess[str]:
        time.sleep(0.2)
        return CompletedProcess(command, 0, stdout="ok", stderr="")

    manager = DeploymentManager(project_root=tmp_path, command_runner=slow_runner)
    started, _ = manager.start_deployment()
    assert started is True

    started_again, message_again = manager.start_deployment()
    assert started_again is False
    assert message_again == "Deployment already running"

    _wait_for_terminal_state(manager)

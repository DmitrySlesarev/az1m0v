"""Background deployment helpers used by the web dashboard."""

from __future__ import annotations

import copy
import logging
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class DeploymentStep:
    """A single deployment step command."""

    name: str
    command: List[str]


class DeploymentManager:
    """Run project deployment steps asynchronously for dashboard users."""

    _INTEGRATION_STEPS: Dict[str, DeploymentStep] = {
        "vesc": DeploymentStep(
            name="Install VESC integration",
            command=["poetry", "run", "python", "scripts/integration/vesc_builder.py"],
        ),
        "simpbms": DeploymentStep(
            name="Install SimpBMS integration",
            command=["poetry", "run", "python", "scripts/integration/simpbms_builder.py"],
        ),
        "quectel": DeploymentStep(
            name="Install Quectel telemetry integration",
            command=["poetry", "run", "python", "scripts/integration/quectel_builder.py"],
        ),
        "mpu6050": DeploymentStep(
            name="Install MPU-6050 integration",
            command=["poetry", "run", "python", "scripts/integration/mpu_builder.py", "--sensor", "mpu6050"],
        ),
        "mpu9250": DeploymentStep(
            name="Install MPU-9250 integration",
            command=["poetry", "run", "python", "scripts/integration/mpu_builder.py", "--sensor", "mpu9250"],
        ),
    }

    def __init__(
        self,
        project_root: Path,
        command_runner: Optional[Callable[..., Any]] = None,
        max_log_lines: int = 400,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self._command_runner = command_runner or subprocess.run
        self._max_log_lines = max_log_lines
        self._logger = logging.getLogger(__name__)
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
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
        """Start a deployment thread if no deployment is currently running."""
        requested_integrations = [str(name).strip().lower() for name in (integrations or []) if str(name).strip()]
        log_lines: List[str] = []

        with self._lock:
            if self._status["state"] == "running":
                return False, "Deployment already running"

            try:
                steps = self._build_steps(requested_integrations)
            except ValueError as exc:
                return False, str(exc)

            self._status = {
                "state": "running",
                "started_at": time.time(),
                "finished_at": None,
                "progress": {"current": 0, "total": len(steps)},
                "current_step": None,
                "error": None,
                "logs": [],
            }
            log_lines.append("Deployment started")
            if requested_integrations:
                log_lines.append(f"Requested integrations: {', '.join(requested_integrations)}")

            self._thread = threading.Thread(
                target=self._run_steps,
                args=(steps,),
                daemon=True,
                name="DashboardDeploymentThread",
            )
            self._thread.start()

        for line in log_lines:
            self._append_log(line)

        return True, "Deployment started"

    def get_status(self) -> Dict[str, Any]:
        """Return a copy of current deployment status."""
        with self._lock:
            return copy.deepcopy(self._status)

    def _build_steps(self, integrations: Sequence[str]) -> List[DeploymentStep]:
        unsupported = [name for name in integrations if name not in self._INTEGRATION_STEPS]
        if unsupported:
            raise ValueError(f"Unsupported integration(s): {', '.join(sorted(set(unsupported)))}")

        steps: List[DeploymentStep] = [
            DeploymentStep(
                name="Install project dependencies",
                command=["bash", "scripts/setup.sh"],
            )
        ]

        seen = set()
        for name in integrations:
            if name in seen:
                continue
            seen.add(name)
            steps.append(self._INTEGRATION_STEPS[name])
        return steps

    def _run_steps(self, steps: Sequence[DeploymentStep]) -> None:
        try:
            for index, step in enumerate(steps, start=1):
                with self._lock:
                    self._status["progress"] = {"current": index, "total": len(steps)}
                    self._status["current_step"] = step.name
                self._append_log(f"[step {index}/{len(steps)}] {step.name}")
                self._append_log(f"Running: {' '.join(step.command)}")

                result = self._command_runner(
                    step.command,
                    cwd=str(self.project_root),
                    capture_output=True,
                    text=True,
                    check=False,
                )

                self._capture_output(result)

                if int(getattr(result, "returncode", 1)) != 0:
                    error = f"Step failed ({step.name}) with exit code {result.returncode}"
                    with self._lock:
                        self._status["state"] = "failed"
                        self._status["error"] = error
                        self._status["finished_at"] = time.time()
                    self._append_log(error)
                    return

            with self._lock:
                self._status["state"] = "succeeded"
                self._status["current_step"] = None
                self._status["finished_at"] = time.time()
            self._append_log("Deployment completed successfully")
        except Exception as exc:
            self._logger.error("Deployment manager failed: %s", exc)
            with self._lock:
                self._status["state"] = "failed"
                self._status["error"] = str(exc)
                self._status["finished_at"] = time.time()
            self._append_log(f"Deployment failed: {exc}")

    def _capture_output(self, result: Any) -> None:
        stdout = str(getattr(result, "stdout", "") or "").strip()
        stderr = str(getattr(result, "stderr", "") or "").strip()
        if stdout:
            for line in stdout.splitlines():
                self._append_log(line)
        if stderr:
            for line in stderr.splitlines():
                self._append_log(f"[stderr] {line}")

    def _append_log(self, line: str) -> None:
        with self._lock:
            logs = self._status.setdefault("logs", [])
            logs.append(line)
            if len(logs) > self._max_log_lines:
                self._status["logs"] = logs[-self._max_log_lines :]

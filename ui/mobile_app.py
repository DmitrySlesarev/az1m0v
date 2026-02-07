"""Mobile app client for the EV project.

Provides a minimal REST client for the dashboard API to support DIY mobile apps.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

try:
    import requests  # type: ignore
    REQUESTS_AVAILABLE = True
except Exception:
    requests = None
    REQUESTS_AVAILABLE = False

import urllib.request


@dataclass
class MobileAppConfig:
    base_url: str = "http://localhost:5000"
    timeout_s: float = 5.0
    api_key: Optional[str] = None


class MobileAppClient:
    """Minimal REST client for the EV dashboard API."""

    def __init__(self, config: MobileAppConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)

    def get_status(self) -> Optional[Dict[str, Any]]:
        """Fetch current system status from dashboard."""
        return self._get_json("/api/status")

    def send_command(self, command: str, payload: Optional[Dict[str, Any]] = None) -> bool:
        """Send control command to dashboard."""
        data = {"command": command, "payload": payload or {}}
        response = self._post_json("/api/control", data)
        return response is not None

    def set_drive_mode(self, mode: str) -> bool:
        return self.send_command("set_drive_mode", {"mode": mode})

    def accelerate(self, throttle_percent: float) -> bool:
        return self.send_command("accelerate", {"throttle_percent": throttle_percent})

    def brake(self, brake_percent: float) -> bool:
        return self.send_command("brake", {"brake_percent": brake_percent})

    def start_charging(self, power_kw: Optional[float] = None, target_soc: float = 100.0) -> bool:
        payload = {"target_soc": target_soc}
        if power_kw is not None:
            payload["power_kw"] = power_kw
        return self.send_command("start_charging", payload)

    def stop_charging(self) -> bool:
        return self.send_command("stop_charging")

    def _build_url(self, path: str) -> str:
        if self.config.base_url.endswith("/") and path.startswith("/"):
            return f"{self.config.base_url[:-1]}{path}"
        return f"{self.config.base_url}{path}"

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers

    def _get_json(self, path: str) -> Optional[Dict[str, Any]]:
        url = self._build_url(path)
        try:
            if REQUESTS_AVAILABLE:
                response = requests.get(url, headers=self._headers(), timeout=self.config.timeout_s)
                response.raise_for_status()
                return response.json()
            req = urllib.request.Request(url, headers=self._headers(), method="GET")
            with urllib.request.urlopen(req, timeout=self.config.timeout_s) as resp:
                return json.loads(resp.read().decode())
        except Exception as exc:
            self.logger.warning(f"Mobile app GET failed: {exc}")
            return None

    def _post_json(self, path: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        url = self._build_url(path)
        body = json.dumps(payload).encode()
        try:
            if REQUESTS_AVAILABLE:
                response = requests.post(url, headers=self._headers(), json=payload, timeout=self.config.timeout_s)
                response.raise_for_status()
                return response.json()
            req = urllib.request.Request(url, headers=self._headers(), data=body, method="POST")
            with urllib.request.urlopen(req, timeout=self.config.timeout_s) as resp:
                return json.loads(resp.read().decode())
        except Exception as exc:
            self.logger.warning(f"Mobile app POST failed: {exc}")
            return None

"""Mobile app client for the EV project.

Provides a minimal REST client for the dashboard API to support DIY mobile apps.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional
import argparse
import sys

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


def _build_client_from_args(args: argparse.Namespace) -> MobileAppClient:
    config = MobileAppConfig(
        base_url=args.base_url,
        timeout_s=args.timeout,
        api_key=args.api_key
    )
    return MobileAppClient(config)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="EV mobile client CLI")
    parser.add_argument("--base-url", default="http://localhost:5000", help="Dashboard base URL")
    parser.add_argument("--timeout", type=float, default=5.0, help="Request timeout in seconds")
    parser.add_argument("--api-key", default=None, help="Optional API key")

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status", help="Fetch current status")

    accel = subparsers.add_parser("accelerate", help="Send accelerate command")
    accel.add_argument("throttle_percent", type=float)

    brake = subparsers.add_parser("brake", help="Send brake command")
    brake.add_argument("brake_percent", type=float)

    drive = subparsers.add_parser("drive-mode", help="Set drive mode")
    drive.add_argument("mode", choices=["eco", "normal", "sport", "reverse"])

    start_charge = subparsers.add_parser("start-charging", help="Start charging")
    start_charge.add_argument("--power-kw", type=float, default=None)
    start_charge.add_argument("--target-soc", type=float, default=100.0)

    subparsers.add_parser("stop-charging", help="Stop charging")

    args = parser.parse_args(argv)
    client = _build_client_from_args(args)

    if args.command == "status":
        status = client.get_status()
        if status is None:
            return 1
        print(json.dumps(status, indent=2))
        return 0

    if args.command == "accelerate":
        return 0 if client.accelerate(args.throttle_percent) else 1

    if args.command == "brake":
        return 0 if client.brake(args.brake_percent) else 1

    if args.command == "drive-mode":
        return 0 if client.set_drive_mode(args.mode) else 1

    if args.command == "start-charging":
        return 0 if client.start_charging(power_kw=args.power_kw, target_soc=args.target_soc) else 1

    if args.command == "stop-charging":
        return 0 if client.stop_charging() else 1

    return 1


if __name__ == "__main__":
    sys.exit(main())

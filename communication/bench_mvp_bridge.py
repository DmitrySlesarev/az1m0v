"""Bench MVP bridge for Raspberry Pi + Arduino + RAK4630 setups."""

from __future__ import annotations

import json
import logging
import math
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

try:
    import serial  # type: ignore
except Exception:  # pragma: no cover - exercised in environments without pyserial
    serial = None


@dataclass
class SerialEndpointConfig:
    """Serial endpoint configuration."""

    port: str
    baudrate: int
    timeout_s: float


class BenchMVPBridge:
    """
    Bridge USB serial bench nodes into CAN-oriented EV runtime state.

    Expected line format from serial endpoints: one JSON object per line.
    """

    def __init__(self, config: Dict[str, Any], can_protocol: Optional[Any] = None):
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.can_protocol = can_protocol

        self.enabled = bool(config.get("enabled", False))
        self.simulation_mode = bool(config.get("simulation_mode", True))
        self.prefer_lorawan = bool(config.get("prefer_lorawan", True))
        self.heartbeat_timeout_s = float(config.get("heartbeat_timeout_s", 10.0))
        self.lora_min_rssi_dbm = float(config.get("lora_min_rssi_dbm", -120.0))

        default_baud = int(config.get("default_baudrate", 115200))
        timeout_s = float(config.get("read_timeout_s", 0.01))
        self.arduino_config = SerialEndpointConfig(
            port=str(config.get("arduino_port", "/dev/ttyACM0")),
            baudrate=int(config.get("arduino_baudrate", default_baud)),
            timeout_s=timeout_s,
        )
        self.rak_config = SerialEndpointConfig(
            port=str(config.get("rak_port", "/dev/ttyACM1")),
            baudrate=int(config.get("rak_baudrate", default_baud)),
            timeout_s=timeout_s,
        )

        self._arduino_serial = None
        self._rak_serial = None
        self._started = False
        self._last_simulation_update = 0.0

        now = time.time()
        self._heartbeats = {
            "arduino": 0.0,
            "rak4630": 0.0,
            "can": now,  # Local runtime updates imply CAN path alive
        }
        self._rssi_dbm = -140.0
        self._snr_db = 0.0
        self._mode = "can_primary"

        self._latest_payload: Dict[str, Any] = {
            "battery": {},
            "motor": {},
            "charging": {},
            "vehicle": {},
            "temperature": {},
            "bench_network": self._build_network_status(),
        }

    def start(self) -> None:
        """Start serial endpoints if configured."""
        if not self.enabled or self._started:
            return

        self._started = True
        self._open_serial_endpoints()
        self.logger.info(
            "Bench MVP bridge started: simulation=%s arduino=%s rak=%s",
            self.simulation_mode,
            self.arduino_config.port,
            self.rak_config.port,
        )

    def stop(self) -> None:
        """Stop serial endpoints."""
        self._started = False
        for endpoint in (self._arduino_serial, self._rak_serial):
            if endpoint is None:
                continue
            try:
                endpoint.close()
            except Exception:
                pass
        self._arduino_serial = None
        self._rak_serial = None

    def poll_once(self) -> Dict[str, Any]:
        """Poll available messages and return latest bridge payload."""
        if not self.enabled:
            return {"bench_network": self._build_network_status()}

        if not self._started:
            self.start()

        if self.simulation_mode:
            self._simulate_messages()
        else:
            self._poll_serial()

        self._mode = self._compute_mode()
        self._latest_payload["bench_network"] = self._build_network_status()
        return self._latest_payload

    def _open_serial_endpoints(self) -> None:
        """Open serial ports if pyserial and devices are available."""
        if self.simulation_mode:
            return

        if serial is None:
            self.logger.warning("pyserial unavailable; bench bridge forced to simulation mode")
            self.simulation_mode = True
            return

        self._arduino_serial = self._open_serial(self.arduino_config)
        self._rak_serial = self._open_serial(self.rak_config)

        if self._arduino_serial is None and self._rak_serial is None:
            self.logger.warning("No serial bench endpoints opened; falling back to simulation")
            self.simulation_mode = True

    def _open_serial(self, endpoint: SerialEndpointConfig):
        try:
            return serial.Serial(endpoint.port, endpoint.baudrate, timeout=endpoint.timeout_s)
        except Exception as exc:
            self.logger.warning("Failed to open %s: %s", endpoint.port, exc)
            return None

    def _poll_serial(self) -> None:
        self._poll_endpoint(self._arduino_serial, source="arduino")
        self._poll_endpoint(self._rak_serial, source="rak4630")

    def _poll_endpoint(self, endpoint: Any, source: str) -> None:
        if endpoint is None:
            return

        try:
            waiting = int(getattr(endpoint, "in_waiting", 0))
        except Exception:
            waiting = 0

        if waiting <= 0:
            return

        try:
            raw = endpoint.readline()
        except Exception as exc:
            self.logger.warning("Failed to read %s serial data: %s", source, exc)
            return

        if not raw:
            return

        if isinstance(raw, bytes):
            decoded = raw.decode("utf-8", errors="replace").strip()
        else:
            decoded = str(raw).strip()

        if not decoded:
            return

        try:
            message = json.loads(decoded)
        except json.JSONDecodeError:
            self.logger.debug("Ignoring non-JSON line from %s: %s", source, decoded)
            return

        self._handle_message(source=source, message=message)

    def _simulate_messages(self) -> None:
        now = time.time()
        if now - self._last_simulation_update < 0.25:
            return

        self._last_simulation_update = now
        wave = math.sin(now / 3.0)
        soc = 62.0 + wave * 6.0
        speed = max(0.0, 40.0 + wave * 12.0)
        current = 18.0 + wave * 5.0

        self._handle_message(
            source="arduino",
            message={
                "kind": "battery_status",
                "voltage": 392.5,
                "current": current,
                "temperature": 29.0 + wave * 1.8,
                "soc": soc,
            },
        )
        self._handle_message(
            source="arduino",
            message={
                "kind": "motor_status",
                "speed_rpm": speed * 48.0,
                "torque_nm": 54.0 + wave * 8.0,
                "temperature_c": 45.0 + wave * 2.0,
            },
        )
        self._handle_message(
            source="arduino",
            message={
                "kind": "vehicle_status",
                "state": "driving",
                "speed_kmh": speed,
                "drive_mode": "normal",
                "power_kw": max(0.0, speed * 0.35),
            },
        )
        self._handle_message(
            source="rak4630",
            message={
                "kind": "link",
                "rssi_dbm": -95.0 + wave * 4.0,
                "snr_db": 7.5 + wave,
            },
        )

    def _handle_message(self, source: str, message: Dict[str, Any]) -> None:
        if not isinstance(message, dict):
            return

        now = time.time()
        self._heartbeats[source] = now
        kind = str(message.get("kind", "")).lower()

        if source == "rak4630" and kind == "link":
            self._rssi_dbm = float(message.get("rssi_dbm", self._rssi_dbm))
            self._snr_db = float(message.get("snr_db", self._snr_db))
            return

        if kind == "battery_status":
            payload = {
                "voltage": float(message.get("voltage", 0.0)),
                "current": float(message.get("current", 0.0)),
                "temperature": float(message.get("temperature", 0.0)),
                "soc": float(message.get("soc", 0.0)),
            }
            self._latest_payload["battery"] = payload
            self._emit_can_battery(payload)
            return

        if kind == "motor_status":
            payload = {
                "speed": float(message.get("speed_rpm", message.get("speed", 0.0))),
                "torque": float(message.get("torque_nm", message.get("torque", 0.0))),
                "temperature": float(message.get("temperature_c", message.get("temperature", 0.0))),
            }
            self._latest_payload["motor"] = payload
            self._emit_can_motor(payload)
            return

        if kind == "charger_status":
            payload = {
                "voltage": float(message.get("voltage", 0.0)),
                "current": float(message.get("current", 0.0)),
                "state": str(message.get("state", "idle")),
            }
            self._latest_payload["charging"] = payload
            self._emit_can_charger(payload)
            return

        if kind == "vehicle_status":
            payload = {
                "state": str(message.get("state", "ready")),
                "speed": float(message.get("speed_kmh", 0.0)),
                "drive_mode": str(message.get("drive_mode", "normal")),
                "power_kw": float(message.get("power_kw", 0.0)),
            }
            self._latest_payload["vehicle"] = payload
            return

        if kind == "temperature":
            sensor_type = str(message.get("sensor_type", "generic"))
            sensor_id = str(message.get("sensor_id", "sensor"))
            value = float(message.get("temperature_c", message.get("temperature", 0.0)))
            self._latest_payload["temperature"] = {
                "last_sensor_type": sensor_type,
                "last_sensor_id": sensor_id,
                "last_temperature_c": value,
            }
            self._emit_can_temperature(sensor_type=sensor_type, sensor_id=sensor_id, temperature_c=value)

    def _emit_can_battery(self, payload: Dict[str, Any]) -> None:
        if self.can_protocol and hasattr(self.can_protocol, "send_battery_status"):
            self.can_protocol.send_battery_status(
                voltage=float(payload.get("voltage", 0.0)),
                current=float(payload.get("current", 0.0)),
                temperature=float(payload.get("temperature", 0.0)),
                soc=float(payload.get("soc", 0.0)) / 100.0,
            )
            self._heartbeats["can"] = time.time()

    def _emit_can_motor(self, payload: Dict[str, Any]) -> None:
        if self.can_protocol and hasattr(self.can_protocol, "send_motor_status"):
            self.can_protocol.send_motor_status(
                speed=float(payload.get("speed", 0.0)),
                torque=float(payload.get("torque", 0.0)),
                temperature=float(payload.get("temperature", 0.0)),
            )
            self._heartbeats["can"] = time.time()

    def _emit_can_charger(self, payload: Dict[str, Any]) -> None:
        if self.can_protocol and hasattr(self.can_protocol, "send_charger_status"):
            self.can_protocol.send_charger_status(
                voltage=float(payload.get("voltage", 0.0)),
                current=float(payload.get("current", 0.0)),
                state=str(payload.get("state", "idle")),
            )
            self._heartbeats["can"] = time.time()

    def _emit_can_temperature(self, sensor_type: str, sensor_id: str, temperature_c: float) -> None:
        if self.can_protocol and hasattr(self.can_protocol, "send_temperature_data"):
            self.can_protocol.send_temperature_data(
                sensor_type=sensor_type,
                sensor_id=sensor_id,
                temperature=temperature_c,
            )
            self._heartbeats["can"] = time.time()

    def _compute_mode(self) -> str:
        now = time.time()
        can_healthy = (now - self._heartbeats["can"]) <= (self.heartbeat_timeout_s * 2.0)
        lora_healthy = (
            (now - self._heartbeats["rak4630"]) <= self.heartbeat_timeout_s
            and self._rssi_dbm >= self.lora_min_rssi_dbm
        )

        if self.prefer_lorawan and lora_healthy and can_healthy:
            return "dual_link"
        if can_healthy:
            return "can_primary"
        return "can_only_safe"

    def _build_network_status(self) -> Dict[str, Any]:
        now = time.time()
        return {
            "mode": self._mode,
            "prefer_lorawan": self.prefer_lorawan,
            "links": {
                "arduino": {
                    "last_heartbeat_age_s": max(0.0, now - self._heartbeats["arduino"]),
                    "online": (now - self._heartbeats["arduino"]) <= self.heartbeat_timeout_s,
                },
                "rak4630": {
                    "last_heartbeat_age_s": max(0.0, now - self._heartbeats["rak4630"]),
                    "online": (now - self._heartbeats["rak4630"]) <= self.heartbeat_timeout_s,
                    "rssi_dbm": self._rssi_dbm,
                    "snr_db": self._snr_db,
                },
                "can": {
                    "last_heartbeat_age_s": max(0.0, now - self._heartbeats["can"]),
                    "online": (now - self._heartbeats["can"]) <= (self.heartbeat_timeout_s * 2.0),
                },
            },
        }

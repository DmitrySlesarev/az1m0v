"""LoRaWAN uplink via RAK AT-command modules (e.g. RAK4631 on USB serial).

Aggregates multi-sensor snapshots from the EV stack, encodes a compact payload,
and sends uplinks on a configurable interval. Expects RUI3-style AT firmware
(AT+NWM, AT+BAND, AT+DEVEUI, AT+APPEUI, AT+APPKEY, AT+JOIN, AT+SEND).

See docs/configuration.md for the ``lorawan`` config section.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class LoRaWANState(Enum):
    """LoRaWAN manager states."""

    DISABLED = "disabled"
    DISCONNECTED = "disconnected"
    JOINING = "joining"
    JOINED = "joined"
    SENDING = "sending"
    ERROR = "error"
    SIMULATION = "simulation"


def _hex_clean(s: str) -> str:
    return re.sub(r"[^0-9a-fA-F]", "", s or "")


def _json_compact(obj: Any, max_bytes: int) -> bytes:
    """Serialize to UTF-8 JSON, shrink if over max_bytes (drops optional keys)."""
    text = json.dumps(obj, separators=(",", ":"), default=str)
    b = text.encode("utf-8")
    if len(b) <= max_bytes:
        return b
    if isinstance(obj, dict):
        drop_order = [
            "imu",
            "temperature",
            "gps",
            "charging",
            "motor",
            "vehicle",
            "battery",
        ]
        trimmed = dict(obj)
        for key in drop_order:
            if key in trimmed:
                del trimmed[key]
                text = json.dumps(trimmed, separators=(",", ":"), default=str)
                b = text.encode("utf-8")
                if len(b) <= max_bytes:
                    return b
        return b[:max_bytes]
    return b[:max_bytes]


@dataclass
class LoRaWANStats:
    uplinks_sent: int = 0
    uplinks_failed: int = 0
    last_uplink_time: float = 0.0
    last_error: Optional[str] = None
    last_rssi: Optional[int] = None
    last_snr: Optional[float] = None


@dataclass
class LoRaWANManager:
    """Collect sensor snapshots and send LoRaWAN uplinks through a RAK serial module."""

    config: Dict[str, Any]
    vehicle_id: str = "EV001"
    logger: logging.Logger = field(default_factory=lambda: logging.getLogger(__name__))

    def __post_init__(self) -> None:
        self._lock = threading.Lock()
        self._serial = None
        self.state = LoRaWANState.DISABLED
        self.stats = LoRaWANStats()
        self._sensor_snapshot: Dict[str, Any] = {}
        self._last_payload_hex: str = ""
        self._last_payload_size: int = 0
        self._next_uplink_deadline: float = 0.0
        self._joined = False

        self.enabled = bool(self.config.get("enabled", False))
        self.simulation_mode = bool(self.config.get("simulation_mode", True))
        self._sources = dict(self.config.get("sensor_sources") or {})

        if not self.enabled:
            self.state = LoRaWANState.DISABLED
            return
        if self.simulation_mode:
            self.state = LoRaWANState.SIMULATION
            self._joined = True
            self.logger.info("LoRaWAN enabled (simulation mode)")
        else:
            self.state = LoRaWANState.DISCONNECTED

    def _source_on(self, name: str) -> bool:
        return bool(self._sources.get(name, True))

    def _flush_serial_input(self) -> None:
        if self._serial and self._serial.in_waiting:
            self._serial.read(self._serial.in_waiting)

    def _read_responses(self, total_wait_s: float) -> List[str]:
        """Collect lines until idle window or total wait elapsed."""
        if not self._serial:
            return []
        deadline = time.time() + total_wait_s
        lines: List[str] = []
        idle_cycles = 0
        while time.time() < deadline:
            if self._serial.in_waiting:
                raw = self._serial.readline()
                text = raw.decode(errors="ignore").strip()
                if text:
                    lines.append(text)
                    self._parse_event_line(text)
                idle_cycles = 0
            else:
                idle_cycles += 1
                if lines and idle_cycles > 5:
                    break
                time.sleep(0.02)
        return lines

    def _parse_event_line(self, text: str) -> None:
        if "JOINED" in text.upper():
            self._joined = True
        rssi_m = re.search(r"RSSI[:=]\s*(-?\d+)", text, re.I)
        if rssi_m:
            try:
                self.stats.last_rssi = int(rssi_m.group(1))
            except ValueError:
                pass
        snr_m = re.search(r"SNR[:=]\s*(-?\d+(?:\.\d+)?)", text, re.I)
        if snr_m:
            try:
                self.stats.last_snr = float(snr_m.group(1))
            except ValueError:
                pass

    def connect(self) -> bool:
        """Open serial link and attempt LoRaWAN join (hardware mode)."""
        if not self.enabled:
            return False
        if self.simulation_mode:
            self.state = LoRaWANState.SIMULATION
            self._joined = True
            return True

        try:
            import serial  # type: ignore
        except ImportError:
            self.logger.error("pyserial is required for LoRaWAN hardware mode")
            self.state = LoRaWANState.ERROR
            self.stats.last_error = "pyserial not installed"
            return False

        port = self.config.get("serial_port") or "/dev/ttyACM0"
        baud = int(self.config.get("baudrate", 115200))
        try:
            self._serial = serial.Serial(port, baud, timeout=0.1)
        except Exception as exc:
            self.logger.error("LoRaWAN serial open failed: %s", exc)
            self.state = LoRaWANState.ERROR
            self.stats.last_error = str(exc)
            return False

        self.state = LoRaWANState.JOINING
        self._joined = False
        if not self._configure_and_join():
            self.disconnect()
            return False
        self.state = LoRaWANState.JOINED
        self._joined = True
        self.logger.info("LoRaWAN joined on %s", port)
        return True

    def disconnect(self) -> None:
        if self._serial:
            try:
                self._serial.close()
            except Exception:
                pass
            self._serial = None
        self._joined = False
        if self.enabled and not self.simulation_mode:
            self.state = LoRaWANState.DISCONNECTED

    def _at(self, cmd: str, wait_s: Optional[float] = None) -> Tuple[bool, List[str]]:
        if not self._serial:
            return False, []
        wait_s = wait_s if wait_s is not None else float(self.config.get("at_timeout_s", 5.0))
        line = cmd if cmd.upper().startswith("AT") else f"AT{cmd}"
        self._flush_serial_input()
        try:
            self._serial.write((line + "\r\n").encode())
            self._serial.flush()
        except Exception as exc:
            self.logger.error("LoRaWAN AT write failed: %s", exc)
            return False, []
        lines = self._read_responses(wait_s)
        ok = any(l.strip().upper() == "OK" for l in lines)
        err = any(l.upper().startswith("ERROR") for l in lines)
        if err:
            return False, lines
        return ok, lines

    def _configure_and_join(self) -> bool:
        ok, lines = self._at("AT")
        if not ok:
            self.logger.error("LoRaWAN module did not respond to AT (%s)", lines[-3:])
            self.stats.last_error = "AT handshake failed"
            self.state = LoRaWANState.ERROR
            return False

        band = int(self.config.get("band", 10))
        deveui = _hex_clean(self.config.get("dev_eui", ""))
        appeui = _hex_clean(self.config.get("app_eui", ""))
        appkey = _hex_clean(self.config.get("app_key", ""))

        if len(deveui) != 16 or len(appeui) != 16 or len(appkey) != 32:
            self.logger.error(
                "LoRaWAN: dev_eui (16 hex), app_eui (16 hex), app_key (32 hex) required"
            )
            self.stats.last_error = "invalid LoRaWAN keys"
            self.state = LoRaWANState.ERROR
            return False

        steps = [
            "AT+NWM=1",
            f"AT+BAND={band}",
            f"AT+DEVEUI={deveui}",
            f"AT+APPEUI={appeui}",
            f"AT+APPKEY={appkey}",
        ]
        for s in steps:
            ok, resp = self._at(s)
            if not ok:
                self.logger.error("LoRaWAN config failed at %s: %s", s, resp[-5:])
                self.stats.last_error = f"AT fail: {s}"
                self.state = LoRaWANState.ERROR
                return False

        join_timeout = float(self.config.get("join_timeout_s", 120.0))
        self._flush_serial_input()
        try:
            self._serial.write(b"AT+JOIN=1\r\n")
            self._serial.flush()
        except Exception as exc:
            self.logger.error("LoRaWAN join send failed: %s", exc)
            self.stats.last_error = str(exc)
            self.state = LoRaWANState.ERROR
            return False

        deadline = time.time() + join_timeout
        while time.time() < deadline:
            lines = self._read_responses(min(2.0, join_timeout))
            for ln in lines:
                self._parse_event_line(ln)
            if self._joined:
                return True
            time.sleep(0.1)

        self.logger.error("LoRaWAN join timed out")
        self.stats.last_error = "join timeout"
        self.state = LoRaWANState.ERROR
        return False

    def update_sensor_snapshot(self, snapshot: Dict[str, Any]) -> None:
        with self._lock:
            self._sensor_snapshot = dict(snapshot)

    def tick(self) -> None:
        if not self.enabled:
            return
        now = time.time()
        interval = float(self.config.get("update_interval_s", 60.0))
        if now < self._next_uplink_deadline:
            return

        with self._lock:
            snap = dict(self._sensor_snapshot)
        if not snap:
            self._next_uplink_deadline = now + min(interval, 5.0)
            return

        payload = self._build_payload(snap)
        self._next_uplink_deadline = now + interval

        if self.simulation_mode:
            self._last_payload_hex = payload.hex()
            self._last_payload_size = len(payload)
            self.stats.uplinks_sent += 1
            self.stats.last_uplink_time = now
            self.stats.last_error = None
            self.logger.debug(
                "LoRaWAN (sim) uplink %d bytes: %s", len(payload), self._last_payload_hex[:40]
            )
            return

        if not self._serial or not self._joined:
            self.stats.uplinks_failed += 1
            self.stats.last_error = "not joined"
            return

        self.state = LoRaWANState.SENDING
        if self._send_payload_hex(payload):
            self.stats.uplinks_sent += 1
            self.stats.last_uplink_time = now
            self.stats.last_error = None
            self.state = LoRaWANState.JOINED
        else:
            self.stats.uplinks_failed += 1
            self.state = LoRaWANState.ERROR

    def _build_payload(self, snap: Dict[str, Any]) -> bytes:
        max_bytes = int(self.config.get("max_payload_bytes", 51))
        filtered: Dict[str, Any] = {"v": self.vehicle_id, "t": time.time()}
        if self._source_on("battery") and "battery" in snap:
            filtered["battery"] = snap["battery"]
        if self._source_on("motor") and "motor" in snap:
            filtered["motor"] = snap["motor"]
        if self._source_on("vehicle") and "vehicle" in snap:
            filtered["vehicle"] = snap["vehicle"]
        if self._source_on("charging") and "charging" in snap:
            filtered["charging"] = snap["charging"]
        if self._source_on("temperature") and "temperature" in snap:
            filtered["temperature"] = snap["temperature"]
        if self._source_on("gps") and "gps" in snap:
            filtered["gps"] = snap["gps"]
        if self._source_on("imu") and "imu" in snap:
            filtered["imu"] = snap["imu"]
        return _json_compact(filtered, max_bytes)

    def _send_payload_hex(self, payload: bytes) -> bool:
        port = int(self.config.get("application_port", 2))
        ack = 1 if self.config.get("confirmed_uplink", False) else 0
        hx = payload.hex().upper()
        self._last_payload_hex = hx
        self._last_payload_size = len(payload)
        cmd = f"AT+SEND={port}:{ack}:{hx}"
        ok, lines = self._at(cmd, wait_s=float(self.config.get("send_timeout_s", 15.0)))
        if not ok:
            self.logger.warning("LoRaWAN AT+SEND failed: %s", lines[-3:])
            self.stats.last_error = "AT+SEND failed"
            return False
        return True

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            snap = self._sanitize_snapshot_for_ui(dict(self._sensor_snapshot))
        return {
            "state": self.state.value,
            "enabled": self.enabled,
            "simulation_mode": self.simulation_mode,
            "joined": self._joined if self.enabled else False,
            "sensor_sources": dict(self._sources),
            "sensor_snapshot": snap,
            "last_payload_hex_preview": (self._last_payload_hex[:64] + "...")
            if len(self._last_payload_hex) > 64
            else self._last_payload_hex,
            "last_payload_size": self._last_payload_size,
            "stats": {
                "uplinks_sent": self.stats.uplinks_sent,
                "uplinks_failed": self.stats.uplinks_failed,
                "last_uplink_time": self.stats.last_uplink_time,
                "last_error": self.stats.last_error,
                "last_rssi": self.stats.last_rssi,
                "last_snr": self.stats.last_snr,
            },
        }

    def _sanitize_snapshot_for_ui(self, snap: Dict[str, Any]) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for key, val in snap.items():
            if key == "imu" and isinstance(val, dict):
                out[key] = {
                    "temperature_c": val.get("temperature_c"),
                    "status": val.get("status"),
                    "accel": val.get("accelerometer"),
                    "gyro": val.get("gyroscope"),
                }
            else:
                out[key] = val
        return out

    def is_enabled(self) -> bool:
        return self.enabled

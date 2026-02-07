"""GPS module for the EV project.

Provides a minimal GPS interface with optional serial NMEA input or simulation mode.
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass
from typing import Optional, Dict, Any

try:
    import serial  # type: ignore
    SERIAL_AVAILABLE = True
except Exception:
    SERIAL_AVAILABLE = False
    serial = None


@dataclass
class GPSFix:
    """Single GPS fix."""
    latitude: float
    longitude: float
    altitude_m: float
    speed_kmh: float
    heading_deg: float
    timestamp: float
    satellites: Optional[int] = None
    hdop: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "altitude_m": self.altitude_m,
            "speed_kmh": self.speed_kmh,
            "heading_deg": self.heading_deg,
            "timestamp": self.timestamp,
            "satellites": self.satellites,
            "hdop": self.hdop,
        }


@dataclass
class GPSConfig:
    """GPS configuration."""
    serial_port: Optional[str] = None
    baudrate: int = 9600
    update_interval_s: float = 1.0
    simulation_mode: bool = True


class GPS:
    """Minimal GPS reader with optional NMEA serial input."""

    def __init__(self, config: GPSConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.is_connected = False
        self.last_fix: Optional[GPSFix] = None
        self.last_update_time = 0.0
        self._serial = None
        self._initialize()

    def _initialize(self) -> None:
        if self.config.simulation_mode or not self.config.serial_port:
            self.is_connected = True
            self.logger.info("GPS running in simulation mode")
            return

        if not SERIAL_AVAILABLE:
            self.logger.warning("pyserial not available, falling back to simulation mode")
            self.config.simulation_mode = True
            self.is_connected = True
            return

        try:
            self._serial = serial.Serial(self.config.serial_port, self.config.baudrate, timeout=1)
            self.is_connected = True
            self.logger.info(f"GPS connected on {self.config.serial_port}")
        except Exception as exc:
            self.logger.warning(f"Failed to open GPS serial port: {exc}")
            self.config.simulation_mode = True
            self.is_connected = True

    def read_fix(self) -> Optional[GPSFix]:
        """Return the latest GPS fix if available."""
        now = time.time()
        if now - self.last_update_time < self.config.update_interval_s:
            return self.last_fix

        if not self.is_connected:
            return None

        if self.config.simulation_mode:
            fix = self._simulate_fix(now)
        else:
            fix = self._read_serial_fix()

        if fix:
            self.last_fix = fix
            self.last_update_time = now
        return fix

    def _simulate_fix(self, timestamp: float) -> GPSFix:
        """Generate a simple circular path around a reference point."""
        base_lat = 37.4219999
        base_lon = -122.0840575
        radius_deg = 0.0003
        angle = timestamp * 0.1
        lat = base_lat + radius_deg * math.cos(angle)
        lon = base_lon + radius_deg * math.sin(angle)
        speed_kmh = 10.0 + 2.0 * math.sin(angle)
        heading = (math.degrees(angle) % 360.0)
        return GPSFix(
            latitude=lat,
            longitude=lon,
            altitude_m=5.0,
            speed_kmh=speed_kmh,
            heading_deg=heading,
            timestamp=timestamp,
            satellites=8,
            hdop=0.9,
        )

    def _read_serial_fix(self) -> Optional[GPSFix]:
        """Read and parse NMEA sentences from serial."""
        if not self._serial:
            return None

        try:
            line = self._serial.readline().decode(errors="ignore").strip()
            if not line.startswith("$"):
                return None
            if "GPRMC" in line or "GNRMC" in line:
                return self._parse_rmc(line)
            if "GPGGA" in line or "GNGGA" in line:
                return self._parse_gga(line)
        except Exception as exc:
            self.logger.debug(f"GPS read error: {exc}")
        return None

    def _parse_rmc(self, sentence: str) -> Optional[GPSFix]:
        parts = sentence.split(",")
        if len(parts) < 12 or parts[2] != "A":
            return None
        lat = self._parse_lat_lon(parts[3], parts[4])
        lon = self._parse_lat_lon(parts[5], parts[6])
        speed_kmh = float(parts[7] or 0.0) * 1.852
        heading = float(parts[8] or 0.0)
        if lat is None or lon is None:
            return None
        return GPSFix(
            latitude=lat,
            longitude=lon,
            altitude_m=0.0,
            speed_kmh=speed_kmh,
            heading_deg=heading,
            timestamp=time.time(),
        )

    def _parse_gga(self, sentence: str) -> Optional[GPSFix]:
        parts = sentence.split(",")
        if len(parts) < 10:
            return None
        lat = self._parse_lat_lon(parts[2], parts[3])
        lon = self._parse_lat_lon(parts[4], parts[5])
        satellites = int(parts[7] or 0)
        hdop = float(parts[8] or 0.0)
        altitude = float(parts[9] or 0.0)
        if lat is None or lon is None:
            return None
        return GPSFix(
            latitude=lat,
            longitude=lon,
            altitude_m=altitude,
            speed_kmh=0.0,
            heading_deg=0.0,
            timestamp=time.time(),
            satellites=satellites,
            hdop=hdop,
        )

    def _parse_lat_lon(self, raw: str, direction: str) -> Optional[float]:
        if not raw:
            return None
        try:
            if "." not in raw:
                return None
            degrees_len = 2 if direction in {"N", "S"} else 3
            degrees = float(raw[:degrees_len])
            minutes = float(raw[degrees_len:])
            value = degrees + (minutes / 60.0)
            if direction in {"S", "W"}:
                value *= -1.0
            return value
        except ValueError:
            return None

    def get_status(self) -> Dict[str, Any]:
        fix = self.last_fix
        return {
            "connected": self.is_connected,
            "simulation_mode": self.config.simulation_mode,
            "last_fix": fix.to_dict() if fix else None,
        }

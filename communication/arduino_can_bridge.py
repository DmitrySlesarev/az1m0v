"""Bridge between EV CAN bus and an Arduino peripheral (I/O coprocessor)."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from communication.can_bus import CANBusInterface, EVCANProtocol, CANFrame
from communication.arduino_peripheral_can import (
    build_arduino_command_frame,
    parse_arduino_status_frame,
)

OptionalDashboardUpdate = Optional[Callable[[str, Dict[str, Any]], None]]


class ArduinoPeripheralBridge:
    """
    Receives peripheral STATUS on CAN, sends COMMAND from dashboard / logic.

    Optional: inject analog channels into TemperatureSensorManager readings
    (see ``inject_temperatures`` in config).
    """

    def __init__(
        self,
        can_bus: CANBusInterface,
        can_protocol: EVCANProtocol,
        config: Dict[str, Any],
        temperature_manager: Optional[Any] = None,
    ):
        self.can_bus = can_bus
        self.can_protocol = can_protocol
        self.config = config or {}
        self.temperature_manager = temperature_manager
        self.logger = logging.getLogger(__name__)

        ids = self.can_protocol.CAN_IDS
        self._status_id = int(
            self.config.get("status_can_id", ids.get("ARDUINO_PERIPHERAL_STATUS", 0x310))
        )
        self._command_id = int(
            self.config.get("command_can_id", ids.get("ARDUINO_PERIPHERAL_COMMAND", 0x311))
        )
        self._analog_unit = str(self.config.get("analog_unit", "centi_c"))
        self._inject: List[Dict[str, Any]] = list(self.config.get("inject_temperatures") or [])
        self._resend_s = float(self.config.get("resend_command_interval_s", 0.0) or 0.0)

        self._digital_out = int(self.config.get("default_digital_outputs", 0)) & 0xFF
        self._pwm = max(0, min(255, int(self.config.get("default_pwm_aux", 0))))
        self._flags = int(self.config.get("default_flags", 0)) & 0xFF
        self._listen_only = bool(self.config.get("listen_only_default", False))

        self._last_status: Dict[str, Any] = {}
        self._rx_count = 0
        self._tx_count = 0
        self._lock = threading.Lock()
        self._last_command_sent = 0.0
        self._dashboard_update: OptionalDashboardUpdate = None

        self._register_handler()

    def bind_dashboard(self, update_fn: Callable[[str, Dict[str, Any]], None]) -> None:
        """Wire ``dashboard.update_data`` (or compatible)."""
        self._dashboard_update = update_fn
        self._push_dashboard_state()

    def _register_handler(self) -> None:
        def _on_frame(frame: CANFrame) -> None:
            if frame.can_id != self._status_id:
                return
            parsed = parse_arduino_status_frame(frame.data, analog_unit=self._analog_unit)
            if not parsed:
                return
            with self._lock:
                self._rx_count += 1
                self._last_status = parsed
            self._apply_injections(parsed.get("analog_c") or [])
            self._push_dashboard_state()

        self.can_bus.register_message_handler(self._status_id, _on_frame)
        self.logger.info(
            "Arduino peripheral CAN: RX ID 0x%03X, TX command ID 0x%03X",
            self._status_id,
            self._command_id,
        )

    def _apply_injections(self, analog_c: List[Optional[float]]) -> None:
        if not self._inject or not self.temperature_manager:
            return
        sensors = getattr(self.temperature_manager, "sensors", None)
        if not sensors:
            return
        for rule in self._inject:
            try:
                ch = int(rule.get("channel", 0))
                sid = str(rule.get("sensor_id", ""))
                if not sid or ch < 0 or ch >= len(analog_c):
                    continue
                val = analog_c[ch]
                if val is None:
                    continue
                if sid in sensors:
                    sensors[sid].set_temperature(float(val))
            except (TypeError, ValueError) as exc:
                self.logger.debug("inject_temperatures skip: %s", exc)

    def _push_dashboard_state(self) -> None:
        if not self._dashboard_update:
            return
        payload = self.get_status_dict()
        try:
            self._dashboard_update("arduino", payload)
        except Exception as exc:
            self.logger.warning("Dashboard update failed: %s", exc)

    def get_status_dict(self) -> Dict[str, Any]:
        with self._lock:
            last = dict(self._last_status) if self._last_status else {}
            rx = self._rx_count
            tx = self._tx_count
            dout = self._digital_out
            pwm = self._pwm
            flags = self._flags
            listen = self._listen_only
        base = {
            "enabled": True,
            "configured": True,
            "status_can_id": self._status_id,
            "command_can_id": self._command_id,
            "status_can_id_hex": f"{self._status_id:03X}",
            "command_can_id_hex": f"{self._command_id:03X}",
            "digital_outputs": dout,
            "pwm_aux": pwm,
            "flags": flags,
            "listen_only": listen,
            "frames_rx": rx,
            "frames_tx": tx,
            "last_rx_time": last.get("timestamp"),
            "digital_inputs": last.get("digital_inputs"),
            "analog_c": last.get("analog_c"),
            "analog_raw": last.get("analog_raw"),
        }
        return base

    def set_listen_only(self, enabled: bool) -> None:
        with self._lock:
            self._listen_only = bool(enabled)
        self.send_command()

    def set_digital_bit(self, bit: int, on: bool) -> None:
        bit = int(bit)
        if bit < 0 or bit > 7:
            return
        with self._lock:
            if on:
                self._digital_out |= 1 << bit
            else:
                self._digital_out &= ~(1 << bit)
        self.send_command()

    def set_pwm_aux(self, value: int) -> None:
        with self._lock:
            self._pwm = max(0, min(255, int(value)))
        self.send_command()

    def send_command(self) -> bool:
        """Emit COMMAND frame on CAN. Flag bit0 = listen_only (sketch may ignore outputs)."""
        with self._lock:
            dout = self._digital_out
            pwm = self._pwm
            flags = (self._flags & 0xFE) | (0x01 if self._listen_only else 0)
            payload = build_arduino_command_frame(dout, pwm, flags)
            self._tx_count += 1
            self._last_command_sent = time.time()

        frame = CANFrame(
            can_id=self._command_id,
            data=payload,
            timestamp=time.time(),
            dlc=8,
        )
        ok = self.can_bus.send_frame(frame)
        self._push_dashboard_state()
        return ok

    def tick(self) -> None:
        """Call from main loop to periodically refresh command frame."""
        if self._resend_s <= 0:
            return
        now = time.time()
        if now - self._last_command_sent >= self._resend_s:
            self.send_command()

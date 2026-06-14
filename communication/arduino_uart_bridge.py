"""Bridge between the EV IP/UART transport and an Arduino peripheral endpoint."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from communication.ip_uart_transport import EVTCPIPProtocol, ITFrame, TCPIPTransportInterface
from communication.uart_peripheral import (
    build_arduino_command_payload,
    parse_arduino_status_payload,
)

OptionalDashboardUpdate = Optional[Callable[[str, Dict[str, Any]], None]]


class ArduinoUARTPeripheralBridge:
    """
    Receives peripheral status from a UART endpoint and sends compact commands.

    In a Raspberry Pi deployment, IP traffic reaches the edge switch first; the
    switch then forwards these frames over COM/UART to the Arduino endpoint.
    """

    def __init__(
        self,
        transport: TCPIPTransportInterface,
        protocol: EVTCPIPProtocol,
        config: Dict[str, Any],
        temperature_manager: Optional[Any] = None,
    ):
        self.transport = transport
        self.protocol = protocol
        self.config = config or {}
        self.temperature_manager = temperature_manager
        self.logger = logging.getLogger(__name__)

        ids = self.protocol.SERVICE_IDS
        self._status_id = int(
            self.config.get("status_service_id", self.config.get("status_can_id", ids["ARDUINO_PERIPHERAL_STATUS"]))
        )
        self._command_id = int(
            self.config.get("command_service_id", self.config.get("command_can_id", ids["ARDUINO_PERIPHERAL_COMMAND"]))
        )
        self._destination = str(self.config.get("destination", "peripheral"))
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
        """Wire ``dashboard.update_data`` or a compatible callback."""

        self._dashboard_update = update_fn
        self._push_dashboard_state()

    def _register_handler(self) -> None:
        def _on_frame(frame: ITFrame) -> None:
            service_id = getattr(frame, "service_id", None)
            if not isinstance(service_id, int):
                service_id = getattr(frame, "can_id", None)
            if service_id != self._status_id:
                return
            payload = getattr(frame, "payload", None)
            if not isinstance(payload, (bytes, bytearray)):
                payload = getattr(frame, "data", b"")
            parsed = parse_arduino_status_payload(payload, analog_unit=self._analog_unit)
            if not parsed:
                return
            with self._lock:
                self._rx_count += 1
                self._last_status = parsed
            self._apply_injections(parsed.get("analog_c") or [])
            self._push_dashboard_state()

        self.transport.register_message_handler(self._status_id, _on_frame)
        self.logger.info(
            "Arduino UART peripheral: RX service 0x%04X, TX command service 0x%04X, destination %s",
            self._status_id,
            self._command_id,
            self._destination,
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
        try:
            self._dashboard_update("arduino", self.get_status_dict())
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
        return {
            "enabled": True,
            "configured": True,
            "status_service_id": self._status_id,
            "command_service_id": self._command_id,
            "status_can_id": self._status_id,
            "command_can_id": self._command_id,
            "status_can_id_hex": f"{self._status_id:04X}",
            "command_can_id_hex": f"{self._command_id:04X}",
            "destination": self._destination,
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
        """Emit a command frame toward the configured UART endpoint destination."""

        with self._lock:
            dout = self._digital_out
            pwm = self._pwm
            flags = (self._flags & 0xFE) | (0x01 if self._listen_only else 0)
            payload = build_arduino_command_payload(dout, pwm, flags)
            self._tx_count += 1
            self._last_command_sent = time.time()

        frame = ITFrame(
            service_id=self._command_id,
            payload=payload,
            source="raspberry-pi",
            destination=self._destination,
            timestamp=time.time(),
            metadata={"endpoint": "arduino"},
        )
        ok = self.transport.send_frame(frame)
        self._push_dashboard_state()
        return ok

    def tick(self) -> None:
        """Call from the main loop to periodically refresh command frames."""

        if self._resend_s <= 0:
            return
        now = time.time()
        if now - self._last_command_sent >= self._resend_s:
            self.send_command()


ArduinoPeripheralBridge = ArduinoUARTPeripheralBridge

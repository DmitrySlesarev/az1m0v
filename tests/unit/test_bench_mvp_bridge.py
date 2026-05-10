"""Unit tests for bench MVP bridge."""

import time
from unittest.mock import Mock

from communication.bench_mvp_bridge import BenchMVPBridge


def test_simulation_poll_updates_payload_and_network_mode():
    bridge = BenchMVPBridge(
        config={
            "enabled": True,
            "simulation_mode": True,
            "prefer_lorawan": True,
            "heartbeat_timeout_s": 10.0,
            "lora_min_rssi_dbm": -120.0,
        }
    )

    bridge.start()
    payload = bridge.poll_once()

    assert "battery" in payload
    assert "motor" in payload
    assert "vehicle" in payload
    assert "bench_network" in payload
    assert payload["bench_network"]["mode"] in {"dual_link", "can_primary"}


def test_mode_falls_back_to_can_primary_when_lora_stale():
    bridge = BenchMVPBridge(
        config={
            "enabled": True,
            "simulation_mode": True,
            "prefer_lorawan": True,
            "heartbeat_timeout_s": 2.0,
            "lora_min_rssi_dbm": -110.0,
        }
    )
    bridge.start()
    bridge.poll_once()

    now = time.time()
    bridge._heartbeats["can"] = now
    bridge._heartbeats["rak4630"] = now - 10.0
    bridge._rssi_dbm = -95.0

    payload = bridge.poll_once()
    assert payload["bench_network"]["mode"] == "can_primary"


def test_battery_message_is_forwarded_to_can_protocol():
    can_protocol = Mock()
    bridge = BenchMVPBridge(
        config={"enabled": True, "simulation_mode": True},
        can_protocol=can_protocol,
    )

    bridge._handle_message(
        source="arduino",
        message={
            "kind": "battery_status",
            "voltage": 398.0,
            "current": 23.5,
            "temperature": 31.0,
            "soc": 80.0,
        },
    )

    can_protocol.send_battery_status.assert_called_once()
    args = can_protocol.send_battery_status.call_args.kwargs
    assert args["voltage"] == 398.0
    assert args["current"] == 23.5
    assert args["temperature"] == 31.0
    assert args["soc"] == 0.8

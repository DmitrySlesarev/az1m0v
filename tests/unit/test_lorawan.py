"""Unit tests for LoRaWAN manager."""

from communication.lorawan import LoRaWANManager, LoRaWANState


def _base_cfg(**overrides):
    cfg = {
        "enabled": True,
        "simulation_mode": True,
        "serial_port": "/dev/ttyACM0",
        "baudrate": 115200,
        "band": 10,
        "dev_eui": "",
        "app_eui": "",
        "app_key": "",
        "application_port": 2,
        "confirmed_uplink": False,
        "update_interval_s": 0.01,
        "max_payload_bytes": 120,
        "join_timeout_s": 120.0,
        "at_timeout_s": 5.0,
        "send_timeout_s": 15.0,
        "sensor_sources": {
            "battery": True,
            "motor": False,
            "vehicle": True,
            "charging": False,
            "temperature": False,
            "gps": False,
            "imu": False,
        },
    }
    cfg.update(overrides)
    return cfg


class TestLoRaWANManager:
    def test_disabled_manager(self):
        m = LoRaWANManager(config={"enabled": False}, vehicle_id="T1")
        assert m.state == LoRaWANState.DISABLED
        assert not m.is_enabled()
        m.tick()
        assert m.stats.uplinks_sent == 0

    def test_simulation_connect_and_uplink(self):
        m = LoRaWANManager(config=_base_cfg(), vehicle_id="EVSIM")
        assert m.connect()
        assert m.state == LoRaWANState.SIMULATION
        m.update_sensor_snapshot(
            {"battery": {"soc": 42.0, "voltage": 400.0}, "vehicle": {"speed_kmh": 12.0}}
        )
        m.tick()
        assert m.stats.uplinks_sent == 1
        assert m._last_payload_size > 0
        st = m.get_status()
        assert st["enabled"] is True
        assert st["sensor_snapshot"]["battery"]["soc"] == 42.0
        assert st["stats"]["uplinks_sent"] == 1

    def test_sensor_sources_filter_motor(self):
        m = LoRaWANManager(config=_base_cfg(sensor_sources={"motor": True, "battery": False}))
        m.connect()
        m.update_sensor_snapshot(
            {"battery": {"soc": 99.0}, "motor": {"speed_rpm": 1000.0}}
        )
        m.tick()
        raw = bytes.fromhex(m._last_payload_hex)
        assert b"motor" in raw
        assert b"battery" not in raw

    def test_get_status_includes_joined_in_simulation(self):
        m = LoRaWANManager(config=_base_cfg(), vehicle_id="X")
        m.connect()
        assert m.get_status()["joined"] is True

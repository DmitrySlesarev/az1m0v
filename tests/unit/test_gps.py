"""Unit tests for GPS module."""

from sensors.gps import GPS, GPSConfig


def test_gps_simulation_fix():
    """GPS simulation should return a valid fix."""
    gps = GPS(GPSConfig(simulation_mode=True))
    fix = gps.read_fix()

    assert gps.is_connected is True
    assert fix is not None
    assert -90.0 <= fix.latitude <= 90.0
    assert -180.0 <= fix.longitude <= 180.0
    assert fix.speed_kmh >= 0.0

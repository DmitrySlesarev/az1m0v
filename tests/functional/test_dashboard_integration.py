"""Functional/integration tests for EV dashboard."""

import pytest
import time
import threading
from unittest.mock import Mock, MagicMock, patch
from ui.dashboard import EVDashboard
from communication.can_bus import CANBusInterface, EVCANProtocol, CANFrame
import struct


class TestDashboardIntegration:
    """Integration tests for dashboard with CAN bus."""

    @pytest.fixture
    def can_interface(self):
        """Create a CAN bus interface for testing."""
        interface = CANBusInterface("can0", 500000)
        interface.connect()
        return interface

    @pytest.fixture
    def ev_protocol(self, can_interface):
        """Create an EV CAN protocol instance."""
        return EVCANProtocol(can_interface)

    @pytest.fixture
    def dashboard(self, can_interface, ev_protocol):
        """Create a dashboard instance with CAN bus integration."""
        with patch('ui.dashboard.Flask'), patch('ui.dashboard.SocketIO'):
            dashboard = EVDashboard(
                can_bus=can_interface,
                can_protocol=ev_protocol,
                host='127.0.0.1',
                port=5003,
                debug=False
            )
            return dashboard

    def test_dashboard_can_integration(self, dashboard, can_interface, ev_protocol):
        """Test dashboard integration with CAN bus."""
        # Verify CAN bus is connected
        assert dashboard.can_bus == can_interface
        assert dashboard.can_protocol == ev_protocol
        
        # Verify handlers are registered
        dashboard._register_can_handlers()
        assert len(can_interface.message_handlers) > 0

    def test_dashboard_receives_can_data(self, dashboard):
        """Test that dashboard receives and processes CAN data."""
        # Simulate CAN frame data
        voltage = 400.0
        current = 50.0
        temperature = 25.0
        soc = 0.85
        
        # Update dashboard directly (simulating CAN handler)
        dashboard._update_battery_data(voltage, current, temperature, soc)
        
        # Verify data is stored
        assert dashboard.latest_data['battery']['voltage'] == 400.0
        assert dashboard.latest_data['battery']['current'] == 50.0
        assert dashboard.latest_data['battery']['temperature'] == 25.0
        assert dashboard.latest_data['battery']['soc'] == 85.0

    def test_dashboard_can_stats_update(self, dashboard, can_interface):
        """Test that dashboard updates CAN statistics."""
        # Send some frames
        frame1 = CANFrame(
            can_id=0x183,
            data=b'\x00' * 8,
            timestamp=time.time(),
            dlc=8
        )
        frame2 = CANFrame(
            can_id=0x203,
            data=b'\x00' * 8,
            timestamp=time.time(),
            dlc=8
        )
        
        can_interface.send_frame(frame1)
        can_interface.send_frame(frame2)
        
        # Update stats
        dashboard._update_can_stats()
        
        # Verify stats are updated
        assert dashboard.latest_data['can_stats']['frames_sent'] >= 2
        assert dashboard.latest_data['can_stats']['is_connected'] is True

    def test_dashboard_multiple_data_updates(self, dashboard):
        """Test dashboard handling multiple data updates."""
        # Update battery
        dashboard._update_battery_data(400.0, 50.0, 25.0, 0.85)
        
        # Update motor
        dashboard._update_motor_data(3000.0, 150.0, 60.0)
        
        # Update charging
        dashboard._update_charging_data(400.0, 30.0, 'charging')
        
        # Update vehicle
        dashboard._update_vehicle_data('driving')
        
        # Verify all data is present
        assert dashboard.latest_data['battery']['voltage'] == 400.0
        assert dashboard.latest_data['motor']['speed'] == 3000.0
        assert dashboard.latest_data['charging']['state'] == 'charging'
        assert dashboard.latest_data['vehicle']['state'] == 'driving'

    def test_dashboard_manual_data_update(self, dashboard):
        """Test manual data update via update_data method."""
        dashboard.update_data('battery', {'voltage': 400.0, 'current': 50.0})
        dashboard.update_data('motor', {'speed': 3000.0, 'torque': 150.0})
        
        assert dashboard.latest_data['battery']['voltage'] == 400.0
        assert dashboard.latest_data['battery']['current'] == 50.0
        assert dashboard.latest_data['motor']['speed'] == 3000.0
        assert dashboard.latest_data['motor']['torque'] == 150.0

    def test_dashboard_timestamp_updates(self, dashboard):
        """Test that timestamps are updated on data changes."""
        initial_time = dashboard.latest_data['timestamp']
        time.sleep(0.1)
        
        dashboard._update_battery_data(400.0, 50.0, 25.0, 0.85)
        
        assert dashboard.latest_data['timestamp'] > initial_time

    def test_dashboard_without_can_bus(self):
        """Test dashboard functionality without CAN bus."""
        with patch('ui.dashboard.Flask'), patch('ui.dashboard.SocketIO'):
            dashboard = EVDashboard(host='127.0.0.1', port=5004)
            
            # Should work without CAN bus
            dashboard._update_battery_data(400.0, 50.0, 25.0, 0.85)
            dashboard._update_can_stats()  # Should not raise error
            
            assert dashboard.latest_data['battery']['voltage'] == 400.0

    def test_dashboard_data_rounding(self, dashboard):
        """Test that dashboard data is properly rounded."""
        dashboard._update_battery_data(400.123456, 50.987654, 25.555555, 0.851234)
        
        # Check rounding to 2 decimal places (except SOC which is percentage)
        assert dashboard.latest_data['battery']['voltage'] == 400.12
        assert dashboard.latest_data['battery']['current'] == 50.99
        assert dashboard.latest_data['battery']['temperature'] == 25.56
        assert dashboard.latest_data['battery']['soc'] == 85.1  # Percentage with 1 decimal


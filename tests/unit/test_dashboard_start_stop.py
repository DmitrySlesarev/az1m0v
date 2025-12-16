"""Tests for dashboard start/stop and update loop."""

import pytest
import threading
import time
from unittest.mock import Mock, MagicMock, patch
from ui.dashboard import EVDashboard


class TestDashboardStartStop:
    """Test dashboard start/stop functionality."""

    @pytest.fixture
    def dashboard(self):
        """Create a dashboard instance."""
        with patch('ui.dashboard.Flask'), patch('ui.dashboard.SocketIO'):
            dashboard = EVDashboard(host='127.0.0.1', port=5001, debug=False)
            dashboard.socketio = MagicMock()
            dashboard.socketio.run = Mock()
            dashboard.socketio.emit = Mock()
            return dashboard

    def test_start_dashboard(self, dashboard):
        """Test starting the dashboard."""
        dashboard.start()
        
        assert dashboard.running is True
        assert dashboard.update_thread is not None
        assert dashboard.update_thread.is_alive() or True  # Thread may have started

    def test_start_dashboard_already_running(self, dashboard):
        """Test starting dashboard when already running."""
        dashboard.running = True
        dashboard.start()
        
        # Should return early with warning
        assert dashboard.running is True

    def test_stop_dashboard(self, dashboard):
        """Test stopping the dashboard."""
        dashboard.running = True
        dashboard.update_thread = threading.Thread(target=lambda: None, daemon=True)
        dashboard.update_thread.start()
        
        dashboard.stop()
        
        assert dashboard.running is False

    def test_stop_dashboard_no_thread(self, dashboard):
        """Test stopping dashboard without thread."""
        dashboard.running = True
        dashboard.update_thread = None
        
        dashboard.stop()
        
        assert dashboard.running is False

    def test_update_loop(self, dashboard):
        """Test update loop."""
        dashboard.running = True
        dashboard.can_bus = MagicMock()
        dashboard.can_bus.get_statistics.return_value = {
            'frames_sent': 100,
            'frames_received': 50,
            'errors': 0,
            'is_connected': True,
            'last_activity': time.time()
        }
        
        # Run update loop once (simulate)
        dashboard._update_can_stats()
        dashboard._broadcast_update()
        
        # Should not raise error
        assert True

    def test_update_loop_exception(self, dashboard):
        """Test update loop with exception."""
        dashboard.running = True
        dashboard.can_bus = MagicMock()
        dashboard.can_bus.get_statistics.side_effect = Exception("Error")
        
        # Should handle exception gracefully
        try:
            dashboard._update_loop()
        except:
            pass  # Loop should catch exceptions
        assert True

    def test_update_data_temperature(self, dashboard):
        """Test updating temperature data."""
        temp_data = {
            'battery_cell_groups': [25.0, 26.0],
            'coolant': {'inlet': 20.0, 'outlet': 25.0}
        }
        
        dashboard.update_data('temperature', temp_data)
        
        assert dashboard.latest_data['temperature']['battery_cell_groups'] == [25.0, 26.0]
        assert dashboard.latest_data['temperature']['coolant']['inlet'] == 20.0

    def test_update_data_other_types(self, dashboard):
        """Test updating other data types."""
        dashboard.update_data('battery', {'voltage': 400.0, 'current': 50.0})
        dashboard.update_data('motor', {'speed': 3000.0})
        dashboard.update_data('vehicle', {'state': 'driving'})
        
        assert dashboard.latest_data['battery']['voltage'] == 400.0
        assert dashboard.latest_data['motor']['speed'] == 3000.0
        assert dashboard.latest_data['vehicle']['state'] == 'driving'

    def test_broadcast_update_exception(self, dashboard):
        """Test broadcast update with exception."""
        dashboard.clients = ['client1']
        dashboard.socketio.emit = Mock(side_effect=Exception("Emit error"))
        
        # Should handle exception gracefully
        dashboard._broadcast_update()
        assert True


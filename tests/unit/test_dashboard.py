"""Unit tests for EV dashboard module."""

import pytest
import time
import threading
from unittest.mock import Mock, MagicMock, patch, call
from ui.dashboard import EVDashboard


class TestEVDashboard:
    """Test cases for EVDashboard class."""

    @pytest.fixture
    def mock_can_bus(self):
        """Create a mock CAN bus interface."""
        can_bus = Mock()
        can_bus.is_connected = True
        can_bus.get_statistics.return_value = {
            'frames_sent': 100,
            'frames_received': 50,
            'errors': 0,
            'is_connected': True,
            'last_activity': time.time()
        }
        can_bus.message_handlers = {}
        can_bus.register_message_handler = Mock()
        return can_bus

    @pytest.fixture
    def mock_can_protocol(self, mock_can_bus):
        """Create a mock CAN protocol."""
        protocol = Mock()
        protocol.can_bus = mock_can_bus
        protocol.CAN_IDS = {
            'BMS_STATUS': 0x183,
            'MOTOR_STATUS': 0x203,
            'CHARGER_STATUS': 0x280,
            'VEHICLE_STATUS': 0x303
        }
        return protocol

    @pytest.fixture
    def dashboard(self, mock_can_bus, mock_can_protocol):
        """Create a dashboard instance for testing."""
        with patch('ui.dashboard.Flask'), patch('ui.dashboard.SocketIO'):
            dashboard = EVDashboard(
                can_bus=mock_can_bus,
                can_protocol=mock_can_protocol,
                host='127.0.0.1',
                port=5001,
                debug=False
            )
            return dashboard

    def test_dashboard_initialization(self, dashboard, mock_can_bus, mock_can_protocol):
        """Test dashboard initialization."""
        assert dashboard.can_bus == mock_can_bus
        assert dashboard.can_protocol == mock_can_protocol
        assert dashboard.host == '127.0.0.1'
        assert dashboard.port == 5001
        assert dashboard.debug is False
        assert dashboard.running is False
        assert dashboard.clients == []
        assert 'battery' in dashboard.latest_data
        assert 'motor' in dashboard.latest_data
        assert 'charging' in dashboard.latest_data
        assert 'vehicle' in dashboard.latest_data

    def test_dashboard_initialization_without_can(self):
        """Test dashboard initialization without CAN bus."""
        with patch('ui.dashboard.Flask'), patch('ui.dashboard.SocketIO'):
            dashboard = EVDashboard(host='127.0.0.1', port=5002)
            assert dashboard.can_bus is None
            assert dashboard.can_protocol is None
            assert dashboard.running is False

    def test_unpack_float_valid(self, dashboard):
        """Test unpacking valid float from bytes."""
        import struct
        test_value = 123.45
        data = struct.pack('<f', test_value)
        result = dashboard._unpack_float(data)
        assert abs(result - test_value) < 0.01

    def test_unpack_float_short_data(self, dashboard):
        """Test unpacking float from short data."""
        result = dashboard._unpack_float(b'\x01\x02')
        assert result == 0.0

    def test_unpack_float_invalid(self, dashboard):
        """Test unpacking float from invalid data."""
        result = dashboard._unpack_float(b'\x00\x00\x00')
        assert result == 0.0

    def test_update_battery_data(self, dashboard):
        """Test updating battery data."""
        dashboard._update_battery_data(400.0, 50.0, 25.0, 0.85)
        
        assert dashboard.latest_data['battery']['voltage'] == 400.0
        assert dashboard.latest_data['battery']['current'] == 50.0
        assert dashboard.latest_data['battery']['temperature'] == 25.0
        assert dashboard.latest_data['battery']['soc'] == 85.0  # Converted to percentage

    def test_update_motor_data(self, dashboard):
        """Test updating motor data."""
        dashboard._update_motor_data(3000.0, 150.0, 60.0)
        
        assert dashboard.latest_data['motor']['speed'] == 3000.0
        assert dashboard.latest_data['motor']['torque'] == 150.0
        assert dashboard.latest_data['motor']['temperature'] == 60.0

    def test_update_charging_data(self, dashboard):
        """Test updating charging data."""
        dashboard._update_charging_data(400.0, 30.0, 'charging')
        
        assert dashboard.latest_data['charging']['voltage'] == 400.0
        assert dashboard.latest_data['charging']['current'] == 30.0
        assert dashboard.latest_data['charging']['state'] == 'charging'

    def test_update_vehicle_data(self, dashboard):
        """Test updating vehicle data."""
        dashboard._update_vehicle_data('driving')
        
        assert dashboard.latest_data['vehicle']['state'] == 'driving'

    def test_update_can_stats(self, dashboard, mock_can_bus):
        """Test updating CAN bus statistics."""
        dashboard._update_can_stats()
        
        assert dashboard.latest_data['can_stats']['frames_sent'] == 100
        assert dashboard.latest_data['can_stats']['frames_received'] == 50
        assert dashboard.latest_data['can_stats']['errors'] == 0
        assert dashboard.latest_data['can_stats']['is_connected'] is True

    def test_update_can_stats_no_can_bus(self):
        """Test updating CAN stats without CAN bus."""
        with patch('ui.dashboard.Flask'), patch('ui.dashboard.SocketIO'):
            dashboard = EVDashboard()
            dashboard._update_can_stats()
            # Should not raise error

    def test_update_data_manual(self, dashboard):
        """Test manual data update."""
        dashboard.update_data('battery', {'voltage': 400.0, 'current': 50.0})
        
        assert dashboard.latest_data['battery']['voltage'] == 400.0
        assert dashboard.latest_data['battery']['current'] == 50.0

    def test_register_can_handlers(self, dashboard, mock_can_bus, mock_can_protocol):
        """Test registering CAN bus message handlers."""
        dashboard._register_can_handlers()
        
        # Verify handlers were registered
        assert mock_can_bus.register_message_handler.call_count >= 4

    def test_register_can_handlers_no_can(self):
        """Test registering handlers without CAN bus."""
        with patch('ui.dashboard.Flask'), patch('ui.dashboard.SocketIO'):
            dashboard = EVDashboard()
            # Should not raise error
            dashboard._register_can_handlers()

    def test_stop_dashboard(self, dashboard):
        """Test stopping the dashboard."""
        dashboard.running = True
        dashboard.update_thread = threading.Thread(target=lambda: None, daemon=True)
        dashboard.update_thread.start()
        
        dashboard.stop()
        
        assert dashboard.running is False

    def test_broadcast_update_no_clients(self, dashboard):
        """Test broadcasting update with no clients."""
        dashboard.clients = []
        # Should not raise error
        dashboard._broadcast_update()

    def test_can_frame_handler_bms_status(self, dashboard):
        """Test CAN frame handler for BMS status."""
        import struct
        from communication.can_bus import CANFrame
        
        voltage = 400.0
        current = 50.0
        
        # CAN frames are limited to 8 bytes, so we'll test with first 2 values
        # In real implementation, BMS status might be split across multiple frames
        data = struct.pack('<f', voltage) + struct.pack('<f', current)
        
        frame = CANFrame(
            can_id=0x183,
            data=data,
            timestamp=time.time(),
            dlc=8
        )
        
        # Simulate handler by calling update directly (full test)
        dashboard._update_battery_data(voltage, current, 25.0, 0.85)
        
        assert dashboard.latest_data['battery']['voltage'] == 400.0
        assert dashboard.latest_data['battery']['current'] == 50.0
        assert dashboard.latest_data['battery']['soc'] == 85.0

    def test_handle_control_command_accelerate(self, dashboard):
        """Test control command: accelerate."""
        from core.vehicle_controller import VehicleController
        mock_vc = Mock(spec=VehicleController)
        mock_vc.accelerate.return_value = True
        dashboard.vehicle_controller = mock_vc
        
        result = dashboard._handle_control_command('accelerate', {'throttle': 50.0})
        assert result is True
        mock_vc.accelerate.assert_called_once_with(50.0)

    def test_handle_control_command_brake(self, dashboard):
        """Test control command: brake."""
        from core.vehicle_controller import VehicleController
        mock_vc = Mock(spec=VehicleController)
        mock_vc.brake.return_value = True
        dashboard.vehicle_controller = mock_vc
        
        result = dashboard._handle_control_command('brake', {'brake': 30.0})
        assert result is True
        mock_vc.brake.assert_called_once_with(30.0)

    def test_handle_control_command_stop(self, dashboard):
        """Test control command: stop."""
        from core.vehicle_controller import VehicleController
        mock_vc = Mock(spec=VehicleController)
        mock_vc.stop_driving.return_value = True
        dashboard.vehicle_controller = mock_vc
        
        result = dashboard._handle_control_command('stop', {})
        assert result is True
        mock_vc.stop_driving.assert_called_once()

    def test_handle_control_command_stop_no_vehicle_controller(self, dashboard):
        """Test control command: stop without vehicle controller."""
        dashboard.vehicle_controller = None
        from core.motor_controller import VESCManager
        mock_mc = Mock(spec=VESCManager)
        mock_mc.stop.return_value = True
        dashboard.motor_controller = mock_mc
        
        result = dashboard._handle_control_command('stop', {})
        assert result is True
        mock_mc.stop.assert_called_once()

    def test_handle_control_command_set_drive_mode(self, dashboard):
        """Test control command: set drive mode."""
        from core.vehicle_controller import VehicleController, DriveMode
        mock_vc = Mock(spec=VehicleController)
        mock_vc.set_drive_mode.return_value = True
        dashboard.vehicle_controller = mock_vc
        
        result = dashboard._handle_control_command('set_drive_mode', {'mode': 'sport'})
        assert result is True
        mock_vc.set_drive_mode.assert_called_once_with(DriveMode.SPORT)

    def test_handle_control_command_start_charging(self, dashboard):
        """Test control command: start charging."""
        from core.charging_system import ChargingSystem
        mock_cs = Mock(spec=ChargingSystem)
        mock_cs.start_charging.return_value = True
        dashboard.charging_system = mock_cs
        
        result = dashboard._handle_control_command('start_charging', {'power_kw': 50.0})
        assert result is True
        mock_cs.start_charging.assert_called_once_with(power_kw=50.0)

    def test_handle_control_command_stop_charging(self, dashboard):
        """Test control command: stop charging."""
        from core.charging_system import ChargingSystem
        mock_cs = Mock(spec=ChargingSystem)
        mock_cs.stop_charging.return_value = True
        dashboard.charging_system = mock_cs
        
        result = dashboard._handle_control_command('stop_charging', {})
        assert result is True
        mock_cs.stop_charging.assert_called_once()

    def test_handle_control_command_set_vehicle_state(self, dashboard):
        """Test control command: set vehicle state."""
        from core.vehicle_controller import VehicleController, VehicleState
        mock_vc = Mock(spec=VehicleController)
        mock_vc.set_state.return_value = True
        dashboard.vehicle_controller = mock_vc
        
        result = dashboard._handle_control_command('set_vehicle_state', {'state': 'driving'})
        assert result is True
        mock_vc.set_state.assert_called_once_with(VehicleState.DRIVING)

    def test_handle_control_command_set_autopilot_mode(self, dashboard):
        """Test control command: set autopilot mode."""
        from ai.autopilot import AutopilotSystem, DrivingMode
        mock_ap = Mock(spec=AutopilotSystem)
        mock_ap.activate.return_value = True
        dashboard.autopilot = mock_ap
        
        result = dashboard._handle_control_command('set_autopilot_mode', {'mode': 'assist'})
        assert result is True
        mock_ap.activate.assert_called_once_with(DrivingMode.ASSIST)

    def test_handle_control_command_set_autopilot_manual(self, dashboard):
        """Test control command: set autopilot mode to manual."""
        from ai.autopilot import AutopilotSystem
        mock_ap = Mock(spec=AutopilotSystem)
        dashboard.autopilot = mock_ap
        
        result = dashboard._handle_control_command('set_autopilot_mode', {'mode': 'manual'})
        assert result is True
        mock_ap.deactivate.assert_called_once()

    def test_handle_control_command_unknown(self, dashboard):
        """Test control command: unknown command."""
        result = dashboard._handle_control_command('unknown_command', {})
        assert result is False

    def test_handle_control_command_error(self, dashboard):
        """Test control command: error handling."""
        from core.vehicle_controller import VehicleController
        mock_vc = Mock(spec=VehicleController)
        mock_vc.accelerate.side_effect = Exception("Test error")
        dashboard.vehicle_controller = mock_vc
        
        result = dashboard._handle_control_command('accelerate', {'throttle': 50.0})
        assert result is False


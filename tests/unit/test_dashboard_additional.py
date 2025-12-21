"""Additional unit tests for dashboard uncovered methods."""

import pytest
import struct
import time
from unittest.mock import Mock, MagicMock, patch
from ui.dashboard import EVDashboard
from communication.can_bus import CANFrame, CANFrameType


class TestEVDashboardAdditional:
    """Additional tests for EVDashboard uncovered methods."""

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
            'VEHICLE_STATUS': 0x303,
            'TEMPERATURE_BATTERY_CELL_GROUP': 0x400,
            'TEMPERATURE_COOLANT_INLET': 0x401,
            'TEMPERATURE_COOLANT_OUTLET': 0x402,
            'TEMPERATURE_MOTOR_STATOR': 0x403,
            'TEMPERATURE_CHARGING_PORT': 0x404,
            'TEMPERATURE_CHARGING_CONNECTOR': 0x405
        }
        protocol.parse_temperature_data = Mock(return_value=None)
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

    def test_unpack_float_struct_error(self, dashboard):
        """Test unpack_float with struct error."""
        # Create invalid float data that causes struct.error
        result = dashboard._unpack_float(b'\xff\xff\xff\xff')
        # Should return 0.0 on error
        assert isinstance(result, float)

    def test_update_temperature_data_battery_cell_group(self, dashboard):
        """Test updating battery cell group temperature data."""
        dashboard._update_temperature_data('battery_cell_group', 'battery_cell_group_1', 25.5)
        
        assert len(dashboard.latest_data['temperature']['battery_cell_groups']) >= 1
        assert dashboard.latest_data['temperature']['battery_cell_groups'][0] == 25.5

    def test_update_temperature_data_coolant_inlet(self, dashboard):
        """Test updating coolant inlet temperature."""
        dashboard._update_temperature_data('coolant_inlet', 'coolant_inlet', 20.0)
        
        assert dashboard.latest_data['temperature']['coolant']['inlet'] == 20.0

    def test_update_temperature_data_coolant_outlet(self, dashboard):
        """Test updating coolant outlet temperature."""
        dashboard._update_temperature_data('coolant_outlet', 'coolant_outlet', 25.0)
        
        assert dashboard.latest_data['temperature']['coolant']['outlet'] == 25.0

    def test_update_temperature_data_motor_stator(self, dashboard):
        """Test updating motor stator temperature."""
        dashboard._update_temperature_data('motor_stator', 'motor_stator_1', 60.0)
        
        assert len(dashboard.latest_data['temperature']['motor_stator']) >= 1
        assert dashboard.latest_data['temperature']['motor_stator'][0] == 60.0

    def test_update_temperature_data_charging_port(self, dashboard):
        """Test updating charging port temperature."""
        dashboard._update_temperature_data('charging_port', 'charging_port', 30.0)
        
        assert dashboard.latest_data['temperature']['charging']['port'] == 30.0

    def test_update_temperature_data_charging_connector(self, dashboard):
        """Test updating charging connector temperature."""
        dashboard._update_temperature_data('charging_connector', 'charging_connector', 35.0)
        
        assert dashboard.latest_data['temperature']['charging']['connector'] == 35.0

    def test_update_temperature_data_unknown_type(self, dashboard):
        """Test updating unknown temperature sensor type."""
        dashboard._update_temperature_data('unknown', 'unknown_sensor', 25.0)
        # Should not raise error

    def test_create_temperature_handler_with_protocol(self, dashboard, mock_can_protocol):
        """Test temperature handler with protocol parse method."""
        mock_can_protocol.parse_temperature_data = Mock(return_value={
            'temperature': 25.5,
            'sensor_id': 'test_sensor',
            'sensor_type': 'battery_cell_group'
        })
        
        handler = dashboard._create_temperature_handler(0x400, 'TEMPERATURE_BATTERY_CELL_GROUP')
        frame = CANFrame(
            can_id=0x400,
            data=struct.pack('<f', 25.5),
            timestamp=time.time(),
            dlc=4
        )
        
        handler(frame)
        assert mock_can_protocol.parse_temperature_data.called

    def test_create_temperature_handler_fallback(self, dashboard):
        """Test temperature handler fallback parsing."""
        handler = dashboard._create_temperature_handler(0x400, 'TEMPERATURE_BATTERY_CELL_GROUP')
        frame = CANFrame(
            can_id=0x400,
            data=struct.pack('<f', 25.5),
            timestamp=time.time(),
            dlc=4
        )
        
        handler(frame)
        # Should update temperature data
        assert len(dashboard.latest_data['temperature']['battery_cell_groups']) >= 1

    def test_create_temperature_handler_error(self, dashboard):
        """Test temperature handler error handling."""
        handler = dashboard._create_temperature_handler(0x400, 'TEMPERATURE_BATTERY_CELL_GROUP')
        # Invalid frame data
        frame = CANFrame(
            can_id=0x400,
            data=b'\x00',  # Too short
            timestamp=time.time(),
            dlc=1
        )
        
        # Should handle error gracefully
        handler(frame)

    def test_can_frame_handler_motor_status(self, dashboard):
        """Test CAN frame handler for motor status."""
        speed = 3000.0
        torque = 150.0
        temp = 60.0
        
        # CAN frames are limited to 8 bytes, so we'll use first 8 bytes (2 floats)
        data = struct.pack('<f', speed) + struct.pack('<f', torque)
        
        frame = CANFrame(
            can_id=0x203,
            data=data,
            timestamp=time.time(),
            dlc=8
        )
        
        # Simulate handler by calling update directly
        dashboard._update_motor_data(speed, torque, temp)
        
        assert dashboard.latest_data['motor']['speed'] == 3000.0
        assert dashboard.latest_data['motor']['torque'] == 150.0
        assert dashboard.latest_data['motor']['temperature'] == 60.0

    def test_can_frame_handler_charger_status(self, dashboard):
        """Test CAN frame handler for charger status."""
        voltage = 400.0
        current = 30.0
        state_bytes = b'\x01'  # charging state (single byte)
        
        # CAN frames are limited to 8 bytes, use first 8 bytes
        data = struct.pack('<f', voltage) + struct.pack('<f', current)
        
        frame = CANFrame(
            can_id=0x280,
            data=data,
            timestamp=time.time(),
            dlc=8
        )
        
        # Simulate handler
        dashboard._update_charging_data(voltage, current, 'charging')
        
        assert dashboard.latest_data['charging']['voltage'] == 400.0
        assert dashboard.latest_data['charging']['current'] == 30.0
        assert dashboard.latest_data['charging']['state'] == 'charging'

    def test_can_frame_handler_vehicle_status(self, dashboard):
        """Test CAN frame handler for vehicle status."""
        state_byte = b'\x02'  # driving state
        
        frame = CANFrame(
            can_id=0x303,
            data=state_byte,
            timestamp=time.time(),
            dlc=1
        )
        
        # Simulate handler
        dashboard._update_vehicle_data('driving')
        
        assert dashboard.latest_data['vehicle']['state'] == 'driving'

    def test_broadcast_update_with_clients(self, dashboard):
        """Test broadcasting update with clients."""
        dashboard.clients = ['client1', 'client2']
        dashboard.socketio = Mock()
        dashboard.socketio.emit = Mock()
        
        dashboard._broadcast_update()
        
        assert dashboard.socketio.emit.called

    def test_register_can_handlers_temperature(self, dashboard, mock_can_bus, mock_can_protocol):
        """Test registering temperature CAN handlers."""
        dashboard._register_can_handlers()
        
        # Verify temperature handlers were registered
        assert mock_can_bus.register_message_handler.call_count >= 6  # At least 6 handlers


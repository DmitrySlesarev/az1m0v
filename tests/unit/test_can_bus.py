"""Unit tests for CAN bus communication system."""

import pytest
import time
from unittest.mock import Mock, patch
from communication.can_bus import (
    CANFrame, CANMessage, CANFrameType, CANBusInterface, EVCANProtocol
)


class TestCANFrame:
    """Test CANFrame dataclass."""

    def test_can_frame_creation(self):
        """Test creating a CAN frame."""
        frame = CANFrame(
            can_id=0x123,
            data=b'\x01\x02\x03\x04',
            timestamp=time.time(),
            dlc=4
        )

        assert frame.can_id == 0x123
        assert frame.data == b'\x01\x02\x03\x04'
        assert frame.dlc == 4
        assert frame.frame_type == CANFrameType.DATA
        assert not frame.is_extended
        assert not frame.is_remote

    def test_can_frame_validation_valid_dlc(self):
        """Test CAN frame with valid DLC."""
        frame = CANFrame(
            can_id=0x123,
            data=b'\x01\x02\x03\x04\x05\x06\x07\x08',
            timestamp=time.time(),
            dlc=8
        )

        assert frame.dlc == 8
        assert len(frame.data) == 8

    def test_can_frame_validation_invalid_dlc(self):
        """Test CAN frame with invalid DLC."""
        with pytest.raises(ValueError, match="DLC cannot exceed 8 bytes"):
            CANFrame(
                can_id=0x123,
                data=b'\x01\x02\x03\x04',
                timestamp=time.time(),
                dlc=9
            )

    def test_can_frame_validation_data_length_mismatch(self):
        """Test CAN frame with data length mismatch."""
        with pytest.raises(ValueError, match="Data length.*must match DLC"):
            CANFrame(
                can_id=0x123,
                data=b'\x01\x02\x03\x04',
                timestamp=time.time(),
                dlc=8
            )

    def test_can_frame_extended_id(self):
        """Test CAN frame with extended ID."""
        frame = CANFrame(
            can_id=0x12345678,
            data=b'\x01\x02',
            timestamp=time.time(),
            dlc=2,
            is_extended=True
        )

        assert frame.is_extended is True
        assert frame.can_id == 0x12345678

    def test_can_frame_remote_frame(self):
        """Test CAN frame as remote frame."""
        frame = CANFrame(
            can_id=0x123,
            data=b'',
            timestamp=time.time(),
            dlc=0,
            is_remote=True
        )

        assert frame.is_remote is True
        assert frame.dlc == 0


class TestCANMessage:
    """Test CANMessage dataclass."""

    def test_can_message_creation(self):
        """Test creating a CAN message."""
        message = CANMessage(
            message_id=0x123,
            name="TEST_MESSAGE",
            description="Test message for unit testing",
            data={"voltage": 400.0, "current": 50.0},
            timestamp=time.time(),
            source="TestECU"
        )

        assert message.message_id == 0x123
        assert message.name == "TEST_MESSAGE"
        assert message.description == "Test message for unit testing"
        assert message.data == {"voltage": 400.0, "current": 50.0}
        assert message.source == "TestECU"
        assert message.priority == 0  # Default priority

    def test_can_message_with_priority(self):
        """Test CAN message with custom priority."""
        message = CANMessage(
            message_id=0x123,
            name="TEST_MESSAGE",
            description="Test message",
            data={},
            timestamp=time.time(),
            source="TestECU",
            priority=5
        )

        assert message.priority == 5


class TestCANBusInterface:
    """Test CANBusInterface class."""

    @pytest.fixture
    def can_interface(self):
        """Create a CANBusInterface instance for testing."""
        return CANBusInterface("can0", 500000, "socketcan")

    def test_can_interface_initialization(self, can_interface):
        """Test CANBusInterface initialization."""
        assert can_interface.channel == "can0"
        assert can_interface.bitrate == 500000
        assert can_interface.interface == "socketcan"
        assert not can_interface.is_connected
        assert len(can_interface.message_handlers) == 0
        assert can_interface.stats['frames_sent'] == 0
        assert can_interface.stats['frames_received'] == 0
        assert can_interface.stats['errors'] == 0

    def test_can_interface_connect(self, can_interface):
        """Test CAN bus connection."""
        result = can_interface.connect()

        assert result is True
        assert can_interface.is_connected is True

    def test_can_interface_disconnect(self, can_interface):
        """Test CAN bus disconnection."""
        can_interface.connect()
        can_interface.disconnect()

        assert not can_interface.is_connected

    def test_send_frame_success(self, can_interface):
        """Test successful frame sending."""
        can_interface.connect()

        frame = CANFrame(
            can_id=0x123,
            data=b'\x01\x02\x03\x04',
            timestamp=time.time(),
            dlc=4
        )

        result = can_interface.send_frame(frame)

        assert result is True
        assert can_interface.stats['frames_sent'] == 1
        assert can_interface.stats['last_activity'] > 0

    def test_send_frame_not_connected(self, can_interface):
        """Test sending frame when not connected."""
        frame = CANFrame(
            can_id=0x123,
            data=b'\x01\x02\x03\x04',
            timestamp=time.time(),
            dlc=4
        )

        result = can_interface.send_frame(frame)

        assert result is False
        assert can_interface.stats['frames_sent'] == 0

    def test_register_message_handler(self, can_interface):
        """Test registering message handlers."""
        handler = Mock()

        can_interface.register_message_handler(0x123, handler)

        assert 0x123 in can_interface.message_handlers
        assert handler in can_interface.message_handlers[0x123]

    def test_register_multiple_handlers_same_id(self, can_interface):
        """Test registering multiple handlers for same CAN ID."""
        handler1 = Mock()
        handler2 = Mock()

        can_interface.register_message_handler(0x123, handler1)
        can_interface.register_message_handler(0x123, handler2)

        assert len(can_interface.message_handlers[0x123]) == 2
        assert handler1 in can_interface.message_handlers[0x123]
        assert handler2 in can_interface.message_handlers[0x123]

    def test_get_statistics(self, can_interface):
        """Test getting CAN bus statistics."""
        can_interface.connect()

        stats = can_interface.get_statistics()

        assert stats['channel'] == "can0"
        assert stats['bitrate'] == 500000
        assert stats['is_connected'] is True
        assert stats['frames_sent'] == 0
        assert stats['frames_received'] == 0
        assert stats['errors'] == 0
        assert 'last_activity' in stats


class TestEVCANProtocol:
    """Test EVCANProtocol class."""

    @pytest.fixture
    def can_interface(self):
        """Create a CANBusInterface instance for testing."""
        interface = CANBusInterface("can0", 500000)
        interface.connect()
        return interface

    @pytest.fixture
    def ev_protocol(self, can_interface):
        """Create an EVCANProtocol instance for testing."""
        return EVCANProtocol(can_interface)

    def test_ev_protocol_initialization(self, ev_protocol, can_interface):
        """Test EVCANProtocol initialization."""
        assert ev_protocol.can_bus == can_interface
        assert len(ev_protocol.CAN_IDS) > 0

    def test_can_ids_defined(self, ev_protocol):
        """Test that standard CAN IDs are defined."""
        expected_ids = [
            'BMS_VOLTAGE', 'BMS_CURRENT', 'BMS_TEMPERATURE', 'BMS_STATUS', 'BMS_SOC',
            'MOTOR_SPEED', 'MOTOR_TORQUE', 'MOTOR_TEMPERATURE', 'MOTOR_STATUS',
            'CHARGER_STATUS', 'CHARGER_VOLTAGE', 'CHARGER_CURRENT',
            'VEHICLE_SPEED', 'VEHICLE_ACCELERATION', 'VEHICLE_STATUS',
            'BRAKE_STATUS', 'STEERING_ANGLE'
        ]

        for expected_id in expected_ids:
            assert expected_id in ev_protocol.CAN_IDS

    def test_can_ids_unique(self, ev_protocol):
        """Test that all CAN IDs are unique."""
        can_ids = list(ev_protocol.CAN_IDS.values())
        assert len(can_ids) == len(set(can_ids))

    def test_send_battery_status(self, ev_protocol):
        """Test sending battery status message."""
        with patch.object(ev_protocol.can_bus, 'send_frame') as mock_send:
            mock_send.return_value = True

            result = ev_protocol.send_battery_status(400.0, 50.0, 25.0, 0.85)

            assert result is True
            mock_send.assert_called_once()

            # Verify the frame was created correctly
            call_args = mock_send.call_args[0][0]
            assert call_args.can_id == ev_protocol.CAN_IDS['BMS_STATUS']
            assert call_args.dlc == 8

    def test_send_motor_status(self, ev_protocol):
        """Test sending motor status message."""
        with patch.object(ev_protocol.can_bus, 'send_frame') as mock_send:
            mock_send.return_value = True

            result = ev_protocol.send_motor_status(3000.0, 150.0, 60.0)

            assert result is True
            mock_send.assert_called_once()

            # Verify the frame was created correctly
            call_args = mock_send.call_args[0][0]
            assert call_args.can_id == ev_protocol.CAN_IDS['MOTOR_STATUS']
            assert call_args.dlc == 8

    def test_serialize_data(self, ev_protocol):
        """Test data serialization."""
        data = {
            'voltage': 400.0,
            'current': 50.0,
            'temperature': 25.0
        }

        serialized = ev_protocol._serialize_data(data)

        assert isinstance(serialized, bytes)
        assert len(serialized) <= 8  # CAN frame limit

    def test_serialize_data_mixed_types(self, ev_protocol):
        """Test serialization with mixed data types."""
        data = {
            'voltage': 400.0,
            'current': 50,  # int
            'temperature': 25.0,
            'status': 'active'  # string (should be ignored)
        }

        serialized = ev_protocol._serialize_data(data)

        assert isinstance(serialized, bytes)
        assert len(serialized) <= 8

    def test_send_message_failure(self, ev_protocol):
        """Test message sending failure."""
        with patch.object(ev_protocol.can_bus, 'send_frame') as mock_send:
            mock_send.return_value = False

            result = ev_protocol.send_battery_status(400.0, 50.0, 25.0, 0.85)

            assert result is False


class TestCANFrameType:
    """Test CANFrameType enum."""

    def test_can_frame_type_values(self):
        """Test that all expected frame types are present."""
        expected_types = ["data", "remote", "error", "overload"]

        for expected_type in expected_types:
            assert hasattr(CANFrameType, expected_type.upper()), f"Missing frame type: {expected_type}"

    def test_can_frame_type_enum_values(self):
        """Test that enum values match expected strings."""
        assert CANFrameType.DATA.value == "data"
        assert CANFrameType.REMOTE.value == "remote"
        assert CANFrameType.ERROR.value == "error"
        assert CANFrameType.OVERLOAD.value == "overload"


class TestCANBusInterfaceErrorHandling:
    """Test CANBusInterface error handling."""

    @pytest.fixture
    def can_interface(self):
        """Create a CANBusInterface instance for testing."""
        return CANBusInterface("can0", 500000)

    def test_send_frame_error_tracking(self, can_interface):
        """Test error tracking in frame sending."""
        can_interface.connect()

        # Test normal operation
        frame = CANFrame(
            can_id=0x123,
            data=b'\x01\x02\x03\x04',
            timestamp=time.time(),
            dlc=4
        )

        result = can_interface.send_frame(frame)
        assert result is True
        assert can_interface.stats['errors'] == 0

    def test_connection_error_handling(self, can_interface):
        """Test connection error handling."""
        # Test normal connection
        result = can_interface.connect()
        assert result is True
        assert can_interface.is_connected


class TestCANMessageValidation:
    """Test CAN message validation."""

    def test_message_with_empty_data(self):
        """Test CAN message with empty data."""
        message = CANMessage(
            message_id=0x123,
            name="EMPTY_MESSAGE",
            description="Message with no data",
            data={},
            timestamp=time.time(),
            source="TestECU"
        )

        assert message.data == {}
        assert message.message_id == 0x123

    def test_message_with_large_data(self):
        """Test CAN message with large data dictionary."""
        large_data = {f"key_{i}": i for i in range(10)}

        message = CANMessage(
            message_id=0x123,
            name="LARGE_MESSAGE",
            description="Message with large data",
            data=large_data,
            timestamp=time.time(),
            source="TestECU"
        )

        assert len(message.data) == 10
        assert message.data["key_0"] == 0
        assert message.data["key_9"] == 9

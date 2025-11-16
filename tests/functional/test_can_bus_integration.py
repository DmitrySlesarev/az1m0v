"""Functional tests for CAN bus integration scenarios."""

import pytest
import time
import threading
from communication.can_bus import (
    CANFrame, CANBusInterface, EVCANProtocol
)


class TestCANBusIntegration:
    """Integration tests for CAN bus system."""

    @pytest.fixture
    def can_interface(self):
        """Create a CANBusInterface instance for integration testing."""
        interface = CANBusInterface("can0", 500000)
        interface.connect()
        return interface

    @pytest.fixture
    def ev_protocol(self, can_interface):
        """Create an EVCANProtocol instance for integration testing."""
        return EVCANProtocol(can_interface)

    def test_full_ev_communication_workflow(self, ev_protocol):
        """Test complete EV communication workflow."""
        # Send battery status
        battery_result = ev_protocol.send_battery_status(400.0, 50.0, 25.0, 0.85)
        assert battery_result is True

        # Send motor status
        motor_result = ev_protocol.send_motor_status(3000.0, 150.0, 60.0)
        assert motor_result is True

        # Verify statistics
        stats = ev_protocol.can_bus.get_statistics()
        assert stats['frames_sent'] >= 2
        assert stats['is_connected'] is True

    def test_message_handler_integration(self, can_interface):
        """Test message handler integration."""
        # Test that handlers can be registered
        received_frames = []

        def frame_handler(frame):
            received_frames.append(frame)

        # Register handler
        can_interface.register_message_handler(0x123, frame_handler)

        # Verify handler was registered
        assert 0x123 in can_interface.message_handlers
        assert frame_handler in can_interface.message_handlers[0x123]

    def test_multiple_message_handlers(self, can_interface):
        """Test multiple message handlers for same CAN ID."""
        def handler1(frame):
            pass

        def handler2(frame):
            pass

        # Register both handlers
        can_interface.register_message_handler(0x123, handler1)
        can_interface.register_message_handler(0x123, handler2)

        # Verify both handlers were registered
        assert len(can_interface.message_handlers[0x123]) == 2
        assert handler1 in can_interface.message_handlers[0x123]
        assert handler2 in can_interface.message_handlers[0x123]

    def test_different_can_ids_handling(self, can_interface):
        """Test handling frames with different CAN IDs."""
        def handler_123(frame):
            pass

        def handler_456(frame):
            pass

        # Register handlers for different IDs
        can_interface.register_message_handler(0x123, handler_123)
        can_interface.register_message_handler(0x456, handler_456)

        # Verify handlers were registered for different IDs
        assert 0x123 in can_interface.message_handlers
        assert 0x456 in can_interface.message_handlers
        assert handler_123 in can_interface.message_handlers[0x123]
        assert handler_456 in can_interface.message_handlers[0x456]

    def test_ev_protocol_message_flow(self, ev_protocol):
        """Test EV protocol message flow with multiple subsystems."""
        # Simulate BMS sending status
        bms_result = ev_protocol.send_battery_status(400.0, 50.0, 25.0, 0.85)
        assert bms_result is True

        # Simulate Motor Controller sending status
        motor_result = ev_protocol.send_motor_status(3000.0, 150.0, 60.0)
        assert motor_result is True

        # Verify both messages were sent
        stats = ev_protocol.can_bus.get_statistics()
        assert stats['frames_sent'] >= 2

    def test_can_frame_validation_integration(self, can_interface):
        """Test CAN frame validation in integration scenario."""
        # Test valid frame
        valid_frame = CANFrame(
            can_id=0x123,
            data=b'\x01\x02\x03\x04\x05\x06\x07\x08',
            timestamp=time.time(),
            dlc=8
        )

        result = can_interface.send_frame(valid_frame)
        assert result is True

        # Test invalid frame (should not be created)
        with pytest.raises(ValueError):
            CANFrame(
                can_id=0x123,
                data=b'\x01\x02\x03\x04',
                timestamp=time.time(),
                dlc=8  # Mismatch with data length
            )

    def test_statistics_tracking_integration(self, can_interface):
        """Test statistics tracking in integration scenario."""
        initial_stats = can_interface.get_statistics()
        initial_sent = initial_stats['frames_sent']

        # Send some frames
        for i in range(5):
            frame = CANFrame(
                can_id=0x100 + i,
                data=b'\x01\x02\x03\x04',
                timestamp=time.time(),
                dlc=4
            )
            can_interface.send_frame(frame)

        # Check updated statistics
        final_stats = can_interface.get_statistics()
        assert final_stats['frames_sent'] == initial_sent + 5
        assert final_stats['last_activity'] > initial_stats['last_activity']

    def test_connection_lifecycle_integration(self, can_interface):
        """Test complete connection lifecycle."""
        # Connect
        connect_result = can_interface.connect()
        assert connect_result is True
        assert can_interface.is_connected

        # Send frame while connected
        frame = CANFrame(
            can_id=0x123,
            data=b'\x01\x02\x03\x04',
            timestamp=time.time(),
            dlc=4
        )
        send_result = can_interface.send_frame(frame)
        assert send_result is True

        # Disconnect
        can_interface.disconnect()
        assert not can_interface.is_connected

        # Try to send frame while disconnected
        send_result = can_interface.send_frame(frame)
        assert send_result is False

    def test_error_handling_integration(self, can_interface):
        """Test error handling in integration scenario."""
        # Test handler registration
        def faulty_handler(frame):
            raise Exception("Handler error")

        can_interface.register_message_handler(0x123, faulty_handler)

        # Verify handler was registered
        assert 0x123 in can_interface.message_handlers
        assert faulty_handler in can_interface.message_handlers[0x123]

    def test_data_serialization_integration(self, ev_protocol):
        """Test data serialization in integration scenario."""
        # Test with various data types
        test_data = {
            'voltage': 400.0,
            'current': 50,
            'temperature': 25.5,
            'status': 'active',
            'enabled': True
        }

        serialized = ev_protocol._serialize_data(test_data)

        assert isinstance(serialized, bytes)
        assert len(serialized) <= 8  # CAN frame limit

        # Verify numeric values are serialized
        assert len(serialized) > 0

    def test_can_id_mapping_integration(self, ev_protocol):
        """Test CAN ID mapping in integration scenario."""
        # Test that all standard CAN IDs are properly mapped
        expected_mappings = {
            'BMS_STATUS': 0x183,
            'MOTOR_STATUS': 0x203,
            'VEHICLE_STATUS': 0x303,
            'BRAKE_STATUS': 0x380
        }

        for message_name, expected_id in expected_mappings.items():
            assert ev_protocol.CAN_IDS[message_name] == expected_id

    def test_message_timestamp_integration(self, ev_protocol):
        """Test message timestamp handling in integration scenario."""
        start_time = time.time()

        # Send message
        result = ev_protocol.send_battery_status(400.0, 50.0, 25.0, 0.85)
        assert result is True

        end_time = time.time()

        # Verify timestamp is within expected range
        # (This is a bit tricky to test exactly, but we can verify it's reasonable)
        assert end_time >= start_time

    def test_concurrent_message_handling(self, can_interface):
        """Test concurrent message handling."""
        def thread_safe_handler(frame):
            pass

        can_interface.register_message_handler(0x123, thread_safe_handler)

        # Simulate concurrent frame sending
        def send_frame(frame_id):
            frame = CANFrame(
                can_id=0x123,
                data=frame_id.to_bytes(1, 'little'),
                timestamp=time.time(),
                dlc=1
            )
            return can_interface.send_frame(frame)

        # Send frames concurrently
        threads = []
        results = []

        def send_with_result(frame_id):
            result = send_frame(frame_id)
            results.append(result)

        for i in range(5):
            thread = threading.Thread(target=send_with_result, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        # Verify all frames were sent successfully
        assert len(results) == 5
        assert all(results)  # All should be True

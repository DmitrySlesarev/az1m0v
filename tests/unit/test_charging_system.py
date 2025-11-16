"""Unit tests for charging system."""

import pytest
import time
from unittest.mock import Mock
from core.charging_system import (
    ChargingSystem, ChargingStatus, ChargingState, ConnectorType
)
from core.battery_management import BatteryManagementSystem
from core.motor_controller import VESCManager


class TestChargingState:
    """Test ChargingState enum."""

    def test_charging_state_values(self):
        """Test that all expected charging states are present."""
        expected_states = [
            "disconnected", "idle", "connected", "charging",
            "charging_ac", "charging_dc", "paused", "complete",
            "error", "fault"
        ]

        for state in expected_states:
            assert hasattr(ChargingState, state.upper()), f"Missing state: {state}"

    def test_charging_state_enum_values(self):
        """Test that enum values match expected strings."""
        assert ChargingState.DISCONNECTED.value == "disconnected"
        assert ChargingState.CHARGING.value == "charging"
        assert ChargingState.CHARGING_AC.value == "charging_ac"
        assert ChargingState.CHARGING_DC.value == "charging_dc"
        assert ChargingState.COMPLETE.value == "complete"
        assert ChargingState.ERROR.value == "error"


class TestConnectorType:
    """Test ConnectorType enum."""

    def test_connector_type_values(self):
        """Test that all expected connector types are present."""
        expected_types = ["CCS1", "CCS2", "CHADEMO", "TESLA", "TYPE2"]

        for connector_type in expected_types:
            assert hasattr(ConnectorType, connector_type), f"Missing connector type: {connector_type}"

    def test_connector_type_enum_values(self):
        """Test that enum values match expected strings."""
        assert ConnectorType.CCS1.value == "CCS1"
        assert ConnectorType.CCS2.value == "CCS2"
        assert ConnectorType.CHADEMO.value == "CHAdeMO"
        assert ConnectorType.TESLA.value == "Tesla"
        assert ConnectorType.TYPE2.value == "Type2"


class TestChargingStatus:
    """Test ChargingStatus dataclass."""

    def test_charging_status_creation(self):
        """Test creating a charging status."""
        status = ChargingStatus(
            state=ChargingState.CHARGING,
            voltage_v=400.0,
            current_a=50.0,
            power_kw=20.0,
            energy_charged_kwh=5.0,
            charging_time_s=900.0,
            connector_type=ConnectorType.CCS2,
            is_fast_charge=True
        )

        assert status.state == ChargingState.CHARGING
        assert status.voltage_v == 400.0
        assert status.current_a == 50.0
        assert status.power_kw == 20.0
        assert status.energy_charged_kwh == 5.0
        assert status.charging_time_s == 900.0
        assert status.connector_type == ConnectorType.CCS2
        assert status.is_fast_charge is True

    def test_charging_status_defaults(self):
        """Test charging status with default values."""
        status = ChargingStatus()

        assert status.state == ChargingState.DISCONNECTED
        assert status.voltage_v == 0.0
        assert status.current_a == 0.0
        assert status.power_kw == 0.0
        assert status.connector_type is None


class TestChargingSystem:
    """Test ChargingSystem class."""

    @pytest.fixture
    def config(self):
        """Create a test configuration."""
        return {
            'ac_max_power_kw': 11.0,
            'dc_max_power_kw': 150.0,
            'connector_type': 'CCS2',
            'fast_charge_enabled': True
        }

    @pytest.fixture
    def bms_config(self):
        """Create BMS configuration."""
        return {
            'capacity_kwh': 75.0,
            'max_charge_rate_kw': 150.0,
            'max_discharge_rate_kw': 200.0,
            'nominal_voltage': 400.0,
            'cell_count': 96
        }

    @pytest.fixture
    def mock_bms(self, bms_config):
        """Create a mock BMS."""
        bms = BatteryManagementSystem(bms_config)
        return bms

    @pytest.fixture
    def mock_motor_controller(self):
        """Create a mock motor controller."""
        motor = Mock(spec=VESCManager)
        motor.is_connected = False
        motor.is_healthy = Mock(return_value=True)
        motor.get_status = Mock(return_value=Mock(state=Mock(value='idle')))
        return motor

    @pytest.fixture
    def mock_can_protocol(self):
        """Create a mock CAN protocol."""
        protocol = Mock()
        protocol.send_charger_status = Mock(return_value=True)
        return protocol

    @pytest.fixture
    def charging_system(self, config, mock_bms, mock_motor_controller, mock_can_protocol):
        """Create a ChargingSystem instance for testing."""
        return ChargingSystem(
            config=config,
            bms=mock_bms,
            motor_controller=mock_motor_controller,
            can_protocol=mock_can_protocol
        )

    def test_charging_system_initialization(self, charging_system, config):
        """Test ChargingSystem initialization."""
        assert charging_system.ac_max_power_kw == 11.0
        assert charging_system.dc_max_power_kw == 150.0
        assert charging_system.connector_type == ConnectorType.CCS2
        assert charging_system.fast_charge_enabled is True
        assert charging_system.current_status.state == ChargingState.DISCONNECTED

    def test_charging_system_initialization_defaults(self):
        """Test ChargingSystem initialization with defaults."""
        config = {}
        system = ChargingSystem(config=config)

        assert system.ac_max_power_kw == 11.0  # Default
        assert system.dc_max_power_kw == 150.0  # Default
        assert system.fast_charge_enabled is True  # Default

    def test_connect_charger(self, charging_system):
        """Test connecting charger."""
        result = charging_system.connect_charger()

        assert result is True
        assert charging_system.current_status.state == ChargingState.CONNECTED
        assert charging_system.current_status.connector_type == ConnectorType.CCS2

    def test_connect_charger_with_type(self, charging_system):
        """Test connecting charger with specific connector type."""
        result = charging_system.connect_charger(ConnectorType.CCS1)

        assert result is True
        assert charging_system.current_status.connector_type == ConnectorType.CCS1

    def test_connect_charger_while_charging(self, charging_system):
        """Test connecting charger while already charging."""
        charging_system.current_status.state = ChargingState.CHARGING

        result = charging_system.connect_charger()

        assert result is False

    def test_connect_charger_motor_running(self, charging_system, mock_motor_controller):
        """Test connecting charger while motor is running."""
        mock_motor_controller.is_connected = True
        mock_motor_controller.get_status.return_value = Mock(state=Mock(value='running'))

        result = charging_system.connect_charger()

        assert result is False

    def test_disconnect_charger(self, charging_system):
        """Test disconnecting charger."""
        charging_system.current_status.state = ChargingState.CONNECTED

        charging_system.disconnect_charger()

        assert charging_system.current_status.state == ChargingState.DISCONNECTED
        assert charging_system.current_status.connector_type is None

    def test_disconnect_charger_while_charging(self, charging_system):
        """Test disconnecting charger while charging."""
        charging_system.current_status.state = ChargingState.CHARGING
        charging_system.stop_charging = Mock(return_value=True)

        charging_system.disconnect_charger()

        charging_system.stop_charging.assert_called_once()
        assert charging_system.current_status.state == ChargingState.DISCONNECTED

    def test_start_charging_not_connected(self, charging_system):
        """Test starting charging when not connected."""
        result = charging_system.start_charging()

        assert result is False

    def test_start_charging_bms_rejected(self, charging_system, mock_bms):
        """Test starting charging when BMS rejects."""
        charging_system.current_status.state = ChargingState.CONNECTED
        mock_bms.get_state = Mock(return_value=Mock(soc=100.0))  # Already full

        result = charging_system.start_charging(target_soc=100.0)

        assert result is False

    def test_start_charging_ac(self, charging_system, mock_bms):
        """Test starting AC charging."""
        charging_system.current_status.state = ChargingState.CONNECTED
        mock_bms.get_state = Mock(return_value=Mock(soc=50.0))
        mock_bms.can_charge = Mock(return_value=True)

        result = charging_system.start_charging(use_fast_charge=False)

        assert result is True
        assert charging_system.current_status.state == ChargingState.CHARGING_AC
        assert charging_system.current_status.is_fast_charge is False

    def test_start_charging_dc(self, charging_system, mock_bms):
        """Test starting DC fast charging."""
        charging_system.current_status.state = ChargingState.CONNECTED
        charging_system.current_status.connector_type = ConnectorType.CCS2  # Fast charge capable
        mock_bms.get_state = Mock(return_value=Mock(soc=50.0))
        mock_bms.can_charge = Mock(return_value=True)

        result = charging_system.start_charging(use_fast_charge=True)

        assert result is True
        assert charging_system.current_status.state == ChargingState.CHARGING_DC
        assert charging_system.current_status.is_fast_charge is True

    def test_start_charging_with_power(self, charging_system, mock_bms):
        """Test starting charging with specific power."""
        charging_system.current_status.state = ChargingState.CONNECTED
        mock_bms.get_state = Mock(return_value=Mock(soc=50.0))
        mock_bms.can_charge = Mock(return_value=True)

        result = charging_system.start_charging(power_kw=50.0)

        assert result is True
        assert charging_system.current_status.power_kw == 50.0

    def test_start_charging_motor_fault(self, charging_system, mock_motor_controller, mock_bms):
        """Test starting charging when motor controller has fault."""
        charging_system.current_status.state = ChargingState.CONNECTED
        mock_motor_controller.is_connected = True
        mock_motor_controller.is_healthy = Mock(return_value=False)
        mock_bms.get_state = Mock(return_value=Mock(soc=50.0))
        mock_bms.can_charge = Mock(return_value=True)

        result = charging_system.start_charging()

        assert result is False
        assert charging_system.current_status.state == ChargingState.ERROR
        assert charging_system.current_status.error_code == "MOTOR_FAULT"

    def test_stop_charging(self, charging_system):
        """Test stopping charging."""
        charging_system.current_status.state = ChargingState.CHARGING
        charging_system.charging_start_time = time.time()

        result = charging_system.stop_charging()

        assert result is True
        assert charging_system.current_status.state == ChargingState.CONNECTED
        assert charging_system.current_status.power_kw == 0.0
        assert charging_system.charging_start_time is None

    def test_stop_charging_not_charging(self, charging_system):
        """Test stopping when not charging."""
        charging_system.current_status.state = ChargingState.CONNECTED

        result = charging_system.stop_charging()

        assert result is False

    def test_pause_charging(self, charging_system):
        """Test pausing charging."""
        charging_system.current_status.state = ChargingState.CHARGING

        result = charging_system.pause_charging()

        assert result is True
        assert charging_system.current_status.state == ChargingState.PAUSED

    def test_resume_charging(self, charging_system, mock_bms):
        """Test resuming paused charging."""
        # First connect charger
        charging_system.connect_charger(ConnectorType.CCS2)
        # Then pause
        charging_system.current_status.state = ChargingState.PAUSED
        charging_system.current_status.power_kw = 50.0
        charging_system.target_soc = 100.0
        charging_system.current_status.is_fast_charge = True
        mock_bms.get_state = Mock(return_value=Mock(soc=50.0))
        mock_bms.can_charge = Mock(return_value=True)

        result = charging_system.resume_charging()

        assert result is True
        assert charging_system.current_status.state in [ChargingState.CHARGING, ChargingState.CHARGING_DC]

    def test_update_status(self, charging_system, mock_bms):
        """Test updating charging status."""
        charging_system.current_status.state = ChargingState.CHARGING
        charging_system.charging_start_time = time.time() - 100

        status = charging_system.update_status(
            voltage_v=400.0,
            current_a=50.0,
            temperature_c=30.0
        )

        assert status.voltage_v == 400.0
        assert status.current_a == 50.0
        assert status.temperature_c == 30.0
        assert status.power_kw > 0

    def test_update_status_from_bms(self, charging_system, mock_bms):
        """Test updating status from BMS data."""
        charging_system.current_status.state = ChargingState.CHARGING
        charging_system.target_soc = 100.0
        charging_system.charging_start_time = time.time()
        from core.battery_management import BatteryState, BatteryStatus
        mock_bms.get_state = Mock(return_value=BatteryState(
            voltage=400.0,
            current=50.0,
            temperature=30.0,
            soc=50.0,
            soh=100.0,
            cell_count=96,
            cell_voltages=[4.0] * 96,
            cell_temperatures=[30.0] * 96,
            status=BatteryStatus.CHARGING,
            timestamp=time.time()
        ))

        status = charging_system.update_status()

        assert status.voltage_v == 400.0
        assert status.current_a == 50.0
        assert status.temperature_c == 30.0

    def test_update_status_complete(self, charging_system, mock_bms):
        """Test status update when target SOC reached."""
        charging_system.current_status.state = ChargingState.CHARGING
        charging_system.current_status.voltage_v = 400.0
        charging_system.current_status.current_a = 50.0
        charging_system.target_soc = 90.0
        charging_system.charging_start_time = time.time() - 100
        from core.battery_management import BatteryState, BatteryStatus
        mock_bms.get_state = Mock(return_value=BatteryState(
            voltage=400.0,
            current=50.0,
            temperature=30.0,
            soc=90.0,
            soh=100.0,
            cell_count=96,
            cell_voltages=[4.0] * 96,
            cell_temperatures=[30.0] * 96,
            status=BatteryStatus.CHARGING,
            timestamp=time.time()
        ))

        status = charging_system.update_status()

        assert status.state == ChargingState.COMPLETE

    def test_update_status_overtemperature(self, charging_system):
        """Test status update with overtemperature."""
        charging_system.current_status.state = ChargingState.CHARGING
        charging_system.max_temperature_c = 60.0
        charging_system.charging_start_time = time.time()
        charging_system.stop_charging = Mock(return_value=True)

        status = charging_system.update_status(temperature_c=70.0)

        assert status.state == ChargingState.ERROR
        assert status.error_code == "OVERTEMPERATURE"
        charging_system.stop_charging.assert_called_once()

    def test_update_status_overvoltage(self, charging_system):
        """Test status update with overvoltage."""
        charging_system.current_status.state = ChargingState.CHARGING
        charging_system.max_voltage_v = 500.0
        charging_system.charging_start_time = time.time()
        charging_system.stop_charging = Mock(return_value=True)

        status = charging_system.update_status(voltage_v=550.0)

        assert status.state == ChargingState.ERROR
        assert status.error_code == "OVERVOLTAGE"

    def test_supports_fast_charge(self, charging_system):
        """Test fast charge support detection."""
        charging_system.current_status.connector_type = ConnectorType.CCS2
        assert charging_system._supports_fast_charge() is True

        charging_system.current_status.connector_type = ConnectorType.TYPE2
        assert charging_system._supports_fast_charge() is False

    def test_is_charging(self, charging_system):
        """Test is_charging check."""
        charging_system.current_status.state = ChargingState.CHARGING
        assert charging_system.is_charging() is True

        charging_system.current_status.state = ChargingState.CHARGING_DC
        assert charging_system.is_charging() is True

        charging_system.current_status.state = ChargingState.CONNECTED
        assert charging_system.is_charging() is False

    def test_is_connected(self, charging_system):
        """Test is_connected check."""
        charging_system.current_status.state = ChargingState.CONNECTED
        assert charging_system.is_connected() is True

        charging_system.current_status.state = ChargingState.DISCONNECTED
        assert charging_system.is_connected() is False

    def test_is_healthy(self, charging_system):
        """Test is_healthy check."""
        charging_system.current_status.state = ChargingState.CHARGING
        charging_system.current_status.temperature_c = 30.0
        charging_system.current_status.voltage_v = 400.0

        assert charging_system.is_healthy() is True

        charging_system.current_status.state = ChargingState.ERROR
        assert charging_system.is_healthy() is False

        charging_system.current_status.state = ChargingState.CHARGING
        charging_system.current_status.temperature_c = 70.0
        charging_system.max_temperature_c = 60.0
        assert charging_system.is_healthy() is False

    def test_get_estimated_time_remaining(self, charging_system, mock_bms):
        """Test time remaining estimation."""
        charging_system.current_status.state = ChargingState.CHARGING
        charging_system.current_status.power_kw = 50.0
        charging_system.target_soc = 100.0
        mock_bms.get_state = Mock(return_value=Mock(soc=50.0))
        mock_bms.config.capacity_kwh = 75.0

        time_remaining = charging_system.get_estimated_time_remaining()

        assert time_remaining is not None
        assert time_remaining > 0

    def test_get_estimated_time_remaining_not_charging(self, charging_system):
        """Test time remaining when not charging."""
        charging_system.current_status.state = ChargingState.CONNECTED

        time_remaining = charging_system.get_estimated_time_remaining()

        assert time_remaining is None

    def test_get_estimated_time_remaining_complete(self, charging_system, mock_bms):
        """Test time remaining when already at target SOC."""
        charging_system.current_status.state = ChargingState.CHARGING
        charging_system.current_status.power_kw = 50.0
        charging_system.target_soc = 90.0
        mock_bms.get_state = Mock(return_value=Mock(soc=90.0))

        time_remaining = charging_system.get_estimated_time_remaining()

        assert time_remaining == 0.0

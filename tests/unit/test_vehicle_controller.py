"""Unit tests for vehicle controller system."""

import pytest
import time
from unittest.mock import Mock
from core.vehicle_controller import (
    VehicleController, VehicleStatus, VehicleState, VehicleConfig, DriveMode
)
from core.battery_management import BatteryManagementSystem, BatteryState, BatteryStatus
from core.motor_controller import VESCManager, MotorStatus, MotorState
from core.charging_system import ChargingSystem, ChargingStatus, ChargingState


class TestVehicleState:
    """Test VehicleState enum."""

    def test_vehicle_state_values(self):
        """Test that all expected vehicle states are present."""
        expected_states = [
            "parked", "ready", "driving", "charging",
            "error", "fault", "emergency", "standby"
        ]

        for expected_state in expected_states:
            assert hasattr(VehicleState, expected_state.upper()), f"Missing state: {expected_state}"

    def test_vehicle_state_enum_values(self):
        """Test that enum values match expected strings."""
        assert VehicleState.PARKED.value == "parked"
        assert VehicleState.READY.value == "ready"
        assert VehicleState.DRIVING.value == "driving"
        assert VehicleState.CHARGING.value == "charging"
        assert VehicleState.ERROR.value == "error"
        assert VehicleState.EMERGENCY.value == "emergency"


class TestDriveMode:
    """Test DriveMode enum."""

    def test_drive_mode_values(self):
        """Test that all expected drive modes are present."""
        expected_modes = ["eco", "normal", "sport", "reverse"]

        for expected_mode in expected_modes:
            assert hasattr(DriveMode, expected_mode.upper()), f"Missing mode: {expected_mode}"

    def test_drive_mode_enum_values(self):
        """Test that enum values match expected strings."""
        assert DriveMode.ECO.value == "eco"
        assert DriveMode.NORMAL.value == "normal"
        assert DriveMode.SPORT.value == "sport"
        assert DriveMode.REVERSE.value == "reverse"


class TestVehicleStatus:
    """Test VehicleStatus dataclass."""

    def test_vehicle_status_creation(self):
        """Test creating a vehicle status."""
        status = VehicleStatus(
            state=VehicleState.DRIVING,
            speed_kmh=60.0,
            acceleration_ms2=2.0,
            power_kw=50.0,
            energy_consumption_kwh=10.0,
            range_km=200.0,
            drive_mode=DriveMode.NORMAL
        )

        assert status.state == VehicleState.DRIVING
        assert status.speed_kmh == 60.0
        assert status.acceleration_ms2 == 2.0
        assert status.power_kw == 50.0
        assert status.energy_consumption_kwh == 10.0
        assert status.range_km == 200.0
        assert status.drive_mode == DriveMode.NORMAL

    def test_vehicle_status_defaults(self):
        """Test vehicle status with default values."""
        status = VehicleStatus()

        assert status.state == VehicleState.PARKED
        assert status.speed_kmh == 0.0
        assert status.acceleration_ms2 == 0.0
        assert status.power_kw == 0.0
        assert status.drive_mode == DriveMode.NORMAL


class TestVehicleConfig:
    """Test VehicleConfig dataclass."""

    def test_vehicle_config_creation(self):
        """Test creating a vehicle config."""
        config = VehicleConfig(
            max_speed_kmh=150.0,
            max_acceleration_ms2=4.0,
            max_deceleration_ms2=-6.0,
            max_power_kw=200.0,
            efficiency_wh_per_km=180.0,
            weight_kg=1800.0
        )

        assert config.max_speed_kmh == 150.0
        assert config.max_acceleration_ms2 == 4.0
        assert config.max_deceleration_ms2 == -6.0
        assert config.max_power_kw == 200.0
        assert config.efficiency_wh_per_km == 180.0
        assert config.weight_kg == 1800.0

    def test_vehicle_config_defaults(self):
        """Test vehicle config with default values."""
        config = VehicleConfig()

        assert config.max_speed_kmh == 120.0
        assert config.max_acceleration_ms2 == 3.0
        assert config.max_deceleration_ms2 == -5.0
        assert config.max_power_kw == 150.0
        assert config.efficiency_wh_per_km == 200.0


class TestVehicleController:
    """Test VehicleController class."""

    @pytest.fixture
    def config(self):
        """Create a test configuration."""
        return {
            'max_speed_kmh': 120.0,
            'max_acceleration_ms2': 3.0,
            'max_deceleration_ms2': -5.0,
            'max_power_kw': 150.0,
            'efficiency_wh_per_km': 200.0,
            'weight_kg': 1500.0
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
        motor.is_connected = True
        motor.is_healthy = Mock(return_value=True)
        motor.stop = Mock(return_value=True)
        motor.set_duty_cycle = Mock(return_value=True)
        motor.set_current = Mock(return_value=True)
        motor.get_status = Mock(return_value=MotorStatus(
            speed_rpm=0.0,
            current_a=0.0,
            voltage_v=400.0,
            duty_cycle=0.0,
            temperature_c=25.0,
            power_w=0.0,
            state=MotorState.IDLE,
            timestamp=time.time()
        ))
        return motor

    @pytest.fixture
    def mock_charging_system(self):
        """Create a mock charging system."""
        charging = Mock(spec=ChargingSystem)
        charging.is_charging = Mock(return_value=False)
        charging.is_connected = Mock(return_value=False)
        charging.is_healthy = Mock(return_value=True)
        charging.connect_charger = Mock(return_value=True)
        charging.start_charging = Mock(return_value=True)
        charging.stop_charging = Mock(return_value=True)
        charging.get_status = Mock(return_value=ChargingStatus())
        return charging

    @pytest.fixture
    def mock_can_protocol(self):
        """Create a mock CAN protocol."""
        protocol = Mock()
        protocol.send_vehicle_status = Mock(return_value=True)
        return protocol

    @pytest.fixture
    def vehicle_controller(self, config, mock_bms, mock_motor_controller, mock_charging_system, mock_can_protocol):
        """Create a VehicleController instance for testing."""
        return VehicleController(
            config=config,
            bms=mock_bms,
            motor_controller=mock_motor_controller,
            charging_system=mock_charging_system,
            can_protocol=mock_can_protocol
        )

    def test_vehicle_controller_initialization(self, vehicle_controller, config):
        """Test VehicleController initialization."""
        assert vehicle_controller.config.max_speed_kmh == config['max_speed_kmh']
        assert vehicle_controller.config.max_power_kw == config['max_power_kw']
        assert vehicle_controller.current_status.state == VehicleState.PARKED
        assert vehicle_controller.bms is not None
        assert vehicle_controller.motor_controller is not None
        assert vehicle_controller.charging_system is not None

    def test_vehicle_controller_initialization_defaults(self):
        """Test VehicleController initialization with defaults."""
        controller = VehicleController(config={})

        assert controller.config.max_speed_kmh == 120.0  # Default
        assert controller.config.max_power_kw == 150.0  # Default
        assert controller.current_status.state == VehicleState.PARKED

    def test_set_state_valid_transition(self, vehicle_controller):
        """Test setting valid state transition."""
        result = vehicle_controller.set_state(VehicleState.READY)

        assert result is True
        assert vehicle_controller.current_status.state == VehicleState.READY

    def test_set_state_invalid_transition(self, vehicle_controller):
        """Test setting invalid state transition."""
        # Cannot go directly from PARKED to DRIVING
        result = vehicle_controller.set_state(VehicleState.DRIVING)

        assert result is False
        assert vehicle_controller.current_status.state == VehicleState.PARKED

    def test_set_state_emergency_always_allowed(self, vehicle_controller):
        """Test that emergency state is always allowed."""
        vehicle_controller.current_status.state = VehicleState.DRIVING

        result = vehicle_controller.set_state(VehicleState.EMERGENCY)

        assert result is True
        assert vehicle_controller.current_status.state == VehicleState.EMERGENCY

    def test_set_state_charging_while_driving_blocked(self, vehicle_controller):
        """Test that charging cannot be set while driving."""
        vehicle_controller.current_status.state = VehicleState.DRIVING

        result = vehicle_controller.set_state(VehicleState.CHARGING)

        assert result is False

    def test_start_driving_success(self, vehicle_controller, mock_bms, mock_motor_controller):
        """Test starting driving successfully."""
        # Set up BMS to allow driving
        mock_bms.get_state = Mock(return_value=BatteryState(
            voltage=400.0,
            current=0.0,
            temperature=25.0,
            soc=50.0,
            soh=100.0,
            cell_count=96,
            cell_voltages=[4.0] * 96,
            cell_temperatures=[25.0] * 96,
            status=BatteryStatus.HEALTHY,
            timestamp=time.time()
        ))

        vehicle_controller.current_status.state = VehicleState.READY

        result = vehicle_controller.start_driving()

        assert result is True
        assert vehicle_controller.current_status.state == VehicleState.DRIVING

    def test_start_driving_while_charging(self, vehicle_controller, mock_charging_system):
        """Test starting driving while charging."""
        mock_charging_system.is_charging.return_value = True
        vehicle_controller.current_status.state = VehicleState.CHARGING

        result = vehicle_controller.start_driving()

        assert result is False

    def test_start_driving_bms_fault(self, vehicle_controller, mock_bms):
        """Test starting driving with BMS fault."""
        mock_bms.get_state = Mock(return_value=BatteryState(
            voltage=400.0,
            current=0.0,
            temperature=25.0,
            soc=50.0,
            soh=100.0,
            cell_count=96,
            cell_voltages=[4.0] * 96,
            cell_temperatures=[25.0] * 96,
            status=BatteryStatus.FAULT,
            timestamp=time.time()
        ))
        vehicle_controller.current_status.state = VehicleState.READY

        result = vehicle_controller.start_driving()

        assert result is False
        assert vehicle_controller.current_status.state == VehicleState.ERROR

    def test_start_driving_low_soc(self, vehicle_controller, mock_bms):
        """Test starting driving with low SOC."""
        mock_bms.get_state = Mock(return_value=BatteryState(
            voltage=400.0,
            current=0.0,
            temperature=25.0,
            soc=3.0,  # Very low SOC
            soh=100.0,
            cell_count=96,
            cell_voltages=[4.0] * 96,
            cell_temperatures=[25.0] * 96,
            status=BatteryStatus.CRITICAL,
            timestamp=time.time()
        ))
        vehicle_controller.current_status.state = VehicleState.READY

        result = vehicle_controller.start_driving()

        assert result is False
        assert vehicle_controller.current_status.state == VehicleState.ERROR

    def test_start_driving_motor_not_connected(self, vehicle_controller, mock_motor_controller):
        """Test starting driving when motor not connected."""
        mock_motor_controller.is_connected = False
        vehicle_controller.current_status.state = VehicleState.READY

        result = vehicle_controller.start_driving()

        assert result is False

    def test_stop_driving(self, vehicle_controller, mock_motor_controller):
        """Test stopping driving."""
        vehicle_controller.current_status.state = VehicleState.DRIVING
        vehicle_controller.current_status.speed_kmh = 60.0

        result = vehicle_controller.stop_driving()

        assert result is True
        assert vehicle_controller.current_status.state == VehicleState.READY
        assert vehicle_controller.current_status.speed_kmh == 0.0
        mock_motor_controller.stop.assert_called_once()

    def test_stop_driving_not_driving(self, vehicle_controller):
        """Test stopping when not driving."""
        vehicle_controller.current_status.state = VehicleState.PARKED

        result = vehicle_controller.stop_driving()

        assert result is False

    def test_accelerate_success(self, vehicle_controller, mock_bms, mock_motor_controller):
        """Test accelerating successfully."""
        vehicle_controller.current_status.state = VehicleState.DRIVING
        vehicle_controller.current_status.speed_kmh = 10.0  # Set initial speed to avoid reset
        vehicle_controller.last_speed_update = time.time() - 1.0  # Set last update time
        mock_bms.can_discharge = Mock(return_value=True)

        result = vehicle_controller.accelerate(50.0)

        assert result is True
        # Power should be set correctly (acceleration might be reset if speed is very low)
        assert vehicle_controller.current_status.power_kw > 0
        mock_motor_controller.set_duty_cycle.assert_called()

    def test_accelerate_not_driving(self, vehicle_controller):
        """Test accelerating when not driving."""
        vehicle_controller.current_status.state = VehicleState.PARKED

        result = vehicle_controller.accelerate(50.0)

        assert result is False

    def test_accelerate_bms_rejects(self, vehicle_controller, mock_bms):
        """Test accelerating when BMS rejects discharge."""
        vehicle_controller.current_status.state = VehicleState.DRIVING
        mock_bms.can_discharge = Mock(return_value=False)

        result = vehicle_controller.accelerate(50.0)

        assert result is False

    def test_accelerate_throttle_clamping(self, vehicle_controller, mock_bms, mock_motor_controller):
        """Test throttle value clamping."""
        vehicle_controller.current_status.state = VehicleState.DRIVING
        mock_bms.can_discharge = Mock(return_value=True)

        # Test over 100%
        result = vehicle_controller.accelerate(150.0)
        assert result is True
        assert vehicle_controller.current_status.acceleration_ms2 <= vehicle_controller.config.max_acceleration_ms2

        # Test negative
        result = vehicle_controller.accelerate(-50.0)
        assert result is True
        assert vehicle_controller.current_status.acceleration_ms2 >= 0

    def test_brake_success(self, vehicle_controller, mock_motor_controller):
        """Test braking successfully."""
        vehicle_controller.current_status.state = VehicleState.DRIVING
        vehicle_controller.current_status.speed_kmh = 60.0

        result = vehicle_controller.brake(50.0)

        assert result is True
        assert vehicle_controller.current_status.acceleration_ms2 < 0
        mock_motor_controller.set_current.assert_called()

    def test_brake_not_driving(self, vehicle_controller):
        """Test braking when not driving."""
        vehicle_controller.current_status.state = VehicleState.PARKED

        result = vehicle_controller.brake(50.0)

        assert result is False

    def test_set_drive_mode(self, vehicle_controller):
        """Test setting drive mode."""
        result = vehicle_controller.set_drive_mode(DriveMode.ECO)

        assert result is True
        assert vehicle_controller.current_status.drive_mode == DriveMode.ECO

    def test_set_drive_mode_while_driving(self, vehicle_controller):
        """Test setting drive mode while driving."""
        vehicle_controller.current_status.state = VehicleState.DRIVING

        result = vehicle_controller.set_drive_mode(DriveMode.SPORT)

        assert result is False

    def test_start_charging_success(self, vehicle_controller, mock_charging_system):
        """Test starting charging successfully."""
        vehicle_controller.current_status.state = VehicleState.PARKED
        mock_charging_system.is_connected.return_value = False
        mock_charging_system.connect_charger.return_value = True
        mock_charging_system.start_charging.return_value = True

        result = vehicle_controller.start_charging()

        assert result is True
        assert vehicle_controller.current_status.state == VehicleState.CHARGING

    def test_start_charging_while_driving(self, vehicle_controller):
        """Test starting charging while driving."""
        vehicle_controller.current_status.state = VehicleState.DRIVING

        result = vehicle_controller.start_charging()

        assert result is False

    def test_start_charging_no_charging_system(self, vehicle_controller):
        """Test starting charging without charging system."""
        vehicle_controller.charging_system = None
        vehicle_controller.current_status.state = VehicleState.PARKED

        result = vehicle_controller.start_charging()

        assert result is False

    def test_stop_charging(self, vehicle_controller, mock_charging_system):
        """Test stopping charging."""
        vehicle_controller.current_status.state = VehicleState.CHARGING
        mock_charging_system.stop_charging.return_value = True

        result = vehicle_controller.stop_charging()

        assert result is True
        assert vehicle_controller.current_status.state == VehicleState.PARKED

    def test_update_status(self, vehicle_controller, mock_bms, mock_motor_controller):
        """Test updating vehicle status."""
        vehicle_controller.current_status.state = VehicleState.DRIVING
        mock_motor_controller.get_status.return_value = MotorStatus(
            speed_rpm=3000.0,
            current_a=50.0,
            voltage_v=400.0,
            duty_cycle=0.5,
            temperature_c=60.0,
            power_w=20000.0,
            state=MotorState.RUNNING,
            timestamp=time.time()
        )
        mock_bms.get_state = Mock(return_value=BatteryState(
            voltage=400.0,
            current=-50.0,
            temperature=30.0,
            soc=50.0,
            soh=100.0,
            cell_count=96,
            cell_voltages=[4.0] * 96,
            cell_temperatures=[30.0] * 96,
            status=BatteryStatus.DISCHARGING,
            timestamp=time.time()
        ))

        status = vehicle_controller.update_status()

        assert status.speed_kmh > 0
        assert status.power_kw > 0
        assert status.range_km > 0

    def test_update_status_range_calculation(self, vehicle_controller, mock_bms):
        """Test range calculation in status update."""
        mock_bms.get_state = Mock(return_value=BatteryState(
            voltage=400.0,
            current=0.0,
            temperature=25.0,
            soc=50.0,
            soh=100.0,
            cell_count=96,
            cell_voltages=[4.0] * 96,
            cell_temperatures=[25.0] * 96,
            status=BatteryStatus.HEALTHY,
            timestamp=time.time()
        ))
        mock_bms.config.capacity_kwh = 75.0

        status = vehicle_controller.update_status()

        # Range should be calculated: (50% * 75kWh * 1000) / 200 Wh/km = 187.5 km
        expected_range = (0.5 * 75.0 * 1000.0) / 200.0
        assert abs(status.range_km - expected_range) < 1.0

    def test_update_status_bms_fault_during_driving(self, vehicle_controller, mock_bms):
        """Test BMS fault detection during driving."""
        vehicle_controller.current_status.state = VehicleState.DRIVING
        mock_bms.get_state = Mock(return_value=BatteryState(
            voltage=400.0,
            current=-50.0,
            temperature=30.0,
            soc=50.0,
            soh=100.0,
            cell_count=96,
            cell_voltages=[4.0] * 96,
            cell_temperatures=[30.0] * 96,
            status=BatteryStatus.FAULT,
            timestamp=time.time()
        ))

        vehicle_controller.update_status()

        assert vehicle_controller.current_status.state == VehicleState.ERROR

    def test_update_status_charging_complete(self, vehicle_controller, mock_charging_system):
        """Test charging completion detection."""
        vehicle_controller.current_status.state = VehicleState.CHARGING
        charging_status = ChargingStatus()
        charging_status.state = ChargingState.COMPLETE
        mock_charging_system.get_status.return_value = charging_status

        vehicle_controller.update_status()

        assert vehicle_controller.current_status.state == VehicleState.PARKED

    def test_get_statistics(self, vehicle_controller):
        """Test getting vehicle statistics."""
        vehicle_controller.current_status.state = VehicleState.DRIVING
        vehicle_controller.current_status.speed_kmh = 60.0
        vehicle_controller.current_status.range_km = 200.0
        vehicle_controller.stats['total_distance_km'] = 100.0

        stats = vehicle_controller.get_statistics()

        assert 'total_distance_km' in stats
        assert 'current_speed_kmh' in stats
        assert 'current_range_km' in stats
        assert stats['current_speed_kmh'] == 60.0
        assert stats['current_range_km'] == 200.0

    def test_is_healthy(self, vehicle_controller, mock_bms, mock_motor_controller, mock_charging_system):
        """Test health check."""
        vehicle_controller.current_status.state = VehicleState.READY
        mock_bms.get_state = Mock(return_value=BatteryState(
            voltage=400.0,
            current=0.0,
            temperature=25.0,
            soc=50.0,
            soh=100.0,
            cell_count=96,
            cell_voltages=[4.0] * 96,
            cell_temperatures=[25.0] * 96,
            status=BatteryStatus.HEALTHY,
            timestamp=time.time()
        ))

        assert vehicle_controller.is_healthy() is True

    def test_is_healthy_error_state(self, vehicle_controller):
        """Test health check with error state."""
        vehicle_controller.current_status.state = VehicleState.ERROR

        assert vehicle_controller.is_healthy() is False

    def test_is_healthy_bms_fault(self, vehicle_controller, mock_bms):
        """Test health check with BMS fault."""
        vehicle_controller.current_status.state = VehicleState.READY
        mock_bms.get_state = Mock(return_value=BatteryState(
            voltage=400.0,
            current=0.0,
            temperature=25.0,
            soc=50.0,
            soh=100.0,
            cell_count=96,
            cell_voltages=[4.0] * 96,
            cell_temperatures=[25.0] * 96,
            status=BatteryStatus.FAULT,
            timestamp=time.time()
        ))

        assert vehicle_controller.is_healthy() is False

    def test_emergency_stop(self, vehicle_controller, mock_motor_controller, mock_charging_system):
        """Test emergency stop."""
        vehicle_controller.current_status.state = VehicleState.DRIVING
        vehicle_controller.current_status.speed_kmh = 60.0
        mock_charging_system.is_charging.return_value = True
        mock_charging_system.stop_charging.return_value = True

        result = vehicle_controller.emergency_stop()

        assert result is True
        assert vehicle_controller.current_status.state == VehicleState.EMERGENCY
        assert vehicle_controller.current_status.speed_kmh == 0.0
        assert vehicle_controller.current_status.acceleration_ms2 == 0.0
        mock_motor_controller.stop.assert_called_once()
        mock_charging_system.stop_charging.assert_called_once()

    def test_update_speed(self, vehicle_controller):
        """Test speed update calculation."""
        vehicle_controller.current_status.state = VehicleState.DRIVING
        vehicle_controller.current_status.acceleration_ms2 = 2.0
        vehicle_controller.current_status.speed_kmh = 0.0
        vehicle_controller.last_speed_update = time.time() - 1.0  # 1 second ago

        vehicle_controller._update_speed()

        # Speed should increase: v = v0 + a*t = 0 + 2.0 * 1.0 = 2.0 m/s = 7.2 km/h
        assert vehicle_controller.current_status.speed_kmh > 0

    def test_update_speed_max_limit(self, vehicle_controller):
        """Test speed update with maximum limit."""
        vehicle_controller.current_status.state = VehicleState.DRIVING
        vehicle_controller.current_status.acceleration_ms2 = 10.0  # High acceleration
        vehicle_controller.current_status.speed_kmh = 100.0
        vehicle_controller.config.max_speed_kmh = 120.0
        vehicle_controller.last_speed_update = time.time() - 10.0  # Long time

        vehicle_controller._update_speed()

        # Speed should be clamped to max (with small tolerance for floating point)
        assert vehicle_controller.current_status.speed_kmh <= vehicle_controller.config.max_speed_kmh + 0.01

    def test_update_energy_consumption(self, vehicle_controller):
        """Test energy consumption update."""
        vehicle_controller.current_status.state = VehicleState.DRIVING
        vehicle_controller.current_status.power_kw = 50.0
        vehicle_controller.stats['last_update'] = time.time() - 1.0  # 1 second ago

        initial_energy = vehicle_controller.stats['total_energy_consumed_kwh']

        vehicle_controller._update_energy_consumption()

        # Energy should increase: 50kW * 1s / 3600 = 0.0139 kWh
        assert vehicle_controller.stats['total_energy_consumed_kwh'] > initial_energy

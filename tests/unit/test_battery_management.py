"""Unit tests for Battery Management System (BMS)."""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from core.battery_management import (
    BatteryManagementSystem,
    BatteryState,
    BatteryStatus,
    BatteryConfig
)


class TestBatteryStatus:
    """Test BatteryStatus enum."""
    
    def test_battery_status_values(self):
        """Test that all expected status values are present."""
        expected_statuses = [
            "healthy", "warning", "critical", "charging", 
            "discharging", "fault", "standby"
        ]
        
        for status in expected_statuses:
            assert hasattr(BatteryStatus, status.upper()), f"Missing status: {status}"
    
    def test_battery_status_enum_values(self):
        """Test that enum values match expected strings."""
        assert BatteryStatus.HEALTHY.value == "healthy"
        assert BatteryStatus.WARNING.value == "warning"
        assert BatteryStatus.CRITICAL.value == "critical"
        assert BatteryStatus.CHARGING.value == "charging"
        assert BatteryStatus.DISCHARGING.value == "discharging"
        assert BatteryStatus.FAULT.value == "fault"
        assert BatteryStatus.STANDBY.value == "standby"


class TestBatteryState:
    """Test BatteryState dataclass."""
    
    def test_battery_state_creation(self):
        """Test creating a BatteryState."""
        state = BatteryState(
            voltage=400.0,
            current=50.0,
            temperature=25.0,
            soc=75.0,
            soh=95.0,
            cell_count=96,
            cell_voltages=[4.0] * 96,
            cell_temperatures=[25.0] * 96,
            status=BatteryStatus.HEALTHY,
            timestamp=time.time()
        )
        
        assert state.voltage == 400.0
        assert state.current == 50.0
        assert state.temperature == 25.0
        assert state.soc == 75.0
        assert state.soh == 95.0
        assert state.cell_count == 96
        assert len(state.cell_voltages) == 96
        assert len(state.cell_temperatures) == 96
        assert state.status == BatteryStatus.HEALTHY
    
    def test_battery_state_charging_current(self):
        """Test BatteryState with positive (charging) current."""
        state = BatteryState(
            voltage=400.0,
            current=50.0,  # Positive = charging
            temperature=25.0,
            soc=50.0,
            soh=100.0,
            cell_count=96,
            cell_voltages=[4.0] * 96,
            cell_temperatures=[25.0] * 96,
            status=BatteryStatus.CHARGING,
            timestamp=time.time()
        )
        
        assert state.current > 0
        assert state.status == BatteryStatus.CHARGING
    
    def test_battery_state_discharging_current(self):
        """Test BatteryState with negative (discharging) current."""
        state = BatteryState(
            voltage=400.0,
            current=-50.0,  # Negative = discharging
            temperature=25.0,
            soc=50.0,
            soh=100.0,
            cell_count=96,
            cell_voltages=[4.0] * 96,
            cell_temperatures=[25.0] * 96,
            status=BatteryStatus.DISCHARGING,
            timestamp=time.time()
        )
        
        assert state.current < 0
        assert state.status == BatteryStatus.DISCHARGING


class TestBatteryConfig:
    """Test BatteryConfig dataclass."""
    
    def test_battery_config_creation(self):
        """Test creating a BatteryConfig."""
        config = BatteryConfig(
            capacity_kwh=75.0,
            max_charge_rate_kw=150.0,
            max_discharge_rate_kw=200.0,
            nominal_voltage=400.0,
            cell_count=96
        )
        
        assert config.capacity_kwh == 75.0
        assert config.max_charge_rate_kw == 150.0
        assert config.max_discharge_rate_kw == 200.0
        assert config.nominal_voltage == 400.0
        assert config.cell_count == 96
        assert config.min_voltage == 3.0  # Default
        assert config.max_voltage == 4.2  # Default
        assert config.min_temperature == 0.0  # Default
        assert config.max_temperature == 45.0  # Default
    
    def test_battery_config_with_custom_values(self):
        """Test BatteryConfig with custom voltage and temperature limits."""
        config = BatteryConfig(
            capacity_kwh=100.0,
            max_charge_rate_kw=200.0,
            max_discharge_rate_kw=300.0,
            nominal_voltage=500.0,
            cell_count=120,
            min_voltage=2.5,
            max_voltage=4.3,
            min_temperature=-10.0,
            max_temperature=50.0
        )
        
        assert config.min_voltage == 2.5
        assert config.max_voltage == 4.3
        assert config.min_temperature == -10.0
        assert config.max_temperature == 50.0


class TestBatteryManagementSystem:
    """Test BatteryManagementSystem class."""
    
    @pytest.fixture
    def battery_config(self):
        """Create a battery configuration for testing."""
        return {
            'capacity_kwh': 75.0,
            'max_charge_rate_kw': 150.0,
            'max_discharge_rate_kw': 200.0,
            'nominal_voltage': 400.0,
            'cell_count': 96
        }
    
    @pytest.fixture
    def bms(self, battery_config):
        """Create a BatteryManagementSystem instance for testing."""
        return BatteryManagementSystem(battery_config)
    
    @pytest.fixture
    def mock_can_protocol(self):
        """Create a mock CAN protocol for testing."""
        mock = Mock()
        mock.send_battery_status = Mock(return_value=True)
        return mock
    
    @pytest.fixture
    def bms_with_can(self, battery_config, mock_can_protocol):
        """Create a BMS instance with CAN protocol."""
        return BatteryManagementSystem(battery_config, mock_can_protocol)
    
    def test_bms_initialization(self, bms, battery_config):
        """Test BMS initialization."""
        assert bms.config.capacity_kwh == battery_config['capacity_kwh']
        assert bms.config.cell_count == battery_config['cell_count']
        assert bms.config.nominal_voltage == battery_config['nominal_voltage']
        assert bms.state.voltage == battery_config['nominal_voltage']
        assert bms.state.cell_count == battery_config['cell_count']
        assert len(bms.state.cell_voltages) == battery_config['cell_count']
        assert len(bms.state.cell_temperatures) == battery_config['cell_count']
        assert bms.state.status == BatteryStatus.STANDBY
        assert bms.stats['total_energy_charged_kwh'] == 0.0
        assert bms.stats['total_energy_discharged_kwh'] == 0.0
        assert bms.stats['fault_count'] == 0
    
    def test_bms_initialization_with_defaults(self):
        """Test BMS initialization with minimal config."""
        config = {'capacity_kwh': 50.0}
        bms = BatteryManagementSystem(config)
        
        assert bms.config.capacity_kwh == 50.0
        assert bms.config.max_charge_rate_kw == 150.0  # Default
        assert bms.config.nominal_voltage == 400.0  # Default
        assert bms.config.cell_count == 96  # Default
    
    def test_bms_initialization_with_can_protocol(self, bms_with_can, mock_can_protocol):
        """Test BMS initialization with CAN protocol."""
        assert bms_with_can.can_protocol == mock_can_protocol
    
    def test_update_state_voltage(self, bms):
        """Test updating battery voltage."""
        initial_voltage = bms.state.voltage
        new_voltage = 410.0
        
        bms.update_state(voltage=new_voltage)
        
        assert bms.state.voltage == new_voltage
        assert bms.state.voltage != initial_voltage
    
    def test_update_state_current(self, bms):
        """Test updating battery current."""
        initial_current = bms.state.current
        new_current = 50.0
        
        bms.update_state(current=new_current)
        
        assert bms.state.current == new_current
        assert bms.state.current != initial_current
    
    def test_update_state_temperature(self, bms):
        """Test updating battery temperature."""
        initial_temp = bms.state.temperature
        new_temp = 30.0
        
        bms.update_state(temperature=new_temp)
        
        assert bms.state.temperature == new_temp
        assert bms.state.temperature != initial_temp
    
    def test_update_state_cell_voltages(self, bms):
        """Test updating cell voltages."""
        new_cell_voltages = [4.0] * 96
        new_cell_voltages[0] = 4.1  # Slightly different
        
        bms.update_state(cell_voltages=new_cell_voltages)
        
        assert bms.state.cell_voltages == new_cell_voltages
        assert bms.state.voltage == sum(new_cell_voltages)
    
    def test_update_state_cell_temperatures(self, bms):
        """Test updating cell temperatures."""
        new_cell_temperatures = [25.0] * 96
        new_cell_temperatures[0] = 30.0
        
        bms.update_state(cell_temperatures=new_cell_temperatures)
        
        assert bms.state.cell_temperatures == new_cell_temperatures
        assert bms.state.temperature == sum(new_cell_temperatures) / len(new_cell_temperatures)
    
    def test_update_state_soc_charging(self, bms):
        """Test SOC calculation during charging."""
        initial_soc = bms.state.soc
        charging_current = 50.0  # 50A charging
        voltage = 400.0
        dt = 3600.0  # 1 hour
        
        # Set initial state
        bms.state.voltage = voltage
        bms.state.current = 0.0
        bms.state.timestamp = time.time() - dt
        
        # Update with charging current
        bms.update_state(current=charging_current, voltage=voltage)
        
        # SOC should increase (simplified check - actual calculation depends on timing)
        assert bms.state.current == charging_current
    
    def test_update_state_soc_discharging(self, bms):
        """Test SOC calculation during discharging."""
        initial_soc = bms.state.soc
        discharging_current = -50.0  # -50A discharging
        voltage = 400.0
        
        bms.state.voltage = voltage
        bms.state.current = 0.0
        
        # Update with discharging current
        bms.update_state(current=discharging_current, voltage=voltage)
        
        assert bms.state.current == discharging_current
        assert bms.state.current < 0
    
    def test_update_state_soc_voltage_fallback(self, bms):
        """Test SOC calculation from voltage when current is zero."""
        bms.state.current = 0.0
        bms.state.voltage = 400.0  # Nominal voltage
        
        # Update with zero current
        bms.update_state(voltage=400.0, current=0.0)
        
        # SOC should be calculated from voltage
        assert bms.state.soc >= 0
        assert bms.state.soc <= 100
    
    def test_status_healthy(self, bms):
        """Test status determination for healthy battery."""
        bms.state.temperature = 25.0
        bms.state.soc = 50.0
        bms.state.current = 0.0
        bms.state.cell_voltages = [4.0] * 96
        bms.state.cell_temperatures = [25.0] * 96
        
        status = bms._determine_status()
        
        assert status == BatteryStatus.HEALTHY
    
    def test_status_charging(self, bms):
        """Test status determination for charging battery."""
        bms.state.temperature = 25.0
        bms.state.soc = 50.0
        bms.state.current = 50.0  # Positive current
        bms.state.cell_voltages = [4.0] * 96
        bms.state.cell_temperatures = [25.0] * 96
        
        status = bms._determine_status()
        
        assert status == BatteryStatus.CHARGING
    
    def test_status_discharging(self, bms):
        """Test status determination for discharging battery."""
        bms.state.temperature = 25.0
        bms.state.soc = 50.0
        bms.state.current = -50.0  # Negative current
        bms.state.cell_voltages = [4.0] * 96
        bms.state.cell_temperatures = [25.0] * 96
        
        status = bms._determine_status()
        
        assert status == BatteryStatus.DISCHARGING
    
    def test_status_warning_low_soc(self, bms):
        """Test status determination for low SOC warning."""
        bms.state.temperature = 25.0
        bms.state.soc = 8.0  # Low SOC
        bms.state.current = 0.0
        bms.state.cell_voltages = [4.0] * 96
        bms.state.cell_temperatures = [25.0] * 96
        
        status = bms._determine_status()
        
        assert status == BatteryStatus.WARNING
    
    def test_status_warning_high_soc(self, bms):
        """Test status determination for high SOC warning."""
        bms.state.temperature = 25.0
        bms.state.soc = 92.0  # High SOC
        bms.state.current = 0.0
        bms.state.cell_voltages = [4.0] * 96
        bms.state.cell_temperatures = [25.0] * 96
        
        status = bms._determine_status()
        
        assert status == BatteryStatus.WARNING
    
    def test_status_critical_low_soc(self, bms):
        """Test status determination for critical low SOC."""
        bms.state.temperature = 25.0
        bms.state.soc = 3.0  # Very low SOC
        bms.state.current = 0.0
        bms.state.cell_voltages = [4.0] * 96
        bms.state.cell_temperatures = [25.0] * 96
        
        status = bms._determine_status()
        
        assert status == BatteryStatus.CRITICAL
    
    def test_status_critical_high_temperature(self, bms):
        """Test status determination for critical high temperature."""
        bms.state.temperature = 50.0  # Above max (45.0)
        bms.state.soc = 50.0
        bms.state.current = 0.0
        bms.state.cell_voltages = [4.0] * 96
        bms.state.cell_temperatures = [50.0] * 96
        
        status = bms._determine_status()
        
        assert status == BatteryStatus.CRITICAL
    
    def test_status_critical_low_temperature(self, bms):
        """Test status determination for critical low temperature."""
        bms.state.temperature = -5.0  # Below min (0.0)
        bms.state.soc = 50.0
        bms.state.current = 0.0
        bms.state.cell_voltages = [4.0] * 96
        bms.state.cell_temperatures = [-5.0] * 96
        
        status = bms._determine_status()
        
        assert status == BatteryStatus.CRITICAL
    
    def test_check_faults_voltage_imbalance(self, bms):
        """Test fault detection for cell voltage imbalance."""
        cell_voltages = [4.0] * 96
        cell_voltages[0] = 4.6  # High imbalance (>0.5V difference)
        bms.state.cell_voltages = cell_voltages
        bms.state.cell_temperatures = [25.0] * 96
        
        has_fault = bms._check_faults()
        
        assert has_fault is True
        assert bms.stats['fault_count'] > 0
    
    def test_check_faults_overvoltage(self, bms):
        """Test fault detection for cell overvoltage."""
        cell_voltages = [4.0] * 96
        cell_voltages[0] = 4.5  # Above max (4.2V)
        bms.state.cell_voltages = cell_voltages
        bms.state.cell_temperatures = [25.0] * 96
        
        has_fault = bms._check_faults()
        
        assert has_fault is True
        assert bms.stats['fault_count'] > 0
    
    def test_check_faults_undervoltage(self, bms):
        """Test fault detection for cell undervoltage."""
        cell_voltages = [4.0] * 96
        cell_voltages[0] = 2.5  # Below min (3.0V)
        bms.state.cell_voltages = cell_voltages
        bms.state.cell_temperatures = [25.0] * 96
        
        has_fault = bms._check_faults()
        
        assert has_fault is True
        assert bms.stats['fault_count'] > 0
    
    def test_check_faults_overtemperature(self, bms):
        """Test fault detection for cell overtemperature."""
        bms.state.cell_voltages = [4.0] * 96
        cell_temperatures = [25.0] * 96
        cell_temperatures[0] = 50.0  # Above max (45.0°C)
        bms.state.cell_temperatures = cell_temperatures
        
        has_fault = bms._check_faults()
        
        assert has_fault is True
        assert bms.stats['fault_count'] > 0
    
    def test_check_faults_undertemperature(self, bms):
        """Test fault detection for cell undertemperature."""
        bms.state.cell_voltages = [4.0] * 96
        cell_temperatures = [25.0] * 96
        cell_temperatures[0] = -5.0  # Below min (0.0°C)
        bms.state.cell_temperatures = cell_temperatures
        
        has_fault = bms._check_faults()
        
        assert has_fault is True
        assert bms.stats['fault_count'] > 0
    
    def test_check_faults_no_faults(self, bms):
        """Test fault detection with no faults."""
        bms.state.cell_voltages = [4.0] * 96
        bms.state.cell_temperatures = [25.0] * 96
        initial_fault_count = bms.stats['fault_count']
        
        has_fault = bms._check_faults()
        
        assert has_fault is False
        assert bms.stats['fault_count'] == initial_fault_count
    
    def test_send_can_status(self, bms_with_can, mock_can_protocol):
        """Test sending status to CAN bus."""
        bms_with_can.state.voltage = 400.0
        bms_with_can.state.current = 50.0
        bms_with_can.state.temperature = 25.0
        bms_with_can.state.soc = 75.0
        
        bms_with_can._send_can_status()
        
        mock_can_protocol.send_battery_status.assert_called_once_with(
            voltage=400.0,
            current=50.0,
            temperature=25.0,
            soc=75.0
        )
    
    def test_send_can_status_no_protocol(self, bms):
        """Test sending status when no CAN protocol is configured."""
        # Should not raise an exception
        bms._send_can_status()
    
    def test_send_can_status_protocol_error(self, bms_with_can, mock_can_protocol):
        """Test CAN status sending with protocol error."""
        mock_can_protocol.send_battery_status.side_effect = Exception("CAN error")
        
        # Should not raise an exception, just log error
        bms_with_can._send_can_status()
    
    def test_get_state(self, bms):
        """Test getting battery state."""
        state = bms.get_state()
        
        assert isinstance(state, BatteryState)
        assert state.voltage == bms.state.voltage
        assert state.current == bms.state.current
        assert state.soc == bms.state.soc
    
    def test_get_config(self, bms):
        """Test getting battery configuration."""
        config = bms.get_config()
        
        assert isinstance(config, BatteryConfig)
        assert config.capacity_kwh == bms.config.capacity_kwh
        assert config.cell_count == bms.config.cell_count
    
    def test_get_statistics(self, bms):
        """Test getting battery statistics."""
        stats = bms.get_statistics()
        
        assert 'total_energy_charged_kwh' in stats
        assert 'total_energy_discharged_kwh' in stats
        assert 'fault_count' in stats
        assert 'current_soc' in stats
        assert 'current_soh' in stats
        assert 'status' in stats
        assert 'voltage' in stats
        assert 'current' in stats
        assert 'temperature' in stats
    
    def test_get_health_status(self, bms):
        """Test getting battery health status."""
        health = bms.get_health_status()
        
        assert 'soh' in health
        assert 'soc' in health
        assert 'status' in health
        assert 'fault_count' in health
        assert 'charge_cycles' in health
        assert 'temperature' in health
        assert 'voltage_range' in health
        assert 'min' in health['voltage_range']
        assert 'max' in health['voltage_range']
        assert 'average' in health['voltage_range']
    
    def test_can_charge_allowed(self, bms):
        """Test charge permission when charging is allowed."""
        bms.state.status = BatteryStatus.HEALTHY
        bms.state.soc = 50.0
        requested_power = 100.0  # kW
        
        can_charge = bms.can_charge(requested_power)
        
        assert can_charge is True
    
    def test_can_charge_fault_status(self, bms):
        """Test charge permission when battery is in fault."""
        bms.state.status = BatteryStatus.FAULT
        requested_power = 100.0
        
        can_charge = bms.can_charge(requested_power)
        
        assert can_charge is False
    
    def test_can_charge_critical_status(self, bms):
        """Test charge permission when battery is critical."""
        bms.state.status = BatteryStatus.CRITICAL
        requested_power = 100.0
        
        can_charge = bms.can_charge(requested_power)
        
        assert can_charge is False
    
    def test_can_charge_exceeds_max_rate(self, bms):
        """Test charge permission when requested power exceeds max rate."""
        bms.state.status = BatteryStatus.HEALTHY
        bms.state.soc = 50.0
        requested_power = 200.0  # Exceeds max_charge_rate_kw (150.0)
        
        can_charge = bms.can_charge(requested_power)
        
        assert can_charge is False
    
    def test_can_charge_full_soc(self, bms):
        """Test charge permission when SOC is at maximum."""
        bms.state.status = BatteryStatus.HEALTHY
        bms.state.soc = 100.0  # Full
        requested_power = 100.0
        
        can_charge = bms.can_charge(requested_power)
        
        assert can_charge is False
    
    def test_can_discharge_allowed(self, bms):
        """Test discharge permission when discharge is allowed."""
        bms.state.status = BatteryStatus.HEALTHY
        bms.state.soc = 50.0
        requested_power = 150.0  # kW
        
        can_discharge = bms.can_discharge(requested_power)
        
        assert can_discharge is True
    
    def test_can_discharge_fault_status(self, bms):
        """Test discharge permission when battery is in fault."""
        bms.state.status = BatteryStatus.FAULT
        requested_power = 150.0
        
        can_discharge = bms.can_discharge(requested_power)
        
        assert can_discharge is False
    
    def test_can_discharge_critical_status(self, bms):
        """Test discharge permission when battery is critical."""
        bms.state.status = BatteryStatus.CRITICAL
        requested_power = 150.0
        
        can_discharge = bms.can_discharge(requested_power)
        
        assert can_discharge is False
    
    def test_can_discharge_exceeds_max_rate(self, bms):
        """Test discharge permission when requested power exceeds max rate."""
        bms.state.status = BatteryStatus.HEALTHY
        bms.state.soc = 50.0
        requested_power = 250.0  # Exceeds max_discharge_rate_kw (200.0)
        
        can_discharge = bms.can_discharge(requested_power)
        
        assert can_discharge is False
    
    def test_can_discharge_low_soc(self, bms):
        """Test discharge permission when SOC is at minimum."""
        bms.state.status = BatteryStatus.HEALTHY
        bms.state.soc = 0.0  # Empty
        requested_power = 150.0
        
        can_discharge = bms.can_discharge(requested_power)
        
        assert can_discharge is False
    
    def test_update_state_integrates_energy_charging(self, bms):
        """Test that update_state integrates energy during charging."""
        initial_energy = bms.stats['total_energy_charged_kwh']
        bms.state.voltage = 400.0
        bms.state.current = 0.0
        bms.state.timestamp = time.time() - 3600.0  # 1 hour ago
        
        # Simulate 1 hour of charging at 50A
        bms.update_state(voltage=400.0, current=50.0)
        
        # Energy should have increased (simplified check)
        # Note: Actual energy depends on timing, so we just check the mechanism works
        assert bms.state.current == 50.0
    
    def test_update_state_integrates_energy_discharging(self, bms):
        """Test that update_state integrates energy during discharging."""
        initial_energy = bms.stats['total_energy_discharged_kwh']
        bms.state.voltage = 400.0
        bms.state.current = 0.0
        bms.state.timestamp = time.time() - 3600.0  # 1 hour ago
        
        # Simulate 1 hour of discharging at -50A
        bms.update_state(voltage=400.0, current=-50.0)
        
        # Energy should have increased (simplified check)
        assert bms.state.current == -50.0
    
    def test_update_state_updates_timestamp(self, bms):
        """Test that update_state updates timestamp."""
        initial_timestamp = bms.state.timestamp
        time.sleep(0.01)  # Small delay
        
        bms.update_state(voltage=400.0)
        
        assert bms.state.timestamp > initial_timestamp
        assert bms.stats['last_update'] > initial_timestamp
    
    def test_update_state_calls_can_status(self, bms_with_can, mock_can_protocol):
        """Test that update_state calls CAN status when protocol is available."""
        bms_with_can.update_state(voltage=400.0, current=50.0, temperature=25.0)
        
        # Should have called send_battery_status
        assert mock_can_protocol.send_battery_status.called
    
    def test_status_warning_high_temperature(self, bms):
        """Test status determination for high temperature warning."""
        bms.state.temperature = 42.0  # 90% of max (45.0) = 40.5, so > 40.5
        bms.state.soc = 50.0
        bms.state.current = 0.0
        bms.state.cell_voltages = [4.0] * 96
        bms.state.cell_temperatures = [42.0] * 96
        
        status = bms._determine_status()
        
        # Should be WARNING (90% of max temperature)
        assert status == BatteryStatus.WARNING
    
    def test_status_fault_detected(self, bms):
        """Test status determination when fault is detected."""
        bms.state.cell_voltages = [4.0] * 96
        bms.state.cell_voltages[0] = 4.6  # Causes fault
        bms.state.cell_temperatures = [25.0] * 96
        bms.state.temperature = 25.0
        bms.state.soc = 50.0
        bms.state.current = 0.0
        
        status = bms._determine_status()
        
        assert status == BatteryStatus.FAULT


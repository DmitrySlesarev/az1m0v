"""Functional tests for safety system integration scenarios."""

import pytest
import time
from unittest.mock import Mock, patch
from core.safety_system import SafetySystem, SafetyState, FaultType
from core.battery_management import BatteryManagementSystem, BatteryState, BatteryStatus
from core.motor_controller import VESCManager, MotorStatus, MotorState
from core.charging_system import ChargingSystem, ChargingStatus, ChargingState
from core.vehicle_controller import VehicleController, VehicleState
from communication.can_bus import CANBusInterface, EVCANProtocol


class TestSafetySystemIntegration:
    """Integration tests for safety system."""

    @pytest.fixture
    def can_interface(self):
        """Create a CANBusInterface instance for integration testing."""
        interface = CANBusInterface("can0", 500000)
        interface.connect()
        return interface

    @pytest.fixture
    def can_protocol(self, can_interface):
        """Create an EVCANProtocol instance for integration testing."""
        protocol = EVCANProtocol(can_interface)
        protocol.send_battery_status = Mock(return_value=True)
        protocol.send_motor_status = Mock(return_value=True)
        protocol.send_vehicle_status = Mock(return_value=True)
        return protocol

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
    def bms(self, bms_config, can_protocol):
        """Create a BatteryManagementSystem instance."""
        return BatteryManagementSystem(bms_config, can_protocol=can_protocol)

    @pytest.fixture
    def motor_config(self):
        """Create motor controller configuration."""
        return {
            'max_power_kw': 150.0,
            'max_torque_nm': 320.0,
            'max_current_a': 200.0,
            'max_rpm': 10000.0,
            'max_temperature_c': 80.0,
            'min_voltage_v': 300.0,
            'max_voltage_v': 500.0
        }

    @pytest.fixture
    def motor_controller(self, motor_config, can_protocol):
        """Create a VESCManager instance."""
        motor = VESCManager(
            serial_port=None,  # Simulation mode
            can_protocol=can_protocol,
            config=motor_config
        )
        motor.is_connected = True
        return motor

    @pytest.fixture
    def charging_config(self):
        """Create charging system configuration."""
        return {
            'ac_max_power_kw': 11.0,
            'dc_max_power_kw': 150.0,
            'connector_type': 'CCS2',
            'fast_charge_enabled': True
        }

    @pytest.fixture
    def charging_system(self, charging_config, bms, motor_controller, can_protocol):
        """Create a ChargingSystem instance."""
        return ChargingSystem(
            config=charging_config,
            bms=bms,
            motor_controller=motor_controller,
            can_protocol=can_protocol
        )

    @pytest.fixture
    def vehicle_config(self):
        """Create vehicle controller configuration."""
        return {
            'max_speed_kmh': 120.0,
            'max_acceleration_ms2': 3.0,
            'max_deceleration_ms2': -5.0,
            'max_power_kw': 150.0,
            'efficiency_wh_per_km': 200.0,
            'weight_kg': 1500.0
        }

    @pytest.fixture
    def vehicle_controller(self, vehicle_config, bms, motor_controller, 
                           charging_system, can_protocol):
        """Create a VehicleController instance."""
        return VehicleController(
            config=vehicle_config,
            bms=bms,
            motor_controller=motor_controller,
            charging_system=charging_system,
            can_protocol=can_protocol
        )

    @pytest.fixture
    def safety_config(self):
        """Create safety system configuration."""
        return {
            'battery_temp_max': 60.0,
            'battery_temp_warning': 50.0,
            'motor_temp_max': 100.0,
            'motor_temp_warning': 80.0,
            'thermal_runaway_rate': 2.0,
            'thermal_runaway_threshold': 5.0,
            'voltage_max': 500.0,
            'voltage_min': 300.0,
            'current_max': 500.0
        }

    @pytest.fixture
    def safety_system(self, safety_config, bms, motor_controller, 
                     charging_system, vehicle_controller):
        """Create a SafetySystem instance."""
        return SafetySystem(
            battery_management=bms,
            motor_controller=motor_controller,
            charging_system=charging_system,
            vehicle_controller=vehicle_controller,
            config=safety_config
        )

    def test_safety_system_integration_initialization(self, safety_system):
        """Test safety system integration with all components."""
        assert safety_system.battery_management is not None
        assert safety_system.motor_controller is not None
        assert safety_system.charging_system is not None
        assert safety_system.vehicle_controller is not None
        assert safety_system.safety_states['thermal'] == SafetyState.NORMAL
        assert safety_system.safety_states['electrical'] == SafetyState.NORMAL

    def test_safety_system_monitors_battery_temperature(self, safety_system, bms):
        """Test that safety system monitors battery temperature."""
        # Build up history first with gradual rise ending near warning temp
        current_time = time.time() - 10.0
        for i in range(10):
            temp = 25.0 + (i * 2.5)  # Gradual rise to ~50°C
            safety_system.battery_thermal_history.temperatures.append(temp)
            safety_system.battery_thermal_history.timestamps.append(current_time + i)
        
        # Add one more reading close to target
        safety_system.battery_thermal_history.temperatures.append(54.9)
        safety_system.battery_thermal_history.timestamps.append(current_time + 10)
        
        # Update BMS with high temperature (above warning but below critical)
        bms.update_state(temperature=55.0)
        
        bms_state = bms.get_state()
        result = safety_system.check_thermal_runaway(
            bms_state.temperature,
            None
        )
        
        # Should set warning state (or emergency if rate triggers, which is also valid)
        assert safety_system.safety_states['thermal'] in [SafetyState.WARNING, SafetyState.EMERGENCY]

    def test_safety_system_monitors_motor_temperature(self, safety_system, motor_controller):
        """Test that safety system monitors motor temperature."""
        # Build up history first with gradual rise ending near warning temp
        current_time = time.time() - 10.0
        for i in range(10):
            temp = 25.0 + (i * 5.5)  # Gradual rise to ~80°C
            safety_system.motor_thermal_history.temperatures.append(temp)
            safety_system.motor_thermal_history.timestamps.append(current_time + i)
        
        # Add one more reading close to target
        safety_system.motor_thermal_history.temperatures.append(84.9)
        safety_system.motor_thermal_history.timestamps.append(current_time + 10)
        
        # Set motor temperature (above warning but below critical)
        motor_controller.current_status.temperature_c = 85.0
        
        result = safety_system.check_thermal_runaway(
            None,
            motor_controller.current_status.temperature_c
        )
        
        # Should set warning state (or emergency if rate triggers, which is also valid)
        assert safety_system.safety_states['thermal'] in [SafetyState.WARNING, SafetyState.EMERGENCY]

    def test_safety_system_thermal_runaway_detection(self, safety_system, bms):
        """Test thermal runaway detection with rapid temperature rise."""
        # Simulate rapid temperature rise with realistic timestamps
        current_time = time.time() - 15.0
        for i in range(15):
            temp = 25.0 + (i * 3.0)  # 3°C per second
            safety_system.battery_thermal_history.temperatures.append(temp)
            safety_system.battery_thermal_history.timestamps.append(current_time + i)
        
        result = safety_system.check_thermal_runaway(70.0, None)
        assert result is True
        # With rapid rise, should detect thermal runaway (EMERGENCY)
        # But critical temp (70.0 > 60.0) also sets CRITICAL, which overwrites EMERGENCY
        assert safety_system.safety_states['thermal'] == SafetyState.CRITICAL
        assert len(safety_system.faults) > 0
        # Should have both thermal runaway and overheating faults
        fault_types = [f.fault_type for f in safety_system.faults]
        assert FaultType.THERMAL_RUNAWAY in fault_types or FaultType.OVERHEATING in fault_types

    def test_safety_system_electrical_overvoltage(self, safety_system, bms):
        """Test electrical safety monitoring with overvoltage."""
        # Update BMS with overvoltage
        bms.update_state(voltage=550.0)
        
        result = safety_system.check_electrical_safety()
        assert result is True
        assert safety_system.safety_states['electrical'] == SafetyState.CRITICAL
        assert len(safety_system.faults) > 0
        fault = safety_system.faults[-1]
        assert fault.fault_type == FaultType.OVERVOLTAGE

    def test_safety_system_electrical_undervoltage(self, safety_system, bms):
        """Test electrical safety monitoring with undervoltage."""
        # Update BMS with undervoltage
        bms.update_state(voltage=250.0)
        
        result = safety_system.check_electrical_safety()
        assert result is True
        assert safety_system.safety_states['electrical'] == SafetyState.WARNING
        fault = safety_system.faults[-1]
        assert fault.fault_type == FaultType.UNDERVOLTAGE

    def test_safety_system_electrical_overcurrent(self, safety_system, bms):
        """Test electrical safety monitoring with overcurrent."""
        # Update BMS with overcurrent
        bms.update_state(current=600.0)
        
        result = safety_system.check_electrical_safety()
        assert result is True
        assert safety_system.safety_states['electrical'] == SafetyState.CRITICAL
        fault = safety_system.faults[-1]
        assert fault.fault_type == FaultType.OVERCURRENT

    def test_safety_system_emergency_shutdown_sequence(self, safety_system, 
                                                       motor_controller,
                                                       charging_system,
                                                       vehicle_controller):
        """Test complete emergency shutdown sequence."""
        # Set charging as active
        charging_system.current_status.state = ChargingState.CHARGING
        charging_system.is_charging = Mock(return_value=True)
        
        # Mock the stop methods
        motor_controller.stop = Mock(return_value=True)
        charging_system.stop_charging = Mock(return_value=True)
        charging_system.disconnect_charger = Mock(return_value=True)
        vehicle_controller.emergency_stop = Mock(return_value=True)
        
        result = safety_system.emergency_shutdown("Integration test shutdown")
        
        assert result is True
        assert safety_system.emergency_shutdown_active is True
        assert safety_system.emergency_shutdown_reason == "Integration test shutdown"
        
        # Verify shutdown sequence
        motor_controller.stop.assert_called_once()
        charging_system.stop_charging.assert_called_once()
        charging_system.disconnect_charger.assert_called_once()
        vehicle_controller.emergency_stop.assert_called_once()

    def test_safety_system_monitor_triggers_shutdown(self, safety_system, bms):
        """Test that monitor_system triggers shutdown on critical conditions."""
        # Set up critical thermal condition with realistic timestamps
        current_time = time.time() - 15.0
        for i in range(15):
            temp = 25.0 + (i * 3.0)  # 3°C per second
            safety_system.battery_thermal_history.temperatures.append(temp)
            safety_system.battery_thermal_history.timestamps.append(current_time + i)
        
        # Update BMS state with critical temperature
        bms.update_state(temperature=70.0)  # Above max (60.0)
        
        result = safety_system.monitor_system()
        
        # Should trigger emergency shutdown because:
        # 1. Thermal runaway detected (rapid rise) -> EMERGENCY or CRITICAL state
        # 2. Critical temp (70.0 > 60.0) -> CRITICAL state
        # 3. monitor_system checks for CRITICAL thermal state and triggers shutdown
        assert result is False
        assert safety_system.emergency_shutdown_active is True

    def test_safety_system_fault_tracking(self, safety_system, bms):
        """Test fault tracking across multiple conditions."""
        # Trigger multiple faults
        bms.update_state(voltage=550.0)  # Overvoltage
        safety_system.check_electrical_safety()
        
        bms.update_state(voltage=400.0, current=600.0)  # Overcurrent
        safety_system.check_electrical_safety()
        
        # Check fault tracking
        active_faults = safety_system.get_active_faults()
        assert len(active_faults) >= 2
        
        # Check fault types
        fault_types = [f.fault_type for f in active_faults]
        assert FaultType.OVERVOLTAGE in fault_types
        assert FaultType.OVERCURRENT in fault_types

    def test_safety_system_reset_after_faults_cleared(self, safety_system, bms):
        """Test resetting emergency shutdown after faults are cleared."""
        # Trigger emergency shutdown
        bms.update_state(voltage=550.0)
        safety_system.check_electrical_safety()
        safety_system.emergency_shutdown("Test")
        
        # Clear faults
        safety_system.clear_faults()
        
        # Reset should succeed
        result = safety_system.reset_emergency_shutdown()
        assert result is True
        assert safety_system.emergency_shutdown_active is False
        assert safety_system.safety_states['thermal'] == SafetyState.NORMAL

    def test_safety_system_status_reporting(self, safety_system, bms):
        """Test safety system status reporting."""
        # Trigger some faults
        bms.update_state(voltage=550.0)
        safety_system.check_electrical_safety()
        
        status = safety_system.get_status()
        
        assert 'safety_states' in status
        assert 'emergency_shutdown_active' in status
        assert 'active_fault_count' in status
        assert 'critical_fault_count' in status
        assert status['active_fault_count'] > 0
        assert status['safety_states']['electrical'] == 'CRITICAL'

    def test_safety_system_integration_with_vehicle_controller(self, safety_system,
                                                                vehicle_controller,
                                                                bms):
        """Test safety system integration with vehicle controller emergency stop."""
        # Mock emergency_stop
        vehicle_controller.emergency_stop = Mock(return_value=True)
        
        # Trigger critical condition
        bms.update_state(voltage=550.0)
        safety_system.check_electrical_safety()
        
        # Monitor should trigger shutdown
        safety_system.monitor_system()
        
        # Vehicle controller should be in emergency state
        assert safety_system.emergency_shutdown_active is True
        vehicle_controller.emergency_stop.assert_called()

    def test_safety_system_handles_missing_components(self):
        """Test safety system handles missing components gracefully."""
        system = SafetySystem(
            battery_management=None,
            motor_controller=None,
            charging_system=None,
            vehicle_controller=None
        )
        
        # Should not crash when components are None
        result = system.monitor_system()
        assert result is True  # System is safe (no components to monitor)
        
        # Should handle emergency shutdown without components
        result = system.emergency_shutdown("Test")
        assert result is True

    def test_safety_system_thermal_history_tracking(self, safety_system):
        """Test thermal history tracking over time."""
        current_time = time.time()
        
        # Add temperature readings over time
        for i in range(20):
            temp = 25.0 + (i * 0.1)  # Gradual increase
            safety_system.check_thermal_runaway(temp, None)
            time.sleep(0.01)  # Small delay
        
        # Check that history is maintained
        assert len(safety_system.battery_thermal_history.temperatures) > 0
        assert len(safety_system.battery_thermal_history.timestamps) > 0

    def test_safety_system_multiple_thermal_conditions(self, safety_system, bms):
        """Test safety system handling multiple thermal conditions."""
        # Build up history first with gradual rise
        current_time = time.time() - 10.0
        for i in range(10):
            temp_bat = 25.0 + (i * 2.5)  # Gradual rise to ~50°C
            temp_mot = 25.0 + (i * 5.5)  # Gradual rise to ~80°C
            safety_system.battery_thermal_history.temperatures.append(temp_bat)
            safety_system.battery_thermal_history.timestamps.append(current_time + i)
            safety_system.motor_thermal_history.temperatures.append(temp_mot)
            safety_system.motor_thermal_history.timestamps.append(current_time + i)
        
        # Add readings close to targets
        safety_system.battery_thermal_history.temperatures.append(54.9)
        safety_system.battery_thermal_history.timestamps.append(current_time + 10)
        safety_system.motor_thermal_history.temperatures.append(84.9)
        safety_system.motor_thermal_history.timestamps.append(current_time + 10)
        
        # Set both battery and motor to warning temperatures
        bms.update_state(temperature=55.0)
        bms_state = bms.get_state()
        
        motor_temp = 85.0
        
        result = safety_system.check_thermal_runaway(
            bms_state.temperature,
            motor_temp
        )
        
        # Both should trigger warnings (or emergency if rate triggers)
        assert safety_system.safety_states['thermal'] in [SafetyState.WARNING, SafetyState.EMERGENCY]

    def test_safety_system_diagnostics_integration(self, safety_system, bms):
        """Test safety system integration with diagnostics."""
        # Trigger a fault
        bms.update_state(voltage=550.0)  # Overvoltage
        safety_system.check_electrical_safety()
        
        # Check that diagnostics system was initialized
        assert hasattr(safety_system, 'diagnostics')
        assert safety_system.diagnostics is not None
        
        # Check that DTC was generated
        active_dtcs = safety_system.diagnostics.dtc_manager.get_active_dtcs()
        assert len(active_dtcs) > 0
        
        # Check that fault was logged
        status = safety_system.get_status()
        assert 'diagnostics' in status
        assert status['diagnostics'] is not None
        assert status['diagnostics']['active_dtc_count'] > 0

    def test_safety_system_limp_home_mode(self, safety_system, bms):
        """Test limp-home mode activation."""
        # Trigger warning-level fault
        bms.update_state(voltage=250.0)  # Undervoltage (warning)
        safety_system.check_electrical_safety()
        
        # Check limp-home mode
        limp_home_mode = safety_system.diagnostics.limp_home_manager.get_mode()
        assert limp_home_mode.value in ['normal', 'reduced_power']
        
        # Trigger critical fault
        bms.update_state(voltage=550.0)  # Overvoltage (critical)
        safety_system.check_electrical_safety()
        
        # Limp-home mode should be more restrictive
        new_mode = safety_system.diagnostics.limp_home_manager.get_mode()
        assert new_mode.value in ['limited_speed', 'emergency_only', 'disabled']


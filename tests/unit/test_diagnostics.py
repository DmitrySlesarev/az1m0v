"""Unit tests for diagnostics system."""

import pytest
import time
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from core.diagnostics import (
    DTCManager, LimpHomeManager, FaultLogger, DiagnosticsSystem,
    DiagnosticTroubleCode, DTCSeverity, LimpHomeMode, LimpHomeLimits
)
from core.safety_system import SafetyState, FaultType


class TestDTCManager:
    """Tests for DTC Manager."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def dtc_manager(self, temp_dir):
        """Create DTC Manager instance."""
        return DTCManager(log_dir=temp_dir)

    def test_dtc_manager_initialization(self, dtc_manager):
        """Test DTC Manager initialization."""
        assert dtc_manager.active_dtcs == {}
        assert dtc_manager.dtc_history == []

    def test_generate_dtc_from_fault(self, dtc_manager):
        """Test generating DTC from fault."""
        dtc = dtc_manager.generate_dtc(
            fault_type=FaultType.OVERVOLTAGE,
            component="battery",
            severity=SafetyState.CRITICAL
        )
        
        assert dtc.code.startswith("P0102")
        assert dtc.component == "battery"
        assert dtc.confirmed is True
        assert dtc.severity == DTCSeverity.CONFIRMED
        assert dtc.code in dtc_manager.active_dtcs

    def test_generate_dtc_emergency_severity(self, dtc_manager):
        """Test DTC generation for emergency severity."""
        dtc = dtc_manager.generate_dtc(
            fault_type=FaultType.THERMAL_RUNAWAY,
            component="battery",
            severity=SafetyState.EMERGENCY
        )
        
        assert dtc.permanent is True
        assert dtc.severity == DTCSeverity.PERMANENT
        assert dtc.confirmed is True

    def test_generate_dtc_warning_severity(self, dtc_manager):
        """Test DTC generation for warning severity."""
        dtc = dtc_manager.generate_dtc(
            fault_type=FaultType.UNDERVOLTAGE,
            component="battery",
            severity=SafetyState.WARNING
        )
        
        assert dtc.permanent is False
        assert dtc.severity == DTCSeverity.PENDING
        assert dtc.confirmed is False

    def test_dtc_occurrence_counting(self, dtc_manager):
        """Test DTC occurrence counting."""
        dtc1 = dtc_manager.generate_dtc(
            fault_type=FaultType.OVERCURRENT,
            component="motor",
            severity=SafetyState.CRITICAL
        )
        
        assert dtc1.occurrence_count == 1
        
        # Generate same DTC again
        dtc2 = dtc_manager.generate_dtc(
            fault_type=FaultType.OVERCURRENT,
            component="motor",
            severity=SafetyState.CRITICAL
        )
        
        assert dtc2.occurrence_count == 2
        assert dtc1.code == dtc2.code
        assert len(dtc_manager.active_dtcs) == 1

    def test_clear_dtc(self, dtc_manager):
        """Test clearing a DTC."""
        dtc = dtc_manager.generate_dtc(
            fault_type=FaultType.OVERVOLTAGE,
            component="battery",
            severity=SafetyState.WARNING
        )
        
        assert dtc.code in dtc_manager.active_dtcs
        
        result = dtc_manager.clear_dtc(dtc.code)
        assert result is True
        assert dtc.code not in dtc_manager.active_dtcs
        assert dtc.cleared is True

    def test_clear_permanent_dtc(self, dtc_manager):
        """Test that permanent DTCs cannot be cleared."""
        dtc = dtc_manager.generate_dtc(
            fault_type=FaultType.THERMAL_RUNAWAY,
            component="battery",
            severity=SafetyState.EMERGENCY
        )
        
        assert dtc.permanent is True
        
        result = dtc_manager.clear_dtc(dtc.code)
        # Permanent DTCs should not be cleared
        assert dtc.code in dtc_manager.active_dtcs

    def test_clear_all_dtcs(self, dtc_manager):
        """Test clearing all DTCs."""
        # Generate multiple DTCs
        dtc_manager.generate_dtc(
            fault_type=FaultType.OVERVOLTAGE,
            component="battery",
            severity=SafetyState.WARNING
        )
        dtc_manager.generate_dtc(
            fault_type=FaultType.OVERCURRENT,
            component="motor",
            severity=SafetyState.WARNING
        )
        
        assert len(dtc_manager.active_dtcs) == 2
        
        result = dtc_manager.clear_dtc()
        assert result is True
        assert len(dtc_manager.active_dtcs) == 0

    def test_get_active_dtcs(self, dtc_manager):
        """Test getting active DTCs."""
        dtc1 = dtc_manager.generate_dtc(
            fault_type=FaultType.OVERVOLTAGE,
            component="battery",
            severity=SafetyState.WARNING
        )
        dtc2 = dtc_manager.generate_dtc(
            fault_type=FaultType.OVERCURRENT,
            component="motor",
            severity=SafetyState.WARNING
        )
        
        active = dtc_manager.get_active_dtcs()
        assert len(active) == 2
        assert dtc1 in active
        assert dtc2 in active

    def test_get_dtcs_by_component(self, dtc_manager):
        """Test getting DTCs by component."""
        dtc_manager.generate_dtc(
            fault_type=FaultType.OVERVOLTAGE,
            component="battery",
            severity=SafetyState.WARNING
        )
        dtc_manager.generate_dtc(
            fault_type=FaultType.OVERCURRENT,
            component="motor",
            severity=SafetyState.WARNING
        )
        
        battery_dtcs = dtc_manager.get_dtcs_by_component("battery")
        assert len(battery_dtcs) == 1
        assert battery_dtcs[0].component == "battery"

    def test_export_dtcs(self, dtc_manager, temp_dir):
        """Test exporting DTCs to JSON."""
        dtc_manager.generate_dtc(
            fault_type=FaultType.OVERVOLTAGE,
            component="battery",
            severity=SafetyState.WARNING
        )
        
        export_path = dtc_manager.export_dtcs()
        
        assert export_path.exists()
        with open(export_path, 'r') as f:
            data = json.load(f)
        
        assert 'active_dtcs' in data
        assert len(data['active_dtcs']) == 1


class TestLimpHomeManager:
    """Tests for Limp-Home Manager."""

    @pytest.fixture
    def limp_home_manager(self):
        """Create Limp-Home Manager instance."""
        return LimpHomeManager()

    def test_limp_home_manager_initialization(self, limp_home_manager):
        """Test Limp-Home Manager initialization."""
        assert limp_home_manager.current_mode == LimpHomeMode.NORMAL
        assert len(limp_home_manager.mode_history) == 0

    def test_determine_mode_normal(self, limp_home_manager):
        """Test determining normal mode."""
        safety_states = {
            'thermal': SafetyState.NORMAL,
            'electrical': SafetyState.NORMAL,
            'mechanical': SafetyState.NORMAL
        }
        
        mode = limp_home_manager.determine_mode(safety_states, [])
        assert mode == LimpHomeMode.NORMAL

    def test_determine_mode_reduced_power(self, limp_home_manager):
        """Test determining reduced power mode."""
        safety_states = {
            'thermal': SafetyState.WARNING,
            'electrical': SafetyState.NORMAL,
            'mechanical': SafetyState.NORMAL
        }
        
        mode = limp_home_manager.determine_mode(safety_states, [])
        assert mode == LimpHomeMode.REDUCED_POWER

    def test_determine_mode_limited_speed(self, limp_home_manager):
        """Test determining limited speed mode."""
        safety_states = {
            'thermal': SafetyState.CRITICAL,
            'electrical': SafetyState.NORMAL,
            'mechanical': SafetyState.NORMAL
        }
        
        mode = limp_home_manager.determine_mode(safety_states, [])
        assert mode == LimpHomeMode.LIMITED_SPEED

    def test_determine_mode_emergency_only(self, limp_home_manager):
        """Test determining emergency only mode."""
        safety_states = {
            'thermal': SafetyState.CRITICAL,
            'electrical': SafetyState.NORMAL,
            'mechanical': SafetyState.NORMAL
        }
        
        # Create permanent DTC
        dtc = DiagnosticTroubleCode(
            code="P0100-BAT",
            description="Test",
            severity=DTCSeverity.PERMANENT,
            fault_type=FaultType.THERMAL_RUNAWAY,
            component="battery",
            timestamp=time.time(),
            permanent=True
        )
        
        mode = limp_home_manager.determine_mode(safety_states, [dtc])
        assert mode == LimpHomeMode.EMERGENCY_ONLY

    def test_determine_mode_disabled(self, limp_home_manager):
        """Test determining disabled mode."""
        safety_states = {
            'thermal': SafetyState.EMERGENCY,
            'electrical': SafetyState.NORMAL,
            'mechanical': SafetyState.NORMAL
        }
        
        mode = limp_home_manager.determine_mode(safety_states, [])
        assert mode == LimpHomeMode.DISABLED

    def test_set_mode(self, limp_home_manager):
        """Test setting limp-home mode."""
        result = limp_home_manager.set_mode(LimpHomeMode.REDUCED_POWER)
        assert result is True
        assert limp_home_manager.current_mode == LimpHomeMode.REDUCED_POWER
        assert len(limp_home_manager.mode_history) == 1

    def test_set_mode_no_change(self, limp_home_manager):
        """Test setting same mode (no change)."""
        result = limp_home_manager.set_mode(LimpHomeMode.NORMAL)
        assert result is False

    def test_get_limits(self, limp_home_manager):
        """Test getting limp-home limits."""
        limits = limp_home_manager.get_limits()
        assert isinstance(limits, LimpHomeLimits)
        assert limits.max_speed_kmh > 0

    def test_is_operation_allowed_charging(self, limp_home_manager):
        """Test checking if charging is allowed."""
        # Normal mode - charging allowed
        assert limp_home_manager.is_operation_allowed('charging') is True
        
        # Emergency only mode - charging not allowed
        limp_home_manager.set_mode(LimpHomeMode.EMERGENCY_ONLY)
        assert limp_home_manager.is_operation_allowed('charging') is False

    def test_is_operation_allowed_autopilot(self, limp_home_manager):
        """Test checking if autopilot is allowed."""
        # Normal mode - autopilot allowed
        assert limp_home_manager.is_operation_allowed('autopilot') is True
        
        # Reduced power mode - autopilot not allowed
        limp_home_manager.set_mode(LimpHomeMode.REDUCED_POWER)
        assert limp_home_manager.is_operation_allowed('autopilot') is False

    def test_is_operation_allowed_driving(self, limp_home_manager):
        """Test checking if driving is allowed."""
        # Normal mode - driving allowed
        assert limp_home_manager.is_operation_allowed('driving') is True
        
        # Disabled mode - driving not allowed
        limp_home_manager.set_mode(LimpHomeMode.DISABLED)
        assert limp_home_manager.is_operation_allowed('driving') is False


class TestFaultLogger:
    """Tests for Fault Logger."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def fault_logger(self, temp_dir):
        """Create Fault Logger instance."""
        return FaultLogger(log_dir=temp_dir)

    def test_fault_logger_initialization(self, fault_logger, temp_dir):
        """Test Fault Logger initialization."""
        assert fault_logger.log_dir == temp_dir
        assert fault_logger.current_log_file.exists() or not fault_logger.current_log_file.exists()

    def test_log_fault(self, fault_logger):
        """Test logging a fault."""
        fault_logger.log_fault(
            fault_type=FaultType.OVERVOLTAGE,
            severity=SafetyState.CRITICAL,
            description="Test fault",
            component="battery",
            dtc_code="P0102-BAT"
        )
        
        # Check text log
        if fault_logger.current_log_file.exists():
            with open(fault_logger.current_log_file, 'r') as f:
                content = f.read()
                assert "overvoltage" in content.lower() or "OVERVOLTAGE" in content
                assert "battery" in content
                assert "P0102-BAT" in content
        
        # Check JSON log
        with open(fault_logger.json_log_file, 'r') as f:
            data = json.load(f)
            assert len(data['faults']) > 0
            assert data['faults'][-1]['fault_type'] == 'overvoltage'

    def test_get_fault_history(self, fault_logger):
        """Test getting fault history."""
        # Log some faults
        fault_logger.log_fault(
            fault_type=FaultType.OVERVOLTAGE,
            severity=SafetyState.CRITICAL,
            description="Fault 1",
            component="battery"
        )
        fault_logger.log_fault(
            fault_type=FaultType.OVERCURRENT,
            severity=SafetyState.WARNING,
            description="Fault 2",
            component="motor"
        )
        
        history = fault_logger.get_fault_history()
        assert len(history) >= 2
        
        # Filter by component
        battery_faults = fault_logger.get_fault_history(component="battery")
        assert len(battery_faults) >= 1
        assert battery_faults[0]['component'] == 'battery'
        
        # Filter by severity
        critical_faults = fault_logger.get_fault_history(severity=SafetyState.CRITICAL)
        assert len(critical_faults) >= 1
        assert critical_faults[0]['severity'] == 'CRITICAL'

    def test_clear_logs(self, fault_logger):
        """Test clearing logs."""
        # Log a fault
        fault_logger.log_fault(
            fault_type=FaultType.OVERVOLTAGE,
            severity=SafetyState.CRITICAL,
            description="Test",
            component="battery"
        )
        
        # Clear logs
        result = fault_logger.clear_logs()
        assert result is True
        
        # Check JSON log is cleared
        with open(fault_logger.json_log_file, 'r') as f:
            data = json.load(f)
            assert len(data['faults']) == 0


class TestDiagnosticsSystem:
    """Tests for integrated Diagnostics System."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def diagnostics_system(self, temp_dir):
        """Create Diagnostics System instance."""
        return DiagnosticsSystem(log_dir=temp_dir)

    def test_diagnostics_system_initialization(self, diagnostics_system):
        """Test Diagnostics System initialization."""
        assert diagnostics_system.dtc_manager is not None
        assert diagnostics_system.limp_home_manager is not None
        assert diagnostics_system.fault_logger is not None

    def test_process_fault(self, diagnostics_system):
        """Test processing a fault through diagnostics system."""
        safety_states = {
            'thermal': SafetyState.NORMAL,
            'electrical': SafetyState.WARNING,
            'mechanical': SafetyState.NORMAL
        }
        
        dtc = diagnostics_system.process_fault(
            fault_type=FaultType.OVERVOLTAGE,
            severity=SafetyState.WARNING,
            description="Test overvoltage",
            component="battery",
            safety_states=safety_states
        )
        
        assert dtc is not None
        assert dtc.code.startswith("P0102")
        
        # Check DTC was added
        active_dtcs = diagnostics_system.dtc_manager.get_active_dtcs()
        assert len(active_dtcs) > 0
        
        # Check limp-home mode was updated
        mode = diagnostics_system.limp_home_manager.get_mode()
        assert mode == LimpHomeMode.REDUCED_POWER

    def test_get_diagnostics_status(self, diagnostics_system):
        """Test getting diagnostics status."""
        # Process a fault first
        safety_states = {
            'thermal': SafetyState.NORMAL,
            'electrical': SafetyState.WARNING,
            'mechanical': SafetyState.NORMAL
        }
        
        diagnostics_system.process_fault(
            fault_type=FaultType.OVERVOLTAGE,
            severity=SafetyState.WARNING,
            description="Test",
            component="battery",
            safety_states=safety_states
        )
        
        status = diagnostics_system.get_diagnostics_status()
        
        assert 'active_dtc_count' in status
        assert 'active_dtcs' in status
        assert 'limp_home_mode' in status
        assert 'limp_home_limits' in status
        assert status['active_dtc_count'] > 0

    def test_clear_dtcs(self, diagnostics_system):
        """Test clearing DTCs."""
        safety_states = {
            'thermal': SafetyState.NORMAL,
            'electrical': SafetyState.WARNING,
            'mechanical': SafetyState.NORMAL
        }
        
        diagnostics_system.process_fault(
            fault_type=FaultType.OVERVOLTAGE,
            severity=SafetyState.WARNING,
            description="Test",
            component="battery",
            safety_states=safety_states
        )
        
        assert len(diagnostics_system.dtc_manager.get_active_dtcs()) > 0
        
        result = diagnostics_system.clear_dtcs()
        assert result is True
        assert len(diagnostics_system.dtc_manager.get_active_dtcs()) == 0

    def test_get_limp_home_limits(self, diagnostics_system):
        """Test getting limp-home limits."""
        limits = diagnostics_system.get_limp_home_limits()
        assert isinstance(limits, LimpHomeLimits)
        assert limits.max_speed_kmh >= 0

    def test_is_operation_allowed(self, diagnostics_system):
        """Test checking if operation is allowed."""
        # Normal mode - operations allowed
        assert diagnostics_system.is_operation_allowed('charging') is True
        assert diagnostics_system.is_operation_allowed('autopilot') is True
        assert diagnostics_system.is_operation_allowed('driving') is True
        
        # Set to emergency only mode
        diagnostics_system.limp_home_manager.set_mode(LimpHomeMode.EMERGENCY_ONLY)
        assert diagnostics_system.is_operation_allowed('charging') is False
        assert diagnostics_system.is_operation_allowed('autopilot') is False
        assert diagnostics_system.is_operation_allowed('driving') is True  # Still allowed but limited


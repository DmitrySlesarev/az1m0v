"""Diagnostics module for OBD-II style fault detection and diagnostics.
Provides DTC (Diagnostic Trouble Code) system, limp-home modes, and fault logging.
"""

import logging
import time
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime
from collections import deque

from core.safety_system import SafetyState, FaultType


class DTCSeverity(Enum):
    """DTC severity levels (similar to OBD-II)."""
    PENDING = "P"  # Pending - fault detected but not confirmed
    CONFIRMED = "C"  # Confirmed - fault confirmed
    PERMANENT = "U"  # Permanent - fault stored in non-volatile memory


class LimpHomeMode(Enum):
    """Limp-home mode levels."""
    NORMAL = "normal"  # Full operation
    REDUCED_POWER = "reduced_power"  # Reduced power output (50%)
    LIMITED_SPEED = "limited_speed"  # Limited speed (30 km/h max)
    EMERGENCY_ONLY = "emergency_only"  # Emergency operation only (10 km/h max)
    DISABLED = "disabled"  # Vehicle disabled


@dataclass
class DiagnosticTroubleCode:
    """Diagnostic Trouble Code (DTC) - OBD-II style."""
    code: str  # Format: P#### (e.g., P0100, P0201)
    description: str
    severity: DTCSeverity
    fault_type: FaultType
    component: str
    timestamp: float
    confirmed: bool = False
    permanent: bool = False
    freeze_frame_data: Optional[Dict[str, Any]] = None  # Snapshot of conditions when DTC was set
    occurrence_count: int = 1
    first_occurrence: float = field(default_factory=time.time)
    last_occurrence: float = field(default_factory=time.time)
    cleared: bool = False
    cleared_timestamp: Optional[float] = None


@dataclass
class LimpHomeLimits:
    """Limits applied in limp-home mode."""
    max_speed_kmh: float
    max_power_kw: float
    max_acceleration_ms2: float
    max_current_a: float
    charging_allowed: bool
    autopilot_allowed: bool


class DTCManager:
    """Manages Diagnostic Trouble Codes (DTCs) - OBD-II style."""
    
    # DTC Code mapping: FaultType -> DTC code prefix and description
    DTC_MAPPING: Dict[FaultType, Tuple[str, str]] = {
        # P0xxx - Powertrain codes
        FaultType.THERMAL_RUNAWAY: ("P0100", "Battery Thermal Runaway Detected"),
        FaultType.OVERHEATING: ("P0101", "System Overheating"),
        FaultType.OVERVOLTAGE: ("P0102", "Battery Overvoltage"),
        FaultType.UNDERVOLTAGE: ("P0103", "Battery Undervoltage"),
        FaultType.OVERCURRENT: ("P0104", "Battery Overcurrent"),
        FaultType.BATTERY_FAULT: ("P0105", "Battery Management System Fault"),
        FaultType.MOTOR_FAULT: ("P0200", "Motor Controller Fault"),
        FaultType.CHARGING_FAULT: ("P0300", "Charging System Fault"),
        FaultType.COMMUNICATION_LOSS: ("P0400", "Communication Bus Fault"),
        FaultType.MECHANICAL_FAILURE: ("P0500", "Mechanical System Fault"),
        FaultType.UNKNOWN: ("P0999", "Unknown System Fault"),
    }
    
    def __init__(self, log_dir: Optional[Path] = None):
        """
        Initialize DTC Manager.
        
        Args:
            log_dir: Directory for storing DTC logs (default: ./logs)
        """
        self.logger = logging.getLogger(__name__)
        self.log_dir = log_dir or Path("./logs")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Active DTCs (not cleared)
        self.active_dtcs: Dict[str, DiagnosticTroubleCode] = {}
        
        # DTC history (all DTCs including cleared ones)
        self.dtc_history: List[DiagnosticTroubleCode] = []
        
        # Maximum history size
        self.max_history_size = 1000
        
        self.logger.info("DTC Manager initialized")
    
    def generate_dtc(self, fault_type: FaultType, component: str, 
                     severity: SafetyState, freeze_frame: Optional[Dict[str, Any]] = None) -> DiagnosticTroubleCode:
        """
        Generate a DTC from a fault.
        
        Args:
            fault_type: Type of fault
            component: Component where fault occurred
            severity: Safety state severity
            freeze_frame: Optional snapshot of system conditions
            
        Returns:
            DiagnosticTroubleCode object
        """
        code_prefix, description = self.DTC_MAPPING.get(
            fault_type, 
            ("P0999", "Unknown Fault")
        )
        
        # Add component-specific suffix (e.g., P0100-BAT for battery, P0100-MOT for motor)
        component_suffix = component.upper()[:3]
        dtc_code = f"{code_prefix}-{component_suffix}"
        
        # Determine DTC severity based on safety state
        if severity == SafetyState.EMERGENCY:
            dtc_severity = DTCSeverity.PERMANENT
            permanent = True
            confirmed = True
        elif severity == SafetyState.CRITICAL:
            dtc_severity = DTCSeverity.CONFIRMED
            permanent = False
            confirmed = True
        else:
            dtc_severity = DTCSeverity.PENDING
            permanent = False
            confirmed = False
        
        current_time = time.time()
        
        # Check if DTC already exists
        if dtc_code in self.active_dtcs:
            existing_dtc = self.active_dtcs[dtc_code]
            existing_dtc.occurrence_count += 1
            existing_dtc.last_occurrence = current_time
            if not existing_dtc.confirmed and confirmed:
                existing_dtc.confirmed = True
                existing_dtc.severity = DTCSeverity.CONFIRMED
            if not existing_dtc.permanent and permanent:
                existing_dtc.permanent = True
                existing_dtc.severity = DTCSeverity.PERMANENT
            if freeze_frame:
                existing_dtc.freeze_frame_data = freeze_frame
            return existing_dtc
        
        # Create new DTC
        dtc = DiagnosticTroubleCode(
            code=dtc_code,
            description=description,
            severity=dtc_severity,
            fault_type=fault_type,
            component=component,
            timestamp=current_time,
            confirmed=confirmed,
            permanent=permanent,
            freeze_frame_data=freeze_frame,
            first_occurrence=current_time,
            last_occurrence=current_time
        )
        
        self.active_dtcs[dtc_code] = dtc
        self.dtc_history.append(dtc)
        
        # Limit history size
        if len(self.dtc_history) > self.max_history_size:
            self.dtc_history = self.dtc_history[-self.max_history_size:]
        
        self.logger.warning(f"DTC set: {dtc_code} - {description} ({component})")
        
        return dtc
    
    def clear_dtc(self, dtc_code: Optional[str] = None) -> bool:
        """
        Clear a DTC or all DTCs.
        
        Args:
            dtc_code: Specific DTC code to clear, or None to clear all
            
        Returns:
            True if cleared successfully, False otherwise
        """
        if dtc_code:
            if dtc_code in self.active_dtcs:
                dtc = self.active_dtcs[dtc_code]
                # Cannot clear permanent DTCs
                if dtc.permanent:
                    self.logger.warning(f"Cannot clear permanent DTC: {dtc_code}")
                    return False
                dtc.cleared = True
                dtc.cleared_timestamp = time.time()
                del self.active_dtcs[dtc_code]
                self.logger.info(f"DTC cleared: {dtc_code}")
                return True
            return False
        else:
            # Clear all non-permanent DTCs
            cleared_count = 0
            permanent_dtcs = []
            for code, dtc in list(self.active_dtcs.items()):
                if dtc.permanent:
                    permanent_dtcs.append(code)
                else:
                    dtc.cleared = True
                    dtc.cleared_timestamp = time.time()
                    del self.active_dtcs[code]
                    cleared_count += 1
            
            if permanent_dtcs:
                self.logger.warning(f"Cannot clear permanent DTCs: {', '.join(permanent_dtcs)}")
            
            self.logger.info(f"Cleared {cleared_count} DTC(s)")
            return cleared_count > 0
    
    def get_active_dtcs(self) -> List[DiagnosticTroubleCode]:
        """Get all active (not cleared) DTCs."""
        return list(self.active_dtcs.values())
    
    def get_dtc_by_code(self, dtc_code: str) -> Optional[DiagnosticTroubleCode]:
        """Get DTC by code."""
        return self.active_dtcs.get(dtc_code)
    
    def get_dtcs_by_component(self, component: str) -> List[DiagnosticTroubleCode]:
        """Get all DTCs for a specific component."""
        return [dtc for dtc in self.active_dtcs.values() if dtc.component == component]
    
    def get_dtc_history(self, limit: Optional[int] = None) -> List[DiagnosticTroubleCode]:
        """
        Get DTC history.
        
        Args:
            limit: Maximum number of DTCs to return (None = all)
            
        Returns:
            List of DiagnosticTroubleCode objects
        """
        history = self.dtc_history
        if limit:
            history = history[-limit:]
        return history
    
    def export_dtcs(self, filepath: Optional[Path] = None) -> Path:
        """
        Export DTCs to JSON file.
        
        Args:
            filepath: Path to export file (default: logs/dtcs_<timestamp>.json)
            
        Returns:
            Path to exported file
        """
        if not filepath:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = self.log_dir / f"dtcs_{timestamp}.json"
        
        export_data = {
            'export_timestamp': time.time(),
            'active_dtcs': [asdict(dtc) for dtc in self.active_dtcs.values()],
            'history': [asdict(dtc) for dtc in self.dtc_history[-100:]]  # Last 100
        }
        
        with open(filepath, 'w') as f:
            json.dump(export_data, f, indent=2, default=str)
        
        self.logger.info(f"DTCs exported to {filepath}")
        return filepath


class LimpHomeManager:
    """Manages limp-home modes for degraded operation."""
    
    # Limp-home mode configurations
    LIMP_HOME_CONFIGS: Dict[LimpHomeMode, LimpHomeLimits] = {
        LimpHomeMode.NORMAL: LimpHomeLimits(
            max_speed_kmh=120.0,
            max_power_kw=150.0,
            max_acceleration_ms2=3.0,
            max_current_a=500.0,
            charging_allowed=True,
            autopilot_allowed=True
        ),
        LimpHomeMode.REDUCED_POWER: LimpHomeLimits(
            max_speed_kmh=80.0,
            max_power_kw=75.0,  # 50% of normal
            max_acceleration_ms2=1.5,  # 50% of normal
            max_current_a=250.0,  # 50% of normal
            charging_allowed=True,
            autopilot_allowed=False
        ),
        LimpHomeMode.LIMITED_SPEED: LimpHomeLimits(
            max_speed_kmh=30.0,
            max_power_kw=30.0,  # 20% of normal
            max_acceleration_ms2=0.6,  # 20% of normal
            max_current_a=100.0,  # 20% of normal
            charging_allowed=True,
            autopilot_allowed=False
        ),
        LimpHomeMode.EMERGENCY_ONLY: LimpHomeLimits(
            max_speed_kmh=10.0,
            max_power_kw=10.0,  # Minimal power
            max_acceleration_ms2=0.3,  # Minimal acceleration
            max_current_a=50.0,  # Minimal current
            charging_allowed=False,
            autopilot_allowed=False
        ),
        LimpHomeMode.DISABLED: LimpHomeLimits(
            max_speed_kmh=0.0,
            max_power_kw=0.0,
            max_acceleration_ms2=0.0,
            max_current_a=0.0,
            charging_allowed=False,
            autopilot_allowed=False
        ),
    }
    
    def __init__(self):
        """Initialize Limp-Home Manager."""
        self.logger = logging.getLogger(__name__)
        self.current_mode = LimpHomeMode.NORMAL
        self.mode_history: deque = deque(maxlen=100)  # Track mode changes
        
        self.logger.info("Limp-Home Manager initialized")
    
    def determine_mode(self, safety_states: Dict[str, SafetyState], 
                      active_dtcs: List[DiagnosticTroubleCode]) -> LimpHomeMode:
        """
        Determine appropriate limp-home mode based on safety states and DTCs.
        
        Args:
            safety_states: Dictionary of safety states (thermal, electrical, mechanical)
            active_dtcs: List of active DTCs
            
        Returns:
            LimpHomeMode enum value
        """
        # Check for emergency conditions
        if any(state == SafetyState.EMERGENCY for state in safety_states.values()):
            return LimpHomeMode.DISABLED
        
        # Check for critical conditions
        if any(state == SafetyState.CRITICAL for state in safety_states.values()):
            # Check for permanent DTCs
            permanent_dtcs = [dtc for dtc in active_dtcs if dtc.permanent]
            if permanent_dtcs:
                return LimpHomeMode.EMERGENCY_ONLY
            return LimpHomeMode.LIMITED_SPEED
        
        # Check for confirmed DTCs
        confirmed_dtcs = [dtc for dtc in active_dtcs if dtc.confirmed]
        if confirmed_dtcs:
            # Multiple confirmed DTCs -> more restrictive
            if len(confirmed_dtcs) >= 2:
                return LimpHomeMode.LIMITED_SPEED
            return LimpHomeMode.REDUCED_POWER
        
        # Check for warnings
        if any(state == SafetyState.WARNING for state in safety_states.values()):
            return LimpHomeMode.REDUCED_POWER
        
        # Normal operation
        return LimpHomeMode.NORMAL
    
    def set_mode(self, mode: LimpHomeMode) -> bool:
        """
        Set limp-home mode.
        
        Args:
            mode: LimpHomeMode to set
            
        Returns:
            True if mode changed, False otherwise
        """
        if mode == self.current_mode:
            return False
        
        old_mode = self.current_mode
        self.current_mode = mode
        
        # Record mode change
        self.mode_history.append({
            'mode': mode.value,
            'timestamp': time.time(),
            'previous_mode': old_mode.value
        })
        
        self.logger.warning(f"Limp-home mode changed: {old_mode.value} -> {mode.value}")
        return True
    
    def get_limits(self) -> LimpHomeLimits:
        """Get current limp-home mode limits."""
        return self.LIMP_HOME_CONFIGS[self.current_mode]
    
    def get_mode(self) -> LimpHomeMode:
        """Get current limp-home mode."""
        return self.current_mode
    
    def is_operation_allowed(self, operation: str) -> bool:
        """
        Check if an operation is allowed in current limp-home mode.
        
        Args:
            operation: Operation to check ('charging', 'autopilot', 'driving')
            
        Returns:
            True if allowed, False otherwise
        """
        limits = self.get_limits()
        
        if operation == 'charging':
            return limits.charging_allowed
        elif operation == 'autopilot':
            return limits.autopilot_allowed
        elif operation == 'driving':
            return self.current_mode != LimpHomeMode.DISABLED
        
        return False


class FaultLogger:
    """Persistent fault logging with timestamps."""
    
    def __init__(self, log_dir: Optional[Path] = None, max_file_size_mb: float = 10.0):
        """
        Initialize Fault Logger.
        
        Args:
            log_dir: Directory for fault logs (default: ./logs)
            max_file_size_mb: Maximum log file size before rotation (MB)
        """
        self.logger = logging.getLogger(__name__)
        self.log_dir = log_dir or Path("./logs")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024
        
        # Current log file
        self.current_log_file = self.log_dir / "faults.log"
        
        # JSON log file for structured data
        self.json_log_file = self.log_dir / "faults.json"
        
        # Initialize JSON log if it doesn't exist
        if not self.json_log_file.exists():
            with open(self.json_log_file, 'w') as f:
                json.dump({'faults': []}, f)
        
        self.logger.info(f"Fault Logger initialized (log_dir={self.log_dir})")
    
    def log_fault(self, fault_type: FaultType, severity: SafetyState, 
                  description: str, component: str, dtc_code: Optional[str] = None,
                  freeze_frame: Optional[Dict[str, Any]] = None) -> None:
        """
        Log a fault with timestamp.
        
        Args:
            fault_type: Type of fault
            severity: Safety state severity
            description: Fault description
            component: Component where fault occurred
            dtc_code: Optional DTC code
            freeze_frame: Optional snapshot of system conditions
        """
        timestamp = time.time()
        dt_str = datetime.fromtimestamp(timestamp).isoformat()
        
        # Text log entry
        log_entry = (
            f"[{dt_str}] "
            f"SEVERITY={severity.value} "
            f"TYPE={fault_type.value} "
            f"COMPONENT={component} "
            f"DTC={dtc_code or 'N/A'} "
            f"DESC={description}"
        )
        
        # Write to text log
        self._write_text_log(log_entry)
        
        # Structured JSON log entry
        json_entry = {
            'timestamp': timestamp,
            'datetime': dt_str,
            'fault_type': fault_type.value,
            'severity': severity.value,
            'component': component,
            'description': description,
            'dtc_code': dtc_code,
            'freeze_frame': freeze_frame
        }
        
        # Write to JSON log
        self._write_json_log(json_entry)
        
        self.logger.warning(f"Fault logged: {fault_type.value} - {description} ({component})")
    
    def _write_text_log(self, entry: str) -> None:
        """Write entry to text log file with rotation."""
        try:
            # Check file size and rotate if needed
            if self.current_log_file.exists():
                if self.current_log_file.stat().st_size > self.max_file_size_bytes:
                    self._rotate_log_file()
            
            with open(self.current_log_file, 'a') as f:
                f.write(entry + '\n')
        except Exception as e:
            self.logger.error(f"Error writing to fault log: {e}")
    
    def _write_json_log(self, entry: Dict[str, Any]) -> None:
        """Write entry to JSON log file."""
        try:
            # Read existing log
            if self.json_log_file.exists():
                with open(self.json_log_file, 'r') as f:
                    data = json.load(f)
            else:
                data = {'faults': []}
            
            # Append new entry
            data['faults'].append(entry)
            
            # Keep only last 10000 entries
            if len(data['faults']) > 10000:
                data['faults'] = data['faults'][-10000:]
            
            # Write back
            with open(self.json_log_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            self.logger.error(f"Error writing to JSON fault log: {e}")
    
    def _rotate_log_file(self) -> None:
        """Rotate log file when it gets too large."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            rotated_file = self.log_dir / f"faults_{timestamp}.log"
            self.current_log_file.rename(rotated_file)
            self.logger.info(f"Fault log rotated: {rotated_file}")
        except Exception as e:
            self.logger.error(f"Error rotating log file: {e}")
    
    def get_fault_history(self, limit: Optional[int] = None, 
                          component: Optional[str] = None,
                          severity: Optional[SafetyState] = None) -> List[Dict[str, Any]]:
        """
        Get fault history from JSON log.
        
        Args:
            limit: Maximum number of faults to return
            component: Filter by component
            severity: Filter by severity
            
        Returns:
            List of fault dictionaries
        """
        try:
            if not self.json_log_file.exists():
                return []
            
            with open(self.json_log_file, 'r') as f:
                data = json.load(f)
            
            faults = data.get('faults', [])
            
            # Apply filters
            if component:
                faults = [f for f in faults if f.get('component') == component]
            if severity:
                faults = [f for f in faults if f.get('severity') == severity.value]
            
            # Sort by timestamp (newest first)
            faults.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
            
            # Apply limit
            if limit:
                faults = faults[:limit]
            
            return faults
        except Exception as e:
            self.logger.error(f"Error reading fault history: {e}")
            return []
    
    def clear_logs(self) -> bool:
        """
        Clear all fault logs.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if self.current_log_file.exists():
                self.current_log_file.unlink()
            
            if self.json_log_file.exists():
                with open(self.json_log_file, 'w') as f:
                    json.dump({'faults': []}, f)
            
            self.logger.info("Fault logs cleared")
            return True
        except Exception as e:
            self.logger.error(f"Error clearing logs: {e}")
            return False


class DiagnosticsSystem:
    """
    Integrated diagnostics system combining DTC management, limp-home modes, and fault logging.
    """
    
    def __init__(self, log_dir: Optional[Path] = None):
        """
        Initialize Diagnostics System.
        
        Args:
            log_dir: Directory for storing diagnostic logs
        """
        self.logger = logging.getLogger(__name__)
        self.log_dir = log_dir or Path("./logs")
        
        # Initialize subsystems
        self.dtc_manager = DTCManager(log_dir=self.log_dir)
        self.limp_home_manager = LimpHomeManager()
        self.fault_logger = FaultLogger(log_dir=self.log_dir)
        
        self.logger.info("Diagnostics System initialized")
    
    def process_fault(self, fault_type: FaultType, severity: SafetyState,
                     description: str, component: str, 
                     safety_states: Dict[str, SafetyState],
                     freeze_frame: Optional[Dict[str, Any]] = None) -> DiagnosticTroubleCode:
        """
        Process a fault through the diagnostics system.
        
        Args:
            fault_type: Type of fault
            severity: Safety state severity
            description: Fault description
            component: Component where fault occurred
            safety_states: Current safety states
            freeze_frame: Optional snapshot of system conditions
            
        Returns:
            DiagnosticTroubleCode object
        """
        # Generate DTC
        dtc = self.dtc_manager.generate_dtc(
            fault_type=fault_type,
            component=component,
            severity=severity,
            freeze_frame=freeze_frame
        )
        
        # Log fault
        self.fault_logger.log_fault(
            fault_type=fault_type,
            severity=severity,
            description=description,
            component=component,
            dtc_code=dtc.code,
            freeze_frame=freeze_frame
        )
        
        # Update limp-home mode
        active_dtcs = self.dtc_manager.get_active_dtcs()
        new_mode = self.limp_home_manager.determine_mode(safety_states, active_dtcs)
        self.limp_home_manager.set_mode(new_mode)
        
        return dtc
    
    def get_diagnostics_status(self) -> Dict[str, Any]:
        """
        Get comprehensive diagnostics status.
        
        Returns:
            Dictionary with diagnostics information
        """
        active_dtcs = self.dtc_manager.get_active_dtcs()
        limp_home_limits = self.limp_home_manager.get_limits()
        
        return {
            'active_dtc_count': len(active_dtcs),
            'active_dtcs': [asdict(dtc) for dtc in active_dtcs],
            'limp_home_mode': self.limp_home_manager.get_mode().value,
            'limp_home_limits': {
                'max_speed_kmh': limp_home_limits.max_speed_kmh,
                'max_power_kw': limp_home_limits.max_power_kw,
                'max_acceleration_ms2': limp_home_limits.max_acceleration_ms2,
                'max_current_a': limp_home_limits.max_current_a,
                'charging_allowed': limp_home_limits.charging_allowed,
                'autopilot_allowed': limp_home_limits.autopilot_allowed
            },
            'log_directory': str(self.log_dir)
        }
    
    def clear_dtcs(self, dtc_code: Optional[str] = None) -> bool:
        """Clear DTC(s)."""
        return self.dtc_manager.clear_dtc(dtc_code)
    
    def get_limp_home_limits(self) -> LimpHomeLimits:
        """Get current limp-home mode limits."""
        return self.limp_home_manager.get_limits()
    
    def is_operation_allowed(self, operation: str) -> bool:
        """Check if operation is allowed in current limp-home mode."""
        return self.limp_home_manager.is_operation_allowed(operation)


"""Safety System module for the EV project.
Monitors system health, detects faults, and manages emergency shutdowns.
"""

import logging
import time
from typing import Dict, List, Optional, Any, Callable, TYPE_CHECKING
from dataclasses import dataclass, field
from enum import Enum
from collections import deque

if TYPE_CHECKING:
    from core.diagnostics import DiagnosticsSystem


class SafetyState(Enum):
    """Safety state levels."""
    NORMAL = "NORMAL"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    EMERGENCY = "EMERGENCY"


class FaultType(Enum):
    """Types of system faults."""
    THERMAL_RUNAWAY = "thermal_runaway"
    OVERHEATING = "overheating"
    OVERVOLTAGE = "overvoltage"
    UNDERVOLTAGE = "undervoltage"
    OVERCURRENT = "overcurrent"
    MECHANICAL_FAILURE = "mechanical_failure"
    COMMUNICATION_LOSS = "communication_loss"
    BATTERY_FAULT = "battery_fault"
    MOTOR_FAULT = "motor_fault"
    CHARGING_FAULT = "charging_fault"
    UNKNOWN = "unknown"


@dataclass
class Fault:
    """Represents a system fault."""
    fault_type: FaultType
    severity: SafetyState
    description: str
    timestamp: float
    component: str = "unknown"
    resolved: bool = False
    resolution_time: Optional[float] = None


@dataclass
class ThermalHistory:
    """Tracks temperature history for thermal runaway detection."""
    temperatures: deque = field(default_factory=lambda: deque(maxlen=60))  # Last 60 readings (1 minute at 1Hz)
    timestamps: deque = field(default_factory=lambda: deque(maxlen=60))
    max_rate_c_per_s: float = 0.0  # Maximum rate of temperature rise detected


class SafetySystem:
    """
    Safety System for monitoring and protecting EV components.
    Detects thermal runaway, manages emergency shutdowns, and tracks system faults.
    """

    def __init__(
        self,
        battery_management: Optional[Any] = None,
        motor_controller: Optional[Any] = None,
        charging_system: Optional[Any] = None,
        vehicle_controller: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the Safety System.
        
        Args:
            battery_management: Optional BatteryManagementSystem instance
            motor_controller: Optional VESCManager instance
            charging_system: Optional ChargingSystem instance
            vehicle_controller: Optional VehicleController instance
            config: Optional configuration dictionary with safety thresholds
        """
        self.battery_management = battery_management
        self.motor_controller = motor_controller
        self.charging_system = charging_system
        self.vehicle_controller = vehicle_controller
        
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        # Initialize faults list
        self.faults: List[Fault] = []
        
        # Initialize safety states
        self.safety_states = {
            'thermal': SafetyState.NORMAL,
            'electrical': SafetyState.NORMAL,
            'mechanical': SafetyState.NORMAL
        }
        
        # Configuration thresholds
        self.battery_temp_max = self.config.get('battery_temp_max', 60.0)  # °C
        self.battery_temp_warning = self.config.get('battery_temp_warning', 50.0)  # °C
        self.motor_temp_max = self.config.get('motor_temp_max', 100.0)  # °C
        self.motor_temp_warning = self.config.get('motor_temp_warning', 80.0)  # °C
        self.thermal_runaway_rate = self.config.get('thermal_runaway_rate', 2.0)  # °C per second
        self.thermal_runaway_threshold = self.config.get('thermal_runaway_threshold', 5.0)  # °C rise in 10 seconds
        self.voltage_max = self.config.get('voltage_max', 500.0)  # V
        self.voltage_min = self.config.get('voltage_min', 300.0)  # V
        self.current_max = self.config.get('current_max', 500.0)  # A
        
        # Thermal history tracking
        self.battery_thermal_history = ThermalHistory()
        self.motor_thermal_history = ThermalHistory()
        
        # Emergency shutdown state
        self.emergency_shutdown_active = False
        self.emergency_shutdown_reason: Optional[str] = None
        self.emergency_shutdown_time: Optional[float] = None
        
        # Shutdown callback (can be set externally)
        self.shutdown_callback: Optional[Callable[[str], None]] = None
        
        # Initialize diagnostics system (lazy import to avoid circular dependency)
        self._diagnostics_log_dir = self.config.get('diagnostics_log_dir', None)
        self._diagnostics = None
        
        self.logger.info("Safety System initialized")

    def check_thermal_runaway(self, battery_temp: float, motor_temp: float) -> bool:
        """
        Check for thermal runaway conditions in battery and motor.
        
        Thermal runaway is detected when:
        1. Temperature rises rapidly (exceeds rate threshold)
        2. Temperature exceeds critical threshold
        3. Temperature continues rising despite cooling
        
        Args:
            battery_temp: Current battery temperature in °C
            motor_temp: Current motor temperature in °C
            
        Returns:
            True if thermal runaway is detected, False otherwise
        """
        current_time = time.time()
        thermal_runaway_detected = False
        
        # Check battery thermal runaway
        if battery_temp is not None:
            self.battery_thermal_history.temperatures.append(battery_temp)
            self.battery_thermal_history.timestamps.append(current_time)
            
            if len(self.battery_thermal_history.temperatures) >= 10:
                # Calculate temperature rise rate over last 10 seconds
                recent_temps = list(self.battery_thermal_history.temperatures)[-10:]
                recent_times = list(self.battery_thermal_history.timestamps)[-10:]
                
                temp_rise = recent_temps[-1] - recent_temps[0]
                time_span = recent_times[-1] - recent_times[0]
                
                if time_span > 0:
                    rate_c_per_s = temp_rise / time_span
                    self.battery_thermal_history.max_rate_c_per_s = max(
                        self.battery_thermal_history.max_rate_c_per_s,
                        rate_c_per_s
                    )
                    
                    # Check for thermal runaway conditions
                    if (rate_c_per_s > self.thermal_runaway_rate and 
                        temp_rise > self.thermal_runaway_threshold):
                        thermal_runaway_detected = True
                        self._add_fault(
                            FaultType.THERMAL_RUNAWAY,
                            SafetyState.EMERGENCY,
                            f"Battery thermal runaway detected: {rate_c_per_s:.2f}°C/s, "
                            f"temperature {battery_temp:.1f}°C",
                            "battery"
                        )
                        self.safety_states['thermal'] = SafetyState.EMERGENCY
                        self.logger.critical(
                            f"BATTERY THERMAL RUNAWAY: Rate={rate_c_per_s:.2f}°C/s, "
                            f"Temp={battery_temp:.1f}°C"
                        )
                    
                    # Check for critical temperature
                    if battery_temp > self.battery_temp_max:
                        thermal_runaway_detected = True
                        self._add_fault(
                            FaultType.OVERHEATING,
                            SafetyState.CRITICAL,
                            f"Battery temperature critical: {battery_temp:.1f}°C (max: {self.battery_temp_max}°C)",
                            "battery"
                        )
                        self.safety_states['thermal'] = SafetyState.CRITICAL
                        self.logger.critical(f"Battery temperature critical: {battery_temp:.1f}°C")
                    
                    # Check for warning temperature
                    elif battery_temp > self.battery_temp_warning:
                        if self.safety_states['thermal'] == SafetyState.NORMAL:
                            self.safety_states['thermal'] = SafetyState.WARNING
                            self.logger.warning(f"Battery temperature warning: {battery_temp:.1f}°C")
        
        # Check motor thermal runaway
        if motor_temp is not None:
            self.motor_thermal_history.temperatures.append(motor_temp)
            self.motor_thermal_history.timestamps.append(current_time)
            
            if len(self.motor_thermal_history.temperatures) >= 10:
                # Calculate temperature rise rate over last 10 seconds
                recent_temps = list(self.motor_thermal_history.temperatures)[-10:]
                recent_times = list(self.motor_thermal_history.timestamps)[-10:]
                
                temp_rise = recent_temps[-1] - recent_temps[0]
                time_span = recent_times[-1] - recent_times[0]
                
                if time_span > 0:
                    rate_c_per_s = temp_rise / time_span
                    self.motor_thermal_history.max_rate_c_per_s = max(
                        self.motor_thermal_history.max_rate_c_per_s,
                        rate_c_per_s
                    )
                    
                    # Check for thermal runaway conditions
                    if (rate_c_per_s > self.thermal_runaway_rate and 
                        temp_rise > self.thermal_runaway_threshold):
                        thermal_runaway_detected = True
                        self._add_fault(
                            FaultType.THERMAL_RUNAWAY,
                            SafetyState.EMERGENCY,
                            f"Motor thermal runaway detected: {rate_c_per_s:.2f}°C/s, "
                            f"temperature {motor_temp:.1f}°C",
                            "motor"
                        )
                        self.safety_states['thermal'] = SafetyState.EMERGENCY
                        self.logger.critical(
                            f"MOTOR THERMAL RUNAWAY: Rate={rate_c_per_s:.2f}°C/s, "
                            f"Temp={motor_temp:.1f}°C"
                        )
                    
                    # Check for critical temperature
                    if motor_temp > self.motor_temp_max:
                        thermal_runaway_detected = True
                        self._add_fault(
                            FaultType.OVERHEATING,
                            SafetyState.CRITICAL,
                            f"Motor temperature critical: {motor_temp:.1f}°C (max: {self.motor_temp_max}°C)",
                            "motor"
                        )
                        self.safety_states['thermal'] = SafetyState.CRITICAL
                        self.logger.critical(f"Motor temperature critical: {motor_temp:.1f}°C")
                    
                    # Check for warning temperature
                    elif motor_temp > self.motor_temp_warning:
                        if self.safety_states['thermal'] == SafetyState.NORMAL:
                            self.safety_states['thermal'] = SafetyState.WARNING
                            self.logger.warning(f"Motor temperature warning: {motor_temp:.1f}°C")
        
        return thermal_runaway_detected

    def check_electrical_safety(self) -> bool:
        """
        Check electrical system safety (voltage, current).
        
        Returns:
            True if electrical fault detected, False otherwise
        """
        fault_detected = False
        
        # Check battery electrical parameters
        if self.battery_management:
            try:
                bms_state = self.battery_management.get_state()
                if bms_state:
                    # Check overvoltage
                    if bms_state.voltage > self.voltage_max:
                        fault_detected = True
                        self.safety_states['electrical'] = SafetyState.CRITICAL
                        self._add_fault(
                            FaultType.OVERVOLTAGE,
                            SafetyState.CRITICAL,
                            f"Battery overvoltage: {bms_state.voltage:.1f}V (max: {self.voltage_max}V)",
                            "battery"
                        )
                        self.logger.critical(f"Battery overvoltage: {bms_state.voltage:.1f}V")
                    
                    # Check undervoltage
                    elif bms_state.voltage < self.voltage_min:
                        fault_detected = True
                        self._add_fault(
                            FaultType.UNDERVOLTAGE,
                            SafetyState.WARNING,
                            f"Battery undervoltage: {bms_state.voltage:.1f}V (min: {self.voltage_min}V)",
                            "battery"
                        )
                        if self.safety_states['electrical'] == SafetyState.NORMAL:
                            self.safety_states['electrical'] = SafetyState.WARNING
                        self.logger.warning(f"Battery undervoltage: {bms_state.voltage:.1f}V")
                    
                    # Check overcurrent
                    if abs(bms_state.current) > self.current_max:
                        fault_detected = True
                        self.safety_states['electrical'] = SafetyState.CRITICAL
                        self._add_fault(
                            FaultType.OVERCURRENT,
                            SafetyState.CRITICAL,
                            f"Battery overcurrent: {bms_state.current:.1f}A (max: {self.current_max}A)",
                            "battery"
                        )
                        self.logger.critical(f"Battery overcurrent: {abs(bms_state.current):.1f}A")
                    
                    # Check battery status
                    if bms_state.status.value == 'fault':
                        fault_detected = True
                        self.safety_states['electrical'] = SafetyState.CRITICAL
                        self._add_fault(
                            FaultType.BATTERY_FAULT,
                            SafetyState.CRITICAL,
                            "Battery management system reported fault",
                            "battery"
                        )
            except Exception as e:
                self.logger.error(f"Error checking battery electrical safety: {e}")
        
        # Check motor electrical parameters
        if self.motor_controller:
            try:
                motor_status = self.motor_controller.get_status()
                if motor_status:
                    # Check motor voltage
                    if motor_status.voltage_v > self.voltage_max:
                        fault_detected = True
                        self.safety_states['electrical'] = SafetyState.CRITICAL
                        self._add_fault(
                            FaultType.OVERVOLTAGE,
                            SafetyState.CRITICAL,
                            f"Motor overvoltage: {motor_status.voltage_v:.1f}V (max: {self.voltage_max}V)",
                            "motor"
                        )
                    
                    # Check motor current
                    if abs(motor_status.current_a) > self.current_max:
                        fault_detected = True
                        self.safety_states['electrical'] = SafetyState.CRITICAL
                        self._add_fault(
                            FaultType.OVERCURRENT,
                            SafetyState.CRITICAL,
                            f"Motor overcurrent: {abs(motor_status.current_a):.1f}A (max: {self.current_max}A)",
                            "motor"
                        )
                    
                    # Check motor state
                    if motor_status.state.value == 'error':
                        fault_detected = True
                        self.safety_states['mechanical'] = SafetyState.CRITICAL
                        self._add_fault(
                            FaultType.MOTOR_FAULT,
                            SafetyState.CRITICAL,
                            "Motor controller reported error state",
                            "motor"
                        )
            except Exception as e:
                self.logger.error(f"Error checking motor electrical safety: {e}")
        
        return fault_detected

    def emergency_shutdown(self, reason: str) -> bool:
        """
        Execute graceful emergency shutdown sequence.
        
        Shutdown sequence:
        1. Stop motor immediately
        2. Stop charging if active
        3. Disconnect charging system
        4. Set vehicle to emergency state
        5. Log shutdown reason
        
        Args:
            reason: Reason for emergency shutdown
            
        Returns:
            True if shutdown successful, False otherwise
        """
        if self.emergency_shutdown_active:
            self.logger.warning("Emergency shutdown already active")
            return False
        
        self.logger.critical(f"EMERGENCY SHUTDOWN INITIATED: {reason}")
        self.emergency_shutdown_active = True
        self.emergency_shutdown_reason = reason
        self.emergency_shutdown_time = time.time()
        
        shutdown_success = True
        
        try:
            # Step 1: Stop motor immediately
            if self.motor_controller:
                try:
                    if self.motor_controller.is_connected:
                        self.motor_controller.stop()
                        self.logger.info("Motor stopped")
                except Exception as e:
                    self.logger.error(f"Error stopping motor: {e}")
                    shutdown_success = False
            
            # Step 2: Stop charging if active
            if self.charging_system:
                try:
                    if self.charging_system.is_charging():
                        self.charging_system.stop_charging()
                        self.logger.info("Charging stopped")
                    
                    # Step 3: Disconnect charging system
                    self.charging_system.disconnect_charger()
                    self.logger.info("Charging system disconnected")
                except Exception as e:
                    self.logger.error(f"Error stopping charging: {e}")
                    shutdown_success = False
            
            # Step 4: Set vehicle to emergency state
            if self.vehicle_controller:
                try:
                    # Use emergency_stop if available, otherwise just log
                    if hasattr(self.vehicle_controller, 'emergency_stop'):
                        self.vehicle_controller.emergency_stop()
                        self.logger.info("Vehicle controller emergency stop activated")
                except Exception as e:
                    self.logger.error(f"Error activating vehicle emergency stop: {e}")
                    shutdown_success = False
            
            # Step 5: Call external shutdown callback if set
            if self.shutdown_callback:
                try:
                    self.shutdown_callback(reason)
                except Exception as e:
                    self.logger.error(f"Error in shutdown callback: {e}")
            
            # Update safety states
            self.safety_states['thermal'] = SafetyState.EMERGENCY
            self.safety_states['electrical'] = SafetyState.EMERGENCY
            self.safety_states['mechanical'] = SafetyState.EMERGENCY
            
            self.logger.critical(f"Emergency shutdown complete: {reason}")
            
        except Exception as e:
            self.logger.critical(f"Critical error during emergency shutdown: {e}")
            shutdown_success = False
        
        return shutdown_success

    def monitor_system(self) -> bool:
        """
        Monitor all system components and check for safety issues.
        This should be called periodically (e.g., every second).
        
        Returns:
            True if system is safe, False if emergency shutdown was triggered
        """
        if self.emergency_shutdown_active:
            return False
        
        # Get current temperatures
        battery_temp = None
        motor_temp = None
        
        if self.battery_management:
            try:
                bms_state = self.battery_management.get_state()
                if bms_state:
                    battery_temp = bms_state.temperature
            except Exception as e:
                self.logger.error(f"Error getting battery temperature: {e}")
        
        if self.motor_controller:
            try:
                motor_status = self.motor_controller.get_status()
                if motor_status:
                    motor_temp = motor_status.temperature_c
            except Exception as e:
                self.logger.error(f"Error getting motor temperature: {e}")
        
        # Check thermal runaway
        thermal_runaway = self.check_thermal_runaway(battery_temp, motor_temp)
        
        # Check electrical safety
        electrical_fault = self.check_electrical_safety()
        
        # Trigger emergency shutdown if critical conditions detected
        if thermal_runaway or electrical_fault:
            if (self.safety_states['thermal'] in [SafetyState.EMERGENCY, SafetyState.CRITICAL] or
                self.safety_states['electrical'] == SafetyState.CRITICAL):
                reason = "Critical safety fault detected"
                if thermal_runaway:
                    reason += " (thermal runaway)"
                if electrical_fault:
                    reason += " (electrical fault)"
                self.emergency_shutdown(reason)
                return False
        
        return True

    def _add_fault(self, fault_type: FaultType, severity: SafetyState, 
                   description: str, component: str) -> None:
        """
        Add a fault to the faults list.
        
        Args:
            fault_type: Type of fault
            severity: Severity level
            description: Description of the fault
            component: Component where fault occurred
        """
        fault = Fault(
            fault_type=fault_type,
            severity=severity,
            description=description,
            timestamp=time.time(),
            component=component
        )
        self.faults.append(fault)
        
        # Keep only last 100 faults
        if len(self.faults) > 100:
            self.faults = self.faults[-100:]
        
        # Process fault through diagnostics system
        try:
            # Lazy initialization of diagnostics
            if self._diagnostics is None:
                from core.diagnostics import DiagnosticsSystem
                from pathlib import Path
                log_dir = self._diagnostics_log_dir
                if log_dir:
                    log_dir = Path(log_dir)
                self._diagnostics = DiagnosticsSystem(log_dir=log_dir)
            
            # Create freeze frame with current system state
            freeze_frame = self._create_freeze_frame()
            
            # Process through diagnostics (generates DTC, logs fault, updates limp-home mode)
            self._diagnostics.process_fault(
                fault_type=fault_type,
                severity=severity,
                description=description,
                component=component,
                safety_states=self.safety_states,
                freeze_frame=freeze_frame
            )
        except Exception as e:
            self.logger.error(f"Error processing fault through diagnostics: {e}")

    def clear_faults(self, component: Optional[str] = None) -> None:
        """
        Clear resolved faults.
        
        Args:
            component: Optional component name to clear faults for specific component.
                      If None, clears all resolved faults.
        """
        if component:
            for fault in self.faults:
                if fault.component == component and not fault.resolved:
                    fault.resolved = True
                    fault.resolution_time = time.time()
        else:
            for fault in self.faults:
                if not fault.resolved:
                    fault.resolved = True
                    fault.resolution_time = time.time()

    def get_active_faults(self) -> List[Fault]:
        """
        Get list of active (unresolved) faults.
        
        Returns:
            List of active Fault objects
        """
        return [fault for fault in self.faults if not fault.resolved]

    def get_faults_by_severity(self, severity: SafetyState) -> List[Fault]:
        """
        Get faults filtered by severity level.
        
        Args:
            severity: Severity level to filter by
            
        Returns:
            List of Fault objects with specified severity
        """
        return [fault for fault in self.faults if fault.severity == severity]

    def reset_emergency_shutdown(self) -> bool:
        """
        Reset emergency shutdown state (after manual inspection/repair).
        
        Returns:
            True if reset successful, False otherwise
        """
        if not self.emergency_shutdown_active:
            return False
        
        # Check that all critical faults are resolved
        critical_faults = self.get_faults_by_severity(SafetyState.EMERGENCY)
        active_critical = [f for f in critical_faults if not f.resolved]
        
        if active_critical:
            self.logger.warning(
                f"Cannot reset emergency shutdown: {len(active_critical)} active critical faults"
            )
            return False
        
        self.emergency_shutdown_active = False
        self.emergency_shutdown_reason = None
        self.emergency_shutdown_time = None
        
        # Reset safety states to normal
        self.safety_states['thermal'] = SafetyState.NORMAL
        self.safety_states['electrical'] = SafetyState.NORMAL
        self.safety_states['mechanical'] = SafetyState.NORMAL
        
        # Clear thermal history
        self.battery_thermal_history.temperatures.clear()
        self.battery_thermal_history.timestamps.clear()
        self.battery_thermal_history.max_rate_c_per_s = 0.0
        self.motor_thermal_history.temperatures.clear()
        self.motor_thermal_history.timestamps.clear()
        self.motor_thermal_history.max_rate_c_per_s = 0.0
        
        self.logger.info("Emergency shutdown state reset")
        return True

    def _create_freeze_frame(self) -> Dict[str, Any]:
        """
        Create a freeze frame snapshot of current system conditions.
        
        Returns:
            Dictionary with system state snapshot
        """
        freeze_frame = {
            'timestamp': time.time(),
            'safety_states': {k: v.value for k, v in self.safety_states.items()},
            'emergency_shutdown_active': self.emergency_shutdown_active,
        }
        
        # Add battery state if available
        if self.battery_management:
            try:
                bms_state = self.battery_management.get_state()
                if bms_state:
                    freeze_frame['battery'] = {
                        'voltage': bms_state.voltage,
                        'current': bms_state.current,
                        'temperature': bms_state.temperature,
                        'soc': bms_state.soc,
                        'status': bms_state.status.value
                    }
            except Exception:
                pass
        
        # Add motor state if available
        if self.motor_controller:
            try:
                motor_status = self.motor_controller.get_status()
                if motor_status:
                    freeze_frame['motor'] = {
                        'voltage': motor_status.voltage_v,
                        'current': motor_status.current_a,
                        'temperature': motor_status.temperature_c,
                        'speed_rpm': motor_status.speed_rpm,
                        'state': motor_status.state.value
                    }
            except Exception:
                pass
        
        # Add thermal history rates
        freeze_frame['thermal_rates'] = {
            'battery_max_rate_c_per_s': self.battery_thermal_history.max_rate_c_per_s,
            'motor_max_rate_c_per_s': self.motor_thermal_history.max_rate_c_per_s
        }
        
        return freeze_frame
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current safety system status.
        
        Returns:
            Dictionary with safety system status information
        """
        active_faults = self.get_active_faults()
        critical_faults = [f for f in active_faults if f.severity == SafetyState.EMERGENCY]
        
        status = {
            'safety_states': {k: v.value for k, v in self.safety_states.items()},
            'emergency_shutdown_active': self.emergency_shutdown_active,
            'emergency_shutdown_reason': self.emergency_shutdown_reason,
            'emergency_shutdown_time': self.emergency_shutdown_time,
            'active_fault_count': len(active_faults),
            'critical_fault_count': len(critical_faults),
            'total_fault_count': len(self.faults),
            'battery_thermal_max_rate': self.battery_thermal_history.max_rate_c_per_s,
            'motor_thermal_max_rate': self.motor_thermal_history.max_rate_c_per_s,
        }
        
        # Add diagnostics information
        try:
            if self._diagnostics is None:
                # Lazy initialization
                from core.diagnostics import DiagnosticsSystem
                from pathlib import Path
                log_dir = self._diagnostics_log_dir
                if log_dir:
                    log_dir = Path(log_dir)
                self._diagnostics = DiagnosticsSystem(log_dir=log_dir)
            
            diagnostics_status = self._diagnostics.get_diagnostics_status()
            status['diagnostics'] = diagnostics_status
        except Exception as e:
            self.logger.error(f"Error getting diagnostics status: {e}")
            status['diagnostics'] = None
        
        return status
    
    @property
    def diagnostics(self):
        """Get diagnostics system (lazy initialization)."""
        if self._diagnostics is None:
            from core.diagnostics import DiagnosticsSystem
            from pathlib import Path
            log_dir = self._diagnostics_log_dir
            if log_dir:
                log_dir = Path(log_dir)
            self._diagnostics = DiagnosticsSystem(log_dir=log_dir)
        return self._diagnostics


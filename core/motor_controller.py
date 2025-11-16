"""Motor controller module for the EV project.
Implements high-level interface for VESC (Vedder Electronic Speed Controller).
"""

import time
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

try:
    from pyvesc import VESC
    from pyvesc.messages import SetDutyCycle, SetRPM, SetCurrent, GetValues
    VESC_AVAILABLE = True
except ImportError:
    VESC_AVAILABLE = False
    # Create mock classes for when VESC is not available
    class VESC:
        def __init__(self, *args, **kwargs):
            pass
        def set_duty_cycle(self, *args, **kwargs):
            pass
        def set_rpm(self, *args, **kwargs):
            pass
        def set_current(self, *args, **kwargs):
            pass
        def get_measurements(self, *args, **kwargs):
            return None
        def stop_heartbeat(self, *args, **kwargs):
            pass
    
    class SetDutyCycle:
        def __init__(self, *args, **kwargs):
            pass
    
    class SetRPM:
        def __init__(self, *args, **kwargs):
            pass
    
    class SetCurrent:
        def __init__(self, *args, **kwargs):
            pass
    
    class GetValues:
        pass


class MotorState(Enum):
    """Motor controller states."""
    DISCONNECTED = "disconnected"
    IDLE = "idle"
    RUNNING = "running"
    BRAKING = "braking"
    ERROR = "error"


@dataclass
class MotorStatus:
    """Motor status information."""
    speed_rpm: float = 0.0
    current_a: float = 0.0
    voltage_v: float = 0.0
    duty_cycle: float = 0.0
    temperature_c: float = 0.0
    power_w: float = 0.0
    state: MotorState = MotorState.DISCONNECTED
    timestamp: float = 0.0


class VESCManager:
    """
    High-level manager for VESC (Vedder Electronic Speed Controller).
    Provides interface for controlling motor via VESC and integrates with CAN bus.
    """
    
    def __init__(
        self,
        serial_port: Optional[str] = None,
        can_bus: Optional[Any] = None,
        can_protocol: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize VESC manager.
        
        Args:
            serial_port: Serial port for UART communication (e.g., '/dev/ttyUSB0')
            can_bus: CAN bus interface (optional, for CAN communication)
            can_protocol: EV CAN protocol instance (optional)
            config: Configuration dictionary with motor parameters
        """
        self.serial_port = serial_port
        self.can_bus = can_bus
        self.can_protocol = can_protocol
        self.config = config or {}
        
        self.logger = logging.getLogger(__name__)
        self.vesc: Optional[VESC] = None
        self.is_connected = False
        self.current_status = MotorStatus()
        
        # Motor limits from config
        self.max_power_kw = self.config.get('max_power_kw', 150.0)
        self.max_torque_nm = self.config.get('max_torque_nm', 320.0)
        self.max_current_a = self.config.get('max_current_a', 200.0)
        self.max_rpm = self.config.get('max_rpm', 10000.0)
        
        # Safety limits
        self.max_temperature_c = self.config.get('max_temperature_c', 80.0)
        self.min_voltage_v = self.config.get('min_voltage_v', 300.0)
        self.max_voltage_v = self.config.get('max_voltage_v', 500.0)
    
    def connect(self, serial_port: Optional[str] = None) -> bool:
        """
        Connect to VESC controller.
        
        Args:
            serial_port: Serial port (uses instance port if not provided)
        
        Returns:
            True if connection successful, False otherwise
        """
        port = serial_port or self.serial_port
        if not port:
            self.logger.error("No serial port specified for VESC connection")
            return False
        
        if not VESC_AVAILABLE:
            self.logger.warning("VESC library not available. Running in simulation mode.")
            self.is_connected = True
            self.current_status.state = MotorState.IDLE
            self.serial_port = port
            return True
        
        try:
            
            self.logger.info(f"Connecting to VESC on {port}...")
            self.vesc = VESC(serial_port=port)
            self.is_connected = True
            self.current_status.state = MotorState.IDLE
            self.serial_port = port
            
            self.logger.info("VESC connected successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to connect to VESC: {e}")
            self.is_connected = False
            return False
    
    def disconnect(self) -> None:
        """Disconnect from VESC controller."""
        if self.vesc:
            try:
                if hasattr(self.vesc, 'stop_heartbeat'):
                    self.vesc.stop_heartbeat()
            except Exception as e:
                self.logger.warning(f"Error stopping VESC heartbeat: {e}")
        
        self.vesc = None
        self.is_connected = False
        self.current_status.state = MotorState.DISCONNECTED
        self.logger.info("VESC disconnected")
    
    def set_duty_cycle(self, duty_cycle: float) -> bool:
        """
        Set motor duty cycle.
        
        Args:
            duty_cycle: Duty cycle in range [-1.0, 1.0] (negative for reverse)
        
        Returns:
            True if command sent successfully, False otherwise
        """
        if not self.is_connected:
            self.logger.error("Cannot set duty cycle: not connected to VESC")
            return False
        
        # Validate duty cycle
        if abs(duty_cycle) > 1.0:
            self.logger.error(f"Invalid duty cycle: {duty_cycle} (must be in [-1.0, 1.0])")
            return False
        
        try:
            if VESC_AVAILABLE and self.vesc:
                self.vesc.set_duty_cycle(duty_cycle)
            else:
                # Simulation mode
                self.current_status.duty_cycle = duty_cycle
            
            self.current_status.state = MotorState.RUNNING
            self.logger.debug(f"Set duty cycle to {duty_cycle}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to set duty cycle: {e}")
            return False
    
    def set_rpm(self, rpm: float) -> bool:
        """
        Set motor RPM.
        
        Args:
            rpm: Target RPM (can be negative for reverse)
        
        Returns:
            True if command sent successfully, False otherwise
        """
        if not self.is_connected:
            self.logger.error("Cannot set RPM: not connected to VESC")
            return False
        
        # Validate RPM
        if abs(rpm) > self.max_rpm:
            self.logger.warning(f"RPM {rpm} exceeds maximum {self.max_rpm}, clamping")
            rpm = max(-self.max_rpm, min(self.max_rpm, rpm))
        
        try:
            if VESC_AVAILABLE and self.vesc:
                self.vesc.set_rpm(int(rpm))
            else:
                # Simulation mode
                self.current_status.speed_rpm = rpm
            
            self.current_status.state = MotorState.RUNNING
            self.logger.debug(f"Set RPM to {rpm}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to set RPM: {e}")
            return False
    
    def set_current(self, current_a: float) -> bool:
        """
        Set motor current.
        
        Args:
            current_a: Target current in Amperes (can be negative for reverse/braking)
        
        Returns:
            True if command sent successfully, False otherwise
        """
        if not self.is_connected:
            self.logger.error("Cannot set current: not connected to VESC")
            return False
        
        # Validate current
        if abs(current_a) > self.max_current_a:
            self.logger.warning(f"Current {current_a}A exceeds maximum {self.max_current_a}A, clamping")
            current_a = max(-self.max_current_a, min(self.max_current_a, current_a))
        
        try:
            if VESC_AVAILABLE and self.vesc:
                self.vesc.set_current(current_a)
            else:
                # Simulation mode
                self.current_status.current_a = current_a
            
            if current_a < 0:
                self.current_status.state = MotorState.BRAKING
            else:
                self.current_status.state = MotorState.RUNNING
            
            self.logger.debug(f"Set current to {current_a}A")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to set current: {e}")
            return False
    
    def stop(self) -> bool:
        """
        Stop the motor (set to zero).
        
        Returns:
            True if command sent successfully, False otherwise
        """
        return self.set_current(0.0)
    
    def get_status(self) -> MotorStatus:
        """
        Get current motor status.
        
        Returns:
            MotorStatus object with current motor parameters
        """
        if not self.is_connected:
            return MotorStatus(state=MotorState.DISCONNECTED)
        
        try:
            if VESC_AVAILABLE and self.vesc:
                # Get measurements from VESC
                measurements = self.vesc.get_measurements()
                if measurements:
                    self.current_status.speed_rpm = getattr(measurements, 'rpm', 0.0)
                    self.current_status.current_a = getattr(measurements, 'avg_motor_current', 0.0)
                    self.current_status.voltage_v = getattr(measurements, 'v_in', 0.0)
                    self.current_status.duty_cycle = getattr(measurements, 'duty_cycle_now', 0.0)
                    self.current_status.temperature_c = getattr(measurements, 'temp_mos', 0.0)
                    self.current_status.power_w = (
                        self.current_status.voltage_v * self.current_status.current_a
                    )
                    self.current_status.timestamp = time.time()
                    
                    # Check safety limits
                    if self.current_status.temperature_c > self.max_temperature_c:
                        self.current_status.state = MotorState.ERROR
                        self.logger.warning(f"Motor temperature {self.current_status.temperature_c}°C exceeds limit")
                    elif self.current_status.voltage_v < self.min_voltage_v:
                        self.current_status.state = MotorState.ERROR
                        self.logger.warning(f"Motor voltage {self.current_status.voltage_v}V below minimum")
                    elif abs(self.current_status.speed_rpm) < 1.0 and abs(self.current_status.current_a) < 0.1:
                        self.current_status.state = MotorState.IDLE
                    else:
                        self.current_status.state = MotorState.RUNNING
            else:
                # Simulation mode - update timestamp
                self.current_status.timestamp = time.time()
            
            # Check safety limits (works in both real and simulation mode)
            # Only check voltage if it's been measured (non-zero)
            if self.current_status.temperature_c > self.max_temperature_c:
                self.current_status.state = MotorState.ERROR
                self.logger.warning(f"Motor temperature {self.current_status.temperature_c}°C exceeds limit")
            elif self.current_status.voltage_v > 0 and self.current_status.voltage_v < self.min_voltage_v:
                self.current_status.state = MotorState.ERROR
                self.logger.warning(f"Motor voltage {self.current_status.voltage_v}V below minimum")
            elif self.current_status.voltage_v > 0 and self.current_status.voltage_v > self.max_voltage_v:
                self.current_status.state = MotorState.ERROR
                self.logger.warning(f"Motor voltage {self.current_status.voltage_v}V above maximum")
            elif self.current_status.state != MotorState.ERROR:
                # Only update state if not in error
                if abs(self.current_status.speed_rpm) < 1.0 and abs(self.current_status.current_a) < 0.1:
                    self.current_status.state = MotorState.IDLE
                else:
                    self.current_status.state = MotorState.RUNNING
            
            # Send status to CAN bus if available
            if self.can_protocol:
                self._send_status_to_can()
            
            return self.current_status
            
        except Exception as e:
            self.logger.error(f"Failed to get motor status: {e}")
            self.current_status.state = MotorState.ERROR
            return self.current_status
    
    def _send_status_to_can(self) -> None:
        """Send motor status to CAN bus."""
        if not self.can_protocol:
            return
        
        try:
            self.can_protocol.send_motor_status(
                speed=self.current_status.speed_rpm,
                torque=self._calculate_torque(),
                temperature=self.current_status.temperature_c
            )
        except Exception as e:
            self.logger.warning(f"Failed to send motor status to CAN: {e}")
    
    def _calculate_torque(self) -> float:
        """
        Calculate estimated torque from current motor parameters.
        
        Returns:
            Estimated torque in N⋅m
        """
        # Simplified torque calculation: T = (P * 60) / (2 * π * RPM)
        # Or from power: T = P / ω, where ω = 2π * RPM / 60
        if abs(self.current_status.speed_rpm) < 1.0:
            return 0.0
        
        power_w = self.current_status.power_w
        if power_w <= 0:
            return 0.0
        
        omega = 2 * 3.14159 * self.current_status.speed_rpm / 60.0
        torque_nm = power_w / omega if omega > 0 else 0.0
        
        # Clamp to maximum torque
        return max(-self.max_torque_nm, min(self.max_torque_nm, torque_nm))
    
    def is_healthy(self) -> bool:
        """
        Check if motor controller is healthy.
        
        Returns:
            True if healthy, False otherwise
        """
        if not self.is_connected:
            return False
        
        status = self.get_status()
        
        # Check for error conditions
        if status.state == MotorState.ERROR:
            return False
        
        if status.temperature_c > self.max_temperature_c:
            return False
        
        if status.voltage_v < self.min_voltage_v or status.voltage_v > self.max_voltage_v:
            return False
        
        return True

"""Vehicle controller module for the EV project.
High-level controller that coordinates battery management, motor control, and charging systems.
Manages overall vehicle state and provides unified interface for vehicle operations.
"""

import time
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum


class VehicleState(Enum):
    """Vehicle operational states."""
    PARKED = "parked"
    READY = "ready"
    DRIVING = "driving"
    CHARGING = "charging"
    ERROR = "error"
    FAULT = "fault"
    EMERGENCY = "emergency"
    STANDBY = "standby"


class DriveMode(Enum):
    """Vehicle drive modes."""
    ECO = "eco"
    NORMAL = "normal"
    SPORT = "sport"
    REVERSE = "reverse"


@dataclass
class VehicleStatus:
    """Vehicle status information."""
    state: VehicleState = VehicleState.PARKED
    speed_kmh: float = 0.0
    acceleration_ms2: float = 0.0
    power_kw: float = 0.0
    energy_consumption_kwh: float = 0.0
    range_km: float = 0.0
    drive_mode: DriveMode = DriveMode.NORMAL
    timestamp: float = 0.0


@dataclass
class VehicleConfig:
    """Vehicle configuration parameters."""
    max_speed_kmh: float = 120.0
    max_acceleration_ms2: float = 3.0
    max_deceleration_ms2: float = -5.0
    max_power_kw: float = 150.0
    efficiency_wh_per_km: float = 200.0  # Energy consumption per km
    weight_kg: float = 1500.0


class VehicleController:
    """
    High-level vehicle controller that coordinates BMS, motor controller, and charging system.
    Manages overall vehicle state and provides unified interface for vehicle operations.
    """

    def __init__(
        self,
        config: Dict[str, Any],
        bms: Optional[Any] = None,
        motor_controller: Optional[Any] = None,
        charging_system: Optional[Any] = None,
        can_protocol: Optional[Any] = None
    ):
        """
        Initialize vehicle controller.
        
        Args:
            config: Configuration dictionary with vehicle parameters
            bms: Battery Management System instance
            motor_controller: Motor controller instance (VESCManager)
            charging_system: Charging system instance
            can_protocol: EV CAN protocol instance (optional)
        """
        self.config = VehicleConfig(
            max_speed_kmh=config.get('max_speed_kmh', 120.0),
            max_acceleration_ms2=config.get('max_acceleration_ms2', 3.0),
            max_deceleration_ms2=config.get('max_deceleration_ms2', -5.0),
            max_power_kw=config.get('max_power_kw', 150.0),
            efficiency_wh_per_km=config.get('efficiency_wh_per_km', 200.0),
            weight_kg=config.get('weight_kg', 1500.0)
        )

        self.bms = bms
        self.motor_controller = motor_controller
        self.charging_system = charging_system
        self.can_protocol = can_protocol

        self.logger = logging.getLogger(__name__)
        self.current_status = VehicleStatus()

        # Driving state
        self.driving_start_time: Optional[float] = None
        self.last_speed_update: float = time.time()
        self.last_speed: float = 0.0

        # Statistics
        self.stats = {
            'total_distance_km': 0.0,
            'total_energy_consumed_kwh': 0.0,
            'driving_time_s': 0.0,
            'fault_count': 0,
            'last_update': time.time()
        }

        self.logger.info(
            f"Vehicle controller initialized: max_speed={self.config.max_speed_kmh}km/h, "
            f"max_power={self.config.max_power_kw}kW"
        )

    def set_state(self, state: VehicleState) -> bool:
        """
        Set vehicle state.
        
        Args:
            state: Target vehicle state
            
        Returns:
            True if state change successful, False otherwise
        """
        # Validate state transitions
        if not self._can_transition_to_state(self.current_status.state, state):
            self.logger.warning(f"Cannot transition from {self.current_status.state.value} to {state.value}")
            return False

        old_state = self.current_status.state
        self.current_status.state = state
        self.current_status.timestamp = time.time()

        # Handle state-specific actions
        if state == VehicleState.DRIVING:
            self.driving_start_time = time.time()
        elif state in [VehicleState.PARKED, VehicleState.READY]:
            if self.driving_start_time:
                self.stats['driving_time_s'] += time.time() - self.driving_start_time
                self.driving_start_time = None

        self.logger.info(f"Vehicle state changed: {old_state.value} -> {state.value}")

        # Send state to CAN bus
        if self.can_protocol:
            self._send_status_to_can()

        return True

    def _can_transition_to_state(self, current_state: VehicleState, new_state: VehicleState) -> bool:
        """Check if state transition is allowed."""
        # Can always transition to ERROR or EMERGENCY
        if new_state in [VehicleState.ERROR, VehicleState.EMERGENCY]:
            return True

        # Can always transition from ERROR/EMERGENCY to PARKED/STANDBY
        if current_state in [VehicleState.ERROR, VehicleState.EMERGENCY]:
            return new_state in [VehicleState.PARKED, VehicleState.STANDBY]

        # Cannot drive while charging
        if new_state == VehicleState.DRIVING and self.charging_system:
            if self.charging_system.is_charging():
                return False

        # Cannot charge while driving
        if new_state == VehicleState.CHARGING and self.current_status.state == VehicleState.DRIVING:
            return False

        # Valid transitions
        valid_transitions = {
            VehicleState.PARKED: [VehicleState.READY, VehicleState.CHARGING, VehicleState.STANDBY],
            VehicleState.READY: [VehicleState.DRIVING, VehicleState.PARKED, VehicleState.CHARGING],
            VehicleState.DRIVING: [VehicleState.READY, VehicleState.PARKED],
            VehicleState.CHARGING: [VehicleState.PARKED, VehicleState.READY],
            VehicleState.STANDBY: [VehicleState.PARKED, VehicleState.READY],
            VehicleState.FAULT: [VehicleState.PARKED, VehicleState.STANDBY]
        }

        return new_state in valid_transitions.get(current_state, [])

    def start_driving(self) -> bool:
        """
        Start driving (transition to DRIVING state).
        
        Returns:
            True if successful, False otherwise
        """
        # Check if charging
        if self.charging_system and self.charging_system.is_charging():
            self.logger.error("Cannot start driving while charging")
            return False

        # Check BMS health
        if self.bms:
            bms_state = self.bms.get_state()
            if bms_state.status.value in ['fault', 'critical']:
                self.logger.error("BMS fault detected, cannot start driving")
                self.set_state(VehicleState.ERROR)
                return False

            if bms_state.soc < 5.0:
                self.logger.error("Battery SOC too low, cannot start driving")
                self.set_state(VehicleState.ERROR)
                return False

        # Check motor controller
        if self.motor_controller:
            if not self.motor_controller.is_connected:
                self.logger.error("Motor controller not connected")
                return False

            if not self.motor_controller.is_healthy():
                self.logger.error("Motor controller not healthy")
                self.set_state(VehicleState.ERROR)
                return False

        return self.set_state(VehicleState.DRIVING)

    def stop_driving(self) -> bool:
        """
        Stop driving (transition to READY or PARKED state).
        
        Returns:
            True if successful, False otherwise
        """
        if self.current_status.state != VehicleState.DRIVING:
            self.logger.warning("Not currently driving")
            return False

        # Stop motor
        if self.motor_controller:
            self.motor_controller.stop()

        # Reset speed and acceleration
        self.current_status.speed_kmh = 0.0
        self.current_status.acceleration_ms2 = 0.0
        self.current_status.power_kw = 0.0

        return self.set_state(VehicleState.READY)

    def accelerate(self, throttle_percent: float) -> bool:
        """
        Accelerate vehicle.
        
        Args:
            throttle_percent: Throttle position (0-100%)
            
        Returns:
            True if command successful, False otherwise
        """
        if self.current_status.state != VehicleState.DRIVING:
            self.logger.error("Cannot accelerate: vehicle not in driving state")
            return False

        # Validate throttle
        throttle_percent = max(0.0, min(100.0, throttle_percent))

        # Check BMS can discharge
        if self.bms:
            # Calculate requested power
            requested_power_kw = (throttle_percent / 100.0) * self.config.max_power_kw

            if not self.bms.can_discharge(requested_power_kw):
                self.logger.warning(f"BMS cannot discharge at {requested_power_kw}kW")
                return False

        # Calculate target acceleration
        target_acceleration = (throttle_percent / 100.0) * self.config.max_acceleration_ms2

        # Limit acceleration
        target_acceleration = min(target_acceleration, self.config.max_acceleration_ms2)
        self.current_status.acceleration_ms2 = target_acceleration

        # Calculate power
        power_kw = (throttle_percent / 100.0) * self.config.max_power_kw
        self.current_status.power_kw = power_kw

        # Send command to motor controller
        if self.motor_controller:
            # Convert throttle to duty cycle or current
            duty_cycle = throttle_percent / 100.0
            self.motor_controller.set_duty_cycle(duty_cycle)

        # Update speed (simplified physics)
        self._update_speed()

        # Update energy consumption
        self._update_energy_consumption()

        # Send status to CAN bus
        if self.can_protocol:
            self._send_status_to_can()

        return True

    def brake(self, brake_percent: float) -> bool:
        """
        Apply brakes.
        
        Args:
            brake_percent: Brake position (0-100%)
            
        Returns:
            True if command successful, False otherwise
        """
        if self.current_status.state != VehicleState.DRIVING:
            self.logger.warning("Cannot brake: vehicle not in driving state")
            return False

        # Validate brake
        brake_percent = max(0.0, min(100.0, brake_percent))

        # Calculate deceleration
        deceleration = (brake_percent / 100.0) * abs(self.config.max_deceleration_ms2)
        self.current_status.acceleration_ms2 = -deceleration

        # Apply regenerative braking if motor controller supports it
        if self.motor_controller:
            # Negative current for regenerative braking
            regen_current = -(brake_percent / 100.0) * 50.0  # Max 50A regen
            self.motor_controller.set_current(regen_current)

        # Update speed
        self._update_speed()

        # Send status to CAN bus
        if self.can_protocol:
            self._send_status_to_can()

        return True

    def set_drive_mode(self, mode: DriveMode) -> bool:
        """
        Set drive mode.
        
        Args:
            mode: Drive mode (ECO, NORMAL, SPORT, REVERSE)
            
        Returns:
            True if successful, False otherwise
        """
        if self.current_status.state == VehicleState.DRIVING:
            self.logger.warning("Cannot change drive mode while driving")
            return False

        self.current_status.drive_mode = mode

        # Adjust limits based on mode
        if mode == DriveMode.ECO:
            self.config.max_power_kw = self.config.max_power_kw * 0.7
            self.config.max_acceleration_ms2 = self.config.max_acceleration_ms2 * 0.7
        elif mode == DriveMode.SPORT:
            self.config.max_power_kw = self.config.max_power_kw * 1.2
            self.config.max_acceleration_ms2 = self.config.max_acceleration_ms2 * 1.2
        else:  # NORMAL
            # Reset to defaults (would need to store original values)
            pass

        self.logger.info(f"Drive mode set to {mode.value}")
        return True

    def start_charging(self, power_kw: Optional[float] = None, target_soc: float = 100.0) -> bool:
        """
        Start charging process.
        
        Args:
            power_kw: Requested charging power (None = use max available)
            target_soc: Target state of charge (0-100%)
            
        Returns:
            True if charging started, False otherwise
        """
        if self.current_status.state == VehicleState.DRIVING:
            self.logger.error("Cannot start charging while driving")
            return False

        if not self.charging_system:
            self.logger.error("Charging system not available")
            return False

        # Connect charger if not connected
        if not self.charging_system.is_connected():
            if not self.charging_system.connect_charger():
                return False

        # Start charging
        if self.charging_system.start_charging(power_kw=power_kw, target_soc=target_soc):
            self.set_state(VehicleState.CHARGING)
            return True

        return False

    def stop_charging(self) -> bool:
        """
        Stop charging process.
        
        Returns:
            True if charging stopped, False otherwise
        """
        if not self.charging_system:
            return False

        if self.charging_system.stop_charging():
            self.set_state(VehicleState.PARKED)
            return True

        return False

    def update_status(self) -> VehicleStatus:
        """
        Update vehicle status from subsystems.
        
        Returns:
            Updated VehicleStatus
        """
        current_time = time.time()

        # Update from motor controller
        if self.motor_controller and self.motor_controller.is_connected:
            motor_status = self.motor_controller.get_status()
            # Convert RPM to km/h (simplified, would need gear ratio and wheel size)
            # Assuming 1 RPM = 0.1 km/h (example conversion)
            self.current_status.speed_kmh = abs(motor_status.speed_rpm) * 0.1
            self.current_status.power_kw = abs(motor_status.power_w) / 1000.0

        # Update from BMS
        if self.bms:
            bms_state = self.bms.get_state()
            # Calculate range
            if bms_state.soc > 0 and self.config.efficiency_wh_per_km > 0:
                available_energy_kwh = (bms_state.soc / 100.0) * self.bms.config.capacity_kwh
                self.current_status.range_km = (available_energy_kwh * 1000.0) / self.config.efficiency_wh_per_km
            else:
                self.current_status.range_km = 0.0

            # Check for BMS faults
            if bms_state.status.value in ['fault', 'critical']:
                if self.current_status.state == VehicleState.DRIVING:
                    self.logger.error("BMS fault detected during driving")
                    self.set_state(VehicleState.ERROR)

        # Update from charging system
        if self.charging_system:
            charging_status = self.charging_system.get_status()
            if charging_status.state.value in ['charging', 'charging_ac', 'charging_dc']:
                if self.current_status.state != VehicleState.CHARGING:
                    self.set_state(VehicleState.CHARGING)
            elif self.current_status.state == VehicleState.CHARGING:
                if charging_status.state.value == 'complete':
                    self.set_state(VehicleState.PARKED)
                elif charging_status.state.value in ['error', 'fault']:
                    self.set_state(VehicleState.ERROR)

        # Update driving statistics
        if self.current_status.state == VehicleState.DRIVING:
            if self.driving_start_time:
                dt = current_time - self.stats['last_update']
                if dt > 0:
                    # Update distance (simplified)
                    distance_km = (self.current_status.speed_kmh * dt) / 3600.0
                    self.stats['total_distance_km'] += distance_km

                    # Update energy consumption
                    self._update_energy_consumption()

        self.current_status.timestamp = current_time
        self.stats['last_update'] = current_time

        # Send status to CAN bus
        if self.can_protocol:
            self._send_status_to_can()

        return self.current_status

    def _update_speed(self) -> None:
        """Update vehicle speed based on acceleration."""
        current_time = time.time()
        dt = current_time - self.last_speed_update

        if dt > 0:
            # Update speed: v = v0 + a*t
            speed_ms = self.current_status.speed_kmh / 3.6  # Convert to m/s
            speed_ms += self.current_status.acceleration_ms2 * dt

            # Limit speed
            max_speed_ms = self.config.max_speed_kmh / 3.6
            speed_ms = max(0.0, min(max_speed_ms, speed_ms))

            # Convert back to km/h
            self.current_status.speed_kmh = speed_ms * 3.6

            # If speed is very low, set to zero
            if self.current_status.speed_kmh < 0.1:
                self.current_status.speed_kmh = 0.0
                self.current_status.acceleration_ms2 = 0.0

        self.last_speed_update = current_time
        self.last_speed = self.current_status.speed_kmh

    def _update_energy_consumption(self) -> None:
        """Update energy consumption statistics."""
        current_time = time.time()
        dt = current_time - self.stats['last_update']

        if dt > 0 and self.current_status.power_kw > 0:
            # Calculate energy consumed
            energy_kwh = (self.current_status.power_kw * dt) / 3600.0
            self.stats['total_energy_consumed_kwh'] += energy_kwh
            self.current_status.energy_consumption_kwh = self.stats['total_energy_consumed_kwh']

    def get_status(self) -> VehicleStatus:
        """
        Get current vehicle status.
        
        Returns:
            Current VehicleStatus
        """
        return self.update_status()

    def get_statistics(self) -> Dict:
        """
        Get vehicle statistics.
        
        Returns:
            Dictionary with vehicle statistics
        """
        return {
            **self.stats,
            'current_speed_kmh': self.current_status.speed_kmh,
            'current_range_km': self.current_status.range_km,
            'state': self.current_status.state.value,
            'drive_mode': self.current_status.drive_mode.value,
            'power_kw': self.current_status.power_kw
        }

    def is_healthy(self) -> bool:
        """
        Check if vehicle is healthy.
        
        Returns:
            True if healthy, False otherwise
        """
        if self.current_status.state in [VehicleState.ERROR, VehicleState.FAULT, VehicleState.EMERGENCY]:
            return False

        # Check BMS
        if self.bms:
            bms_state = self.bms.get_state()
            if bms_state.status.value in ['fault', 'critical']:
                return False

        # Check motor controller
        if self.motor_controller:
            if not self.motor_controller.is_healthy():
                return False

        # Check charging system
        if self.charging_system:
            if not self.charging_system.is_healthy():
                return False

        return True

    def emergency_stop(self) -> bool:
        """
        Emergency stop - immediately stop all vehicle operations.
        
        Returns:
            True if successful, False otherwise
        """
        self.logger.critical("EMERGENCY STOP ACTIVATED")

        # Stop motor immediately
        if self.motor_controller:
            self.motor_controller.stop()

        # Stop charging if active
        if self.charging_system and self.charging_system.is_charging():
            self.charging_system.stop_charging()

        # Reset all movement parameters
        self.current_status.speed_kmh = 0.0
        self.current_status.acceleration_ms2 = 0.0
        self.current_status.power_kw = 0.0

        # Set emergency state
        self.set_state(VehicleState.EMERGENCY)

        return True

    def _send_status_to_can(self) -> None:
        """Send vehicle status to CAN bus."""
        if not self.can_protocol:
            return

        try:
            if hasattr(self.can_protocol, 'send_vehicle_status'):
                self.can_protocol.send_vehicle_status(
                    speed=self.current_status.speed_kmh,
                    acceleration=self.current_status.acceleration_ms2,
                    state=self.current_status.state.value
                )
        except Exception as e:
            self.logger.warning(f"Failed to send vehicle status to CAN: {e}")

"""Autopilot system for high-level autonomous driving decisions."""

from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class DrivingMode(Enum):
    """Autonomous driving modes."""
    MANUAL = "manual"
    ASSIST = "assist"
    AUTOPILOT = "autopilot"
    EMERGENCY = "emergency"


@dataclass
class VehicleState:
    """Current vehicle state information."""
    position: Tuple[float, float, float]
    velocity: Tuple[float, float, float]
    heading: float
    speed: float


@dataclass
class EnvironmentState:
    """Current environment state from sensors."""
    detected_objects: List[Dict]
    lane_info: List[Dict]
    traffic_lights: List[Dict]
    road_conditions: str


@dataclass
class DrivingCommand:
    """High-level driving command."""
    steering_angle: float
    throttle: float
    brake: float
    emergency_brake: bool


class AutopilotSystem:
    """High-level autonomous driving system."""

    def __init__(self, config: Dict):
        """Initialize the autopilot system."""
        self.config = config
        self.current_mode = DrivingMode.MANUAL
        self.vehicle_state = None
        self.environment_state = None
        self.is_active = False

        # Safety parameters
        self.min_following_distance = config.get('min_following_distance', 2.0)
        self.max_speed = config.get('max_speed', 30.0)
        self.emergency_brake_threshold = config.get('emergency_brake_threshold', 1.5)
        self.autopilot_activation_max_speed = config.get('autopilot_activation_max_speed', 25.0)
        self.assist_target_speed = config.get('assist_target_speed', 25.0)
        self.speed_control_deadband = config.get('speed_control_deadband', 0.5)
        self.speed_control_throttle_gain = config.get('speed_control_throttle_gain', 0.2)
        self.speed_control_brake_gain = config.get('speed_control_brake_gain', 0.3)
        self.speed_control_hold_throttle = config.get('speed_control_hold_throttle', 0.1)
        self.lane_steering_gain = config.get('lane_steering_gain', 0.1)
        self.adaptive_cruise_follow_distance_multiplier = config.get(
            'adaptive_cruise_follow_distance_multiplier', 3.0
        )
        self.adaptive_cruise_vehicle_classes = config.get(
            'adaptive_cruise_vehicle_classes', ['car', 'truck', 'bus']
        )

    def activate(self, mode: DrivingMode) -> bool:
        """Activate autopilot in specified mode."""
        if not self._can_activate_mode(mode):
            return False

        self.current_mode = mode
        self.is_active = True
        return True

    def deactivate(self) -> None:
        """Deactivate autopilot system."""
        self.is_active = False
        self.current_mode = DrivingMode.MANUAL

    def _can_activate_mode(self, mode: DrivingMode) -> bool:
        """Check if the specified mode can be activated."""
        if not self.vehicle_state or not self.environment_state:
            return False

        if mode == DrivingMode.AUTOPILOT and self.vehicle_state.speed > self.autopilot_activation_max_speed:
            return False

        if self.environment_state.road_conditions in ['snow', 'ice']:
            return mode != DrivingMode.AUTOPILOT

        return True

    def update_sensor_data(self, vehicle_state: VehicleState, environment_state: EnvironmentState) -> None:
        """Update sensor data for decision making."""
        self.vehicle_state = vehicle_state
        self.environment_state = environment_state

    def make_driving_decision(self) -> DrivingCommand:
        """Make high-level driving decision based on current state."""
        if not self.is_active or not self.vehicle_state or not self.environment_state:
            return self._create_neutral_command()

        if self.current_mode == DrivingMode.EMERGENCY:
            return self._handle_emergency()

        # Check for emergency situations first
        emergency_command = self._check_emergency_conditions()
        if emergency_command:
            return emergency_command

        # Make mode-specific decisions
        if self.current_mode == DrivingMode.ASSIST:
            return self._assist_mode_decision()
        elif self.current_mode == DrivingMode.AUTOPILOT:
            return self._autopilot_mode_decision()
        else:
            return self._create_neutral_command()

    def _check_emergency_conditions(self) -> Optional[DrivingCommand]:
        """Check for emergency conditions requiring immediate action."""
        for obj in self.environment_state.detected_objects:
            if obj.get('distance', float('inf')) < self.emergency_brake_threshold:
                return DrivingCommand(
                    steering_angle=0.0,
                    throttle=0.0,
                    brake=1.0,
                    emergency_brake=True
                )
        return None

    def _assist_mode_decision(self) -> DrivingCommand:
        """Make driving decision in assist mode."""
        steering_angle = self._calculate_lane_keeping_steering()
        throttle, brake = self._calculate_adaptive_cruise()

        return DrivingCommand(
            steering_angle=steering_angle,
            throttle=throttle,
            brake=brake,
            emergency_brake=False
        )

    def _autopilot_mode_decision(self) -> DrivingCommand:
        """Make driving decision in full autopilot mode."""
        steering_angle = self._calculate_path_following_steering()
        throttle, brake = self._calculate_speed_control()

        return DrivingCommand(
            steering_angle=steering_angle,
            throttle=throttle,
            brake=brake,
            emergency_brake=False
        )

    def _calculate_lane_keeping_steering(self) -> float:
        """Calculate steering angle for lane keeping."""
        if not self.environment_state.lane_info:
            return 0.0

        closest_lane = min(self.environment_state.lane_info,
                          key=lambda lane: abs(lane.get('distance_to_lane', 0)))

        distance_to_center = closest_lane.get('distance_to_lane', 0)
        steering_gain = self.lane_steering_gain

        return -distance_to_center * steering_gain

    def _calculate_adaptive_cruise(self) -> Tuple[float, float]:
        """Calculate throttle and brake for adaptive cruise control."""
        closest_vehicle = None
        min_distance = float('inf')

        for obj in self.environment_state.detected_objects:
            if obj.get('class_name') in self.adaptive_cruise_vehicle_classes:
                distance = obj.get('distance', float('inf'))
                if distance < min_distance:
                    min_distance = distance
                    closest_vehicle = obj

        if closest_vehicle and min_distance < (
            self.min_following_distance * self.adaptive_cruise_follow_distance_multiplier
        ):
            target_speed = min(self.assist_target_speed, closest_vehicle.get('speed', 0))
            return self._calculate_speed_control(target_speed)
        else:
            return self._calculate_speed_control(self.assist_target_speed)

    def _calculate_path_following_steering(self) -> float:
        """Calculate steering angle for path following."""
        return self._calculate_lane_keeping_steering()

    def _calculate_speed_control(self, target_speed: float = 25.0) -> Tuple[float, float]:
        """Calculate throttle and brake to achieve target speed."""
        current_speed = self.vehicle_state.speed
        speed_error = target_speed - current_speed

        if speed_error > self.speed_control_deadband:
            throttle = min(1.0, speed_error * self.speed_control_throttle_gain)
            brake = 0.0
        elif speed_error < -self.speed_control_deadband:
            throttle = 0.0
            brake = min(1.0, abs(speed_error) * self.speed_control_brake_gain)
        else:
            throttle = self.speed_control_hold_throttle
            brake = 0.0

        return throttle, brake

    def _handle_emergency(self) -> DrivingCommand:
        """Handle emergency driving mode."""
        return DrivingCommand(
            steering_angle=0.0,
            throttle=0.0,
            brake=1.0,
            emergency_brake=True
        )

    def _create_neutral_command(self) -> DrivingCommand:
        """Create neutral driving command."""
        return DrivingCommand(
            steering_angle=0.0,
            throttle=0.0,
            brake=0.0,
            emergency_brake=False
        )

    def get_system_status(self) -> Dict:
        """Get current autopilot system status."""
        return {
            'is_active': self.is_active,
            'current_mode': self.current_mode.value,
            'vehicle_state_available': self.vehicle_state is not None,
            'environment_state_available': self.environment_state is not None,
            'safety_parameters': {
                'min_following_distance': self.min_following_distance,
                'max_speed': self.max_speed,
                'emergency_brake_threshold': self.emergency_brake_threshold,
                'autopilot_activation_max_speed': self.autopilot_activation_max_speed,
                'assist_target_speed': self.assist_target_speed,
                'speed_control_deadband': self.speed_control_deadband,
                'speed_control_throttle_gain': self.speed_control_throttle_gain,
                'speed_control_brake_gain': self.speed_control_brake_gain,
                'speed_control_hold_throttle': self.speed_control_hold_throttle,
                'lane_steering_gain': self.lane_steering_gain,
                'adaptive_cruise_follow_distance_multiplier': self.adaptive_cruise_follow_distance_multiplier
            }
        }

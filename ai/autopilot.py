"""Autopilot system for high-level autonomous driving decisions.

This module keeps the existing rule-based logic but can also consume
NVIDIA Alpamayo-compatible predictors when configured.
"""

from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple


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


class _CallablePredictorAdapter:
    """Adapt a plain callable to a predictor-like object."""

    def __init__(self, func: Callable[[Dict[str, Any]], Dict[str, Any]]):
        self._func = func

    def predict(self, scene_payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._func(scene_payload)


class AutopilotSystem:
    """High-level autonomous driving system."""

    _DEFAULT_VEHICLE_LIMITS: Dict[str, Dict[str, float]] = {
        "general": {
            "max_steering_angle": 0.7,
            "max_throttle": 1.0,
            "max_brake": 1.0,
        },
        "city_car": {
            "max_steering_angle": 0.85,
            "max_throttle": 0.8,
            "max_brake": 1.0,
        },
        "suv": {
            "max_steering_angle": 0.6,
            "max_throttle": 0.9,
            "max_brake": 1.0,
        },
        "truck": {
            "max_steering_angle": 0.45,
            "max_throttle": 0.7,
            "max_brake": 1.0,
        },
    }

    def __init__(
        self,
        config: Dict[str, Any],
        alpamayo_predictor: Optional[Any] = None,
    ):
        """Initialize the autopilot system."""
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.current_mode = DrivingMode.MANUAL
        self.vehicle_state: Optional[VehicleState] = None
        self.environment_state: Optional[EnvironmentState] = None
        self.is_active = False

        # Safety parameters
        self.min_following_distance = config.get("min_following_distance", 2.0)
        self.max_speed = config.get("max_speed", 30.0)
        self.emergency_brake_threshold = config.get("emergency_brake_threshold", 1.5)
        self.autopilot_activation_max_speed = config.get("autopilot_activation_max_speed", 25.0)
        self.assist_target_speed = config.get("assist_target_speed", 25.0)
        self.speed_control_deadband = config.get("speed_control_deadband", 0.5)
        self.speed_control_throttle_gain = config.get("speed_control_throttle_gain", 0.2)
        self.speed_control_brake_gain = config.get("speed_control_brake_gain", 0.3)
        self.speed_control_hold_throttle = config.get("speed_control_hold_throttle", 0.1)
        self.lane_steering_gain = config.get("lane_steering_gain", 0.1)
        self.adaptive_cruise_follow_distance_multiplier = config.get(
            "adaptive_cruise_follow_distance_multiplier", 3.0
        )
        self.adaptive_cruise_vehicle_classes = config.get(
            "adaptive_cruise_vehicle_classes", ["car", "truck", "bus"]
        )

        # Vehicle profile parameters (for generic vehicle handling envelopes)
        self.vehicle_profile = str(config.get("vehicle_profile", "general")).lower()
        self.vehicle_limits = self._resolve_vehicle_limits()

        # Alpamayo/provider selection
        self.autonomy_provider = str(config.get("autonomy_provider", "rule_based")).lower()
        self.alpamayo_enabled = bool(
            config.get("alpamayo_enabled", self.autonomy_provider == "alpamayo")
        )
        self.alpamayo_fallback_to_rule_based = bool(
            config.get("alpamayo_fallback_to_rule_based", True)
        )
        self.alpamayo_adapter_module = config.get("alpamayo_adapter_module")
        self.alpamayo_adapter_class = config.get("alpamayo_adapter_class")
        self.alpamayo_import_candidates = config.get(
            "alpamayo_import_candidates", ["alpamayo", "alpamayo_tools"]
        )

        self._alpamayo_predictor: Optional[Any] = alpamayo_predictor
        self._alpamayo_backend_module: Optional[str] = None
        self._alpamayo_ready = False
        self._alpamayo_fallback_active = False
        self._alpamayo_last_error: Optional[str] = None
        self._initialize_alpamayo_backend()

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

        if self.environment_state.road_conditions in ["snow", "ice"]:
            return mode != DrivingMode.AUTOPILOT

        return True

    def _resolve_vehicle_limits(self) -> Dict[str, float]:
        """Resolve per-vehicle profile command limits."""
        limits_by_profile = dict(self._DEFAULT_VEHICLE_LIMITS)

        configured_profiles = self.config.get("vehicle_profiles", {})
        if isinstance(configured_profiles, dict):
            for profile_name, profile_limits in configured_profiles.items():
                if isinstance(profile_limits, dict):
                    base = dict(self._DEFAULT_VEHICLE_LIMITS["general"])
                    base.update(profile_limits)
                    limits_by_profile[str(profile_name).lower()] = base

        selected_limits = dict(
            limits_by_profile.get(self.vehicle_profile, limits_by_profile["general"])
        )
        selected_limits["max_steering_angle"] = float(
            self.config.get("max_steering_angle", selected_limits.get("max_steering_angle", 0.7))
        )
        selected_limits["max_throttle"] = float(
            self.config.get("max_throttle", selected_limits.get("max_throttle", 1.0))
        )
        selected_limits["max_brake"] = float(
            self.config.get("max_brake", selected_limits.get("max_brake", 1.0))
        )
        return selected_limits

    def _initialize_alpamayo_backend(self) -> None:
        """Initialize optional Alpamayo predictor backend if configured."""
        if not self.alpamayo_enabled:
            return

        if self._alpamayo_predictor is not None:
            self._alpamayo_ready = True
            self._alpamayo_backend_module = "injected"
            return

        # User-provided adapter path has priority.
        if self.alpamayo_adapter_module and self.alpamayo_adapter_class:
            try:
                module = importlib.import_module(str(self.alpamayo_adapter_module))
                predictor_cls = getattr(module, str(self.alpamayo_adapter_class))
                try:
                    self._alpamayo_predictor = predictor_cls(config=self.config)
                except TypeError:
                    self._alpamayo_predictor = predictor_cls(self.config)
                self._alpamayo_ready = True
                self._alpamayo_backend_module = str(self.alpamayo_adapter_module)
                return
            except Exception as exc:  # pragma: no cover - defensive path
                self._alpamayo_last_error = f"adapter_init_failed: {exc}"

        # Best-effort discovery from known module candidates.
        for module_name in self.alpamayo_import_candidates:
            try:
                module = importlib.import_module(module_name)
                self._alpamayo_backend_module = module_name
                discovered_predictor = self._discover_predictor_from_module(module)
                if discovered_predictor is not None:
                    self._alpamayo_predictor = discovered_predictor
                    self._alpamayo_ready = True
                return
            except ImportError:
                continue
            except Exception as exc:  # pragma: no cover - defensive path
                self._alpamayo_last_error = f"module_init_failed({module_name}): {exc}"

        self._alpamayo_ready = False

    def _discover_predictor_from_module(self, module: Any) -> Optional[Any]:
        """Discover a predictor factory from a loaded module."""
        for factory_name in ("build_autopilot_predictor", "build_predictor"):
            factory = getattr(module, factory_name, None)
            if callable(factory):
                try:
                    return factory(self.config)
                except TypeError:
                    return factory()

        for class_name in ("AlpamayoPredictor", "AutopilotPredictor"):
            predictor_cls = getattr(module, class_name, None)
            if predictor_cls is not None:
                try:
                    return predictor_cls(config=self.config)
                except TypeError:
                    try:
                        return predictor_cls(self.config)
                    except TypeError:
                        return predictor_cls()

        predict_callable = getattr(module, "predict_command", None)
        if callable(predict_callable):
            return _CallablePredictorAdapter(predict_callable)

        return None

    def update_sensor_data(
        self,
        vehicle_state: Optional[VehicleState],
        environment_state: Optional[EnvironmentState],
    ) -> None:
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
        if self.current_mode == DrivingMode.AUTOPILOT:
            return self._autopilot_mode_decision()
        return self._create_neutral_command()

    def _check_emergency_conditions(self) -> Optional[DrivingCommand]:
        """Check for emergency conditions requiring immediate action."""
        if not self.environment_state:
            return None

        for obj in self.environment_state.detected_objects:
            if obj.get("distance", float("inf")) < self.emergency_brake_threshold:
                return self._limit_command(
                    DrivingCommand(
                        steering_angle=0.0,
                        throttle=0.0,
                        brake=1.0,
                        emergency_brake=True,
                    )
                )
        return None

    def _assist_mode_decision(self) -> DrivingCommand:
        """Make driving decision in assist mode."""
        steering_angle = self._calculate_lane_keeping_steering()
        throttle, brake = self._calculate_adaptive_cruise()
        return self._limit_command(
            DrivingCommand(
                steering_angle=steering_angle,
                throttle=throttle,
                brake=brake,
                emergency_brake=False,
            )
        )

    def _autopilot_mode_decision(self) -> DrivingCommand:
        """Make driving decision in full autopilot mode."""
        if self.autonomy_provider == "alpamayo" and self.alpamayo_enabled:
            alpamayo_command = self._alpamayo_mode_decision()
            if alpamayo_command is not None:
                return alpamayo_command

            self._alpamayo_fallback_active = True
            if not self.alpamayo_fallback_to_rule_based:
                return self._handle_emergency()

        steering_angle = self._calculate_path_following_steering()
        throttle, brake = self._calculate_speed_control()
        return self._limit_command(
            DrivingCommand(
                steering_angle=steering_angle,
                throttle=throttle,
                brake=brake,
                emergency_brake=False,
            )
        )

    def _alpamayo_mode_decision(self) -> Optional[DrivingCommand]:
        """Use Alpamayo predictor for high-level decision making."""
        if not self._alpamayo_ready or self._alpamayo_predictor is None:
            return None

        try:
            scene_payload = self._build_scene_payload()
            predictor = self._alpamayo_predictor

            if hasattr(predictor, "predict"):
                prediction = predictor.predict(scene_payload)
            elif hasattr(predictor, "predict_command"):
                prediction = predictor.predict_command(scene_payload)
            elif callable(predictor):
                prediction = predictor(scene_payload)
            else:
                self._alpamayo_last_error = "predictor_not_callable"
                return None

            if not isinstance(prediction, dict):
                self._alpamayo_last_error = "invalid_prediction_type"
                return None

            steering_angle = self._coerce_float(
                prediction.get("steering_angle", prediction.get("steering", 0.0))
            )
            throttle = self._coerce_float(
                prediction.get("throttle", prediction.get("acceleration", 0.0))
            )
            brake = self._coerce_float(prediction.get("brake", 0.0))
            emergency_brake = bool(
                prediction.get("emergency_brake", prediction.get("hard_brake", False))
            )

            if emergency_brake and brake <= 0:
                brake = 1.0
                throttle = 0.0

            return self._limit_command(
                DrivingCommand(
                    steering_angle=steering_angle,
                    throttle=throttle,
                    brake=brake,
                    emergency_brake=emergency_brake,
                )
            )
        except Exception as exc:  # pragma: no cover - defensive path
            self._alpamayo_last_error = f"predict_failed: {exc}"
            return None

    def _build_scene_payload(self) -> Dict[str, Any]:
        """Build a normalized scene payload for the autonomy provider."""
        assert self.vehicle_state is not None
        assert self.environment_state is not None

        return {
            "vehicle_profile": self.vehicle_profile,
            "ego_vehicle": {
                "position": self.vehicle_state.position,
                "velocity": self.vehicle_state.velocity,
                "heading": self.vehicle_state.heading,
                "speed": self.vehicle_state.speed,
            },
            "environment": {
                "detected_objects": self.environment_state.detected_objects,
                "lane_info": self.environment_state.lane_info,
                "traffic_lights": self.environment_state.traffic_lights,
                "road_conditions": self.environment_state.road_conditions,
            },
            "limits": self.vehicle_limits,
        }

    def _coerce_float(self, value: Any) -> float:
        """Convert arbitrary value to float, defaulting to zero."""
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _limit_command(self, command: DrivingCommand) -> DrivingCommand:
        """Apply vehicle-profile command limits to a command."""
        max_steering = max(0.0, float(self.vehicle_limits.get("max_steering_angle", 0.7)))
        max_throttle = max(0.0, float(self.vehicle_limits.get("max_throttle", 1.0)))
        max_brake = max(0.0, float(self.vehicle_limits.get("max_brake", 1.0)))

        steering = max(-max_steering, min(max_steering, command.steering_angle))
        throttle = max(0.0, min(max_throttle, command.throttle))
        brake = max(0.0, min(max_brake, command.brake))

        if command.emergency_brake:
            throttle = 0.0
            brake = max_brake

        return DrivingCommand(
            steering_angle=steering,
            throttle=throttle,
            brake=brake,
            emergency_brake=command.emergency_brake,
        )

    def _calculate_lane_keeping_steering(self) -> float:
        """Calculate steering angle for lane keeping."""
        if not self.environment_state or not self.environment_state.lane_info:
            return 0.0

        closest_lane = min(
            self.environment_state.lane_info,
            key=lambda lane: abs(lane.get("distance_to_lane", 0)),
        )
        distance_to_center = closest_lane.get("distance_to_lane", 0)
        return -distance_to_center * self.lane_steering_gain

    def _calculate_adaptive_cruise(self) -> Tuple[float, float]:
        """Calculate throttle and brake for adaptive cruise control."""
        if not self.environment_state:
            return 0.0, 0.0

        closest_vehicle = None
        min_distance = float("inf")

        for obj in self.environment_state.detected_objects:
            if obj.get("class_name") in self.adaptive_cruise_vehicle_classes:
                distance = obj.get("distance", float("inf"))
                if distance < min_distance:
                    min_distance = distance
                    closest_vehicle = obj

        if closest_vehicle and min_distance < (
            self.min_following_distance * self.adaptive_cruise_follow_distance_multiplier
        ):
            target_speed = min(self.assist_target_speed, closest_vehicle.get("speed", 0))
            return self._calculate_speed_control(target_speed)
        return self._calculate_speed_control(self.assist_target_speed)

    def _calculate_path_following_steering(self) -> float:
        """Calculate steering angle for path following."""
        return self._calculate_lane_keeping_steering()

    def _calculate_speed_control(self, target_speed: float = 25.0) -> Tuple[float, float]:
        """Calculate throttle and brake to achieve target speed."""
        if not self.vehicle_state:
            return 0.0, 0.0

        bounded_target_speed = min(target_speed, self.max_speed)
        current_speed = self.vehicle_state.speed
        speed_error = bounded_target_speed - current_speed

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
        return self._limit_command(
            DrivingCommand(
                steering_angle=0.0,
                throttle=0.0,
                brake=1.0,
                emergency_brake=True,
            )
        )

    def _create_neutral_command(self) -> DrivingCommand:
        """Create neutral driving command."""
        return DrivingCommand(
            steering_angle=0.0,
            throttle=0.0,
            brake=0.0,
            emergency_brake=False,
        )

    def get_system_status(self) -> Dict[str, Any]:
        """Get current autopilot system status."""
        return {
            "is_active": self.is_active,
            "current_mode": self.current_mode.value,
            "vehicle_state_available": self.vehicle_state is not None,
            "environment_state_available": self.environment_state is not None,
            "safety_parameters": {
                "min_following_distance": self.min_following_distance,
                "max_speed": self.max_speed,
                "emergency_brake_threshold": self.emergency_brake_threshold,
                "autopilot_activation_max_speed": self.autopilot_activation_max_speed,
                "assist_target_speed": self.assist_target_speed,
                "speed_control_deadband": self.speed_control_deadband,
                "speed_control_throttle_gain": self.speed_control_throttle_gain,
                "speed_control_brake_gain": self.speed_control_brake_gain,
                "speed_control_hold_throttle": self.speed_control_hold_throttle,
                "lane_steering_gain": self.lane_steering_gain,
                "adaptive_cruise_follow_distance_multiplier": (
                    self.adaptive_cruise_follow_distance_multiplier
                ),
            },
            "autonomy": {
                "provider": self.autonomy_provider,
                "alpamayo_enabled": self.alpamayo_enabled,
                "alpamayo_ready": self._alpamayo_ready,
                "alpamayo_backend_module": self._alpamayo_backend_module,
                "alpamayo_fallback_active": self._alpamayo_fallback_active,
                "alpamayo_last_error": self._alpamayo_last_error,
            },
            "vehicle_profile": self.vehicle_profile,
            "vehicle_limits": self.vehicle_limits,
        }

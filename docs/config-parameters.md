# EV System Configuration Parameters

This document describes configuration parameters used by runtime code in
`config/config.json`.

If a parameter is omitted, the code falls back to the default shown in this
document. Validation rules are defined in `config/config_schema.json`.

## 1) runtime

| Key | Type | Default | Description |
|---|---|---:|---|
| `main_loop_interval_s` | number | `0.1` | Main EV update loop sleep interval. |
| `dashboard_thread_join_timeout_s` | number | `2.0` | Max wait during dashboard shutdown join. |
| `default_temperature_c` | number | `25.0` | Fallback temperature when sensors are unavailable. |

## 2) vehicle

| Key | Type | Description |
|---|---|---|
| `model` | string | Vehicle model identifier. |
| `serial_number` | string | Unique vehicle ID used across telemetry/logging. |
| `manufacturer` | string | Manufacturer name. |

## 3) battery

### Core limits

`capacity_kwh`, `max_charge_rate_kw`, `max_discharge_rate_kw`,
`nominal_voltage`, `cell_count`, `min_voltage`, `max_voltage`,
`min_temperature`, `max_temperature`, `min_soc`, `max_soc`.

### Balancing controls

| Key | Default | Description |
|---|---:|---|
| `balancing_enabled` | `true` | Enables balancing algorithm execution. |
| `balancing_algorithm` | `"adaptive"` | One of: `none`, `passive`, `active`, `adaptive`. |
| `balancing_threshold_mv` | `50.0` | Min cell delta to start balancing. |
| `passive_bleed_current_ma` | `100.0` | Passive balancing bleed current. |
| `active_balance_efficiency` | `0.85` | Active balancing transfer efficiency factor. |
| `balancing_min_soc` | `20.0` | Lower SOC bound for balancing. |
| `balancing_max_soc` | `95.0` | Upper SOC bound for balancing. |
| `adaptive_active_balance_threshold_mv` | `200.0` | Adaptive mode switch threshold (passive -> active). |
| `active_balance_transfer_rate_per_s` | `0.5` | Active transfer rate scale. |
| `active_balance_transfer_cap_ratio` | `0.1` | Max transfer ratio per update step. |

### Status thresholds

| Key | Default | Description |
|---|---:|---|
| `status_critical_soc_low` / `status_critical_soc_high` | `5.0` / `95.0` | SOC range that triggers `CRITICAL`. |
| `status_warning_soc_low` / `status_warning_soc_high` | `10.0` / `90.0` | SOC range that triggers `WARNING`. |
| `status_voltage_imbalance_fault_v` | `0.5` | Cell spread above this triggers `FAULT`. |
| `status_uniform_temperature_spread_c` | `1.0` | Spread threshold for pack-uniform thermal critical check. |
| `status_charge_current_threshold_a` | `0.1` | Current threshold to classify charging/discharging state. |
| `status_warning_temp_high_ratio` | `0.9` | Warning threshold ratio of `max_temperature`. |
| `status_warning_temp_low_ratio` | `1.1` | Warning threshold ratio of `min_temperature`. |

### Charge cycle detection

| Key | Default | Description |
|---|---:|---|
| `charge_cycle_soc_low_threshold` | `20.0` | Low SOC boundary for cycle swing detection. |
| `charge_cycle_soc_high_threshold` | `80.0` | High SOC boundary for cycle swing detection. |
| `charge_cycle_partial_energy_ratio` | `0.8` | Partial cycle energy threshold (x capacity). |
| `charge_cycle_full_energy_ratio` | `1.6` | Full throughput cycle threshold (x capacity). |

### SOH model coefficients

| Key | Default | Description |
|---|---:|---|
| `soh_temperature_history_days` | `30.0` | SOH thermal history window. |
| `soh_high_temperature_threshold_c` | `40.0` | High temp threshold for accelerated aging. |
| `soh_cycle_degradation_per_cycle_pct` | `0.05` | Capacity fade per detected cycle. |
| `soh_high_temp_degradation_per_hour_pct` | `0.00417` | Extra fade per high-temp hour. |
| `soh_fault_degradation_per_fault_pct` | `0.1` | Extra fade per fault event. |
| `soh_calendar_degradation_per_year_pct` | `2.5` | Baseline calendar fade per year. |
| `soh_calendar_temperature_reference_c` | `25.0` | Temperature reference for calendar aging. |
| `soh_calendar_temp_factor_per_10c` | `0.5` | Added aging factor per +10C over reference. |

## 4) motor / motor_controller

`motor` contains drivetrain capability (`max_power_kw`, `max_torque_nm`,
`efficiency`, `type`).

`motor_controller` contains controller/hardware constraints and comms settings:
`type`, `serial_port`, `can_enabled`, `max_current_a`, `max_rpm`,
`max_temperature_c`, `min_voltage_v`, `max_voltage_v`, `update_interval_ms`.

## 5) charging

`ac_max_power_kw`, `dc_max_power_kw`, `connector_type`, `fast_charge_enabled`,
`max_temperature_c`, `max_voltage_v`, `min_voltage_v`.

## 6) sensors

Top-level sensor enablement and base sampling:
`imu_enabled`, `gps_enabled`, `temperature_sensors`, `sampling_rate_hz`.

## 7) imu

Sensor transport, calibration, and simulation toggles:
`sensor_type`, `i2c_address`, `i2c_bus`, `sampling_rate_hz`, `simulation_mode`,
`calibration_samples`, accelerometer/gyro/magnetometer offsets.

## 8) gps

| Key | Default | Description |
|---|---:|---|
| `serial_port` | `null` | Serial NMEA source. If null, simulation can be used. |
| `baudrate` | `9600` | GPS serial baud rate. |
| `update_interval_s` | `1.0` | GPS update poll interval. |
| `simulation_mode` | `true` | Uses synthetic circular trajectory. |
| `simulation_base_latitude` / `simulation_base_longitude` | `37.4219999` / `-122.0840575` | Reference center point. |
| `simulation_radius_deg` | `0.0003` | Circular route radius in degrees. |
| `simulation_angle_rate` | `0.1` | Angular speed of simulated trajectory. |
| `simulation_speed_base_kmh` | `10.0` | Base synthetic speed. |
| `simulation_speed_amplitude_kmh` | `2.0` | Speed oscillation amplitude. |
| `simulation_altitude_m` | `5.0` | Simulated altitude. |
| `simulation_satellites` | `8` | Simulated satellite count. |
| `simulation_hdop` | `0.9` | Simulated HDOP. |

## 9) temperature_sensors

### Global controls

`enabled`, `cells_per_group`, `update_interval_s`, `coolant_enabled`,
`motor_stator_enabled`, `motor_stator_sensors`, `charging_enabled`.

### Sensor profile blocks

Each of these supports:
`min_temperature`, `max_temperature`, `warning_threshold_low`,
`warning_threshold_high`, `fault_threshold_low`, `fault_threshold_high`.

Blocks:
- `battery_cell_group`
- `coolant`
- `motor_stator`
- `charging`

Backward-compatible legacy block:
- `battery` (legacy min/max fallback for battery groups)

## 10) communication / can_bus

`communication`:
- `can_bus_enabled`
- `update_interval_ms`

`can_bus`:
- `channel`
- `bitrate`
- `interface`

## 11) vehicle_controller

Base physics and limits:
`max_speed_kmh`, `max_acceleration_ms2`, `max_deceleration_ms2`,
`max_power_kw`, `efficiency_wh_per_km`, `weight_kg`.

Drive behavior tuning:
- `drive_mode_multiplier_eco`
- `drive_mode_multiplier_normal`
- `drive_mode_multiplier_sport`
- `drive_mode_multiplier_reverse`
- `min_soc_to_drive`
- `regen_max_current_a`
- `rpm_to_speed_factor_kmh`
- `speed_zero_threshold_kmh`

## 12) telemetry

`enabled`, `server_url`, `server_port`, `api_key`, `update_interval_s`,
`connection_timeout_s`, `retry_attempts`, `retry_delay_s`, `use_ssl`,
`cellular_apn`, `cellular_username`, `cellular_password`, `simulation_mode`.

## 13) ui

`dashboard_enabled`, `mobile_app_enabled`, `theme`, `dashboard_host`,
`dashboard_port`, `dashboard_debug`, plus dashboard runtime controls:
- `dashboard_secret_key`
- `dashboard_update_interval_s`
- `dashboard_socketio_cors`

## 14) ai

Core flags:
- `autopilot_enabled`
- `computer_vision_enabled`
- `model_path`

Autopilot safety/tuning:
- `min_following_distance`
- `max_speed`
- `emergency_brake_threshold`
- `autopilot_activation_max_speed`
- `assist_target_speed`
- `speed_control_deadband`
- `speed_control_throttle_gain`
- `speed_control_brake_gain`
- `speed_control_hold_throttle`
- `lane_steering_gain`
- `adaptive_cruise_follow_distance_multiplier`
- `adaptive_cruise_vehicle_classes`

## 15) safety_system

Thermal/electrical thresholds and monitoring windows:
- `battery_temp_max`, `battery_temp_warning`
- `motor_temp_max`, `motor_temp_warning`
- `thermal_runaway_rate`, `thermal_runaway_threshold`
- `thermal_history_max_samples`
- `thermal_runaway_window_samples`
- `voltage_max`, `voltage_min`, `current_max`
- `max_fault_history`
- `diagnostics_log_dir`

## 16) diagnostics

Diagnostics subsystem sizing and limp-home tuning:
- `dtc_max_history_size`
- `dtc_export_history_limit`
- `mode_history_limit`
- `fault_log_max_file_size_mb`
- `fault_json_max_entries`
- `limp_home_profiles`:
  - `normal`
  - `reduced_power`
  - `limited_speed`
  - `emergency_only`
  - `disabled`

Each profile contains:
`max_speed_kmh`, `max_power_kw`, `max_acceleration_ms2`, `max_current_a`,
`charging_allowed`, `autopilot_allowed`.

## 17) logging

`level`, `file_path`, `max_file_size_mb`, `backup_count`.


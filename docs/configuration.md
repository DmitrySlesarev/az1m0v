# EV System Configuration Documentation

This document describes all configuration parameters available in the EV system configuration file (`config/config.json`).

## Overview

The EV system configuration is stored in JSON format and validated against a JSON schema. The configuration is organized into logical sections covering vehicle specifications, battery management, motor control, charging systems, sensors, communication, user interface, AI features, and logging.

## Configuration Sections

### Vehicle Configuration

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `model` | string | Vehicle model identifier | "EV-2024" |
| `serial_number` | string | Unique vehicle serial number | "EV001" |
| `manufacturer` | string | Vehicle manufacturer name | "EV Corp" |

### Battery Configuration

| Parameter | Type | Description | Range/Units | Example |
|-----------|------|-------------|-------------|---------|
| `capacity_kwh` | number | Total battery capacity | ≥ 0 kWh | 75.0 |
| `max_charge_rate_kw` | number | Maximum charging power | ≥ 0 kW | 150.0 |
| `max_discharge_rate_kw` | number | Maximum discharge power | ≥ 0 kW | 200.0 |
| `nominal_voltage` | number | Nominal battery voltage | ≥ 0 V | 400.0 |
| `cell_count` | integer | Number of battery cells | ≥ 1 | 96 |

### Motor Configuration

| Parameter | Type | Description | Range/Units | Example |
|-----------|------|-------------|-------------|---------|
| `max_power_kw` | number | Maximum motor power output | ≥ 0 kW | 150.0 |
| `max_torque_nm` | number | Maximum motor torque | ≥ 0 N⋅m | 320.0 |
| `efficiency` | number | Motor efficiency factor | 0.0 - 1.0 | 0.95 |
| `type` | string | Motor type | permanent_magnet, induction, switched_reluctance | "permanent_magnet" |

### Charging Configuration

| Parameter | Type | Description | Range/Units | Example |
|-----------|------|-------------|-------------|---------|
| `ac_max_power_kw` | number | Maximum AC charging power | ≥ 0 kW | 11.0 |
| `dc_max_power_kw` | number | Maximum DC fast charging power | ≥ 0 kW | 150.0 |
| `connector_type` | string | Charging connector standard | CCS1, CCS2, CHAdeMO, Tesla | "CCS2" |
| `fast_charge_enabled` | boolean | Enable fast charging capability | true/false | true |

### Vehicle Controller Configuration

| Parameter | Type | Description | Range/Units | Example |
|-----------|------|-------------|-------------|---------|
| `max_speed_kmh` | number | Maximum vehicle speed | ≥ 0 km/h | 120.0 |
| `max_acceleration_ms2` | number | Maximum acceleration | ≥ 0 m/s² | 3.0 |
| `max_deceleration_ms2` | number | Maximum deceleration (braking) | ≤ 0 m/s² | -5.0 |
| `max_power_kw` | number | Maximum vehicle power output | ≥ 0 kW | 150.0 |
| `efficiency_wh_per_km` | number | Energy consumption per kilometer | ≥ 0 Wh/km | 200.0 |
| `weight_kg` | number | Vehicle weight | ≥ 0 kg | 1500.0 |

### Sensor Configuration

| Parameter | Type | Description | Range/Units | Example |
|-----------|------|-------------|-------------|---------|
| `imu_enabled` | boolean | Enable Inertial Measurement Unit | true/false | true |
| `gps_enabled` | boolean | Enable GPS positioning | true/false | true |
| `temperature_sensors` | integer | Number of temperature sensors | ≥ 0 | 8 |
| `sampling_rate_hz` | number | Sensor data sampling frequency | ≥ 0 Hz | 100 |

### Communication Configuration

| Parameter | Type | Description | Range/Units | Example |
|-----------|------|-------------|-------------|---------|
| `can_bus_enabled` | boolean | Enable CAN bus communication | true/false | true |
| `telemetry_enabled` | boolean | Enable telemetry data transmission | true/false | true |
| `update_interval_ms` | integer | Communication update interval | ≥ 1 ms | 1000 |

### User Interface Configuration

| Parameter | Type | Description | Options | Example |
|-----------|------|-------------|---------|---------|
| `dashboard_enabled` | boolean | Enable dashboard interface | true/false | true |
| `mobile_app_enabled` | boolean | Enable mobile app interface | true/false | true |
| `theme` | string | UI theme preference | light, dark, auto | "dark" |

### AI Configuration

| Parameter | Type | Description | Range/Units | Example |
|-----------|------|-------------|-------------|---------|
| `autopilot_enabled` | boolean | Enable autopilot functionality | true/false | false |
| `computer_vision_enabled` | boolean | Enable computer vision features | true/false | false |
| `model_path` | string | Path to AI model files | Valid file path | "/models/" |

### Logging Configuration

| Parameter | Type | Description | Range/Options | Example |
|-----------|------|-------------|---------------|---------|
| `level` | string | Logging verbosity level | DEBUG, INFO, WARNING, ERROR, CRITICAL | "INFO" |
| `file_path` | string | Log file location | Valid file path | "/var/log/ev_system.log" |
| `max_file_size_mb` | integer | Maximum log file size | ≥ 1 MB | 100 |
| `backup_count` | integer | Number of backup log files | ≥ 0 | 5 |

## Configuration Validation

The configuration file is validated against `config/config_schema.json` which ensures:

- All required parameters are present
- Data types match expected types
- Numeric values are within valid ranges
- String values match allowed enumerations
- File paths are properly formatted

## Usage Examples

### Loading Configuration

```python
import json
from pathlib import Path

def load_config(config_path: str = "config/config.json") -> dict:
    """Load and return configuration dictionary."""
    with open(config_path, 'r') as f:
        return json.load(f)

# Load configuration
config = load_config()
battery_capacity = config['battery']['capacity_kwh']
```

### Vehicle Controller Configuration Example

```json
{
  "vehicle_controller": {
    "max_speed_kmh": 120.0,
    "max_acceleration_ms2": 3.0,
    "max_deceleration_ms2": -5.0,
    "max_power_kw": 150.0,
    "efficiency_wh_per_km": 200.0,
    "weight_kg": 1500.0
  }
}
```

The vehicle controller coordinates all subsystems and enforces safety rules. Key features:
- **State Management**: Manages vehicle states (PARKED, READY, DRIVING, CHARGING, ERROR, EMERGENCY)
- **Safety Enforcement**: Prevents driving while charging and vice versa
- **Drive Modes**: Supports ECO, NORMAL, SPORT, and REVERSE modes
- **Range Calculation**: Estimates remaining range based on battery SOC and efficiency
- **Energy Tracking**: Monitors energy consumption and distance traveled

### Validating Configuration

```python
import jsonschema
import json

def validate_config(config_path: str, schema_path: str) -> bool:
    """Validate configuration against schema."""
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    with open(schema_path, 'r') as f:
        schema = json.load(f)
    
    try:
        jsonschema.validate(config, schema)
        return True
    except jsonschema.ValidationError as e:
        print(f"Configuration validation error: {e}")
        return False
```

## Best Practices

1. **Backup Configuration**: Always backup your configuration before making changes
2. **Validate Changes**: Use the schema validation before deploying configuration changes
3. **Document Custom Values**: Document any custom parameter values and their rationale
4. **Test Settings**: Test configuration changes in a safe environment first
5. **Version Control**: Keep configuration files under version control

## Troubleshooting

### Common Issues

1. **Invalid JSON**: Ensure proper JSON syntax with correct quotes and commas
2. **Missing Required Fields**: Check that all required parameters are present
3. **Type Mismatches**: Verify numeric values are numbers, not strings
4. **Invalid Enumerations**: Ensure string values match allowed options
5. **File Path Issues**: Verify file paths exist and are accessible

### Validation Errors

When configuration validation fails, check:
- JSON syntax is correct
- All required fields are present
- Data types match schema expectations
- Numeric ranges are within limits
- String values are from allowed enumerations

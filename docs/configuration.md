# EV System Configuration Documentation

This document describes all configuration parameters available in the EV system configuration file (`config/config.json`).

## Overview

The EV system configuration is stored in JSON format and validated against a JSON schema. The configuration is organized into logical sections covering vehicle specifications, battery management, motor control, motor controller hardware, charging systems, sensors, communication, telemetry, user interface, AI features, and logging.

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

### Motor Controller Configuration

| Parameter | Type | Description | Range/Units | Example |
|-----------|------|-------------|-------------|---------|
| `type` | string | Motor controller type | vesc, other | "vesc" |
| `serial_port` | string | Serial port for UART communication | Valid device path | "/dev/ttyUSB0" |
| `can_enabled` | boolean | Enable CAN bus communication | true/false | true |
| `max_current_a` | number | Maximum current limit | ≥ 0 A | 200.0 |
| `max_rpm` | number | Maximum motor RPM | ≥ 0 RPM | 10000.0 |
| `max_temperature_c` | number | Maximum operating temperature | ≥ 0 °C | 80.0 |
| `min_voltage_v` | number | Minimum operating voltage | ≥ 0 V | 300.0 |
| `max_voltage_v` | number | Maximum operating voltage | ≥ 0 V | 500.0 |
| `update_interval_ms` | integer | Controller update interval | ≥ 1 ms | 100 |

### Charging Configuration

| Parameter | Type | Description | Range/Units | Example |
|-----------|------|-------------|-------------|---------|
| `ac_max_power_kw` | number | Maximum AC charging power | ≥ 0 kW | 11.0 |
| `dc_max_power_kw` | number | Maximum DC fast charging power | ≥ 0 kW | 150.0 |
| `connector_type` | string | Charging connector standard | CCS1, CCS2, CHAdeMO, Tesla | "CCS2" |
| `fast_charge_enabled` | boolean | Enable fast charging capability | true/false | true |

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

### Telemetry Configuration

| Parameter | Type | Description | Range/Units | Example |
|-----------|------|-------------|-------------|---------|
| `enabled` | boolean | Enable telemetry system | true/false | true |
| `server_url` | string | Telemetry server URL | Valid URL | "https://telemetry.example.com" |
| `server_port` | integer | Telemetry server port | 1 - 65535 | 443 |
| `api_key` | string | API key for authentication | String | "" |
| `update_interval_s` | number | Telemetry update interval | ≥ 0.1 s | 10.0 |
| `connection_timeout_s` | number | Connection timeout | ≥ 1 s | 30.0 |
| `retry_attempts` | integer | Number of retry attempts | ≥ 0 | 3 |
| `retry_delay_s` | number | Delay between retries | ≥ 0 s | 5.0 |
| `use_ssl` | boolean | Use SSL/TLS encryption | true/false | true |
| `cellular_apn` | string | Cellular APN for connection | String | "internet" |
| `cellular_username` | string | Cellular username | String | "" |
| `cellular_password` | string | Cellular password | String | "" |
| `simulation_mode` | boolean | Enable simulation mode | true/false | true |

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

### Required Configuration Sections

The following sections are required in the configuration file:
- `vehicle` - Vehicle identification information
- `battery` - Battery specifications and limits
- `motor` - Motor specifications
- `motor_controller` - Motor controller hardware configuration
- `charging` - Charging system configuration
- `sensors` - Sensor system configuration
- `communication` - Communication system settings
- `ui` - User interface settings
- `ai` - AI features configuration
- `logging` - Logging system configuration

### Optional Configuration Sections

The following sections are optional but may be included:
- `telemetry` - Telemetry system configuration (for remote monitoring)
- `temperature_sensors` - Advanced temperature sensor configuration (extends basic sensor config)

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

### Motor Controller Configuration Example

```json
{
  "motor_controller": {
    "type": "vesc",
    "serial_port": "/dev/ttyUSB0",
    "can_enabled": true,
    "max_current_a": 200.0,
    "max_rpm": 10000.0,
    "max_temperature_c": 80.0,
    "min_voltage_v": 300.0,
    "max_voltage_v": 500.0,
    "update_interval_ms": 100
  }
}
```

The motor controller manages the VESC (Vedder Electronic Speed Controller) or other motor controller hardware. It provides:
- **Serial Communication**: UART interface for direct motor control
- **CAN Bus Integration**: Optional CAN bus communication for distributed systems
- **Safety Limits**: Enforces current, voltage, temperature, and RPM limits
- **Real-time Monitoring**: Tracks motor status including temperature, current, and RPM

### Telemetry Configuration Example

```json
{
  "telemetry": {
    "enabled": true,
    "server_url": "https://telemetry.example.com",
    "server_port": 443,
    "api_key": "",
    "update_interval_s": 10.0,
    "connection_timeout_s": 30.0,
    "retry_attempts": 3,
    "retry_delay_s": 5.0,
    "use_ssl": true,
    "cellular_apn": "internet",
    "cellular_username": "",
    "cellular_password": "",
    "simulation_mode": true
  }
}
```

The telemetry system enables remote monitoring and data collection. Features include:
- **Remote Data Transmission**: Sends vehicle data to remote servers
- **Cellular Connectivity**: Supports cellular network connections with APN configuration
- **Retry Logic**: Automatic retry with configurable attempts and delays
- **SSL/TLS Security**: Optional encrypted connections
- **Simulation Mode**: Test telemetry without actual hardware connections

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

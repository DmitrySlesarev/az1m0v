# EV System Documentation

Welcome to the Electric Vehicle Management System documentation. This documentation provides comprehensive information about the system architecture, configuration, and usage.

## Documentation Structure

### Configuration Documentation
- **[Configuration Guide](configuration.md)** - Complete reference for all configuration parameters, validation rules, and usage examples

### System Architecture
- **[Architecture Overview](../architecture.txt)** - High-level system structure and component organization

## Quick Start

1. **Configuration Setup**: Start with the [Configuration Guide](configuration.md) to understand and customize system parameters
2. **Installation**: Use the setup script to initialize the environment:
   ```bash
   ./scripts/setup.sh
   ```
3. **Testing**: Run the test suite to verify installation:
   ```bash
   poetry run pytest -q
   ```

## Key Components

### Core Systems
- **Battery Management**: Monitor and control battery operations
- **Motor Controller**: Manage motor performance and efficiency
- **Charging System**: Handle AC/DC charging protocols
- **Vehicle Controller**: Central coordination of all systems

### Sensors & Communication
- **IMU**: Inertial measurement for vehicle dynamics
- **GPS**: Positioning and navigation data
- **Temperature Sensors**: Thermal monitoring
- **CAN Bus**: Vehicle network communication
- **Telemetry**: Remote data transmission

### User Interfaces
- **Dashboard**: Primary control interface
- **Mobile App**: Remote monitoring and control

### AI Features
- **Autopilot**: Autonomous driving capabilities
- **Computer Vision**: Environmental perception

## Configuration Management

The system uses JSON-based configuration with schema validation:

- **Main Config**: `config/config.json` - System parameters
- **Schema**: `config/config_schema.json` - Validation rules
- **Documentation**: `docs/configuration.md` - Parameter reference

## Development

### Project Structure
```
├── core/           # Core system components
├── sensors/        # Sensor interfaces
├── communication/  # Network protocols
├── ui/            # User interfaces
├── ai/            # AI/ML components
├── config/        # Configuration files
├── tests/         # Test suite
├── docs/          # Documentation
└── scripts/       # Utility scripts
```

### Testing
- **Framework**: pytest
- **Run Tests**: `poetry run pytest -q`
- **Coverage**: Add `--cov` flag for coverage reports

### Dependencies
- **Package Manager**: Poetry
- **Install**: `poetry install`

## Support

For questions or issues:
1. Check the configuration documentation
2. Review the test suite for usage examples
3. Validate configuration against the schema
4. Check system logs for error details

## Version Information

- **Current Version**: 0.0.0.1
- **Schema Version**: JSON Schema Draft 07
- **Python Compatibility**: 3.13+

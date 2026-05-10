# EV System Documentation

**az1m0v 1.0.0** — documentation for the first major release.

Welcome to the Electric Vehicle Management System documentation. This documentation provides comprehensive information about the system architecture, configuration, and usage.

## Documentation Structure

### Configuration Documentation
- **[Configuration Guide](configuration.md)** - Complete reference for all configuration parameters, validation rules, and usage examples
- **[Configuration Parameters Reference](config-parameters.md)** - Runtime-focused explanation of each key used by code modules

### System Architecture
- **[Architecture Overview](../architecture.txt)** - High-level system structure and component organization
- **[EV Bench Architecture](EV_BENCH_ARCHITECTURE.md)** - MVP bench topology with Raspberry Pi + CAN + Arduino + RAK4630 and extension to real EV prototype
- **[EV Roadmap and Shopping List](EV_ROADMAP_AND_SHOPPING_LIST.md)** - Iterative build plan and phased purchasing checklist
- **[Arduino Porting Guide](ARDUINO_PORTING.md)** - C firmware-ready control primitives and flashing notes
- **[Arduino Flashing Manual](ARDUINO_FLASHING_MANUAL.md)** - Detailed step-by-step firmware flashing and troubleshooting guide

## Quick Start

1. **Configuration Setup**: Start with the [Configuration Guide](configuration.md) to understand and customize system parameters
2. **Bench/Prototype Planning**: Review [EV Bench Architecture](EV_BENCH_ARCHITECTURE.md) and [EV Roadmap and Shopping List](EV_ROADMAP_AND_SHOPPING_LIST.md) before wiring hardware
3. **Installation**: Use the setup script to initialize the environment:
   ```bash
   ./scripts/setup.sh
   ```
4. **Testing**: Run the test suite to verify installation:
   ```bash
   poetry run pytest -q
   ```

## Key Components

### Core Systems
- **Battery Management**: Monitor and control battery operations with cell-level tracking
- **Motor Controller**: Manage motor performance and efficiency (VESC integration)
- **Charging System**: Handle AC/DC charging protocols with multiple connector support
- **Vehicle Controller**: High-level coordination system managing:
  - Vehicle state transitions (PARKED, READY, DRIVING, CHARGING, ERROR, EMERGENCY)
  - Safety enforcement (prevents driving while charging)
  - Drive modes (ECO, NORMAL, SPORT, REVERSE)
  - Range calculation and energy consumption tracking

### Sensors & Communication
- **IMU**: Inertial measurement for vehicle dynamics
- **GPS**: Positioning and navigation data
- **Temperature Sensors**: Thermal monitoring (feeds BMS, motor, charging)
- **CAN Bus**: Vehicle network communication
- **Telemetry**: Remote data transmission (cellular / Quectel-oriented)
- **LoRaWAN**: Optional RAK AT USB uplink; aggregates a multi-sensor snapshot and surfaces it on the dashboard (see `lorawan` in [configuration.md](configuration.md))

### User Interfaces
- **Dashboard**: Primary control interface
- **Mobile App**: Remote monitoring and control

### AI Features
- **Autopilot**: Autonomous driving capabilities with rule-based and Alpamayo-backed provider modes
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
- **Test Count**: 739+ tests in the default suite (see repository README; optional Playwright tests require `poetry install --with playwright`)
- **Run Tests**: `poetry run pytest -q`
- **Unit Tests**: `poetry run pytest tests/unit/ -v`
- **Functional Tests**: `poetry run pytest tests/functional/ -v`
- **Coverage**: Add `--cov` flag for coverage reports
- **CI/CD**: All tests run automatically on every commit via GitHub Actions

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

- **Current Version**: 1.0.0 (first major release)
- **Schema Version**: JSON Schema Draft 07
- **Python Compatibility**: 3.11–3.13 (see root `pyproject.toml`)

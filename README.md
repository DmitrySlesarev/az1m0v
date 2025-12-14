# az1m0v - Electric Vehicle Management System

An open-source Electric Vehicle (EV) management system providing comprehensive control and monitoring capabilities for electric vehicles.

## Overview

az1m0v is a complete EV management platform featuring battery management, motor control, sensor integration, CAN bus communication, and AI-powered autopilot capabilities. The system is designed with modularity and extensibility in mind, following industry best practices.

## Features

### Core Systems
- **Battery Management System (BMS)**: Comprehensive battery monitoring with cell-level voltage and temperature tracking, SOC/SOH calculation, and safety fault detection
  - Integrated temperature sensor support for cell groups and coolant monitoring
  - Cell group temperature tracking (one sensor per series group)
  - Coolant inlet/outlet temperature monitoring
- **Motor Controller**: VESC (Vedder Electronic Speed Controller) integration with support for:
  - RPM, current, and duty cycle control
  - Real-time status monitoring
  - Safety limit enforcement
  - CAN bus integration
  - Stator winding temperature monitoring (per phase)
- **Charging System**: AC/DC charging management with multiple connector support (CCS1, CCS2, CHAdeMO, Tesla)
  - Charging port and connector temperature monitoring
  - Automatic charging shutdown on overtemperature conditions
- **Vehicle Controller**: High-level vehicle coordination system that:
  - Manages overall vehicle state (PARKED, READY, DRIVING, CHARGING, ERROR, EMERGENCY)
  - Coordinates between BMS, motor controller, and charging system
  - Enforces safety rules (e.g., prevents driving while charging)
  - Provides unified interface for vehicle operations (accelerate, brake, drive modes)
  - Calculates range and tracks energy consumption
  - Integrates with CAN bus for status reporting

### Communication
- **CAN Bus Interface**: Industry-standard CAN bus communication with EV-specific protocol
- **VESC Protocol**: Dedicated CAN IDs and message handlers for VESC motor controller
- **Temperature Sensor Protocol**: CAN bus messages for all temperature sensor types (battery, coolant, motor, charging)
- **Telemetry System**: Remote data transmission and monitoring using Quectel cellular modules:
  - Real-time vehicle data streaming (battery, motor, charging status)
  - GPS location tracking
  - Error reporting and diagnostics
  - Configurable update intervals and retry logic
  - Simulation mode for development

### Sensors & Perception
- **IMU (Inertial Measurement Unit)**: Vehicle dynamics and orientation
- **GPS**: Positioning and navigation data
- **Temperature Sensors**: Comprehensive multi-point thermal monitoring system:
  - Battery cell group sensors (one per series group, configurable)
  - Coolant inlet and outlet sensors
  - Motor stator winding sensors (per phase, typically 3-phase)
  - Charging port and connector sensors
  - Configurable thresholds (warning, fault)
  - Real-time status monitoring and CAN bus integration
  - Automatic fault detection and reporting
- **Computer Vision**: Environmental perception and lane detection

### AI & Autonomy
- **Autopilot System**: Autonomous driving capabilities with multiple modes:
  - Full autopilot
  - Assist mode
  - Emergency mode
- **Computer Vision**: Real-time lane detection and object recognition

### User Interfaces
- **Dashboard**: Web-based real-time monitoring and control interface:
  - Real-time data visualization via WebSocket
  - Battery status (voltage, current, temperature, SOC)
  - Motor status (speed, torque, temperature)
  - Charging system status
  - Vehicle state monitoring
  - CAN bus statistics
  - Responsive design for desktop and mobile
  - Raspberry Pi 4 optimized
- **Mobile App**: Remote monitoring and control capabilities

### Integration & Build Tools
- **VESC Builder**: Automated download, build, and integration of VESC motor controller
- **SimpBMS Builder**: SimpBMS firmware build and integration support
- **Quectel Builder**: Automated download, build, and integration of Quectel QuecPython library for telemetry

## Project Structure

```
az1m0v/
├── core/                    # Core system components
│   ├── battery_management.py
│   ├── motor_controller.py  # VESC integration
│   ├── charging_system.py
│   └── vehicle_controller.py
├── sensors/                 # Sensor interfaces
│   ├── temperature.py      # Comprehensive temperature sensor system
├── communication/           # CAN bus and telemetry
├── ai/                      # Autopilot and AI systems
├── ui/                      # User interfaces
├── config/                  # Configuration files
├── scripts/integration/     # Build and integration scripts
└── tests/                   # Comprehensive test suite
```

See [architecture.txt](architecture.txt) for detailed structure.

## Getting Started

### Prerequisites

- Python 3.13 or higher
- Poetry (for dependency management)
- Linux (recommended for CAN bus support)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd az1m0v
   ```

2. **Install dependencies**
   ```bash
   poetry install
   ```

3. **Configure the system**
   
   Edit `config/config.json` to match your hardware configuration:
   - Set motor controller serial port (e.g., `/dev/ttyUSB0`)
   - Configure battery parameters
   - Adjust sensor settings
   - Enable/disable features as needed

   See [Configuration Documentation](docs/configuration.md) for detailed parameter reference.

4. **Setup integration components (optional)**
   
   For VESC motor controller:
   ```bash
   cd scripts/integration
   python vesc_builder.py
   ```
   
   For SimpBMS:
   ```bash
   python simpbms_builder.py
   ```
   
   For Quectel telemetry:
   ```bash
   python quectel_builder.py
   ```

### Running the System

**Start the main application:**
```bash
poetry run python main.py
```

The system will:
- Load and validate configuration
- Initialize CAN bus (if enabled)
- Connect to motor controller (if serial port configured)
- Start monitoring and control loops
- Handle graceful shutdown on SIGINT/SIGTERM

**Start the web dashboard:**
```bash
poetry run python -m ui.dashboard
```

Or integrate into your application:
```python
from ui.dashboard import EVDashboard
from communication.can_bus import CANBusInterface, EVCANProtocol

# Initialize CAN bus
can_bus = CANBusInterface("can0", 500000)
can_bus.connect()
can_protocol = EVCANProtocol(can_bus)

# Start dashboard
dashboard = EVDashboard(can_bus=can_bus, can_protocol=can_protocol)
dashboard.start()  # Runs on http://0.0.0.0:5000 by default
```

The dashboard provides:
- Real-time WebSocket updates
- REST API endpoint at `/api/status`
- Responsive web interface accessible from any device
- Automatic CAN bus data integration

### Testing

Run the complete test suite:
```bash
poetry run pytest tests/ -v
```

Run specific test categories:
```bash
# Unit tests only
poetry run pytest tests/unit/ -v

# Functional/integration tests
poetry run pytest tests/functional/ -v

# Specific component tests
poetry run pytest tests/unit/test_motor_controller.py -v
```

The project includes **409 tests** covering all major components:
- **45 unit tests** for vehicle controller
- **14 functional/integration tests** for vehicle controller
- **21 unit tests** for telemetry system
- **10 functional/integration tests** for telemetry system
- **24 unit tests** for temperature sensor system
- **7 functional/integration tests** for temperature sensor integration
- Comprehensive test coverage for all core systems
- All tests run automatically on every commit via GitHub Actions

## Configuration

The system uses JSON-based configuration with schema validation:

- **Main Config**: `config/config.json` - System parameters
- **Schema**: `config/config_schema.json` - Validation rules
- **Documentation**: `docs/configuration.md` - Complete parameter reference

Key configuration sections:
- Vehicle specifications (speed limits, acceleration, efficiency)
- Battery parameters (capacity, voltage, cell count)
- Motor controller settings (VESC serial port, limits)
- Charging system configuration
- Vehicle controller settings (drive modes, power limits)
- Telemetry settings (server URL, cellular APN, update intervals)
- Temperature sensor configuration:
  - Cell group sensor settings (cells per group)
  - Coolant sensor enablement
  - Motor stator sensor configuration
  - Charging sensor enablement
  - Update intervals and thresholds
- Sensor enablement
- CAN bus settings
- AI/autopilot configuration
- Logging preferences

## Documentation

- **[Configuration Guide](docs/configuration.md)** - Complete configuration reference
- **[Architecture Overview](architecture.txt)** - System structure and components
- **[Architecture Diagram](architecture.drawio)** - Visual system architecture (open in draw.io)

## Development

### Code Quality

- Type hints throughout
- Comprehensive test coverage
- Industry-standard CAN bus protocols
- JSON schema validation
- Structured logging

### Testing

The project follows pytest best practices:
- Unit tests for individual components
- Functional/integration tests for system workflows
- Mock-based testing for hardware interfaces
- Test fixtures and configuration helpers

**Continuous Integration:**
- All tests run automatically on every commit via GitHub Actions
- Separate test runs for unit and functional tests
- Coverage reports generated and uploaded as artifacts
- Test results published to pull requests

### Contributing

1. Follow existing code style and patterns
2. Add tests for new features
3. Update documentation as needed
4. Ensure all tests pass before submitting

## Hardware Integration

### VESC Motor Controller

The system supports VESC motor controllers via:
- **Serial/UART**: Direct connection via serial port
- **CAN Bus**: CAN-based communication (when enabled)
- **Simulation Mode**: Runs without hardware for development

Configure in `config/config.json`:
```json
{
  "motor_controller": {
    "type": "vesc",
    "serial_port": "/dev/ttyUSB0",
    "can_enabled": true,
    "max_current_a": 200.0,
    "max_rpm": 10000.0
  }
}
```

### CAN Bus

The system implements standard EV CAN protocols:
- ISO 11898 compliant
- EV-specific message IDs
- VESC protocol extensions
- Temperature sensor protocol (CAN IDs 0x400-0x406)
- Message handlers and routing
- Support for battery, motor, charging, and temperature data

## Requirements

- **Python**: 3.13+
- **Poetry**: For dependency management
- **Dependencies**:
  - `jsonschema` - Configuration validation
  - `numpy` - Numerical computations
  - `flask` - Web framework for dashboard
  - `flask-socketio` - WebSocket support for real-time updates
  - `pytest` - Testing framework (dev)
  - `pytest-cov` - Test coverage (dev)

Optional (for VESC):
- `pyvesc` - VESC Python library (installed via integration script)
- `pyserial` - Serial communication

Optional (for Telemetry):
- `quecpython` - Quectel QuecPython library (installed via integration script)
- `requests` - HTTP/HTTPS requests for telemetry transmission

## License

GNU General Public License v3.0

See [LICENSE](LICENSE) for full license text.

## Authors

- Dmitry Slesarev <dvslesar@gmail.com>

## Status

✅ **Active Development** - Core systems implemented and tested
- Battery Management System: ✅ Implemented (with temperature sensor integration)
- Motor Controller (VESC): ✅ Implemented (with stator temperature monitoring)
- Charging System: ✅ Implemented (with port/connector temperature monitoring)
- Vehicle Controller: ✅ Implemented
- CAN Bus Communication: ✅ Implemented (with temperature sensor protocol)
- Telemetry System: ✅ Implemented (Quectel integration)
- Temperature Sensor System: ✅ Implemented (comprehensive multi-point monitoring)
- Sensor Integration: ✅ Implemented
- Autopilot AI: ✅ Implemented
- Configuration System: ✅ Implemented
- Web Dashboard: ✅ Implemented (Flask + WebSocket, CAN bus integrated, Raspberry Pi 4 compatible)
- Test Suite: ✅ Comprehensive test coverage (409 tests, including temperature sensor tests)
- CI/CD: ✅ GitHub Actions workflow running all tests on every commit

## Support

For issues, questions, or contributions, please refer to the project documentation or open an issue in the repository.

# az1m0v - Electric Vehicle Management System

**Version 1.0.0** — first major release.

An open-source Electric Vehicle (EV) management system providing comprehensive control and monitoring capabilities for electric vehicles.

## Bench MVP and Prototype Roadmap

This repository now includes an iterative hardware plan based on:

- Raspberry Pi as the main module
- RS485 CAN HAT + MCP2515 CAN chain
- Arduino over USB 2.0
- RAK4630 WisBlock over USB 2.0
- Future STM32F407 integration

Use these documents first if you are building from a real bench setup:

- **[EV Bench Architecture](docs/EV_BENCH_ARCHITECTURE.md)** - MVP architecture and dual-link CAN + LoRaWAN strategy with fallback rules
- **[EV Roadmap and Shopping List](docs/EV_ROADMAP_AND_SHOPPING_LIST.md)** - phase-by-phase build roadmap (bench -> real-size no trolley -> full-size) and purchase checklist

## Overview

az1m0v is a complete EV management platform featuring battery management, motor control, sensor integration, CAN bus communication, and AI-powered autopilot capabilities. The system is designed with modularity and extensibility in mind, following industry best practices.

## Features

### Core Systems
- **Battery Management System (BMS)**: Comprehensive battery monitoring with cell-level voltage and temperature tracking, SOC/SOH calculation, cell balancing, and safety fault detection
  - Integrated temperature sensor support for cell groups and coolant monitoring
  - Cell group temperature tracking (one sensor per series group)
  - Coolant inlet/outlet temperature monitoring
  - **State of Health (SOH) Calculation**: Advanced battery health monitoring:
    - Cycle-based degradation (0.05% per charge cycle)
    - Temperature history tracking (30-day rolling window)
    - High-temperature degradation acceleration
    - Fault-based degradation tracking
    - Calendar aging (age-based degradation with temperature adjustment)
    - Automatic charge cycle detection (SOC-based and energy-based)
    - Real-time SOH updates on every state change
  - **Cell Balancing Algorithms**: Automatic cell voltage balancing to maximize pack capacity and lifespan:
    - **Passive Balancing**: Dissipative balancing using bleed resistors (simple, cost-effective)
    - **Active Balancing**: Redistributive balancing with energy transfer between cells (efficient, no energy waste)
    - **Adaptive Balancing**: Automatically selects passive or active based on imbalance magnitude
    - Configurable voltage threshold (default 50mV) to trigger balancing
    - SOC range limits (20-95%) to prevent balancing during extreme charge states
    - Real-time balancing state tracking and statistics
    - Automatic balancing during charging and idle states
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
  - Applies drive mode limits derived from base configuration (no cumulative scaling)
  - Calculates range and tracks energy consumption
  - Integrates with CAN bus for status reporting
- **Safety System**: Comprehensive safety monitoring and protection:
  - Thermal runaway detection for battery and motor (rapid temperature rise monitoring)
  - Emergency shutdown coordination (graceful power-down sequence)
  - Electrical safety monitoring (overvoltage, undervoltage, overcurrent detection)
  - Fault tracking and management with severity levels
  - Safety state management (NORMAL, WARNING, CRITICAL, EMERGENCY)
  - Monitors all core components (BMS, motor, charging, vehicle controller)
  - Configurable safety thresholds and thermal rate limits
- **Diagnostics System** (OBD-II Style): Advanced fault detection and diagnostics:
  - **DTC (Diagnostic Trouble Code) System**: Standardized fault codes (P0xxx format) with component-specific suffixes
  - **Limp-Home Modes**: Automatic degraded operation modes:
    - NORMAL: Full operation (120 km/h, 150 kW)
    - REDUCED_POWER: 50% power limit (80 km/h, 75 kW) for warnings
    - LIMITED_SPEED: 20% power limit (30 km/h, 30 kW) for critical faults
    - EMERGENCY_ONLY: Minimal operation (10 km/h, 10 kW) for permanent DTCs
    - DISABLED: Vehicle disabled for emergency conditions
  - **Fault Logging**: Persistent logging with timestamps:
    - Text logs for human-readable fault history
    - JSON logs for programmatic access and analysis
    - Automatic log rotation
    - Freeze frame data capture (system state snapshots)
  - **DTC Management**: 
    - Automatic DTC generation from faults
    - DTC occurrence counting and history tracking
    - DTC clearing (permanent DTCs require manual intervention)
    - DTC export to JSON format
  - **Operation Restrictions**: Automatic restrictions on charging, autopilot, and driving based on limp-home mode

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
- **LoRaWAN (RAK AT modules, e.g. RAK4631)**: Optional USB serial uplink using RUI3-style AT commands; collects a configurable **multi-sensor snapshot** (battery, motor, vehicle state, charging, temperature summary, GPS, IMU) and shows link status plus the encoded payload preview on the **web dashboard**. Uses `pyserial` for hardware mode; `simulation_mode` for bench testing without RF.

### Sensors & Perception
- **IMU (Inertial Measurement Unit)**: Vehicle dynamics and orientation
  - Support for MPU-6050 (6-DOF: accelerometer + gyroscope)
  - Support for MPU-9250 (9-DOF: accelerometer + gyroscope + magnetometer)
  - I2C communication interface
  - Configurable sampling rates and calibration
  - Simulation mode for development
- **GPS**: Positioning and navigation data
  - NMEA serial input or simulation mode for bench setups
- **Temperature Sensors**: Comprehensive multi-point thermal monitoring system:
  - Battery cell group sensors (one per series group, configurable)
  - Coolant inlet and outlet sensors
  - Motor stator winding sensors (per phase, typically 3-phase)
  - Charging port and connector sensors
  - Configurable thresholds (warning, fault)
  - Real-time status monitoring and CAN bus integration
  - TemperatureSensorManager feeds BMS, motor, and charging subsystems
  - Automatic fault detection and reporting
- **Computer Vision**: Environmental perception and lane detection

### AI & Autonomy
- **Autopilot System**: Autonomous driving capabilities with multiple modes:
  - Full autopilot
  - Assist mode
  - Emergency mode
  - Optional NVIDIA Alpamayo provider integration with safe rule-based fallback
  - Vehicle-profile command envelopes for generic vehicle platforms
- **Computer Vision**: Real-time lane detection and object recognition

### User Interfaces
- **Dashboard**: Web-based real-time monitoring and control interface:
  - Real-time data visualization via WebSocket
  - Battery status (voltage, current, temperature, SOC, SOH)
  - Motor status (speed, torque, temperature)
  - Charging system status
  - Vehicle state monitoring
  - CAN bus statistics
  - Responsive design for desktop and mobile
  - Raspberry Pi 4 optimized
- **Mobile App**: Remote monitoring and control capabilities
  - Minimal REST client in `ui/mobile_app.py` for DIY apps

### Mobile CLI (DIY)
Use the minimal CLI to interact with the dashboard API:
```bash
python -m ui.mobile_app status --base-url http://localhost:5000
python -m ui.mobile_app drive-mode eco --base-url http://localhost:5000
python -m ui.mobile_app accelerate 25 --base-url http://localhost:5000
python -m ui.mobile_app stop-charging --base-url http://localhost:5000
```

### Integration & Build Tools
- **VESC Builder**: Automated download, build, and integration of VESC motor controller
- **SimpBMS Builder**: SimpBMS firmware build and integration support
- **Quectel Builder**: Automated download, build, and integration of Quectel QuecPython library for telemetry
- **MPU Builder**: Automated download, build, and integration of MPU-6050/MPU-9250 IMU libraries

## Project Structure

```
az1m0v/
├── core/                    # Core system components
│   ├── battery_management.py
│   ├── motor_controller.py  # VESC integration
│   ├── charging_system.py
│   ├── vehicle_controller.py
│   ├── safety_system.py    # Safety monitoring and protection
│   └── diagnostics.py      # OBD-II style diagnostics (DTC, limp-home, fault logging)
├── sensors/                 # Sensor interfaces
│   ├── temperature.py      # Comprehensive temperature sensor system
├── communication/           # CAN bus, cellular telemetry, LoRaWAN (RAK)
├── ai/                      # Autopilot and AI systems
├── ui/                      # User interfaces
├── config/                  # Configuration files
├── scripts/integration/     # Build and integration scripts
└── tests/                   # Comprehensive test suite
```

See [architecture.txt](architecture.txt) for detailed structure.

## Getting Started

### Prerequisites

- Python **3.11, 3.12, or 3.13** (see `pyproject.toml`)
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
   This installs runtime and dev dependencies. **Playwright** (browser UI tests) is in an optional group; install it only when you need those tests:
   ```bash
   poetry install --with playwright
   ```

3. **Configure the system**
   
   Edit `config/config.json` to match your hardware configuration:
   - Set motor controller serial port (e.g., `/dev/ttyUSB0`)
   - Configure battery parameters
   - Adjust sensor settings
   - Enable/disable features as needed
   - For **LoRaWAN** (RAK4631 / USB): set `lorawan.serial_port` (e.g. `/dev/ttyACM0`), `band`, and OTAA keys; use `lorawan.simulation_mode: true` until the radio is provisioned on your network server

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
   
   For MPU IMU sensors:
   ```bash
   python mpu_builder.py --sensor mpu6050  # or mpu9250
   ```

### Raspberry Pi (and other constrained ARM boards)

Use a **minimal** install so Poetry does not pull optional stacks (Alpamayo / PyTorch, Playwright, heavy dev-only wheels) that often fail or are unavailable on **32-bit ARM (`armv7l`)**.

**About `.pyc` files and `__pycache__`:** Python creates these automatically. They do not break the app on the Pi, but they should **not be committed** to Git (noise, wrong machine fingerprints). The repository `.gitignore` ignores them; delete any that were added by mistake.

**Recommended steps on the Pi**

1. Install **Poetry** and (if you use it) **pyenv**, with Python **3.11+** available on your `PATH` (e.g. Raspberry Pi OS Bullseye with pyenv: `pyenv local 3.11` in the project directory).

2. Point Poetry at that interpreter (pyenv shims are fine):
   ```bash
   poetry env use "$(command -v python3)"
   ```
   Use a real executable name such as `python3.11` or the output of `pyenv which python`, not a full version string like `python3.11.11` unless that binary exists.

3. Run the setup script (it detects Raspberry Pi / `armv7l` / device-tree hints and runs `poetry install --only main`):
   ```bash
   ./scripts/setup.sh
   ```
   If detection fails on your image, force the same behavior:
   ```bash
   AZ1M0V_POETRY_ONLY_MAIN=1 ./scripts/setup.sh
   ```
   Or manually:
   ```bash
   poetry install --only main --no-interaction
   ```

4. The repo includes **`poetry.toml`** with `prefer-active-python = true` so Poetry prefers the interpreter already active in your shell (e.g. after `pyenv local`).

5. Run the stack:
   ```bash
   poetry run python main.py
   ```

**Optional extras (not required for dashboard + main loop)**

- **Alpamayo** (large dependencies including PyTorch): requires Python **≥ 3.12** per upstream. Install with:
  ```bash
  poetry install -E alpamayo
  ```
  On Python 3.11 this extra cannot be resolved; use rule-based autopilot without it.

- **Playwright UI tests** (often no wheel on `armv7l`): on x86_64 / aarch64 dev machines:
  ```bash
  poetry install --with playwright
  playwright install
  ```

### Running the System

**Start the main application (recommended):**
```bash
poetry run python main.py
```

The system will automatically:
- Load and validate configuration from `config/config.json`
- Initialize CAN bus (if enabled in config)
- Initialize Battery Management System (BMS)
- Initialize Motor Controller (VESC, if serial port configured)
- Initialize Charging System
- Initialize Vehicle Controller
- Initialize Sensors (IMU, GPS, Temperature Sensors - if enabled)
- Initialize Autopilot System (if enabled in config)
- **Start the web dashboard** (if `dashboard_enabled: true` in config)
- Start monitoring and control loops
- Handle graceful shutdown on SIGINT/SIGTERM

**Access the web dashboard:**
Once the system is running, the dashboard is automatically available at:
- `http://localhost:5000` (default port, configurable in `config/config.json`)
- The dashboard runs in a background thread and provides:
  - Real-time WebSocket updates from all system components
  - REST API endpoint at `/api/status`
  - Control interface for vehicle operations (accelerate, brake, drive modes, charging, autopilot)
  - Responsive web interface accessible from any device on the network
  - Automatic integration with CAN bus, BMS, motor controller, sensors, cellular telemetry, and LoRaWAN status (when enabled)

**Standalone dashboard mode (alternative):**
If you want to run the dashboard separately without the full EV system:
```bash
poetry run python -m ui
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

**Dashboard control commands:**
The dashboard supports WebSocket control commands for:
- Vehicle acceleration and braking
- Drive mode selection (ECO, NORMAL, SPORT, REVERSE)
- Vehicle state control (PARKED, READY, DRIVING, CHARGING)
- Charging start/stop
- Autopilot mode control (MANUAL, ASSIST, AUTOPILOT)

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

The project includes **739+ tests** by default, plus optional Playwright UI tests (`poetry install --with playwright`), covering all major components:
- **45 unit tests** for vehicle controller
- **14 functional/integration tests** for vehicle controller
- **21 unit tests** for telemetry system
- **10 functional/integration tests** for telemetry system
- **24 unit tests** for temperature sensor system
- **7 functional/integration tests** for temperature sensor integration
- **33 unit tests** for diagnostics system (DTC, limp-home, fault logging)
- **18 functional/integration tests** for safety system (including diagnostics integration)
- Comprehensive test coverage for all core systems
- All tests run automatically on every commit via GitHub Actions

## Configuration

The system uses JSON-based configuration with schema validation:

- **Main Config**: `config/config.json` - System parameters
- **Schema**: `config/config_schema.json` - Validation rules
- **Documentation**: `docs/configuration.md` - Complete parameter reference

Key configuration sections:
- Vehicle specifications (speed limits, acceleration, efficiency)
- Battery parameters (capacity, voltage, cell count, balancing settings):
  - Balancing algorithm selection (none, passive, active, adaptive)
  - Balancing threshold (voltage difference to trigger balancing)
  - Passive balancing bleed current
  - Active balancing efficiency
  - SOC range limits for balancing
- Motor controller settings (VESC serial port, limits)
- Charging system configuration
- Vehicle controller settings (drive modes, power limits)
- Safety system configuration (temperature thresholds, thermal runaway rates, voltage/current limits)
- Diagnostics system configuration (log directory, DTC settings)
- Telemetry settings (server URL, cellular APN, update intervals)
- LoRaWAN settings (serial port, band, OTAA keys, sensor groups in uplink, payload size)
- IMU sensor configuration:
  - Sensor type (MPU-6050 or MPU-9250)
  - I2C address and bus
  - Sampling rate and calibration parameters
- Temperature sensor configuration:
  - Cell group sensor settings (cells per group)
  - Coolant sensor enablement
  - Motor stator sensor configuration
  - Charging sensor enablement
  - Update intervals and thresholds
- Sensor enablement
- CAN bus settings
- Bench MVP bridge settings (`bench_mvp`) for Raspberry Pi + Arduino + RAK4630 serial/CAN integration
- AI/autopilot configuration
  - Provider selection (`autonomy_provider`: `rule_based` or `alpamayo`)
  - Alpamayo adapter configuration (`alpamayo_*` keys)
  - Vehicle profile and command limits (`vehicle_profile`, `vehicle_profiles`)
- Logging preferences

## Documentation

- **[Configuration Guide](docs/configuration.md)** - Complete configuration reference
- **[Architecture Overview](architecture.txt)** - System structure and components
- **[Architecture Diagram](architecture.drawio)** - Visual system architecture (open in draw.io)
- **[EV Bench Architecture](docs/EV_BENCH_ARCHITECTURE.md)** - Bench MVP design and extension path to real EV
- **[EV Roadmap and Shopping List](docs/EV_ROADMAP_AND_SHOPPING_LIST.md)** - Iterative roadmap and phased purchase plan

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

### Bench MVP Bridge (Arduino + RAK4630)

To run the current lab bench as an MVP, enable the `bench_mvp` section in `config/config.json`:

```json
{
  "bench_mvp": {
    "enabled": true,
    "simulation_mode": false,
    "arduino_port": "/dev/ttyACM0",
    "rak_port": "/dev/ttyACM1",
    "prefer_lorawan": true
  }
}
```

The bridge ingests one-JSON-line messages from Arduino/RAK serial links, updates runtime status, emits CAN-compatible updates, and automatically falls back to CAN-primary mode when LoRaWAN link quality drops.

## Requirements

- **Python**: 3.11–3.13
- **Poetry**: For dependency management
- **Dependencies**:
  - `jsonschema` - Configuration validation
  - `numpy` - Numerical computations
  - `flask` - Web framework for dashboard
  - `flask-socketio` - WebSocket support for real-time updates
  - `pyserial` - Serial ports (LoRaWAN RAK module, GPS, and other UART devices)
  - `alpamayo-tools` - Optional extra (`poetry install -E alpamayo`); requires Python ≥ 3.12; pulls PyTorch and related packages
  - `pytest` - Testing framework (dev)
  - `pytest-cov` - Test coverage (dev)
  - `playwright` / `pytest-playwright` - Optional group (`poetry install --with playwright`) for browser tests

Optional (for VESC):
- `pyvesc` - VESC Python library (installed via integration script)

Optional (for Telemetry):
- `quecpython` - Quectel QuecPython library (installed via integration script)
- `requests` - HTTP/HTTPS requests for telemetry transmission

Optional (for IMU):
- `mpu6050-raspberrypi` - MPU-6050 Python library (installed via integration script)
- `mpu9250-jmdev` - MPU-9250 Python library (installed via integration script)
- `smbus2` - I2C communication library (installed via integration script)

## License

GNU General Public License v3.0

See [LICENSE](LICENSE) for full license text.

## Authors

- Dmitry Slesarev <dvslesar@gmail.com>

## Status

✅ **Version 1.0.0** — First major release; core systems implemented and tested
- Battery Management System: ✅ Implemented (with temperature sensor integration, SOC/SOH calculation, cell balancing algorithms)
- Motor Controller (VESC): ✅ Implemented (with stator temperature monitoring)
- Charging System: ✅ Implemented (with port/connector temperature monitoring)
- Vehicle Controller: ✅ Implemented
- Safety System: ✅ Implemented (thermal runaway detection, emergency shutdown, fault tracking)
- Diagnostics System: ✅ Implemented (OBD-II style DTC system, limp-home modes, fault logging)
- CAN Bus Communication: ✅ Implemented (with temperature sensor protocol)
- Telemetry System: ✅ Implemented (Quectel integration)
- LoRaWAN uplink: ✅ Implemented (RAK AT / multi-sensor snapshot + dashboard)
- Temperature Sensor System: ✅ Implemented (comprehensive multi-point monitoring)
- IMU Sensor System: ✅ Implemented (MPU-6050/MPU-9250 support)
- Sensor Integration: ✅ Implemented
- Autopilot AI: ✅ Implemented
- Configuration System: ✅ Implemented
- Web Dashboard: ✅ Implemented (Flask + WebSocket, CAN bus integrated, Raspberry Pi 4 compatible)
- Test Suite: ✅ Comprehensive test coverage (739+ tests in CI; optional browser tests via `poetry install --with playwright`)
- CI/CD: ✅ GitHub Actions workflow running all tests on every commit

## Releases

Release notes and version history: [CHANGELOG.md](CHANGELOG.md).

## Support

For issues, questions, or contributions, please refer to the project documentation or open an issue in the repository.

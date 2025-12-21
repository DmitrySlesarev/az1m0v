# Hardware Requirements for az1m0v EV Management System

This document provides a comprehensive list of all hardware components required to implement the az1m0v Electric Vehicle Management System.

## Table of Contents

1. [Computing Platform](#computing-platform)
2. [Motor Controller](#motor-controller)
3. [Battery Management System](#battery-management-system)
4. [Charging System](#charging-system)
5. [Communication Hardware](#communication-hardware)
6. [Sensors](#sensors)
7. [Computer Vision System](#computer-vision-system)
8. [Power Supply & Distribution](#power-supply--distribution)
9. [Cables & Connectors](#cables--connectors)
10. [Optional Components](#optional-components)

---

## Computing Platform

### Primary Controller
- **Raspberry Pi 4 Model B** (Recommended)
  - 4GB or 8GB RAM
  - MicroSD card (64GB minimum, Class 10 or better)
  - Power supply (5V, 3A minimum)
  - Case with cooling (active cooling recommended for automotive environment)
  - **Alternative**: Any Linux-based single-board computer with:
    - Python 3.13+ support
    - GPIO/I2C/SPI interfaces
    - USB ports
    - Ethernet or WiFi connectivity
    - Sufficient processing power for real-time sensor data processing

### Storage
- MicroSD card (64GB+ recommended for logging and data storage)
- Optional: External USB storage for telemetry data backup

---

## Motor Controller

### VESC (Vedder Electronic Speed Controller)
- **VESC 6** or compatible model
  - Supports UART/Serial communication
  - Optional: CAN bus interface support
  - Current rating: 200A+ (configurable based on motor requirements)
  - Voltage range: 300V - 500V (configurable)
  - RPM range: Up to 10,000 RPM (configurable)
  - Temperature monitoring capability
  - Stator temperature sensor inputs (3-phase motor: 3 sensors)

### Motor Controller Communication
- **Serial/UART Interface**
  - USB-to-Serial adapter (if VESC doesn't have USB)
  - Serial cable (USB-A to appropriate connector)
  - Typical port: `/dev/ttyUSB0` or `/dev/ttyACM0`

### Motor Controller CAN Interface (Optional)
- CAN transceiver module (if using CAN bus for VESC communication)
- CAN bus termination resistors (120Ω, if required)

---

## Battery Management System

### BMS Hardware
- **SimpBMS** or compatible BMS
  - Cell count support: 96 cells (configurable)
  - Voltage monitoring per cell or cell group
  - Current monitoring (shunt or Hall effect sensor)
  - Temperature monitoring per cell group
  - Communication interface (CAN bus or serial)
  - Safety features: overvoltage, undervoltage, overcurrent, overtemperature protection

### Battery Pack
- Battery cells (96 cells in example configuration)
  - Type: Lithium-ion (Li-ion) or Lithium Iron Phosphate (LiFePO4)
  - Nominal voltage: 400V (configurable)
  - Capacity: 75 kWh (configurable)
  - Cell configuration: Series/parallel as per design

### Battery Monitoring
- Cell voltage monitoring boards (if not integrated in BMS)
- Current sensor (shunt resistor or Hall effect sensor)
  - Rating: 200A+ (based on max discharge rate)

---

## Charging System

### Charging Controller
- AC/DC charging controller compatible with:
  - **AC Charging**: Up to 11 kW
  - **DC Fast Charging**: Up to 150 kW
  - Connector types: CCS1, CCS2, CHAdeMO, or Tesla (as configured)

### Charging Port Hardware
- Physical charging connector matching selected standard (CCS2 in example config)
- Charging port temperature sensor
- Charging connector temperature sensor
- Locking mechanism (if required by connector standard)

### Charging Safety
- Contactor/relay for charging circuit control
- Ground fault detection (if required)
- Isolation monitoring (if required by regulations)

---

## Communication Hardware

### CAN Bus Interface
- **CAN Bus Transceiver**
  - ISO 11898 compliant
  - Bitrate: 500 kbps (configurable)
  - Interface: SocketCAN compatible
  - Examples:
    - MCP2515 CAN controller with SPI interface
    - USB-CAN adapter (e.g., Peak PCAN-USB, Kvaser USBcan)
    - Raspberry Pi CAN HAT (e.g., Waveshare CAN HAT)

### CAN Bus Network
- CAN bus cables (twisted pair, shielded)
- CAN bus termination resistors (120Ω at each end of bus)
- CAN bus connectors (e.g., DB9, OBD-II, or custom)

### Telemetry Communication
- **Quectel Cellular Module** (for remote telemetry)
  - Model: Compatible with QuecPython (e.g., EC25, EC20, BG96)
  - Features:
    - 4G/LTE connectivity
    - GPS capability (optional, if separate GPS not used)
    - SIM card slot
    - Antenna connectors (cellular and GPS)
  - **SIM Card**: Data-enabled SIM card with appropriate data plan
  - **Antennas**:
    - Cellular antenna (4G/LTE)
    - GPS antenna (if module includes GPS)

---

## Sensors

### Inertial Measurement Unit (IMU)

**Option 1: MPU-6050 (6-DOF)**
- MPU-6050 sensor module
- I2C interface
- Default I2C address: 0x68 (104 decimal)
- Features: 3-axis accelerometer + 3-axis gyroscope

**Option 2: MPU-9250 (9-DOF)** (Recommended for autopilot)
- MPU-9250 sensor module
- I2C interface
- Default I2C address: 0x68
- Features: 3-axis accelerometer + 3-axis gyroscope + 3-axis magnetometer

**IMU Connection**
- I2C bus connection (typically I2C bus 1 on Raspberry Pi)
- Pull-up resistors (usually included on sensor module)
- I2C level shifter (if sensor operates at different voltage)

### GPS Module
- GPS receiver module
  - UART or I2C interface
  - Update rate: 1-10 Hz (configurable)
  - Antenna: Active GPS antenna with SMA connector
  - Examples: NEO-6M, NEO-8M, or compatible modules

### Temperature Sensors

#### Battery Temperature Sensors
- **Cell Group Temperature Sensors**
  - Quantity: 8 sensors (one per cell group, configurable)
  - Type: Digital temperature sensors (e.g., DS18B20, MAX31855) or analog sensors
  - Temperature range: -40°C to +150°C
  - Accuracy: ±1°C or better
  - Interface: 1-Wire (DS18B20) or analog with ADC

#### Coolant Temperature Sensors
- **Coolant Inlet Sensor**: 1 sensor
- **Coolant Outlet Sensor**: 1 sensor
- Type: Same as battery sensors or automotive-grade coolant temperature sensors
- Temperature range: -40°C to +150°C

#### Motor Temperature Sensors
- **Stator Winding Temperature Sensors**
  - Quantity: 3 sensors (one per phase for 3-phase motor)
  - Type: Thermocouple (K-type) or RTD (PT100/PT1000) or digital sensors
  - Temperature range: -40°C to +200°C
  - Mounting: Embedded in motor stator windings
  - Interface: Thermocouple amplifier (MAX31855) or RTD amplifier

#### Charging Temperature Sensors
- **Charging Port Temperature Sensor**: 1 sensor
- **Charging Connector Temperature Sensor**: 1 sensor
- Type: Digital or analog temperature sensors
- Temperature range: -40°C to +150°C

**Temperature Sensor Interface**
- 1-Wire bus (for DS18B20 sensors) with pull-up resistor
- ADC (Analog-to-Digital Converter) for analog sensors
- Thermocouple amplifier boards (for thermocouple sensors)
- RTD amplifier boards (for RTD sensors)

---

## Computer Vision System

### Cameras (for Autopilot/Computer Vision)

**Primary Camera System** (if autopilot enabled):
- **Front Wide Camera**: 1x wide-angle camera (120°+ FOV)
- **Front Narrow Camera**: 1x telephoto camera (narrow FOV)
- **Front Main Camera**: 1x standard camera
- **Rear Camera**: 1x rear-facing camera
- **Left Repeater Camera**: 1x side camera
- **Right Repeater Camera**: 1x side camera
- **Left Pillar Camera**: 1x pillar-mounted camera
- **Right Pillar Camera**: 1x pillar-mounted camera

**Camera Specifications**:
- Resolution: Minimum 1280x720 (720p), recommended 1920x1080 (1080p) or higher
- Frame rate: 30 FPS minimum
- Interface: USB, MIPI CSI-2, or Ethernet (IP cameras)
- Auto-focus capability
- Low-light performance (for night driving)

**Camera Processing**
- USB 3.0 hub (if using USB cameras)
- MIPI CSI-2 interface (if using Raspberry Pi Camera Module)
- Sufficient USB bandwidth for multiple cameras

---

## Power Supply & Distribution

### System Power Supply
- **12V Power Supply** (for Raspberry Pi and peripherals)
  - Input: Vehicle 12V battery or DC-DC converter from high-voltage battery
  - Output: 5V/3A for Raspberry Pi
  - Efficiency: 85%+ recommended
  - Protection: Overvoltage, undervoltage, overcurrent protection

### Power Distribution
- Fuse box or circuit breakers
- Power distribution board
- Ground distribution point
- Emergency power cutoff switch

### Voltage Level Shifters
- 3.3V to 5V level shifters (for I2C/SPI communication)
- 12V to 3.3V/5V level shifters (for sensor interfaces)

---

## Cables & Connectors

### Communication Cables
- USB cables (Type-A to Micro-USB or Type-C, depending on devices)
- Serial/UART cables
- I2C bus cables (4-wire: VCC, GND, SDA, SCL)
- SPI bus cables (if needed)
- 1-Wire bus cables (for temperature sensors)

### Power Cables
- High-voltage battery cables (rated for 400V+)
- Low-voltage power cables (12V system)
- Ground cables
- Appropriate wire gauges for current ratings

### Connectors
- Automotive-grade connectors (waterproof, vibration-resistant)
- CAN bus connectors
- Sensor connectors
- Power connectors (high-voltage rated)

### Cable Management
- Cable ties and clamps
- Cable shielding and protection
- Strain reliefs
- Waterproof cable glands (for external connections)

---

## Optional Components

### Display/Interface
- **Touchscreen Display** (for dashboard interface)
  - Size: 7" to 10" recommended
  - Resolution: 800x480 minimum, 1024x600 or higher recommended
  - Interface: HDMI or MIPI DSI
  - Touch interface: Capacitive or resistive

### Data Logging
- External USB storage device (for extended data logging)
- Network-attached storage (NAS) for remote data access

### Development & Debugging
- USB-to-Serial adapter (for debugging)
- Logic analyzer (for CAN bus debugging)
- Oscilloscope (for signal analysis)
- Multimeter (for voltage/current measurements)

### Safety Equipment
- Emergency stop button
- Fire suppression system (for battery pack)
- Battery isolation switches
- Warning indicators (LEDs, buzzers)

### Environmental Protection
- Enclosures for electronic components
  - IP65 or higher rating for outdoor/exposed components
  - EMI/RFI shielding
  - Vibration damping
- Cooling system (fans, heat sinks) for high-power components
- Heating system (for cold weather operation)

---

## Hardware Integration Notes

### Raspberry Pi GPIO Pin Usage
- **I2C Bus 1**: IMU sensor (MPU-6050/MPU-9250)
- **SPI Bus**: CAN controller (if using SPI-based CAN interface)
- **UART/Serial**: GPS module, VESC motor controller
- **GPIO Pins**: Temperature sensor interfaces, status LEDs, emergency stop
- **USB Ports**: 
  - USB-to-Serial adapter (VESC)
  - USB cameras (if using USB cameras)
  - USB-CAN adapter (if using USB CAN interface)

### CAN Bus Network Topology
- Star or linear bus topology
- Termination resistors at both ends (120Ω)
- Maximum bus length: 40 meters (at 500 kbps)
- Maximum nodes: 110 (theoretical, practical limit lower)

### Temperature Sensor Network
- **1-Wire Network**: Daisy-chain topology for DS18B20 sensors
- **Analog Sensors**: Individual ADC channels or multiplexed ADC
- **Thermocouples/RTDs**: Individual amplifier boards per sensor

### Power Requirements Summary
- Raspberry Pi 4: ~3W (idle) to ~7W (under load)
- CAN transceiver: ~100mW
- IMU sensor: ~10mW
- Temperature sensors: ~5mW each
- GPS module: ~50mW
- Cellular module: ~200mW (idle) to ~2W (transmitting)
- **Total System Power**: ~5W to ~15W (excluding motor controller and charging system)

---

## Recommended Suppliers & Part Numbers

### Computing Platform
- Raspberry Pi 4 Model B (4GB or 8GB)
- Official Raspberry Pi power supply
- Official Raspberry Pi case

### CAN Bus
- Waveshare CAN HAT for Raspberry Pi
- Peak PCAN-USB (USB-CAN adapter)
- MCP2515 CAN controller module

### Sensors
- MPU-6050 or MPU-9250 breakout boards (Adafruit, SparkFun)
- DS18B20 temperature sensors (waterproof versions available)
- NEO-6M or NEO-8M GPS modules

### Motor Controller
- VESC 6 from VESC Project (vedder.se)
- Compatible VESC clones (verify compatibility)

### BMS
- SimpBMS from Open Source BMS project
- Compatible BMS systems

### Cellular Module
- Quectel EC25 or EC20 modules
- Compatible development boards

---

## Cost Estimation (Approximate)

| Category | Estimated Cost (USD) |
|----------|---------------------|
| Computing Platform (Raspberry Pi 4 + accessories) | $75 - $150 |
| Motor Controller (VESC 6) | $200 - $500 |
| BMS (SimpBMS or compatible) | $300 - $800 |
| CAN Bus Interface | $20 - $100 |
| IMU Sensor (MPU-9250) | $10 - $30 |
| GPS Module | $10 - $50 |
| Temperature Sensors (8-15 sensors) | $50 - $200 |
| Cellular Module (Quectel) | $50 - $150 |
| Charging System Components | $500 - $2000 |
| Cables, Connectors, Enclosures | $100 - $500 |
| **Total (Core System)** | **$1,315 - $4,480** |
| **Total (with Autopilot/Cameras)** | **$2,000 - $6,000+** |

*Note: Costs vary significantly based on supplier, quantity, and specific component choices. Battery pack costs are not included as they vary greatly based on capacity and cell type.*

---

## Safety Considerations

1. **High Voltage Safety**: All high-voltage components (battery, motor, charging) must be properly insulated and protected
2. **EMI/RFI**: Proper shielding required for automotive environment
3. **Vibration**: All components must be rated for automotive vibration levels
4. **Temperature**: Components must operate in -40°C to +85°C range (automotive grade)
5. **Waterproofing**: External components must be IP65 or higher rated
6. **Fault Tolerance**: Critical systems must have redundancy or fail-safe modes
7. **Regulatory Compliance**: Check local regulations for EV components and modifications

---

## Revision History

- **v1.0** (2024): Initial hardware requirements document based on az1m0v project review

---

## Contact & Support

For questions about hardware requirements or compatibility, please refer to the project documentation or open an issue in the repository.

**Project**: az1m0v - Electric Vehicle Management System  
**License**: GPL v3.0


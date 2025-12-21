"""Entry point for the EV Management System (az1m0v)."""

import json
import logging
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Optional, Dict, Any

import jsonschema

from communication.can_bus import CANBusInterface, EVCANProtocol
from communication.telemetry import TelemetrySystem
from core.battery_management import BatteryManagementSystem
from core.motor_controller import VESCManager
from core.charging_system import ChargingSystem
from core.vehicle_controller import VehicleController
from sensors.imu import IMU, IMUConfig, IMUType
from sensors.temperature import TemperatureSensorManager
from ai.autopilot import AutopilotSystem
from ui.dashboard import EVDashboard


class EVSystem:
    """Main EV Management System."""

    def __init__(self, config_path: str = "config/config.json"):
        """Initialize the EV system.
        
        Args:
            config_path: Path to configuration file
        """
        self.config_path = Path(config_path)
        self.config: Dict[str, Any] = {}
        self.running = False

        # Core components
        self.can_bus: Optional[CANBusInterface] = None
        self.can_protocol: Optional[EVCANProtocol] = None
        self.bms: Optional[BatteryManagementSystem] = None
        self.motor_controller: Optional[VESCManager] = None
        self.charging_system: Optional[ChargingSystem] = None
        self.vehicle_controller: Optional[VehicleController] = None
        self.telemetry: Optional[TelemetrySystem] = None
        
        # Sensors
        self.imu: Optional[IMU] = None
        self.temperature_manager: Optional[TemperatureSensorManager] = None
        
        # AI systems
        self.autopilot: Optional[AutopilotSystem] = None
        
        # UI
        self.dashboard: Optional[EVDashboard] = None
        self.dashboard_thread: Optional[threading.Thread] = None

        # Setup logging first
        self._setup_logging()
        self.logger = logging.getLogger(__name__)

        # Load and validate configuration
        self._load_config()

        # Initialize components
        self._initialize_components()

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _setup_logging(self) -> None:
        """Setup logging configuration."""
        # Basic logging setup - will be updated after config load
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    def _load_config(self) -> None:
        """Load and validate configuration."""
        try:
            # Load configuration
            with open(self.config_path, 'r') as f:
                self.config = json.load(f)

            # Validate against schema
            schema_path = self.config_path.parent / "config_schema.json"
            if schema_path.exists():
                with open(schema_path, 'r') as f:
                    schema = json.load(f)
                jsonschema.validate(self.config, schema)
                self.logger.info("Configuration validated successfully")
            else:
                self.logger.warning("Configuration schema not found, skipping validation")

            # Update logging level from config
            log_level = getattr(logging, self.config.get('logging', {}).get('level', 'INFO'))
            logging.getLogger().setLevel(log_level)
            self.logger.info(f"Logging level set to {log_level}")

        except FileNotFoundError:
            self.logger.error(f"Configuration file not found: {self.config_path}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in configuration file: {e}")
            sys.exit(1)
        except jsonschema.ValidationError as e:
            self.logger.error(f"Configuration validation error: {e}")
            sys.exit(1)

    def _initialize_components(self) -> None:
        """Initialize system components."""
        self.logger.info("Initializing EV system components...")

        # Initialize CAN bus if enabled
        if self.config.get('communication', {}).get('can_bus_enabled', False):
            self._initialize_can_bus()

        # Initialize Battery Management System
        self._initialize_bms()

        # Initialize Motor Controller
        self._initialize_motor_controller()

        # Initialize Charging System
        self._initialize_charging_system()

        # Initialize Telemetry System
        self._initialize_telemetry()

        # Initialize Vehicle Controller
        self._initialize_vehicle_controller()

        # Initialize Sensors
        self._initialize_sensors()

        # Initialize Autopilot (if enabled)
        self._initialize_autopilot()

        # Initialize Dashboard (if enabled)
        self._initialize_dashboard()

        self.logger.info("All components initialized successfully")

    def _initialize_can_bus(self) -> None:
        """Initialize CAN bus interface."""
        try:
            can_config = self.config.get('can_bus', {})
            channel = can_config.get('channel', 'can0')
            bitrate = can_config.get('bitrate', 500000)
            interface = can_config.get('interface', 'socketcan')
            
            self.can_bus = CANBusInterface(
                channel=channel,
                bitrate=bitrate,
                interface=interface
            )

            if self.can_bus.connect():
                self.can_protocol = EVCANProtocol(self.can_bus)
                self.logger.info(f"CAN bus initialized and connected on {channel}")
            else:
                self.logger.warning("CAN bus connection failed, continuing without CAN")
        except Exception as e:
            self.logger.error(f"Failed to initialize CAN bus: {e}")

    def _initialize_bms(self) -> None:
        """Initialize Battery Management System."""
        try:
            battery_config = self.config.get('battery', {})
            self.bms = BatteryManagementSystem(
                config=battery_config,
                can_protocol=self.can_protocol
            )
            self.logger.info("Battery Management System initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize BMS: {e}")

    def _initialize_motor_controller(self) -> None:
        """Initialize Motor Controller (VESC)."""
        try:
            motor_config = self.config.get('motor', {})
            motor_controller_config = self.config.get('motor_controller', {})

            # Merge motor and motor_controller configs
            vesc_config = {
                **motor_config,
                **motor_controller_config
            }

            serial_port = motor_controller_config.get('serial_port')

            self.motor_controller = VESCManager(
                serial_port=serial_port,
                can_bus=self.can_bus,
                can_protocol=self.can_protocol,
                config=vesc_config
            )

            # Connect to motor controller if serial port is configured
            if serial_port:
                if self.motor_controller.connect():
                    self.logger.info(f"Motor controller connected on {serial_port}")
                else:
                    self.logger.warning("Motor controller connection failed")
            else:
                self.logger.info("Motor controller initialized (no serial port configured)")

        except Exception as e:
            self.logger.error(f"Failed to initialize motor controller: {e}")

    def _initialize_charging_system(self) -> None:
        """Initialize Charging System."""
        try:
            charging_config = self.config.get('charging', {})

            self.charging_system = ChargingSystem(
                config=charging_config,
                bms=self.bms,
                motor_controller=self.motor_controller,
                can_protocol=self.can_protocol
            )
            self.logger.info("Charging System initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize charging system: {e}")

    def _initialize_telemetry(self) -> None:
        """Initialize Telemetry System."""
        try:
            telemetry_config = self.config.get('telemetry', {})
            vehicle_id = self.config.get('vehicle', {}).get('serial_number', 'EV001')

            if telemetry_config.get('enabled', False):
                self.telemetry = TelemetrySystem(
                    config=telemetry_config,
                    vehicle_id=vehicle_id
                )
                if self.telemetry.connect():
                    self.logger.info("Telemetry System initialized and connected")
                else:
                    self.logger.warning("Telemetry System initialized but not connected")
            else:
                self.logger.info("Telemetry System disabled")
        except Exception as e:
            self.logger.error(f"Failed to initialize telemetry system: {e}")

    def _initialize_vehicle_controller(self) -> None:
        """Initialize Vehicle Controller."""
        try:
            vehicle_config = self.config.get('vehicle_controller', {})
            
            self.vehicle_controller = VehicleController(
                config=vehicle_config,
                bms=self.bms,
                motor_controller=self.motor_controller,
                charging_system=self.charging_system,
                can_protocol=self.can_protocol
            )
            self.logger.info("Vehicle Controller initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize vehicle controller: {e}")

    def _initialize_sensors(self) -> None:
        """Initialize sensor systems."""
        try:
            # Initialize IMU if enabled
            sensors_config = self.config.get('sensors', {})
            if sensors_config.get('imu_enabled', False):
                self._initialize_imu()
            
            # Initialize temperature sensors if enabled
            temp_config = self.config.get('temperature_sensors', {})
            if temp_config.get('enabled', True):
                self._initialize_temperature_sensors()
                
        except Exception as e:
            self.logger.error(f"Failed to initialize sensors: {e}")

    def _initialize_imu(self) -> None:
        """Initialize IMU sensor."""
        try:
            imu_config = self.config.get('imu', {})
            
            # Convert sensor type string to enum
            sensor_type_str = imu_config.get('sensor_type', 'mpu6050').lower()
            if sensor_type_str == 'mpu9250':
                sensor_type = IMUType.MPU9250
            else:
                sensor_type = IMUType.MPU6050
            
            imu_config_obj = IMUConfig(
                sensor_type=sensor_type,
                i2c_address=imu_config.get('i2c_address', 104),
                i2c_bus=imu_config.get('i2c_bus', 1),
                sampling_rate_hz=imu_config.get('sampling_rate_hz', 100.0),
                simulation_mode=imu_config.get('simulation_mode', True),
                calibration_samples=imu_config.get('calibration_samples', 100),
                accel_offset_x=imu_config.get('accel_offset_x', 0.0),
                accel_offset_y=imu_config.get('accel_offset_y', 0.0),
                accel_offset_z=imu_config.get('accel_offset_z', 0.0),
                gyro_offset_x=imu_config.get('gyro_offset_x', 0.0),
                gyro_offset_y=imu_config.get('gyro_offset_y', 0.0),
                gyro_offset_z=imu_config.get('gyro_offset_z', 0.0),
                mag_offset_x=imu_config.get('mag_offset_x', 0.0),
                mag_offset_y=imu_config.get('mag_offset_y', 0.0),
                mag_offset_z=imu_config.get('mag_offset_z', 0.0)
            )
            
            self.imu = IMU(imu_config_obj)
            if self.imu.is_connected:
                self.logger.info(f"IMU initialized: {sensor_type.value}")
            else:
                self.logger.warning("IMU initialization failed")
        except Exception as e:
            self.logger.error(f"Failed to initialize IMU: {e}")

    def _initialize_temperature_sensors(self) -> None:
        """Initialize temperature sensor manager."""
        try:
            # Temperature manager needs full config to access battery config
            self.temperature_manager = TemperatureSensorManager(config=self.config)
            self.logger.info("Temperature Sensor Manager initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize temperature sensors: {e}")

    def _initialize_autopilot(self) -> None:
        """Initialize Autopilot System."""
        try:
            ai_config = self.config.get('ai', {})
            if ai_config.get('autopilot_enabled', False):
                self.autopilot = AutopilotSystem(config=ai_config)
                self.logger.info("Autopilot System initialized")
            else:
                self.logger.info("Autopilot System disabled")
        except Exception as e:
            self.logger.error(f"Failed to initialize autopilot: {e}")

    def _initialize_dashboard(self) -> None:
        """Initialize Dashboard."""
        try:
            ui_config = self.config.get('ui', {})
            if ui_config.get('dashboard_enabled', True):
                dashboard_host = ui_config.get('dashboard_host', '0.0.0.0')
                dashboard_port = ui_config.get('dashboard_port', 5000)
                dashboard_debug = ui_config.get('dashboard_debug', False)
                
                self.dashboard = EVDashboard(
                    can_bus=self.can_bus,
                    can_protocol=self.can_protocol,
                    host=dashboard_host,
                    port=dashboard_port,
                    debug=dashboard_debug
                )
                
                # Store references to system components for dashboard control
                self.dashboard.ev_system = self
                self.dashboard.bms = self.bms
                self.dashboard.motor_controller = self.motor_controller
                self.dashboard.charging_system = self.charging_system
                self.dashboard.vehicle_controller = self.vehicle_controller
                self.dashboard.imu = self.imu
                self.dashboard.temperature_manager = self.temperature_manager
                self.dashboard.autopilot = self.autopilot
                
                self.logger.info(f"Dashboard initialized on {dashboard_host}:{dashboard_port}")
            else:
                self.logger.info("Dashboard disabled")
        except Exception as e:
            self.logger.error(f"Failed to initialize dashboard: {e}")

    def _signal_handler(self, signum, frame) -> None:
        """Handle shutdown signals."""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.shutdown()
        sys.exit(0)

    def start(self) -> None:
        """Start the EV system."""
        if self.running:
            self.logger.warning("System is already running")
            return

        self.logger.info("Starting EV Management System...")
        self.logger.info(f"Vehicle: {self.config.get('vehicle', {}).get('model', 'Unknown')}")
        self.logger.info(f"Serial: {self.config.get('vehicle', {}).get('serial_number', 'Unknown')}")

        self.running = True

        # Start dashboard in separate thread if enabled
        if self.dashboard:
            self.dashboard_thread = threading.Thread(
                target=self.dashboard.start,
                daemon=True,
                name="DashboardThread"
            )
            self.dashboard_thread.start()
            self.logger.info("Dashboard started in background thread")

        # Main loop
        try:
            while self.running:
                self._update_loop()
                time.sleep(0.1)  # 100ms update interval
        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt received")
        finally:
            self.shutdown()

    def _update_loop(self) -> None:
        """Main system update loop."""
        # Update BMS status
        if self.bms:
            # In a real system, this would read from actual sensors
            # For now, we'll just get the current status
            bms_state = self.bms.get_state()
            if bms_state:
                self.logger.debug(f"BMS Status: {bms_state.status.value}, SOC: {bms_state.soc:.1f}%")
                # Update dashboard with BMS data
                if self.dashboard:
                    self.dashboard.update_data('battery', {
                        'voltage': bms_state.voltage,
                        'current': bms_state.current,
                        'temperature': bms_state.temperature if hasattr(bms_state, 'temperature') else 25.0,
                        'soc': bms_state.soc
                    })

        # Update motor controller status
        if self.motor_controller and self.motor_controller.is_connected:
            motor_status = self.motor_controller.get_status()
            if motor_status:
                self.logger.debug(f"Motor Status: {motor_status.state.value}, RPM: {motor_status.speed_rpm:.0f}")
                # Update dashboard with motor data
                if self.dashboard:
                    self.dashboard.update_data('motor', {
                        'speed': motor_status.speed_rpm,
                        'torque': motor_status.torque_nm,
                        'temperature': motor_status.temperature_c
                    })

        # Update charging system status
        if self.charging_system and self.charging_system.is_connected():
            charging_status = self.charging_system.get_status()
            if charging_status:
                self.logger.debug(f"Charging Status: {charging_status.state.value}, Power: {charging_status.power_kw:.2f}kW")
                # Update dashboard with charging data
                if self.dashboard:
                    self.dashboard.update_data('charging', {
                        'voltage': charging_status.voltage,
                        'current': charging_status.current,
                        'state': charging_status.state.value
                    })

        # Update vehicle controller status
        if self.vehicle_controller:
            # Update status from subsystems first
            self.vehicle_controller.update_status()
            vehicle_status = self.vehicle_controller.get_status()
            if vehicle_status:
                # Update dashboard with vehicle data
                if self.dashboard:
                    self.dashboard.update_data('vehicle', {
                        'state': vehicle_status.state.value,
                        'speed': vehicle_status.speed_kmh,
                        'drive_mode': vehicle_status.drive_mode.value if vehicle_status.drive_mode else 'normal'
                    })

        # Update temperature sensors
        if self.temperature_manager:
            self._update_temperature_data()

        # Send telemetry data
        if self.telemetry and self.telemetry.is_enabled():
            self._send_telemetry_data()

    def _update_temperature_data(self) -> None:
        """Update dashboard with temperature sensor data."""
        if not self.dashboard or not self.temperature_manager:
            return
        
        try:
            temp_data = {}
            
            # Battery cell group temperatures
            battery_temps = []
            for i in range(8):  # Assuming 8 cell groups
                sensor_id = f"battery_cell_group_{i+1}"
                if sensor_id in self.temperature_manager.sensors:
                    sensor = self.temperature_manager.sensors[sensor_id]
                    reading = sensor.get_reading()
                    if reading:
                        battery_temps.append(reading.temperature)
            if battery_temps:
                temp_data['battery_cell_groups'] = battery_temps
            
            # Coolant temperatures
            if 'coolant_inlet' in self.temperature_manager.sensors:
                inlet_reading = self.temperature_manager.sensors['coolant_inlet'].get_reading()
                if inlet_reading:
                    temp_data.setdefault('coolant', {})['inlet'] = inlet_reading.temperature
            if 'coolant_outlet' in self.temperature_manager.sensors:
                outlet_reading = self.temperature_manager.sensors['coolant_outlet'].get_reading()
                if outlet_reading:
                    temp_data.setdefault('coolant', {})['outlet'] = outlet_reading.temperature
            
            # Motor stator temperatures
            motor_temps = []
            for i in range(3):  # 3 phases
                sensor_id = f"motor_stator_{i+1}"
                if sensor_id in self.temperature_manager.sensors:
                    sensor = self.temperature_manager.sensors[sensor_id]
                    reading = sensor.get_reading()
                    if reading:
                        motor_temps.append(reading.temperature)
            if motor_temps:
                temp_data['motor_stator'] = motor_temps
            
            # Charging temperatures
            if 'charging_port' in self.temperature_manager.sensors:
                port_reading = self.temperature_manager.sensors['charging_port'].get_reading()
                if port_reading:
                    temp_data.setdefault('charging', {})['port'] = port_reading.temperature
            if 'charging_connector' in self.temperature_manager.sensors:
                connector_reading = self.temperature_manager.sensors['charging_connector'].get_reading()
                if connector_reading:
                    temp_data.setdefault('charging', {})['connector'] = connector_reading.temperature
            
            if temp_data:
                self.dashboard.update_data('temperature', temp_data)
        except Exception as e:
            self.logger.error(f"Error updating temperature data: {e}")

    def _send_telemetry_data(self) -> None:
        """Collect and send telemetry data."""
        try:
            # Get BMS data
            battery_soc = 0.0
            battery_voltage = 0.0
            battery_current = 0.0
            if self.bms:
                bms_state = self.bms.get_state()
                if bms_state:
                    battery_soc = bms_state.soc
                    battery_voltage = bms_state.voltage
                    battery_current = bms_state.current

            # Get motor data
            motor_speed_rpm = 0.0
            motor_current = 0.0
            if self.motor_controller and self.motor_controller.is_connected:
                motor_status = self.motor_controller.get_status()
                if motor_status:
                    motor_speed_rpm = motor_status.speed_rpm
                    motor_current = motor_status.current_a

            # Get charging data
            charging_power_kw = 0.0
            vehicle_state = "unknown"
            if self.charging_system:
                charging_status = self.charging_system.get_status()
                if charging_status:
                    charging_power_kw = charging_status.power_kw
                    vehicle_state = charging_status.state.value

            # Get temperature (from BMS if available)
            temperature = 25.0
            if self.bms:
                bms_state = self.bms.get_state()
                if bms_state and hasattr(bms_state, 'temperature'):
                    temperature = bms_state.temperature

            # Send telemetry data
            self.telemetry.send_data(
                battery_soc=battery_soc,
                battery_voltage=battery_voltage,
                battery_current=battery_current,
                motor_speed_rpm=motor_speed_rpm,
                motor_current=motor_current,
                vehicle_speed_kmh=0.0,  # Would come from vehicle controller
                charging_power_kw=charging_power_kw,
                temperature=temperature,
                state=vehicle_state
            )
        except Exception as e:
            self.logger.error(f"Error sending telemetry data: {e}")

    def shutdown(self) -> None:
        """Shutdown the EV system gracefully."""
        if not self.running:
            return

        self.logger.info("Shutting down EV system...")
        self.running = False

        # Stop charging if active
        if self.charging_system and self.charging_system.is_charging():
            self.charging_system.stop_charging()
            self.charging_system.disconnect_charger()
            self.logger.info("Charging system stopped and disconnected")

        # Stop motor controller
        if self.motor_controller and self.motor_controller.is_connected:
            self.motor_controller.stop()
            self.motor_controller.disconnect()
            self.logger.info("Motor controller stopped and disconnected")

        # Disconnect telemetry
        if self.telemetry:
            self.telemetry.disconnect()
            self.logger.info("Telemetry system disconnected")

        # Stop dashboard
        if self.dashboard:
            self.dashboard.stop()
            if self.dashboard_thread:
                self.dashboard_thread.join(timeout=2.0)
            self.logger.info("Dashboard stopped")

        # Disconnect CAN bus
        if self.can_bus and self.can_bus.is_connected:
            self.can_bus.disconnect()
            self.logger.info("CAN bus disconnected")

        self.logger.info("EV system shutdown complete")


def main() -> None:
    """Main entry point."""
    # Check if config file exists
    config_path = Path("config/config.json")
    if not config_path.exists():
        print(f"Error: Configuration file not found: {config_path}")
        print("Please ensure config/config.json exists and is properly configured.")
        sys.exit(1)

    # Create and start system
    system = EVSystem(config_path=str(config_path))
    system.start()


if __name__ == "__main__":
    main()

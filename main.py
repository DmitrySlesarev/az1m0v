"""Entry point for the EV Management System (az1m0v)."""

import json
import logging
import signal
import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any

import jsonschema

from communication.can_bus import CANBusInterface, EVCANProtocol
from core.battery_management import BatteryManagementSystem
from core.motor_controller import VESCManager
from core.charging_system import ChargingSystem


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

        self.logger.info("All components initialized successfully")

    def _initialize_can_bus(self) -> None:
        """Initialize CAN bus interface."""
        try:
            self.can_bus = CANBusInterface(
                channel="can0",
                bitrate=500000,
                interface="socketcan"
            )

            if self.can_bus.connect():
                self.can_protocol = EVCANProtocol(self.can_bus)
                self.logger.info("CAN bus initialized and connected")
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

        # Update motor controller status
        if self.motor_controller and self.motor_controller.is_connected:
            motor_status = self.motor_controller.get_status()
            if motor_status:
                self.logger.debug(f"Motor Status: {motor_status.state.value}, RPM: {motor_status.speed_rpm:.0f}")

        # Update charging system status
        if self.charging_system and self.charging_system.is_connected():
            charging_status = self.charging_system.get_status()
            if charging_status:
                self.logger.debug(f"Charging Status: {charging_status.state.value}, Power: {charging_status.power_kw:.2f}kW")

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

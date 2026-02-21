"""Entry point for running the dashboard as a module."""

import sys
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from ui.dashboard import EVDashboard
from communication.can_bus import CANBusInterface, EVCANProtocol
from config.settings import Settings

def load_config(config_path: str = "config/config.json") -> dict:
    """Load and validate configuration."""
    try:
        schema_path = Path(config_path).parent / "config_schema.json"
        settings = Settings(config_path=config_path, schema_path=str(schema_path))
        return settings.config
    except Exception as e:
        logging.warning(f"Failed to load config: {e}, using defaults")
        return {}

if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger = logging.getLogger(__name__)
    
    # Load configuration
    config = load_config()
    
    # Initialize CAN bus if enabled
    can_bus = None
    can_protocol = None
    
    if config.get('communication', {}).get('can_bus_enabled', False):
        try:
            can_config = config.get('can_bus', {})
            can_channel = can_config.get('channel', 'can0')
            can_bitrate = can_config.get('bitrate', 500000)
            can_interface = can_config.get('interface', 'socketcan')
            can_bus = CANBusInterface(can_channel, can_bitrate, can_interface)
            if can_bus.connect():
                can_protocol = EVCANProtocol(can_bus)
                logger.info("CAN bus initialized for dashboard")
            else:
                logger.warning("CAN bus connection failed, dashboard will run without CAN")
        except Exception as e:
            logger.warning(f"Failed to initialize CAN bus: {e}")
    
    # Get dashboard settings from config
    dashboard_config = config.get('ui', {})
    host = dashboard_config.get('dashboard_host', '0.0.0.0')
    port = dashboard_config.get('dashboard_port', 5000)
    debug = dashboard_config.get('dashboard_debug', False)
    secret_key = dashboard_config.get('dashboard_secret_key', 'ev-dashboard-secret-key')
    update_interval_s = dashboard_config.get('dashboard_update_interval_s', 1.0)
    socketio_cors = dashboard_config.get('dashboard_socketio_cors', '*')
    
    # Create and start dashboard
    dashboard = EVDashboard(
        can_bus=can_bus,
        can_protocol=can_protocol,
        host=host,
        port=port,
        debug=debug,
        secret_key=secret_key,
        update_interval_s=update_interval_s,
        socketio_cors=socketio_cors
    )
    
    logger.info(f"Starting EV Dashboard on http://{host}:{port}")
    try:
        dashboard.start()
    except KeyboardInterrupt:
        logger.info("Shutting down dashboard...")
        dashboard.stop()


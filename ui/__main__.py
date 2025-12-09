"""Entry point for running the dashboard as a module."""

import sys
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from ui.dashboard import EVDashboard
from communication.can_bus import CANBusInterface, EVCANProtocol
import json
import jsonschema

def load_config(config_path: str = "config/config.json"):
    """Load and validate configuration."""
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        return config
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
            can_bus = CANBusInterface("can0", 500000)
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
    
    # Create and start dashboard
    dashboard = EVDashboard(
        can_bus=can_bus,
        can_protocol=can_protocol,
        host=host,
        port=port,
        debug=False
    )
    
    logger.info(f"Starting EV Dashboard on http://{host}:{port}")
    try:
        dashboard.start()
    except KeyboardInterrupt:
        logger.info("Shutting down dashboard...")
        dashboard.stop()


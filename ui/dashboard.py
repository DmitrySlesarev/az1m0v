"""Web-based dashboard for EV management system with CAN bus integration."""

import json
import logging
import struct
import threading
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit

from communication.can_bus import CANBusInterface, EVCANProtocol, CANFrame, CANMessage


class EVDashboard:
    """Web-based dashboard for EV monitoring and control."""

    def __init__(
        self,
        can_bus: Optional[CANBusInterface] = None,
        can_protocol: Optional[EVCANProtocol] = None,
        host: str = "0.0.0.0",
        port: int = 5000,
        debug: bool = False
    ):
        """Initialize the EV dashboard.
        
        Args:
            can_bus: CAN bus interface instance
            can_protocol: EV CAN protocol instance
            host: Host address to bind to (0.0.0.0 for all interfaces)
            port: Port number to listen on
            debug: Enable debug mode
        """
        self.can_bus = can_bus
        self.can_protocol = can_protocol
        self.host = host
        self.port = port
        self.debug = debug
        self.logger = logging.getLogger(__name__)
        
        # Dashboard state
        self.clients: List[str] = []
        self.running = False
        self.update_thread: Optional[threading.Thread] = None
        
        # Latest data cache
        self.latest_data: Dict[str, Any] = {
            'battery': {},
            'motor': {},
            'charging': {},
            'vehicle': {},
            'can_stats': {},
            'timestamp': time.time()
        }
        
        # Initialize Flask app
        self.app = Flask(__name__, template_folder=str(Path(__file__).parent / 'templates'))
        self.app.config['SECRET_KEY'] = 'ev-dashboard-secret-key'
        self.socketio = SocketIO(
            self.app,
            cors_allowed_origins="*",
            async_mode='threading',  # Use threading for Raspberry Pi compatibility
            logger=False,
            engineio_logger=False
        )
        
        # Setup routes and socket handlers
        self._setup_routes()
        self._setup_socket_handlers()
        
        # Register CAN bus message handlers if available
        if self.can_bus and self.can_protocol:
            self._register_can_handlers()

    def _setup_routes(self) -> None:
        """Setup Flask routes."""
        
        @self.app.route('/')
        def index():
            """Serve the main dashboard page."""
            return render_template('dashboard.html')
        
        @self.app.route('/api/status')
        def api_status():
            """REST API endpoint for current status."""
            return json.dumps(self.latest_data, indent=2)

    def _setup_socket_handlers(self) -> None:
        """Setup WebSocket event handlers."""
        
        @self.socketio.on('connect')
        def handle_connect():
            """Handle client connection."""
            client_id = request.sid
            self.clients.append(client_id)
            self.logger.info(f"Client connected: {client_id}")
            # Send current state to new client
            emit('data_update', self.latest_data)
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            """Handle client disconnection."""
            client_id = request.sid
            if client_id in self.clients:
                self.clients.remove(client_id)
            self.logger.info(f"Client disconnected: {client_id}")
        
        @self.socketio.on('request_update')
        def handle_request_update():
            """Handle client request for data update."""
            emit('data_update', self.latest_data)

    def _register_can_handlers(self) -> None:
        """Register CAN bus message handlers."""
        if not self.can_bus or not self.can_protocol:
            return
        
        # Register handlers for all EV CAN IDs
        can_ids = self.can_protocol.CAN_IDS
        
        def create_handler(can_id: int, message_type: str):
            """Create a handler function for a specific CAN ID."""
            def handler(frame: CANFrame):
                try:
                    # Parse message based on type
                    if message_type == 'BMS_STATUS':
                        # Parse battery status (CAN frame max 8 bytes = 2 floats)
                        # Note: In real implementation, full status may require multiple frames
                        if len(frame.data) >= 8:
                            voltage = self._unpack_float(frame.data[0:4])
                            current = self._unpack_float(frame.data[4:8])
                            # Use default values for temperature and SOC if not in frame
                            temperature = 0.0
                            soc = 0.0
                            if len(frame.data) >= 12:
                                temperature = self._unpack_float(frame.data[8:12])
                            if len(frame.data) >= 16:
                                soc = self._unpack_float(frame.data[12:16])
                            self._update_battery_data(voltage, current, temperature, soc)
                    elif message_type == 'MOTOR_STATUS':
                        # Parse motor status
                        if len(frame.data) >= 12:
                            speed = self._unpack_float(frame.data[0:4])
                            torque = self._unpack_float(frame.data[4:8])
                            temp = self._unpack_float(frame.data[8:12])
                            self._update_motor_data(speed, torque, temp)
                    elif message_type == 'CHARGER_STATUS':
                        # Parse charger status
                        if len(frame.data) >= 12:
                            voltage = self._unpack_float(frame.data[0:4])
                            current = self._unpack_float(frame.data[4:8])
                            state_bytes = frame.data[8:12]
                            state = "unknown"
                            if state_bytes[0] == 0:
                                state = "idle"
                            elif state_bytes[0] == 1:
                                state = "charging"
                            elif state_bytes[0] == 2:
                                state = "complete"
                            self._update_charging_data(voltage, current, state)
                    elif message_type == 'VEHICLE_STATUS':
                        # Parse vehicle status
                        if len(frame.data) >= 4:
                            status_byte = frame.data[0]
                            states = ["parked", "ready", "driving", "charging", "error", "emergency"]
                            if status_byte < len(states):
                                state = states[status_byte]
                                self._update_vehicle_data(state)
                except Exception as e:
                    self.logger.error(f"Error handling CAN frame {can_id:03X}: {e}")
            return handler
        
        # Register handlers for key message types
        if 'BMS_STATUS' in can_ids:
            self.can_bus.register_message_handler(
                can_ids['BMS_STATUS'],
                create_handler(can_ids['BMS_STATUS'], 'BMS_STATUS')
            )
        if 'MOTOR_STATUS' in can_ids:
            self.can_bus.register_message_handler(
                can_ids['MOTOR_STATUS'],
                create_handler(can_ids['MOTOR_STATUS'], 'MOTOR_STATUS')
            )
        if 'CHARGER_STATUS' in can_ids:
            self.can_bus.register_message_handler(
                can_ids['CHARGER_STATUS'],
                create_handler(can_ids['CHARGER_STATUS'], 'CHARGER_STATUS')
            )
        if 'VEHICLE_STATUS' in can_ids:
            self.can_bus.register_message_handler(
                can_ids['VEHICLE_STATUS'],
                create_handler(can_ids['VEHICLE_STATUS'], 'VEHICLE_STATUS')
            )

    def _unpack_float(self, data: bytes) -> float:
        """Unpack a float from bytes (little-endian)."""
        if len(data) < 4:
            return 0.0
        try:
            return struct.unpack('<f', data[:4])[0]
        except struct.error:
            return 0.0

    def _update_battery_data(self, voltage: float, current: float, temperature: float, soc: float) -> None:
        """Update battery data and broadcast to clients."""
        self.latest_data['battery'] = {
            'voltage': round(voltage, 2),
            'current': round(current, 2),
            'temperature': round(temperature, 2),
            'soc': round(soc * 100, 1)  # Convert to percentage
        }
        self.latest_data['timestamp'] = time.time()
        self._broadcast_update()

    def _update_motor_data(self, speed: float, torque: float, temperature: float) -> None:
        """Update motor data and broadcast to clients."""
        self.latest_data['motor'] = {
            'speed': round(speed, 1),
            'torque': round(torque, 1),
            'temperature': round(temperature, 2)
        }
        self.latest_data['timestamp'] = time.time()
        self._broadcast_update()

    def _update_charging_data(self, voltage: float, current: float, state: str) -> None:
        """Update charging data and broadcast to clients."""
        self.latest_data['charging'] = {
            'voltage': round(voltage, 2),
            'current': round(current, 2),
            'state': state
        }
        self.latest_data['timestamp'] = time.time()
        self._broadcast_update()

    def _update_vehicle_data(self, state: str) -> None:
        """Update vehicle state and broadcast to clients."""
        self.latest_data['vehicle'] = {
            'state': state
        }
        self.latest_data['timestamp'] = time.time()
        self._broadcast_update()

    def _update_can_stats(self) -> None:
        """Update CAN bus statistics."""
        if self.can_bus:
            stats = self.can_bus.get_statistics()
            self.latest_data['can_stats'] = {
                'frames_sent': stats.get('frames_sent', 0),
                'frames_received': stats.get('frames_received', 0),
                'errors': stats.get('errors', 0),
                'is_connected': stats.get('is_connected', False),
                'last_activity': stats.get('last_activity', 0.0)
            }
            self.latest_data['timestamp'] = time.time()

    def _broadcast_update(self) -> None:
        """Broadcast data update to all connected clients."""
        if self.clients:
            self.socketio.emit('data_update', self.latest_data)

    def _update_loop(self) -> None:
        """Background thread to periodically update CAN stats."""
        while self.running:
            try:
                self._update_can_stats()
                if self.clients:
                    self._broadcast_update()
                time.sleep(1.0)  # Update every second
            except Exception as e:
                self.logger.error(f"Error in update loop: {e}")
                time.sleep(1.0)

    def start(self) -> None:
        """Start the dashboard server."""
        if self.running:
            self.logger.warning("Dashboard is already running")
            return
        
        self.running = True
        self.update_thread = threading.Thread(target=self._update_loop, daemon=True)
        self.update_thread.start()
        
        self.logger.info(f"Starting EV Dashboard on {self.host}:{self.port}")
        try:
            self.socketio.run(
                self.app,
                host=self.host,
                port=self.port,
                debug=self.debug,
                use_reloader=False,  # Disable reloader for Raspberry Pi
                allow_unsafe_werkzeug=True
            )
        except Exception as e:
            self.logger.error(f"Failed to start dashboard: {e}")
            self.running = False

    def stop(self) -> None:
        """Stop the dashboard server."""
        self.running = False
        if self.update_thread:
            self.update_thread.join(timeout=2.0)
        self.logger.info("Dashboard stopped")

    def update_data(self, data_type: str, data: Dict[str, Any]) -> None:
        """Manually update dashboard data (for testing or external updates).
        
        Args:
            data_type: Type of data ('battery', 'motor', 'charging', 'vehicle')
            data: Data dictionary to update
        """
        if data_type in self.latest_data:
            self.latest_data[data_type].update(data)
            self.latest_data['timestamp'] = time.time()
            self._broadcast_update()

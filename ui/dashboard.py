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
            'temperature': {
                'battery_cell_groups': [],
                'coolant': {'inlet': None, 'outlet': None},
                'motor_stator': [],
                'charging': {'port': None, 'connector': None}
            },
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
            if client_id not in self.clients:
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
        
        @self.socketio.on('control_command')
        def handle_control_command(data: Dict[str, Any]):
            """Handle control commands from client.
            
            Expected data format:
            {
                'command': 'accelerate' | 'brake' | 'stop' | 'set_drive_mode' | 'start_charging' | 
                          'stop_charging' | 'set_vehicle_state' | 'set_autopilot_mode',
                'params': {...}  # Command-specific parameters
            }
            """
            try:
                command = data.get('command')
                params = data.get('params', {})
                result = self._handle_control_command(command, params)
                emit('control_response', {'success': result, 'command': command})
            except Exception as e:
                self.logger.error(f"Error handling control command: {e}")
                emit('control_response', {'success': False, 'command': data.get('command'), 'error': str(e)})

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
        
        # Register temperature sensor handlers
        temp_can_ids = [
            'TEMPERATURE_BATTERY_CELL_GROUP',
            'TEMPERATURE_COOLANT_INLET',
            'TEMPERATURE_COOLANT_OUTLET',
            'TEMPERATURE_MOTOR_STATOR',
            'TEMPERATURE_CHARGING_PORT',
            'TEMPERATURE_CHARGING_CONNECTOR'
        ]
        
        for temp_id in temp_can_ids:
            if temp_id in can_ids:
                self.can_bus.register_message_handler(
                    can_ids[temp_id],
                    self._create_temperature_handler(can_ids[temp_id], temp_id)
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

    def _create_temperature_handler(self, can_id: int, sensor_type: str):
        """Create a handler function for temperature sensor CAN messages."""
        def handler(frame: CANFrame):
            try:
                # Try to use CAN protocol's parse method if available
                if self.can_protocol and hasattr(self.can_protocol, 'parse_temperature_data'):
                    parsed = self.can_protocol.parse_temperature_data(frame)
                    if parsed:
                        temperature = parsed.get('temperature', 0.0)
                        sensor_id = parsed.get('sensor_id', 'unknown')
                        parsed_type = parsed.get('sensor_type', sensor_type.lower().replace('temperature_', ''))
                        self._update_temperature_data(parsed_type, sensor_id, temperature)
                        return
                
                # Fallback: Parse temperature directly from frame
                if len(frame.data) >= 4:
                    temperature = self._unpack_float(frame.data[0:4])
                    
                    # Map CAN ID to sensor type
                    sensor_type_map = {
                        'TEMPERATURE_BATTERY_CELL_GROUP': 'battery_cell_group',
                        'TEMPERATURE_COOLANT_INLET': 'coolant_inlet',
                        'TEMPERATURE_COOLANT_OUTLET': 'coolant_outlet',
                        'TEMPERATURE_MOTOR_STATOR': 'motor_stator',
                        'TEMPERATURE_CHARGING_PORT': 'charging_port',
                        'TEMPERATURE_CHARGING_CONNECTOR': 'charging_connector'
                    }
                    
                    mapped_type = sensor_type_map.get(sensor_type, 'unknown')
                    sensor_id = f"{mapped_type}_{can_id}"
                    self._update_temperature_data(mapped_type, sensor_id, temperature)
                    
            except Exception as e:
                self.logger.error(f"Error handling temperature frame {can_id:03X}: {e}")
        return handler

    def _update_temperature_data(self, sensor_type: str, sensor_id: str, temperature: float) -> None:
        """Update temperature sensor data and broadcast to clients.
        
        Args:
            sensor_type: Type of temperature sensor
            sensor_id: Sensor identifier
            temperature: Temperature reading in Celsius
        """
        temp_data = self.latest_data['temperature']
        
        if sensor_type == 'battery_cell_group':
            if 'battery_cell_groups' not in temp_data:
                temp_data['battery_cell_groups'] = []
            # Try to update specific cell group by ID, or append
            try:
                group_num = int(sensor_id.split('_')[-1]) - 1
                while len(temp_data['battery_cell_groups']) <= group_num:
                    temp_data['battery_cell_groups'].append(None)
                temp_data['battery_cell_groups'][group_num] = round(temperature, 2)
            except (ValueError, IndexError):
                # Fallback: append to list
                temp_data['battery_cell_groups'].append(round(temperature, 2))
        elif sensor_type == 'coolant_inlet':
            temp_data['coolant']['inlet'] = round(temperature, 2)
        elif sensor_type == 'coolant_outlet':
            temp_data['coolant']['outlet'] = round(temperature, 2)
        elif sensor_type == 'motor_stator':
            if 'motor_stator' not in temp_data:
                temp_data['motor_stator'] = []
            try:
                phase_num = int(sensor_id.split('_')[-1]) - 1
                while len(temp_data['motor_stator']) <= phase_num:
                    temp_data['motor_stator'].append(None)
                temp_data['motor_stator'][phase_num] = round(temperature, 2)
            except (ValueError, IndexError):
                temp_data['motor_stator'].append(round(temperature, 2))
        elif sensor_type == 'charging_port':
            temp_data['charging']['port'] = round(temperature, 2)
        elif sensor_type == 'charging_connector':
            temp_data['charging']['connector'] = round(temperature, 2)
        
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
        try:
            if self.clients:
                self.socketio.emit('data_update', self.latest_data)
            else:
                # Broadcast to all namespaces if no specific clients tracked
                # This helps with tests where clients might not be in self.clients
                self.socketio.emit('data_update', self.latest_data, namespace='/')
        except Exception as e:
            self.logger.warning(f"Failed to broadcast update: {e}")

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

    def _handle_control_command(self, command: str, params: Dict[str, Any]) -> bool:
        """Handle control commands from dashboard clients.
        
        Args:
            command: Command name
            params: Command parameters
            
        Returns:
            True if command executed successfully, False otherwise
        """
        # Store references to system components (set by main.py)
        ev_system = getattr(self, 'ev_system', None)
        vehicle_controller = getattr(self, 'vehicle_controller', None)
        motor_controller = getattr(self, 'motor_controller', None)
        charging_system = getattr(self, 'charging_system', None)
        autopilot = getattr(self, 'autopilot', None)
        
        try:
            if command == 'accelerate':
                if vehicle_controller:
                    throttle = params.get('throttle', 0.0)
                    return vehicle_controller.accelerate(throttle)
                return False
            
            elif command == 'brake':
                if vehicle_controller:
                    brake_percent = params.get('brake', 0.0)
                    return vehicle_controller.brake(brake_percent)
                return False
            
            elif command == 'stop':
                if vehicle_controller:
                    return vehicle_controller.stop_driving()
                elif motor_controller:
                    return motor_controller.stop()
                return False
            
            elif command == 'set_drive_mode':
                if vehicle_controller:
                    mode_str = params.get('mode', 'normal').lower()
                    from core.vehicle_controller import DriveMode
                    mode_map = {
                        'eco': DriveMode.ECO,
                        'normal': DriveMode.NORMAL,
                        'sport': DriveMode.SPORT,
                        'reverse': DriveMode.REVERSE
                    }
                    mode = mode_map.get(mode_str, DriveMode.NORMAL)
                    return vehicle_controller.set_drive_mode(mode)
                return False
            
            elif command == 'start_charging':
                if charging_system:
                    power_kw = params.get('power_kw', None)
                    return charging_system.start_charging(power_kw=power_kw)
                return False
            
            elif command == 'stop_charging':
                if charging_system:
                    return charging_system.stop_charging()
                return False
            
            elif command == 'set_vehicle_state':
                if vehicle_controller:
                    state_str = params.get('state', 'parked').lower()
                    from core.vehicle_controller import VehicleState
                    state_map = {
                        'parked': VehicleState.PARKED,
                        'ready': VehicleState.READY,
                        'driving': VehicleState.DRIVING,
                        'charging': VehicleState.CHARGING,
                        'error': VehicleState.ERROR,
                        'emergency': VehicleState.EMERGENCY,
                        'standby': VehicleState.STANDBY
                    }
                    state = state_map.get(state_str, VehicleState.PARKED)
                    return vehicle_controller.set_state(state)
                return False
            
            elif command == 'set_autopilot_mode':
                if autopilot:
                    mode_str = params.get('mode', 'manual').lower()
                    from ai.autopilot import DrivingMode
                    mode_map = {
                        'manual': DrivingMode.MANUAL,
                        'assist': DrivingMode.ASSIST,
                        'autopilot': DrivingMode.AUTOPILOT,
                        'emergency': DrivingMode.EMERGENCY
                    }
                    mode = mode_map.get(mode_str, DrivingMode.MANUAL)
                    if mode == DrivingMode.MANUAL:
                        autopilot.deactivate()
                        return True
                    else:
                        return autopilot.activate(mode)
                return False
            
            else:
                self.logger.warning(f"Unknown control command: {command}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error executing control command {command}: {e}")
            return False

    def update_data(self, data_type: str, data: Dict[str, Any]) -> None:
        """Manually update dashboard data (for testing or external updates).
        
        Args:
            data_type: Type of data ('battery', 'motor', 'charging', 'vehicle', 'temperature')
            data: Data dictionary to update
        """
        if data_type in self.latest_data:
            if data_type == 'temperature' and isinstance(data, dict):
                # Deep update for temperature data
                for key, value in data.items():
                    if key in self.latest_data['temperature']:
                        if isinstance(value, dict):
                            self.latest_data['temperature'][key].update(value)
                        else:
                            self.latest_data['temperature'][key] = value
            else:
                self.latest_data[data_type].update(data)
            self.latest_data['timestamp'] = time.time()
            self._broadcast_update()

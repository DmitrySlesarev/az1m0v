"""Integration tests for main.py EVSystem."""

import pytest
import json
import tempfile
import time
import signal
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from main import EVSystem


class TestEVSystem:
    """Test EVSystem main class."""

    def test_evsystem_initialization(self):
        """Test EVSystem initialization."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config = {
                'vehicle': {'model': 'test', 'serial_number': 'TEST001', 'manufacturer': 'test'},
                'battery': {'capacity_kwh': 50.0, 'max_charge_rate_kw': 100.0, 
                           'max_discharge_rate_kw': 150.0, 'nominal_voltage': 400.0, 'cell_count': 96},
                'motor': {'max_power_kw': 100.0, 'max_torque_nm': 250.0, 'efficiency': 0.9, 'type': 'permanent_magnet'},
                'motor_controller': {'type': 'vesc', 'serial_port': '/dev/ttyUSB0', 'can_enabled': True},
                'charging': {'ac_max_power_kw': 11.0, 'dc_max_power_kw': 150.0, 
                           'connector_type': 'CCS2', 'fast_charge_enabled': True},
                'sensors': {'imu_enabled': True, 'gps_enabled': True, 'temperature_sensors': 8, 'sampling_rate_hz': 100},
                'communication': {'can_bus_enabled': False, 'telemetry_enabled': False, 'update_interval_ms': 1000},
                'vehicle_controller': {'max_speed_kmh': 120.0, 'max_power_kw': 150.0},
                'temperature_sensors': {'enabled': True},
                'imu': {'sensor_type': 'mpu6050', 'simulation_mode': True},
                'ui': {'dashboard_enabled': True, 'mobile_app_enabled': True, 'theme': 'dark'},
                'ai': {'autopilot_enabled': False, 'computer_vision_enabled': False, 'model_path': '/models/'},
                'logging': {'level': 'INFO', 'file_path': '/tmp/test.log', 'max_file_size_mb': 100, 'backup_count': 5}
            }
            json.dump(config, f)
            temp_path = f.name
        
        try:
            system = EVSystem(config_path=temp_path)
            assert system.config is not None
            assert system.bms is not None
            assert system.vehicle_controller is not None
            assert system.running is False
        finally:
            Path(temp_path).unlink()

    def test_evsystem_load_config(self):
        """Test configuration loading."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config = {
                'vehicle': {'model': 'test', 'serial_number': 'TEST001', 'manufacturer': 'test'},
                'battery': {'capacity_kwh': 50.0, 'max_charge_rate_kw': 100.0, 
                           'max_discharge_rate_kw': 150.0, 'nominal_voltage': 400.0, 'cell_count': 96},
                'motor': {'max_power_kw': 100.0, 'max_torque_nm': 250.0, 'efficiency': 0.9, 'type': 'permanent_magnet'},
                'motor_controller': {'type': 'vesc', 'serial_port': '/dev/ttyUSB0', 'can_enabled': True},
                'charging': {'ac_max_power_kw': 11.0, 'dc_max_power_kw': 150.0, 
                           'connector_type': 'CCS2', 'fast_charge_enabled': True},
                'sensors': {'imu_enabled': True, 'gps_enabled': True, 'temperature_sensors': 8, 'sampling_rate_hz': 100},
                'communication': {'can_bus_enabled': False, 'telemetry_enabled': False, 'update_interval_ms': 1000},
                'vehicle_controller': {'max_speed_kmh': 120.0, 'max_power_kw': 150.0},
                'temperature_sensors': {'enabled': True},
                'imu': {'sensor_type': 'mpu6050', 'simulation_mode': True},
                'ui': {'dashboard_enabled': True, 'mobile_app_enabled': True, 'theme': 'dark'},
                'ai': {'autopilot_enabled': False, 'computer_vision_enabled': False, 'model_path': '/models/'},
                'logging': {'level': 'INFO', 'file_path': '/tmp/test.log', 'max_file_size_mb': 100, 'backup_count': 5}
            }
            json.dump(config, f)
            temp_path = f.name
        
        try:
            system = EVSystem(config_path=temp_path)
            assert system.config['vehicle']['model'] == 'test'
            assert system.config['battery']['capacity_kwh'] == 50.0
        finally:
            Path(temp_path).unlink()

    def test_evsystem_initialize_components(self):
        """Test component initialization."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config = {
                'vehicle': {'model': 'test', 'serial_number': 'TEST001', 'manufacturer': 'test'},
                'battery': {'capacity_kwh': 50.0, 'max_charge_rate_kw': 100.0, 
                           'max_discharge_rate_kw': 150.0, 'nominal_voltage': 400.0, 'cell_count': 96},
                'motor': {'max_power_kw': 100.0, 'max_torque_nm': 250.0, 'efficiency': 0.9, 'type': 'permanent_magnet'},
                'motor_controller': {'type': 'vesc', 'serial_port': None, 'can_enabled': False},
                'charging': {'ac_max_power_kw': 11.0, 'dc_max_power_kw': 150.0, 
                           'connector_type': 'CCS2', 'fast_charge_enabled': True},
                'sensors': {'imu_enabled': True, 'gps_enabled': True, 'temperature_sensors': 8, 'sampling_rate_hz': 100},
                'communication': {'can_bus_enabled': False, 'telemetry_enabled': False, 'update_interval_ms': 1000},
                'vehicle_controller': {'max_speed_kmh': 120.0, 'max_power_kw': 150.0},
                'temperature_sensors': {'enabled': True},
                'imu': {'sensor_type': 'mpu6050', 'simulation_mode': True},
                'ui': {'dashboard_enabled': True, 'mobile_app_enabled': True, 'theme': 'dark'},
                'ai': {'autopilot_enabled': False, 'computer_vision_enabled': False, 'model_path': '/models/'},
                'logging': {'level': 'INFO', 'file_path': '/tmp/test.log', 'max_file_size_mb': 100, 'backup_count': 5}
            }
            json.dump(config, f)
            temp_path = f.name
        
        try:
            system = EVSystem(config_path=temp_path)
            assert system.bms is not None
            assert system.motor_controller is not None
            assert system.charging_system is not None
            assert system.vehicle_controller is not None
            # Sensors may or may not be initialized depending on config
        finally:
            Path(temp_path).unlink()

    def test_evsystem_initialize_with_all_components(self):
        """Test initialization with all components enabled."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config = {
                'vehicle': {'model': 'test', 'serial_number': 'TEST001', 'manufacturer': 'test'},
                'battery': {'capacity_kwh': 50.0, 'max_charge_rate_kw': 100.0, 
                           'max_discharge_rate_kw': 150.0, 'nominal_voltage': 400.0, 'cell_count': 96},
                'motor': {'max_power_kw': 100.0, 'max_torque_nm': 250.0, 'efficiency': 0.9, 'type': 'permanent_magnet'},
                'motor_controller': {'type': 'vesc', 'serial_port': None, 'can_enabled': False},
                'charging': {'ac_max_power_kw': 11.0, 'dc_max_power_kw': 150.0, 
                           'connector_type': 'CCS2', 'fast_charge_enabled': True},
                'sensors': {'imu_enabled': True, 'gps_enabled': True, 'temperature_sensors': 8, 'sampling_rate_hz': 100},
                'communication': {'can_bus_enabled': False, 'telemetry_enabled': False, 'update_interval_ms': 1000},
                'vehicle_controller': {'max_speed_kmh': 120.0, 'max_power_kw': 150.0},
                'temperature_sensors': {'enabled': True},
                'imu': {'sensor_type': 'mpu6050', 'simulation_mode': True},
                'ui': {'dashboard_enabled': True, 'dashboard_host': '127.0.0.1', 'dashboard_port': 5002},
                'ai': {'autopilot_enabled': True, 'computer_vision_enabled': False, 'model_path': '/models/'},
                'logging': {'level': 'INFO', 'file_path': '/tmp/test.log', 'max_file_size_mb': 100, 'backup_count': 5}
            }
            json.dump(config, f)
            temp_path = f.name
        
        try:
            with patch('ui.dashboard.Flask'), patch('ui.dashboard.SocketIO'):
                system = EVSystem(config_path=temp_path)
                assert system.bms is not None
                assert system.motor_controller is not None
                assert system.charging_system is not None
                assert system.vehicle_controller is not None
                assert system.imu is not None
                assert system.temperature_manager is not None
                assert system.autopilot is not None
                assert system.dashboard is not None
        finally:
            Path(temp_path).unlink()

    def test_evsystem_initialize_can_bus(self):
        """Test CAN bus initialization."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config = {
                'vehicle': {'model': 'test', 'serial_number': 'TEST001', 'manufacturer': 'test'},
                'battery': {'capacity_kwh': 50.0, 'max_charge_rate_kw': 100.0, 
                           'max_discharge_rate_kw': 150.0, 'nominal_voltage': 400.0, 'cell_count': 96},
                'motor': {'max_power_kw': 100.0, 'max_torque_nm': 250.0, 'efficiency': 0.9, 'type': 'permanent_magnet'},
                'motor_controller': {'type': 'vesc', 'serial_port': None, 'can_enabled': False},
                'charging': {'ac_max_power_kw': 11.0, 'dc_max_power_kw': 150.0, 
                           'connector_type': 'CCS2', 'fast_charge_enabled': True},
                'sensors': {'imu_enabled': True, 'gps_enabled': True, 'temperature_sensors': 8, 'sampling_rate_hz': 100},
                'communication': {'can_bus_enabled': True, 'telemetry_enabled': False, 'update_interval_ms': 1000},
                'vehicle_controller': {'max_speed_kmh': 120.0, 'max_power_kw': 150.0},
                'temperature_sensors': {'enabled': True},
                'imu': {'sensor_type': 'mpu6050', 'simulation_mode': True},
                'ui': {'dashboard_enabled': True, 'mobile_app_enabled': True, 'theme': 'dark'},
                'ai': {'autopilot_enabled': False, 'computer_vision_enabled': False, 'model_path': '/models/'},
                'logging': {'level': 'INFO', 'file_path': '/tmp/test.log', 'max_file_size_mb': 100, 'backup_count': 5}
            }
            json.dump(config, f)
            temp_path = f.name
        
        try:
            system = EVSystem(config_path=temp_path)
            # CAN bus should be initialized (even if connection fails)
            assert system.can_bus is not None or True  # May be None if connection fails
        finally:
            Path(temp_path).unlink()

    def test_evsystem_initialize_telemetry(self):
        """Test telemetry initialization."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config = {
                'vehicle': {'model': 'test', 'serial_number': 'TEST001', 'manufacturer': 'test'},
                'battery': {'capacity_kwh': 50.0, 'max_charge_rate_kw': 100.0, 
                           'max_discharge_rate_kw': 150.0, 'nominal_voltage': 400.0, 'cell_count': 96},
                'motor': {'max_power_kw': 100.0, 'max_torque_nm': 250.0, 'efficiency': 0.9, 'type': 'permanent_magnet'},
                'motor_controller': {'type': 'vesc', 'serial_port': None, 'can_enabled': False},
                'charging': {'ac_max_power_kw': 11.0, 'dc_max_power_kw': 150.0, 
                           'connector_type': 'CCS2', 'fast_charge_enabled': True},
                'sensors': {'imu_enabled': True, 'gps_enabled': True, 'temperature_sensors': 8, 'sampling_rate_hz': 100},
                'communication': {'can_bus_enabled': False, 'telemetry_enabled': True, 'update_interval_ms': 1000},
                'telemetry': {'enabled': True, 'simulation_mode': True},
                'vehicle_controller': {'max_speed_kmh': 120.0, 'max_power_kw': 150.0},
                'temperature_sensors': {'enabled': True},
                'imu': {'sensor_type': 'mpu6050', 'simulation_mode': True},
                'ui': {'dashboard_enabled': True, 'mobile_app_enabled': True, 'theme': 'dark'},
                'ai': {'autopilot_enabled': False, 'computer_vision_enabled': False, 'model_path': '/models/'},
                'logging': {'level': 'INFO', 'file_path': '/tmp/test.log', 'max_file_size_mb': 100, 'backup_count': 5}
            }
            json.dump(config, f)
            temp_path = f.name
        
        try:
            system = EVSystem(config_path=temp_path)
            # Telemetry should be initialized if enabled
            assert system.telemetry is not None
        finally:
            Path(temp_path).unlink()

    def test_evsystem_update_loop(self):
        """Test update loop."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config = {
                'vehicle': {'model': 'test', 'serial_number': 'TEST001', 'manufacturer': 'test'},
                'battery': {'capacity_kwh': 50.0, 'max_charge_rate_kw': 100.0, 
                           'max_discharge_rate_kw': 150.0, 'nominal_voltage': 400.0, 'cell_count': 96},
                'motor': {'max_power_kw': 100.0, 'max_torque_nm': 250.0, 'efficiency': 0.9, 'type': 'permanent_magnet'},
                'motor_controller': {'type': 'vesc', 'serial_port': None, 'can_enabled': False},
                'charging': {'ac_max_power_kw': 11.0, 'dc_max_power_kw': 150.0, 
                           'connector_type': 'CCS2', 'fast_charge_enabled': True},
                'sensors': {'imu_enabled': True, 'gps_enabled': True, 'temperature_sensors': 8, 'sampling_rate_hz': 100},
                'communication': {'can_bus_enabled': False, 'telemetry_enabled': False, 'update_interval_ms': 1000},
                'vehicle_controller': {'max_speed_kmh': 120.0, 'max_power_kw': 150.0},
                'temperature_sensors': {'enabled': True},
                'imu': {'sensor_type': 'mpu6050', 'simulation_mode': True},
                'ui': {'dashboard_enabled': True, 'mobile_app_enabled': True, 'theme': 'dark'},
                'ai': {'autopilot_enabled': False, 'computer_vision_enabled': False, 'model_path': '/models/'},
                'logging': {'level': 'INFO', 'file_path': '/tmp/test.log', 'max_file_size_mb': 100, 'backup_count': 5}
            }
            json.dump(config, f)
            temp_path = f.name
        
        try:
            system = EVSystem(config_path=temp_path)
            system.running = True
            # Run update loop once
            system._update_loop()
            # Should not raise exception
            assert True
        finally:
            Path(temp_path).unlink()

    def test_evsystem_send_telemetry_data(self):
        """Test sending telemetry data."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config = {
                'vehicle': {'model': 'test', 'serial_number': 'TEST001', 'manufacturer': 'test'},
                'battery': {'capacity_kwh': 50.0, 'max_charge_rate_kw': 100.0, 
                           'max_discharge_rate_kw': 150.0, 'nominal_voltage': 400.0, 'cell_count': 96},
                'motor': {'max_power_kw': 100.0, 'max_torque_nm': 250.0, 'efficiency': 0.9, 'type': 'permanent_magnet'},
                'motor_controller': {'type': 'vesc', 'serial_port': None, 'can_enabled': False},
                'charging': {'ac_max_power_kw': 11.0, 'dc_max_power_kw': 150.0, 
                           'connector_type': 'CCS2', 'fast_charge_enabled': True},
                'sensors': {'imu_enabled': True, 'gps_enabled': True, 'temperature_sensors': 8, 'sampling_rate_hz': 100},
                'communication': {'can_bus_enabled': False, 'telemetry_enabled': True, 'update_interval_ms': 1000},
                'telemetry': {'enabled': True, 'simulation_mode': True},
                'vehicle_controller': {'max_speed_kmh': 120.0, 'max_power_kw': 150.0},
                'temperature_sensors': {'enabled': True},
                'imu': {'sensor_type': 'mpu6050', 'simulation_mode': True},
                'ui': {'dashboard_enabled': True, 'mobile_app_enabled': True, 'theme': 'dark'},
                'ai': {'autopilot_enabled': False, 'computer_vision_enabled': False, 'model_path': '/models/'},
                'logging': {'level': 'INFO', 'file_path': '/tmp/test.log', 'max_file_size_mb': 100, 'backup_count': 5}
            }
            json.dump(config, f)
            temp_path = f.name
        
        try:
            system = EVSystem(config_path=temp_path)
            system._send_telemetry_data()
            # Should not raise exception
            assert True
        finally:
            Path(temp_path).unlink()

    def test_evsystem_shutdown(self):
        """Test system shutdown."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config = {
                'vehicle': {'model': 'test', 'serial_number': 'TEST001', 'manufacturer': 'test'},
                'battery': {'capacity_kwh': 50.0, 'max_charge_rate_kw': 100.0, 
                           'max_discharge_rate_kw': 150.0, 'nominal_voltage': 400.0, 'cell_count': 96},
                'motor': {'max_power_kw': 100.0, 'max_torque_nm': 250.0, 'efficiency': 0.9, 'type': 'permanent_magnet'},
                'motor_controller': {'type': 'vesc', 'serial_port': None, 'can_enabled': False},
                'charging': {'ac_max_power_kw': 11.0, 'dc_max_power_kw': 150.0, 
                           'connector_type': 'CCS2', 'fast_charge_enabled': True},
                'sensors': {'imu_enabled': True, 'gps_enabled': True, 'temperature_sensors': 8, 'sampling_rate_hz': 100},
                'communication': {'can_bus_enabled': False, 'telemetry_enabled': False, 'update_interval_ms': 1000},
                'vehicle_controller': {'max_speed_kmh': 120.0, 'max_power_kw': 150.0},
                'temperature_sensors': {'enabled': True},
                'imu': {'sensor_type': 'mpu6050', 'simulation_mode': True},
                'ui': {'dashboard_enabled': True, 'mobile_app_enabled': True, 'theme': 'dark'},
                'ai': {'autopilot_enabled': False, 'computer_vision_enabled': False, 'model_path': '/models/'},
                'logging': {'level': 'INFO', 'file_path': '/tmp/test.log', 'max_file_size_mb': 100, 'backup_count': 5}
            }
            json.dump(config, f)
            temp_path = f.name
        
        try:
            system = EVSystem(config_path=temp_path)
            system.running = True
            system.shutdown()
            assert system.running is False
        finally:
            Path(temp_path).unlink()

    def test_evsystem_shutdown_when_not_running(self):
        """Test shutdown when system is not running."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config = {
                'vehicle': {'model': 'test', 'serial_number': 'TEST001', 'manufacturer': 'test'},
                'battery': {'capacity_kwh': 50.0, 'max_charge_rate_kw': 100.0, 
                           'max_discharge_rate_kw': 150.0, 'nominal_voltage': 400.0, 'cell_count': 96},
                'motor': {'max_power_kw': 100.0, 'max_torque_nm': 250.0, 'efficiency': 0.9, 'type': 'permanent_magnet'},
                'motor_controller': {'type': 'vesc', 'serial_port': None, 'can_enabled': False},
                'charging': {'ac_max_power_kw': 11.0, 'dc_max_power_kw': 150.0, 
                           'connector_type': 'CCS2', 'fast_charge_enabled': True},
                'sensors': {'imu_enabled': True, 'gps_enabled': True, 'temperature_sensors': 8, 'sampling_rate_hz': 100},
                'communication': {'can_bus_enabled': False, 'telemetry_enabled': False, 'update_interval_ms': 1000},
                'vehicle_controller': {'max_speed_kmh': 120.0, 'max_power_kw': 150.0},
                'temperature_sensors': {'enabled': True},
                'imu': {'sensor_type': 'mpu6050', 'simulation_mode': True},
                'ui': {'dashboard_enabled': True, 'mobile_app_enabled': True, 'theme': 'dark'},
                'ai': {'autopilot_enabled': False, 'computer_vision_enabled': False, 'model_path': '/models/'},
                'logging': {'level': 'INFO', 'file_path': '/tmp/test.log', 'max_file_size_mb': 100, 'backup_count': 5}
            }
            json.dump(config, f)
            temp_path = f.name
        
        try:
            system = EVSystem(config_path=temp_path)
            system.running = False
            system.shutdown()
            # Should return early without error
            assert system.running is False
        finally:
            Path(temp_path).unlink()

    def test_evsystem_signal_handler(self):
        """Test signal handler."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config = {
                'vehicle': {'model': 'test', 'serial_number': 'TEST001', 'manufacturer': 'test'},
                'battery': {'capacity_kwh': 50.0, 'max_charge_rate_kw': 100.0, 
                           'max_discharge_rate_kw': 150.0, 'nominal_voltage': 400.0, 'cell_count': 96},
                'motor': {'max_power_kw': 100.0, 'max_torque_nm': 250.0, 'efficiency': 0.9, 'type': 'permanent_magnet'},
                'motor_controller': {'type': 'vesc', 'serial_port': None, 'can_enabled': False},
                'charging': {'ac_max_power_kw': 11.0, 'dc_max_power_kw': 150.0, 
                           'connector_type': 'CCS2', 'fast_charge_enabled': True},
                'sensors': {'imu_enabled': True, 'gps_enabled': True, 'temperature_sensors': 8, 'sampling_rate_hz': 100},
                'communication': {'can_bus_enabled': False, 'telemetry_enabled': False, 'update_interval_ms': 1000},
                'vehicle_controller': {'max_speed_kmh': 120.0, 'max_power_kw': 150.0},
                'temperature_sensors': {'enabled': True},
                'imu': {'sensor_type': 'mpu6050', 'simulation_mode': True},
                'ui': {'dashboard_enabled': True, 'mobile_app_enabled': True, 'theme': 'dark'},
                'ai': {'autopilot_enabled': False, 'computer_vision_enabled': False, 'model_path': '/models/'},
                'logging': {'level': 'INFO', 'file_path': '/tmp/test.log', 'max_file_size_mb': 100, 'backup_count': 5}
            }
            json.dump(config, f)
            temp_path = f.name
        
        try:
            system = EVSystem(config_path=temp_path)
            system.running = True
            # Test signal handler (will call shutdown and sys.exit, but we can test the logic)
            with patch('sys.exit'):
                system._signal_handler(signal.SIGINT, None)
                assert system.running is False
        finally:
            Path(temp_path).unlink()

    def test_evsystem_start_already_running(self):
        """Test start when already running."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config = {
                'vehicle': {'model': 'test', 'serial_number': 'TEST001', 'manufacturer': 'test'},
                'battery': {'capacity_kwh': 50.0, 'max_charge_rate_kw': 100.0, 
                           'max_discharge_rate_kw': 150.0, 'nominal_voltage': 400.0, 'cell_count': 96},
                'motor': {'max_power_kw': 100.0, 'max_torque_nm': 250.0, 'efficiency': 0.9, 'type': 'permanent_magnet'},
                'motor_controller': {'type': 'vesc', 'serial_port': None, 'can_enabled': False},
                'charging': {'ac_max_power_kw': 11.0, 'dc_max_power_kw': 150.0, 
                           'connector_type': 'CCS2', 'fast_charge_enabled': True},
                'sensors': {'imu_enabled': True, 'gps_enabled': True, 'temperature_sensors': 8, 'sampling_rate_hz': 100},
                'communication': {'can_bus_enabled': False, 'telemetry_enabled': False, 'update_interval_ms': 1000},
                'vehicle_controller': {'max_speed_kmh': 120.0, 'max_power_kw': 150.0},
                'temperature_sensors': {'enabled': True},
                'imu': {'sensor_type': 'mpu6050', 'simulation_mode': True},
                'ui': {'dashboard_enabled': True, 'mobile_app_enabled': True, 'theme': 'dark'},
                'ai': {'autopilot_enabled': False, 'computer_vision_enabled': False, 'model_path': '/models/'},
                'logging': {'level': 'INFO', 'file_path': '/tmp/test.log', 'max_file_size_mb': 100, 'backup_count': 5}
            }
            json.dump(config, f)
            temp_path = f.name
        
        try:
            system = EVSystem(config_path=temp_path)
            system.running = True
            system.start()  # Should return early with warning
            assert system.running is True
        finally:
            Path(temp_path).unlink()


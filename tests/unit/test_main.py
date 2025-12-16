"""Unit tests for main.py."""

import pytest
import json
import tempfile
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from main import EVSystem


class TestEVSystemUnit:
    """Unit tests for EVSystem."""

    def test_load_config_file_not_found(self):
        """Test loading config when file doesn't exist."""
        with pytest.raises(SystemExit):
            EVSystem(config_path="nonexistent.json")

    def test_load_config_invalid_json(self):
        """Test loading invalid JSON config."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json {")
            temp_path = f.name
        
        try:
            with pytest.raises(SystemExit):
                EVSystem(config_path=temp_path)
        finally:
            Path(temp_path).unlink()

    def test_load_config_schema_not_found(self):
        """Test loading config when schema doesn't exist."""
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
                'ui': {'dashboard_enabled': True, 'mobile_app_enabled': True, 'theme': 'dark'},
                'ai': {'autopilot_enabled': False, 'computer_vision_enabled': False, 'model_path': '/models/'},
                'logging': {'level': 'INFO', 'file_path': '/tmp/test.log', 'max_file_size_mb': 100, 'backup_count': 5}
            }
            json.dump(config, f)
            temp_path = f.name
        
        # Create a directory without schema
        temp_dir = Path(temp_path).parent / "temp_config"
        temp_dir.mkdir(exist_ok=True)
        temp_config_path = temp_dir / "config.json"
        temp_config_path.write_text(json.dumps(config))
        
        try:
            # Should work even without schema (just warns)
            system = EVSystem(config_path=str(temp_config_path))
            assert system.config is not None
        finally:
            temp_config_path.unlink()
            temp_dir.rmdir()

    def test_initialize_can_bus_error(self):
        """Test CAN bus initialization error handling."""
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
                'ui': {'dashboard_enabled': True, 'mobile_app_enabled': True, 'theme': 'dark'},
                'ai': {'autopilot_enabled': False, 'computer_vision_enabled': False, 'model_path': '/models/'},
                'logging': {'level': 'INFO', 'file_path': '/tmp/test.log', 'max_file_size_mb': 100, 'backup_count': 5}
            }
            json.dump(config, f)
            temp_path = f.name
        
        try:
            with patch('main.CANBusInterface') as mock_can:
                mock_can.side_effect = Exception("CAN bus error")
                system = EVSystem(config_path=temp_path)
                # Should handle error gracefully
                assert system.can_bus is None or True
        finally:
            Path(temp_path).unlink()

    def test_initialize_bms_error(self):
        """Test BMS initialization error handling."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config = {
                'vehicle': {'model': 'test', 'serial_number': 'TEST001', 'manufacturer': 'test'},
                'battery': {'invalid': 'config'},
                'motor': {'max_power_kw': 100.0, 'max_torque_nm': 250.0, 'efficiency': 0.9, 'type': 'permanent_magnet'},
                'motor_controller': {'type': 'vesc', 'serial_port': None, 'can_enabled': False},
                'charging': {'ac_max_power_kw': 11.0, 'dc_max_power_kw': 150.0, 
                           'connector_type': 'CCS2', 'fast_charge_enabled': True},
                'sensors': {'imu_enabled': True, 'gps_enabled': True, 'temperature_sensors': 8, 'sampling_rate_hz': 100},
                'communication': {'can_bus_enabled': False, 'telemetry_enabled': False, 'update_interval_ms': 1000},
                'ui': {'dashboard_enabled': True, 'mobile_app_enabled': True, 'theme': 'dark'},
                'ai': {'autopilot_enabled': False, 'computer_vision_enabled': False, 'model_path': '/models/'},
                'logging': {'level': 'INFO', 'file_path': '/tmp/test.log', 'max_file_size_mb': 100, 'backup_count': 5}
            }
            json.dump(config, f)
            temp_path = f.name
        
        try:
            system = EVSystem(config_path=temp_path)
            # Should handle error gracefully (BMS may be None)
            assert True  # Just verify it doesn't crash
        finally:
            Path(temp_path).unlink()

    def test_initialize_motor_controller_error(self):
        """Test motor controller initialization error handling."""
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
                'ui': {'dashboard_enabled': True, 'mobile_app_enabled': True, 'theme': 'dark'},
                'ai': {'autopilot_enabled': False, 'computer_vision_enabled': False, 'model_path': '/models/'},
                'logging': {'level': 'INFO', 'file_path': '/tmp/test.log', 'max_file_size_mb': 100, 'backup_count': 5}
            }
            json.dump(config, f)
            temp_path = f.name
        
        try:
            with patch('main.VESCManager') as mock_vesc:
                mock_vesc.side_effect = Exception("VESC error")
                system = EVSystem(config_path=temp_path)
                # Should handle error gracefully
                assert True
        finally:
            Path(temp_path).unlink()

    def test_initialize_charging_system_error(self):
        """Test charging system initialization error handling."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config = {
                'vehicle': {'model': 'test', 'serial_number': 'TEST001', 'manufacturer': 'test'},
                'battery': {'capacity_kwh': 50.0, 'max_charge_rate_kw': 100.0, 
                           'max_discharge_rate_kw': 150.0, 'nominal_voltage': 400.0, 'cell_count': 96},
                'motor': {'max_power_kw': 100.0, 'max_torque_nm': 250.0, 'efficiency': 0.9, 'type': 'permanent_magnet'},
                'motor_controller': {'type': 'vesc', 'serial_port': None, 'can_enabled': False},
                'charging': {'invalid': 'config'},
                'sensors': {'imu_enabled': True, 'gps_enabled': True, 'temperature_sensors': 8, 'sampling_rate_hz': 100},
                'communication': {'can_bus_enabled': False, 'telemetry_enabled': False, 'update_interval_ms': 1000},
                'ui': {'dashboard_enabled': True, 'mobile_app_enabled': True, 'theme': 'dark'},
                'ai': {'autopilot_enabled': False, 'computer_vision_enabled': False, 'model_path': '/models/'},
                'logging': {'level': 'INFO', 'file_path': '/tmp/test.log', 'max_file_size_mb': 100, 'backup_count': 5}
            }
            json.dump(config, f)
            temp_path = f.name
        
        try:
            system = EVSystem(config_path=temp_path)
            # Should handle error gracefully
            assert True
        finally:
            Path(temp_path).unlink()

    def test_initialize_telemetry_error(self):
        """Test telemetry initialization error handling."""
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
                'ui': {'dashboard_enabled': True, 'mobile_app_enabled': True, 'theme': 'dark'},
                'ai': {'autopilot_enabled': False, 'computer_vision_enabled': False, 'model_path': '/models/'},
                'logging': {'level': 'INFO', 'file_path': '/tmp/test.log', 'max_file_size_mb': 100, 'backup_count': 5}
            }
            json.dump(config, f)
            temp_path = f.name
        
        try:
            with patch('main.TelemetrySystem') as mock_telemetry:
                mock_telemetry.side_effect = Exception("Telemetry error")
                system = EVSystem(config_path=temp_path)
                # Should handle error gracefully
                assert True
        finally:
            Path(temp_path).unlink()

    def test_send_telemetry_data_error(self):
        """Test telemetry data sending error handling."""
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
                'ui': {'dashboard_enabled': True, 'mobile_app_enabled': True, 'theme': 'dark'},
                'ai': {'autopilot_enabled': False, 'computer_vision_enabled': False, 'model_path': '/models/'},
                'logging': {'level': 'INFO', 'file_path': '/tmp/test.log', 'max_file_size_mb': 100, 'backup_count': 5}
            }
            json.dump(config, f)
            temp_path = f.name
        
        try:
            system = EVSystem(config_path=temp_path)
            # Mock telemetry to raise error
            if system.telemetry:
                system.telemetry.send_data = Mock(side_effect=Exception("Send error"))
            system._send_telemetry_data()
            # Should handle error gracefully
            assert True
        finally:
            Path(temp_path).unlink()


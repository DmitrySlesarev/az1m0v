"""Unit tests for Settings module."""

import pytest
import json
import tempfile
from pathlib import Path
from config.settings import Settings, get_settings, reload_settings


class TestSettings:
    """Test Settings class."""

    def test_settings_load_default(self):
        """Test loading settings with default paths."""
        settings = Settings()
        assert settings.config is not None
        assert 'vehicle' in settings.config
        assert 'battery' in settings.config

    def test_settings_get(self):
        """Test getting configuration values."""
        settings = Settings()
        
        # Test simple get
        model = settings.get('vehicle.model')
        assert model is not None
        
        # Test get with default
        value = settings.get('nonexistent.key', 'default')
        assert value == 'default'
        
        # Test get section
        battery = settings.get_section('battery')
        assert isinstance(battery, dict)
        assert 'capacity_kwh' in battery

    def test_settings_properties(self):
        """Test settings convenience properties."""
        settings = Settings()
        
        assert isinstance(settings.vehicle, dict)
        assert isinstance(settings.battery, dict)
        assert isinstance(settings.motor, dict)
        assert isinstance(settings.motor_controller, dict)
        assert isinstance(settings.charging, dict)
        assert isinstance(settings.sensors, dict)
        assert isinstance(settings.imu, dict)
        assert isinstance(settings.temperature_sensors, dict)
        assert isinstance(settings.communication, dict)
        assert isinstance(settings.telemetry, dict)
        assert isinstance(settings.ui, dict)
        assert isinstance(settings.ai, dict)
        assert isinstance(settings.logging_config, dict)

    def test_settings_set_and_save(self):
        """Test setting and saving configuration."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_config = {
                'vehicle': {'model': 'test', 'serial_number': 'TEST001', 'manufacturer': 'test'},
                'battery': {'capacity_kwh': 50.0, 'max_charge_rate_kw': 100.0, 
                           'max_discharge_rate_kw': 150.0, 'nominal_voltage': 400.0, 'cell_count': 96},
                'motor': {'max_power_kw': 100.0, 'max_torque_nm': 250.0, 'efficiency': 0.9, 'type': 'permanent_magnet'},
                'motor_controller': {'type': 'vesc', 'serial_port': '/dev/ttyUSB0', 'can_enabled': True},
                'charging': {'ac_max_power_kw': 11.0, 'dc_max_power_kw': 150.0, 
                           'connector_type': 'CCS2', 'fast_charge_enabled': True},
                'sensors': {'imu_enabled': True, 'gps_enabled': True, 'temperature_sensors': 8, 'sampling_rate_hz': 100},
                'communication': {'can_bus_enabled': True, 'telemetry_enabled': True, 'update_interval_ms': 1000},
                'ui': {'dashboard_enabled': True, 'mobile_app_enabled': True, 'theme': 'dark'},
                'ai': {'autopilot_enabled': False, 'computer_vision_enabled': False, 'model_path': '/models/'},
                'logging': {'level': 'INFO', 'file_path': '/var/log/test.log', 'max_file_size_mb': 100, 'backup_count': 5}
            }
            json.dump(temp_config, f)
            temp_path = f.name
        
        try:
            settings = Settings(config_path=temp_path)
            
            # Test set
            settings.set('vehicle.model', 'updated')
            assert settings.get('vehicle.model') == 'updated'
            
            # Test save
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f2:
                save_path = f2.name
            
            settings.save(save_path)
            
            # Verify saved
            with open(save_path, 'r') as f:
                saved_config = json.load(f)
            assert saved_config['vehicle']['model'] == 'updated'
            
            Path(save_path).unlink()
        finally:
            Path(temp_path).unlink()

    def test_get_settings_singleton(self):
        """Test get_settings returns singleton."""
        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2

    def test_reload_settings(self):
        """Test reload_settings creates new instance."""
        settings1 = get_settings()
        settings2 = reload_settings()
        assert settings1 is not settings2

    def test_settings_validation(self):
        """Test that settings validates against schema."""
        settings = Settings()
        # If we get here without exception, validation passed
        assert settings.config is not None


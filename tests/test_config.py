"""Configuration validation tests for EV system."""

import json
import pytest
from pathlib import Path
import jsonschema


class TestConfigurationValidation:
    """Test configuration file validation against schema."""
    
    def test_config_file_exists(self, config_path):
        """Test that configuration file exists."""
        assert config_path.exists(), f"Configuration file not found: {config_path}"
    
    def test_schema_file_exists(self, schema_path):
        """Test that schema file exists."""
        assert schema_path.exists(), f"Schema file not found: {schema_path}"
    
    def test_config_valid_json(self, config_path):
        """Test that configuration file contains valid JSON."""
        with open(config_path, 'r') as f:
            json.load(f)  # Should not raise exception
    
    def test_schema_valid_json(self, schema_path):
        """Test that schema file contains valid JSON."""
        with open(schema_path, 'r') as f:
            json.load(f)  # Should not raise exception
    
    def test_config_against_schema(self, config, schema):
        """Test that configuration validates against schema."""
        jsonschema.validate(config, schema)  # Should not raise exception


class TestVehicleConfiguration:
    """Test vehicle configuration parameters."""
    
    def test_vehicle_required_fields(self, vehicle_config):
        """Test that all required vehicle fields are present."""
        required_fields = ['model', 'serial_number', 'manufacturer']
        for field in required_fields:
            assert field in vehicle_config, f"Required field '{field}' missing from vehicle config"
    
    def test_vehicle_field_types(self, vehicle_config):
        """Test that vehicle fields have correct types."""
        assert isinstance(vehicle_config['model'], str)
        assert isinstance(vehicle_config['serial_number'], str)
        assert isinstance(vehicle_config['manufacturer'], str)
    
    def test_vehicle_field_values(self, vehicle_config):
        """Test that vehicle fields have non-empty values."""
        for field in ['model', 'serial_number', 'manufacturer']:
            assert len(vehicle_config[field]) > 0, f"Vehicle field '{field}' cannot be empty"


class TestBatteryConfiguration:
    """Test battery configuration parameters."""
    
    def test_battery_required_fields(self, battery_config):
        """Test that all required battery fields are present."""
        required_fields = ['capacity_kwh', 'max_charge_rate_kw', 'max_discharge_rate_kw', 
                          'nominal_voltage', 'cell_count']
        for field in required_fields:
            assert field in battery_config, f"Required field '{field}' missing from battery config"
    
    def test_battery_field_types(self, battery_config):
        """Test that battery fields have correct types."""
        assert isinstance(battery_config['capacity_kwh'], (int, float))
        assert isinstance(battery_config['max_charge_rate_kw'], (int, float))
        assert isinstance(battery_config['max_discharge_rate_kw'], (int, float))
        assert isinstance(battery_config['nominal_voltage'], (int, float))
        assert isinstance(battery_config['cell_count'], int)
    
    def test_battery_positive_values(self, battery_config):
        """Test that battery values are positive."""
        numeric_fields = ['capacity_kwh', 'max_charge_rate_kw', 'max_discharge_rate_kw', 'nominal_voltage']
        for field in numeric_fields:
            assert battery_config[field] >= 0, f"Battery field '{field}' must be non-negative"
        
        assert battery_config['cell_count'] >= 1, "Cell count must be at least 1"
    
    def test_battery_realistic_values(self, battery_config):
        """Test that battery values are within realistic ranges."""
        assert 10 <= battery_config['capacity_kwh'] <= 200, "Battery capacity should be 10-200 kWh"
        assert 1 <= battery_config['max_charge_rate_kw'] <= 500, "Max charge rate should be 1-500 kW"
        assert 1 <= battery_config['max_discharge_rate_kw'] <= 1000, "Max discharge rate should be 1-1000 kW"
        assert 200 <= battery_config['nominal_voltage'] <= 1000, "Nominal voltage should be 200-1000 V"
        assert 1 <= battery_config['cell_count'] <= 1000, "Cell count should be 1-1000"


class TestMotorConfiguration:
    """Test motor configuration parameters."""
    
    def test_motor_required_fields(self, motor_config):
        """Test that all required motor fields are present."""
        required_fields = ['max_power_kw', 'max_torque_nm', 'efficiency', 'type']
        for field in required_fields:
            assert field in motor_config, f"Required field '{field}' missing from motor config"
    
    def test_motor_field_types(self, motor_config):
        """Test that motor fields have correct types."""
        assert isinstance(motor_config['max_power_kw'], (int, float))
        assert isinstance(motor_config['max_torque_nm'], (int, float))
        assert isinstance(motor_config['efficiency'], (int, float))
        assert isinstance(motor_config['type'], str)
    
    def test_motor_positive_values(self, motor_config):
        """Test that motor values are positive."""
        assert motor_config['max_power_kw'] >= 0, "Max power must be non-negative"
        assert motor_config['max_torque_nm'] >= 0, "Max torque must be non-negative"
        assert 0 <= motor_config['efficiency'] <= 1, "Efficiency must be between 0 and 1"
    
    def test_motor_type_enum(self, motor_config):
        """Test that motor type is from allowed values."""
        allowed_types = ['permanent_magnet', 'induction', 'switched_reluctance']
        assert motor_config['type'] in allowed_types, f"Motor type must be one of {allowed_types}"


class TestChargingConfiguration:
    """Test charging configuration parameters."""
    
    def test_charging_required_fields(self, charging_config):
        """Test that all required charging fields are present."""
        required_fields = ['ac_max_power_kw', 'dc_max_power_kw', 'connector_type', 'fast_charge_enabled']
        for field in required_fields:
            assert field in charging_config, f"Required field '{field}' missing from charging config"
    
    def test_charging_field_types(self, charging_config):
        """Test that charging fields have correct types."""
        assert isinstance(charging_config['ac_max_power_kw'], (int, float))
        assert isinstance(charging_config['dc_max_power_kw'], (int, float))
        assert isinstance(charging_config['connector_type'], str)
        assert isinstance(charging_config['fast_charge_enabled'], bool)
    
    def test_charging_positive_values(self, charging_config):
        """Test that charging power values are positive."""
        assert charging_config['ac_max_power_kw'] >= 0, "AC max power must be non-negative"
        assert charging_config['dc_max_power_kw'] >= 0, "DC max power must be non-negative"
    
    def test_connector_type_enum(self, charging_config):
        """Test that connector type is from allowed values."""
        allowed_types = ['CCS1', 'CCS2', 'CHAdeMO', 'Tesla']
        assert charging_config['connector_type'] in allowed_types, f"Connector type must be one of {allowed_types}"


class TestSensorConfiguration:
    """Test sensor configuration parameters."""
    
    def test_sensor_required_fields(self, sensor_config):
        """Test that all required sensor fields are present."""
        required_fields = ['imu_enabled', 'gps_enabled', 'temperature_sensors', 'sampling_rate_hz']
        for field in required_fields:
            assert field in sensor_config, f"Required field '{field}' missing from sensor config"
    
    def test_sensor_field_types(self, sensor_config):
        """Test that sensor fields have correct types."""
        assert isinstance(sensor_config['imu_enabled'], bool)
        assert isinstance(sensor_config['gps_enabled'], bool)
        assert isinstance(sensor_config['temperature_sensors'], int)
        assert isinstance(sensor_config['sampling_rate_hz'], (int, float))
    
    def test_sensor_non_negative_values(self, sensor_config):
        """Test that sensor numeric values are non-negative."""
        assert sensor_config['temperature_sensors'] >= 0, "Temperature sensor count must be non-negative"
        assert sensor_config['sampling_rate_hz'] >= 0, "Sampling rate must be non-negative"


class TestCommunicationConfiguration:
    """Test communication configuration parameters."""
    
    def test_communication_required_fields(self, communication_config):
        """Test that all required communication fields are present."""
        required_fields = ['can_bus_enabled', 'telemetry_enabled', 'update_interval_ms']
        for field in required_fields:
            assert field in communication_config, f"Required field '{field}' missing from communication config"
    
    def test_communication_field_types(self, communication_config):
        """Test that communication fields have correct types."""
        assert isinstance(communication_config['can_bus_enabled'], bool)
        assert isinstance(communication_config['telemetry_enabled'], bool)
        assert isinstance(communication_config['update_interval_ms'], int)
    
    def test_communication_positive_values(self, communication_config):
        """Test that communication values are positive."""
        assert communication_config['update_interval_ms'] >= 1, "Update interval must be at least 1 ms"


class TestUIConfiguration:
    """Test UI configuration parameters."""
    
    def test_ui_required_fields(self, ui_config):
        """Test that all required UI fields are present."""
        required_fields = ['dashboard_enabled', 'mobile_app_enabled', 'theme']
        for field in required_fields:
            assert field in ui_config, f"Required field '{field}' missing from UI config"
    
    def test_ui_field_types(self, ui_config):
        """Test that UI fields have correct types."""
        assert isinstance(ui_config['dashboard_enabled'], bool)
        assert isinstance(ui_config['mobile_app_enabled'], bool)
        assert isinstance(ui_config['theme'], str)
    
    def test_theme_enum(self, ui_config):
        """Test that theme is from allowed values."""
        allowed_themes = ['light', 'dark', 'auto']
        assert ui_config['theme'] in allowed_themes, f"Theme must be one of {allowed_themes}"


class TestAIConfiguration:
    """Test AI configuration parameters."""
    
    def test_ai_required_fields(self, ai_config):
        """Test that all required AI fields are present."""
        required_fields = ['autopilot_enabled', 'computer_vision_enabled', 'model_path']
        for field in required_fields:
            assert field in ai_config, f"Required field '{field}' missing from AI config"
    
    def test_ai_field_types(self, ai_config):
        """Test that AI fields have correct types."""
        assert isinstance(ai_config['autopilot_enabled'], bool)
        assert isinstance(ai_config['computer_vision_enabled'], bool)
        assert isinstance(ai_config['model_path'], str)
    
    def test_model_path_non_empty(self, ai_config):
        """Test that model path is not empty."""
        assert len(ai_config['model_path']) > 0, "Model path cannot be empty"


class TestLoggingConfiguration:
    """Test logging configuration parameters."""
    
    def test_logging_required_fields(self, logging_config):
        """Test that all required logging fields are present."""
        required_fields = ['level', 'file_path', 'max_file_size_mb', 'backup_count']
        for field in required_fields:
            assert field in logging_config, f"Required field '{field}' missing from logging config"
    
    def test_logging_field_types(self, logging_config):
        """Test that logging fields have correct types."""
        assert isinstance(logging_config['level'], str)
        assert isinstance(logging_config['file_path'], str)
        assert isinstance(logging_config['max_file_size_mb'], int)
        assert isinstance(logging_config['backup_count'], int)
    
    def test_logging_level_enum(self, logging_config):
        """Test that logging level is from allowed values."""
        allowed_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        assert logging_config['level'] in allowed_levels, f"Logging level must be one of {allowed_levels}"
    
    def test_logging_positive_values(self, logging_config):
        """Test that logging numeric values are positive."""
        assert logging_config['max_file_size_mb'] >= 1, "Max file size must be at least 1 MB"
        assert logging_config['backup_count'] >= 0, "Backup count must be non-negative"
    
    def test_file_path_non_empty(self, logging_config):
        """Test that file path is not empty."""
        assert len(logging_config['file_path']) > 0, "File path cannot be empty"

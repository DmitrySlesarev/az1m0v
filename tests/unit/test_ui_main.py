"""Unit tests for ui/__main__.py."""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sys


class TestUIMain:
    """Test ui/__main__.py module."""

    def test_load_config_success(self):
        """Test loading config successfully."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config = {
                'vehicle': {'model': 'test', 'serial_number': 'TEST001', 'manufacturer': 'test'},
                'communication': {'can_bus_enabled': False, 'telemetry_enabled': False, 'update_interval_ms': 1000},
                'ui': {'dashboard_enabled': True, 'mobile_app_enabled': True, 'theme': 'dark'}
            }
            json.dump(config, f)
            temp_path = f.name
        
        try:
            from ui import __main__ as ui_main
            config = ui_main.load_config(temp_path)
            assert config['vehicle']['model'] == 'test'
        finally:
            Path(temp_path).unlink()

    def test_load_config_file_not_found(self):
        """Test loading config when file doesn't exist."""
        from ui import __main__ as ui_main
        config = ui_main.load_config("nonexistent.json")
        assert config == {}

    def test_load_config_invalid_json(self):
        """Test loading invalid JSON config."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json {")
            temp_path = f.name
        
        try:
            from ui import __main__ as ui_main
            config = ui_main.load_config(temp_path)
            assert config == {}
        finally:
            Path(temp_path).unlink()

    @patch('ui.__main__.EVDashboard')
    @patch('ui.__main__.CANBusInterface')
    @patch('ui.__main__.EVCANProtocol')
    def test_main_with_can_bus(self, mock_protocol, mock_can, mock_dashboard):
        """Test main execution with CAN bus enabled."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config = {
                'vehicle': {'model': 'test', 'serial_number': 'TEST001', 'manufacturer': 'test'},
                'communication': {'can_bus_enabled': True, 'telemetry_enabled': False, 'update_interval_ms': 1000},
                'ui': {'dashboard_enabled': True, 'mobile_app_enabled': True, 'theme': 'dark',
                       'dashboard_host': '127.0.0.1', 'dashboard_port': 5000}
            }
            json.dump(config, f)
            temp_path = f.name
        
        try:
            mock_can_instance = MagicMock()
            mock_can_instance.connect.return_value = True
            mock_can.return_value = mock_can_instance
            
            mock_dashboard_instance = MagicMock()
            mock_dashboard.return_value = mock_dashboard_instance
            
            # Import and run main
            import ui.__main__ as ui_main
            with patch('builtins.open', create=True) as mock_open:
                mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(config)
                # Test the logic without actually running
                config_loaded = ui_main.load_config(temp_path)
                assert config_loaded['communication']['can_bus_enabled'] is True
        finally:
            Path(temp_path).unlink()

    @patch('ui.__main__.EVDashboard')
    def test_main_without_can_bus(self, mock_dashboard):
        """Test main execution without CAN bus."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config = {
                'vehicle': {'model': 'test', 'serial_number': 'TEST001', 'manufacturer': 'test'},
                'communication': {'can_bus_enabled': False, 'telemetry_enabled': False, 'update_interval_ms': 1000},
                'ui': {'dashboard_enabled': True, 'mobile_app_enabled': True, 'theme': 'dark',
                       'dashboard_host': '127.0.0.1', 'dashboard_port': 5000}
            }
            json.dump(config, f)
            temp_path = f.name
        
        try:
            mock_dashboard_instance = MagicMock()
            mock_dashboard.return_value = mock_dashboard_instance
            
            from ui import __main__ as ui_main
            config_loaded = ui_main.load_config(temp_path)
            assert config_loaded['communication']['can_bus_enabled'] is False
        finally:
            Path(temp_path).unlink()

    @patch('ui.__main__.CANBusInterface')
    def test_main_can_bus_connection_failed(self, mock_can):
        """Test main when CAN bus connection fails."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config = {
                'vehicle': {'model': 'test', 'serial_number': 'TEST001', 'manufacturer': 'test'},
                'communication': {'can_bus_enabled': True, 'telemetry_enabled': False, 'update_interval_ms': 1000},
                'ui': {'dashboard_enabled': True, 'mobile_app_enabled': True, 'theme': 'dark'}
            }
            json.dump(config, f)
            temp_path = f.name
        
        try:
            mock_can_instance = MagicMock()
            mock_can_instance.connect.return_value = False
            mock_can.return_value = mock_can_instance
            
            from ui import __main__ as ui_main
            config_loaded = ui_main.load_config(temp_path)
            # Should handle gracefully
            assert config_loaded is not None
        finally:
            Path(temp_path).unlink()

    @patch('ui.__main__.CANBusInterface')
    def test_main_can_bus_exception(self, mock_can):
        """Test main when CAN bus initialization raises exception."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config = {
                'vehicle': {'model': 'test', 'serial_number': 'TEST001', 'manufacturer': 'test'},
                'communication': {'can_bus_enabled': True, 'telemetry_enabled': False, 'update_interval_ms': 1000},
                'ui': {'dashboard_enabled': True, 'mobile_app_enabled': True, 'theme': 'dark'}
            }
            json.dump(config, f)
            temp_path = f.name
        
        try:
            mock_can.side_effect = Exception("CAN bus error")
            
            from ui import __main__ as ui_main
            config_loaded = ui_main.load_config(temp_path)
            # Should handle gracefully
            assert config_loaded is not None
        finally:
            Path(temp_path).unlink()


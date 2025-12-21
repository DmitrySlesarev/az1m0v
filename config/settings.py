"""Settings module for the EV project.
Provides centralized configuration loading and validation.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import jsonschema


class Settings:
    """Centralized settings manager for the EV system."""

    def __init__(self, config_path: Optional[str] = None, schema_path: Optional[str] = None):
        """Initialize settings.
        
        Args:
            config_path: Path to configuration file (default: config/config.json)
            schema_path: Path to schema file (default: config/config_schema.json)
        """
        self.logger = logging.getLogger(__name__)
        
        # Default paths
        if config_path is None:
            config_path = Path(__file__).parent / "config.json"
        else:
            config_path = Path(config_path)
            
        if schema_path is None:
            schema_path = Path(__file__).parent / "config_schema.json"
        else:
            schema_path = Path(schema_path)
        
        self.config_path = config_path
        self.schema_path = schema_path
        self.config: Dict[str, Any] = {}
        self.schema: Dict[str, Any] = {}
        
        # Load configuration
        self.load()

    def load(self) -> None:
        """Load and validate configuration."""
        try:
            # Load configuration file
            if not self.config_path.exists():
                raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
            
            with open(self.config_path, 'r') as f:
                self.config = json.load(f)
            
            # Load and validate against schema
            if self.schema_path.exists():
                with open(self.schema_path, 'r') as f:
                    self.schema = json.load(f)
                
                jsonschema.validate(self.config, self.schema)
                self.logger.info("Configuration validated successfully")
            else:
                self.logger.warning("Configuration schema not found, skipping validation")
            
        except FileNotFoundError as e:
            self.logger.error(f"Configuration file not found: {e}")
            raise
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in configuration file: {e}")
            raise
        except jsonschema.ValidationError as e:
            self.logger.error(f"Configuration validation error: {e}")
            raise

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key (supports dot notation).
        
        Args:
            key: Configuration key (e.g., 'battery.capacity_kwh' or 'battery')
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        
        return value if value is not None else default

    def get_section(self, section: str) -> Dict[str, Any]:
        """Get entire configuration section.
        
        Args:
            section: Section name (e.g., 'battery', 'motor')
            
        Returns:
            Configuration section dictionary
        """
        return self.config.get(section, {})

    def set(self, key: str, value: Any) -> None:
        """Set configuration value (supports dot notation).
        
        Args:
            key: Configuration key (e.g., 'battery.capacity_kwh')
            value: Value to set
        """
        keys = key.split('.')
        config = self.config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value

    def save(self, path: Optional[str] = None) -> None:
        """Save configuration to file.
        
        Args:
            path: Optional path to save to (default: original config_path)
        """
        save_path = Path(path) if path else self.config_path
        
        with open(save_path, 'w') as f:
            json.dump(self.config, f, indent=2)
        
        self.logger.info(f"Configuration saved to {save_path}")

    # Convenience methods for common configuration sections
    
    @property
    def vehicle(self) -> Dict[str, Any]:
        """Get vehicle configuration."""
        return self.get_section('vehicle')
    
    @property
    def battery(self) -> Dict[str, Any]:
        """Get battery configuration."""
        return self.get_section('battery')
    
    @property
    def motor(self) -> Dict[str, Any]:
        """Get motor configuration."""
        return self.get_section('motor')
    
    @property
    def motor_controller(self) -> Dict[str, Any]:
        """Get motor controller configuration."""
        return self.get_section('motor_controller')
    
    @property
    def charging(self) -> Dict[str, Any]:
        """Get charging configuration."""
        return self.get_section('charging')
    
    @property
    def vehicle_controller(self) -> Dict[str, Any]:
        """Get vehicle controller configuration."""
        return self.get_section('vehicle_controller')
    
    @property
    def sensors(self) -> Dict[str, Any]:
        """Get sensors configuration."""
        return self.get_section('sensors')
    
    @property
    def imu(self) -> Dict[str, Any]:
        """Get IMU configuration."""
        return self.get_section('imu')
    
    @property
    def temperature_sensors(self) -> Dict[str, Any]:
        """Get temperature sensors configuration."""
        return self.get_section('temperature_sensors')
    
    @property
    def communication(self) -> Dict[str, Any]:
        """Get communication configuration."""
        return self.get_section('communication')
    
    @property
    def telemetry(self) -> Dict[str, Any]:
        """Get telemetry configuration."""
        return self.get_section('telemetry')
    
    @property
    def ui(self) -> Dict[str, Any]:
        """Get UI configuration."""
        return self.get_section('ui')
    
    @property
    def ai(self) -> Dict[str, Any]:
        """Get AI configuration."""
        return self.get_section('ai')
    
    @property
    def logging_config(self) -> Dict[str, Any]:
        """Get logging configuration."""
        return self.get_section('logging')
    
    @property
    def can_bus(self) -> Dict[str, Any]:
        """Get CAN bus configuration."""
        return self.get_section('can_bus')


# Global settings instance
_settings: Optional[Settings] = None


def get_settings(config_path: Optional[str] = None) -> Settings:
    """Get or create global settings instance.
    
    Args:
        config_path: Optional path to configuration file
        
    Returns:
        Settings instance
    """
    global _settings
    if _settings is None:
        _settings = Settings(config_path)
    return _settings


def reload_settings(config_path: Optional[str] = None) -> Settings:
    """Reload settings from file.
    
    Args:
        config_path: Optional path to configuration file
        
    Returns:
        Settings instance
    """
    global _settings
    _settings = Settings(config_path)
    return _settings

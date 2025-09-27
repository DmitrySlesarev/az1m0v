"""Shared pytest fixtures for EV system tests."""

import json
import pytest
from pathlib import Path


@pytest.fixture
def config_path():
    """Path to configuration file."""
    return Path(__file__).parent.parent / "config" / "config.json"


@pytest.fixture
def schema_path():
    """Path to configuration schema."""
    return Path(__file__).parent.parent / "config" / "config_schema.json"


@pytest.fixture
def config(config_path):
    """Load configuration dictionary."""
    with open(config_path, 'r') as f:
        return json.load(f)


@pytest.fixture
def schema(schema_path):
    """Load configuration schema."""
    with open(schema_path, 'r') as f:
        return json.load(f)


@pytest.fixture
def vehicle_config(config):
    """Load vehicle configuration section."""
    return config['vehicle']


@pytest.fixture
def battery_config(config):
    """Load battery configuration section."""
    return config['battery']


@pytest.fixture
def motor_config(config):
    """Load motor configuration section."""
    return config['motor']


@pytest.fixture
def charging_config(config):
    """Load charging configuration section."""
    return config['charging']


@pytest.fixture
def sensor_config(config):
    """Load sensor configuration section."""
    return config['sensors']


@pytest.fixture
def communication_config(config):
    """Load communication configuration section."""
    return config['communication']


@pytest.fixture
def ui_config(config):
    """Load UI configuration section."""
    return config['ui']


@pytest.fixture
def ai_config(config):
    """Load AI configuration section."""
    return config['ai']


@pytest.fixture
def logging_config(config):
    """Load logging configuration section."""
    return config['logging']

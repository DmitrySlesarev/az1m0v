"""Functional tests for Temperature Sensor integration."""

import pytest
import time
from unittest.mock import Mock
from sensors.temperature import TemperatureSensorManager
from core.battery_management import BatteryManagementSystem
from core.motor_controller import VESCManager, MotorState
from core.charging_system import ChargingSystem
from communication.can_bus import CANBusInterface, EVCANProtocol


class TestTemperatureBatteryIntegration:
    """Test temperature sensor integration with battery management."""

    def test_battery_cell_group_temperature_integration(self):
        """Test integration of cell group temperatures with BMS."""
        config = {
            'capacity_kwh': 75.0,
            'cell_count': 96,
            'min_temperature': 0.0,
            'max_temperature': 45.0
        }
        
        temp_config = {
            'battery': {
                'cell_count': 96
            },
            'temperature_sensors': {
                'cells_per_group': 12,
                'coolant_enabled': True
            }
        }
        
        temp_manager = TemperatureSensorManager(temp_config)
        bms = BatteryManagementSystem(config, temperature_sensor_manager=temp_manager)
        
        # Set some cell group temperatures
        for i in range(8):
            sensor = temp_manager.get_sensor(f"battery_cell_group_{i+1}")
            sensor.set_temperature(25.0 + i * 2.0)
        
        # Update BMS state (should read from temperature sensors)
        bms.update_state()
        
        # Check that cell group temperatures are set
        assert len(bms.state.cell_group_temperatures) == 8
        assert bms.state.cell_group_temperatures[0] == 25.0
        assert bms.state.cell_group_temperatures[7] == 39.0

    def test_coolant_temperature_integration(self):
        """Test integration of coolant temperatures with BMS."""
        config = {
            'capacity_kwh': 75.0,
            'cell_count': 96
        }
        
        temp_config = {
            'battery': {
                'cell_count': 96
            },
            'temperature_sensors': {
                'cells_per_group': 12,
                'coolant_enabled': True
            }
        }
        
        temp_manager = TemperatureSensorManager(temp_config)
        bms = BatteryManagementSystem(config, temperature_sensor_manager=temp_manager)
        
        # Set coolant temperatures
        temp_manager.get_sensor("coolant_inlet").set_temperature(20.0)
        temp_manager.get_sensor("coolant_outlet").set_temperature(25.0)
        
        # Update BMS state
        bms.update_state()
        
        # Check coolant temperatures
        assert bms.state.coolant_inlet_temperature == 20.0
        assert bms.state.coolant_outlet_temperature == 25.0


class TestTemperatureMotorIntegration:
    """Test temperature sensor integration with motor controller."""

    def test_motor_stator_temperature_integration(self):
        """Test integration of stator temperatures with motor controller."""
        config = {
            'max_power_kw': 150.0,
            'max_torque_nm': 320.0
        }
        
        temp_config = {
            'battery': {
                'cell_count': 96
            },
            'temperature_sensors': {
                'cells_per_group': 12,
                'motor_stator_enabled': True,
                'motor_stator_sensors': 3
            }
        }
        
        temp_manager = TemperatureSensorManager(temp_config)
        motor = VESCManager(config=config, temperature_sensor_manager=temp_manager)
        motor.is_connected = True
        motor.current_status.state = MotorState.IDLE
        
        # Set stator temperatures
        temp_manager.get_sensor("motor_stator_1").set_temperature(50.0)
        temp_manager.get_sensor("motor_stator_2").set_temperature(55.0)
        temp_manager.get_sensor("motor_stator_3").set_temperature(52.0)
        
        # Get motor status (should read from temperature sensors)
        status = motor.get_status()
        
        # Check stator temperatures
        assert len(status.stator_temperatures) == 3
        assert status.stator_temperatures[0] == 50.0
        assert status.stator_temperatures[1] == 55.0
        assert status.stator_temperatures[2] == 52.0


class TestTemperatureChargingIntegration:
    """Test temperature sensor integration with charging system."""

    def test_charging_port_temperature_integration(self):
        """Test integration of port/connector temperatures with charging system."""
        config = {
            'ac_max_power_kw': 11.0,
            'dc_max_power_kw': 150.0
        }
        
        temp_config = {
            'battery': {
                'cell_count': 96
            },
            'temperature_sensors': {
                'cells_per_group': 12,
                'charging_enabled': True
            }
        }
        
        temp_manager = TemperatureSensorManager(temp_config)
        charging = ChargingSystem(config, temperature_sensor_manager=temp_manager)
        
        # Set charging temperatures
        temp_manager.get_sensor("charging_port").set_temperature(30.0)
        temp_manager.get_sensor("charging_connector").set_temperature(35.0)
        
        # Update charging status
        status = charging.update_status()
        
        # Check temperatures
        assert status.port_temperature == 30.0
        assert status.connector_temperature == 35.0

    def test_charging_temperature_safety(self):
        """Test that charging stops on high port temperature."""
        config = {
            'ac_max_power_kw': 11.0,
            'dc_max_power_kw': 150.0,
            'max_temperature_c': 60.0
        }
        
        temp_config = {
            'battery': {
                'cell_count': 96
            },
            'temperature_sensors': {
                'cells_per_group': 12,
                'charging_enabled': True
            }
        }
        
        temp_manager = TemperatureSensorManager(temp_config)
        charging = ChargingSystem(config, temperature_sensor_manager=temp_manager)
        
        # Connect and start charging
        charging.connect_charger()
        charging.start_charging(power_kw=10.0)
        assert charging.is_charging()
        
        # Set high port temperature
        temp_manager.get_sensor("charging_port").set_temperature(70.0)
        
        # Update status (should stop charging)
        status = charging.update_status()
        
        # Charging should be stopped
        assert not charging.is_charging()
        assert status.error_code == "PORT_OVERTEMPERATURE"


class TestTemperatureCANIntegration:
    """Test temperature sensor CAN bus integration."""

    def test_temperature_can_messages(self):
        """Test sending temperature data over CAN bus."""
        can_bus = CANBusInterface("can0")
        can_bus.connect()
        can_protocol = EVCANProtocol(can_bus)
        
        # Send temperature data
        result = can_protocol.send_temperature_data(
            sensor_type='battery_cell_group',
            sensor_id='cell_group_1',
            temperature=25.5
        )
        assert result is True

    def test_parse_temperature_can_messages(self):
        """Test parsing temperature data from CAN frames."""
        can_bus = CANBusInterface("can0")
        can_protocol = EVCANProtocol(can_bus)
        
        from communication.can_bus import CANFrame, CANFrameType
        import struct
        
        # Create a temperature frame
        temp_data = struct.pack('<f', 25.5)
        frame = CANFrame(
            can_id=can_protocol.CAN_IDS['TEMPERATURE_BATTERY_CELL_GROUP'],
            data=temp_data + b'\x00' * 4,
            timestamp=time.time(),
            dlc=8
        )
        
        # Parse the frame
        result = can_protocol.parse_temperature_data(frame)
        assert result is not None
        assert result['temperature'] == pytest.approx(25.5, abs=0.1)
        assert result['sensor_type'] == 'battery_cell_group'


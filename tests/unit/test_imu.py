"""Unit tests for IMU module."""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from sensors.imu import (
    IMU,
    IMUConfig,
    IMUType,
    IMUStatus,
    IMUReading
)


class TestIMUConfig:
    """Test IMUConfig dataclass."""

    def test_config_creation(self):
        """Test creating an IMUConfig."""
        config = IMUConfig(
            sensor_type=IMUType.MPU6050,
            i2c_address=0x68,
            i2c_bus=1
        )
        assert config.sensor_type == IMUType.MPU6050
        assert config.i2c_address == 0x68
        assert config.i2c_bus == 1
        assert config.sampling_rate_hz == 100.0
        assert config.simulation_mode is True

    def test_config_custom_values(self):
        """Test IMUConfig with custom values."""
        config = IMUConfig(
            sensor_type=IMUType.MPU9250,
            i2c_address=0x69,
            i2c_bus=2,
            sampling_rate_hz=200.0,
            simulation_mode=False,
            calibration_samples=200
        )
        assert config.sensor_type == IMUType.MPU9250
        assert config.i2c_address == 0x69
        assert config.i2c_bus == 2
        assert config.sampling_rate_hz == 200.0
        assert config.simulation_mode is False
        assert config.calibration_samples == 200


class TestIMU:
    """Test IMU class."""

    def test_imu_creation_simulation(self):
        """Test creating an IMU in simulation mode."""
        config = IMUConfig(
            sensor_type=IMUType.MPU6050,
            simulation_mode=True
        )
        imu = IMU(config)
        assert imu.config == config
        assert imu.is_connected is True
        assert imu.last_reading is None
        assert imu.reading_count == 0

    def test_read_data_simulation(self):
        """Test reading data in simulation mode."""
        config = IMUConfig(
            sensor_type=IMUType.MPU6050,
            simulation_mode=True,
            sampling_rate_hz=100.0
        )
        imu = IMU(config)
        
        reading = imu.read_data()
        assert reading is not None
        assert isinstance(reading, IMUReading)
        assert reading.timestamp > 0
        assert "x" in reading.accelerometer
        assert "y" in reading.accelerometer
        assert "z" in reading.accelerometer
        assert "x" in reading.gyroscope
        assert "y" in reading.gyroscope
        assert "z" in reading.gyroscope
        assert reading.magnetometer is None  # MPU-6050 doesn't have magnetometer
        assert reading.status == IMUStatus.HEALTHY
        assert imu.reading_count == 1

    def test_read_data_mpu9250_simulation(self):
        """Test reading data from MPU-9250 in simulation mode."""
        config = IMUConfig(
            sensor_type=IMUType.MPU9250,
            simulation_mode=True
        )
        imu = IMU(config)
        
        reading = imu.read_data()
        assert reading is not None
        assert reading.magnetometer is not None  # MPU-9250 has magnetometer
        assert "x" in reading.magnetometer
        assert "y" in reading.magnetometer
        assert "z" in reading.magnetometer

    def test_read_data_rate_limiting(self):
        """Test that read_data respects sampling rate."""
        config = IMUConfig(
            sensor_type=IMUType.MPU6050,
            simulation_mode=True,
            sampling_rate_hz=100.0  # 10ms between readings
        )
        imu = IMU(config)
        
        reading1 = imu.read_data()
        assert reading1 is not None
        
        # Try to read immediately again - should return same reading
        reading2 = imu.read_data()
        assert reading2 == reading1
        assert imu.reading_count == 1  # Only one actual reading
        
        # Wait a bit and read again
        time.sleep(0.02)  # 20ms
        reading3 = imu.read_data()
        assert reading3 is not None
        assert reading3 != reading1
        assert imu.reading_count == 2

    def test_reading_to_dict(self):
        """Test converting IMUReading to dictionary."""
        reading = IMUReading(
            timestamp=1234567890.0,
            accelerometer={"x": 1.0, "y": 2.0, "z": 9.81},
            gyroscope={"x": 0.1, "y": 0.2, "z": 0.3},
            temperature_c=25.0,
            status=IMUStatus.HEALTHY
        )
        
        data = reading.to_dict()
        assert data["timestamp"] == 1234567890.0
        assert data["accelerometer"]["x"] == 1.0
        assert data["gyroscope"]["z"] == 0.3
        assert data["temperature_c"] == 25.0
        assert data["status"] == "healthy"
        assert "magnetometer" not in data

    def test_reading_to_dict_with_magnetometer(self):
        """Test converting IMUReading with magnetometer to dictionary."""
        reading = IMUReading(
            timestamp=1234567890.0,
            accelerometer={"x": 1.0, "y": 2.0, "z": 9.81},
            gyroscope={"x": 0.1, "y": 0.2, "z": 0.3},
            magnetometer={"x": 20.0, "y": 5.0, "z": 45.0},
            temperature_c=25.0,
            status=IMUStatus.HEALTHY
        )
        
        data = reading.to_dict()
        assert "magnetometer" in data
        assert data["magnetometer"]["x"] == 20.0

    @patch('builtins.__import__')
    def test_initialize_mpu6050_hardware(self, mock_import):
        """Test initializing MPU-6050 with hardware."""
        mock_mpu = MagicMock()
        mock_mpu_module = MagicMock()
        mock_mpu_module.mpu6050.return_value = mock_mpu
        mock_mpu_module.ACCEL_RANGE_2G = 0
        mock_mpu_module.GYRO_RANGE_250DEG = 0
        
        def import_side_effect(name, *args, **kwargs):
            if name == 'mpu6050':
                return mock_mpu_module
            return __import__(name, *args, **kwargs)
        
        mock_import.side_effect = import_side_effect
        
        config = IMUConfig(
            sensor_type=IMUType.MPU6050,
            simulation_mode=False,
            i2c_address=0x68,
            i2c_bus=1
        )
        imu = IMU(config)
        
        assert imu.is_connected is True
        assert imu._mpu6050 is not None

    def test_initialize_mpu6050_fallback_to_simulation(self):
        """Test that initialization falls back to simulation on error."""
        config = IMUConfig(
            sensor_type=IMUType.MPU6050,
            simulation_mode=False
        )
        # Will fail to import and fall back to simulation
        imu = IMU(config)
        
        assert imu.is_connected is True
        assert imu.config.simulation_mode is True
        assert imu._mpu6050 is None

    @patch('builtins.__import__')
    def test_initialize_mpu9250_hardware(self, mock_import):
        """Test initializing MPU-9250 with hardware."""
        mock_mpu = MagicMock()
        mock_mpu_module = MagicMock()
        mock_mpu_module.mpu9250.return_value = mock_mpu
        
        def import_side_effect(name, *args, **kwargs):
            if name == 'mpu9250_jmdev':
                return mock_mpu_module
            return __import__(name, *args, **kwargs)
        
        mock_import.side_effect = import_side_effect
        
        config = IMUConfig(
            sensor_type=IMUType.MPU9250,
            simulation_mode=False,
            i2c_address=0x68,
            i2c_bus=1
        )
        imu = IMU(config)
        
        assert imu.is_connected is True
        assert imu._mpu9250 is not None

    @patch('builtins.__import__')
    def test_read_mpu6050_hardware(self, mock_import):
        """Test reading data from MPU-6050 hardware."""
        mock_mpu = MagicMock()
        mock_mpu.get_accel_data.return_value = {"x": 1.0, "y": 2.0, "z": 10.0}
        mock_mpu.get_gyro_data.return_value = {"x": 0.1, "y": 0.2, "z": 0.3}
        mock_mpu.get_temp.return_value = 25.5
        mock_mpu_module = MagicMock()
        mock_mpu_module.mpu6050.return_value = mock_mpu
        mock_mpu_module.ACCEL_RANGE_2G = 0
        mock_mpu_module.GYRO_RANGE_250DEG = 0
        
        def import_side_effect(name, *args, **kwargs):
            if name == 'mpu6050':
                return mock_mpu_module
            return __import__(name, *args, **kwargs)
        
        mock_import.side_effect = import_side_effect
        
        config = IMUConfig(
            sensor_type=IMUType.MPU6050,
            simulation_mode=False,
            accel_offset_x=0.1,
            accel_offset_y=0.2,
            accel_offset_z=0.3
        )
        imu = IMU(config)
        
        reading = imu.read_data()
        assert reading is not None
        assert reading.accelerometer["x"] == pytest.approx(0.9, abs=0.01)  # 1.0 - 0.1
        assert reading.accelerometer["y"] == pytest.approx(1.8, abs=0.01)  # 2.0 - 0.2
        assert reading.temperature_c == 25.5

    @patch('builtins.__import__')
    def test_read_mpu9250_hardware(self, mock_import):
        """Test reading data from MPU-9250 hardware."""
        mock_mpu = MagicMock()
        mock_mpu.readAccelerometerMaster.return_value = [1.0, 2.0, 10.0]
        mock_mpu.readGyroscopeMaster.return_value = [0.1, 0.2, 0.3]
        mock_mpu.readMagnetometerMaster.return_value = [20.0, 5.0, 45.0]
        mock_mpu.readTemperatureMaster.return_value = 25.5
        mock_mpu_module = MagicMock()
        mock_mpu_module.mpu9250.return_value = mock_mpu
        
        def import_side_effect(name, *args, **kwargs):
            if name == 'mpu9250_jmdev':
                return mock_mpu_module
            return __import__(name, *args, **kwargs)
        
        mock_import.side_effect = import_side_effect
        
        config = IMUConfig(
            sensor_type=IMUType.MPU9250,
            simulation_mode=False
        )
        imu = IMU(config)
        
        reading = imu.read_data()
        assert reading is not None
        assert reading.magnetometer is not None
        assert reading.magnetometer["x"] == 20.0
        assert reading.magnetometer["y"] == 5.0
        assert reading.magnetometer["z"] == 45.0

    def test_calibrate_simulation(self):
        """Test calibration in simulation mode."""
        config = IMUConfig(
            sensor_type=IMUType.MPU6050,
            simulation_mode=True,
            calibration_samples=10
        )
        imu = IMU(config)
        
        result = imu.calibrate()
        assert result is True  # Calibration skipped in simulation

    @patch('builtins.__import__')
    def test_calibrate_hardware(self, mock_import):
        """Test calibration with hardware."""
        mock_mpu = MagicMock()
        mock_mpu.get_accel_data.return_value = {"x": 1.0, "y": 2.0, "z": 10.0}
        mock_mpu.get_gyro_data.return_value = {"x": 0.1, "y": 0.2, "z": 0.3}
        mock_mpu.get_temp.return_value = 25.0
        mock_mpu_module = MagicMock()
        mock_mpu_module.mpu6050.return_value = mock_mpu
        mock_mpu_module.ACCEL_RANGE_2G = 0
        mock_mpu_module.GYRO_RANGE_250DEG = 0
        
        def import_side_effect(name, *args, **kwargs):
            if name == 'mpu6050':
                return mock_mpu_module
            return __import__(name, *args, **kwargs)
        
        mock_import.side_effect = import_side_effect
        
        config = IMUConfig(
            sensor_type=IMUType.MPU6050,
            simulation_mode=False,
            calibration_samples=10
        )
        imu = IMU(config)
        
        result = imu.calibrate()
        assert result is True
        # Check that offsets were calculated
        assert config.accel_offset_x != 0.0 or config.accel_offset_y != 0.0

    def test_get_status(self):
        """Test getting IMU status."""
        config = IMUConfig(
            sensor_type=IMUType.MPU6050,
            i2c_address=0x68,
            i2c_bus=1,
            simulation_mode=True
        )
        imu = IMU(config)
        
        # Read some data first
        imu.read_data()
        
        status = imu.get_status()
        assert status["sensor_type"] == "mpu6050"
        assert status["connected"] is True
        assert status["simulation_mode"] is True
        assert status["reading_count"] == 1
        assert status["i2c_address"] == "0x68"
        assert status["i2c_bus"] == 1

    def test_disconnect(self):
        """Test disconnecting from IMU."""
        config = IMUConfig(
            sensor_type=IMUType.MPU6050,
            simulation_mode=True
        )
        imu = IMU(config)
        
        assert imu.is_connected is True
        imu.disconnect()
        assert imu.is_connected is False
        assert imu._mpu6050 is None

    def test_read_data_when_disconnected(self):
        """Test reading data when disconnected."""
        config = IMUConfig(
            sensor_type=IMUType.MPU6050,
            simulation_mode=True
        )
        imu = IMU(config)
        imu.is_connected = False
        
        reading = imu.read_data()
        assert reading is None

    @patch('builtins.__import__')
    def test_read_data_hardware_error(self, mock_import):
        """Test handling errors when reading from hardware."""
        mock_mpu = MagicMock()
        mock_mpu.get_accel_data.side_effect = Exception("I2C error")
        mock_mpu_module = MagicMock()
        mock_mpu_module.mpu6050.return_value = mock_mpu
        mock_mpu_module.ACCEL_RANGE_2G = 0
        mock_mpu_module.GYRO_RANGE_250DEG = 0
        
        def import_side_effect(name, *args, **kwargs):
            if name == 'mpu6050':
                return mock_mpu_module
            return __import__(name, *args, **kwargs)
        
        mock_import.side_effect = import_side_effect
        
        config = IMUConfig(
            sensor_type=IMUType.MPU6050,
            simulation_mode=False
        )
        imu = IMU(config)
        
        reading = imu.read_data()
        assert reading is None


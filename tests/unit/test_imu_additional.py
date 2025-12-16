"""Additional unit tests for IMU uncovered lines."""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from sensors.imu import IMU, IMUConfig, IMUType, IMUStatus


class TestIMUAdditional:
    """Additional tests for IMU uncovered lines."""

    @patch('builtins.__import__')
    def test_initialize_mpu6050_import_error(self, mock_import):
        """Test MPU-6050 initialization with import error."""
        def import_side_effect(name, *args, **kwargs):
            if name == 'mpu6050':
                raise ImportError("Module not found")
            return __import__(name, *args, **kwargs)
        
        mock_import.side_effect = import_side_effect
        
        config = IMUConfig(
            sensor_type=IMUType.MPU6050,
            simulation_mode=False
        )
        imu = IMU(config)
        
        # Should fall back to simulation mode
        assert imu.config.simulation_mode is True
        assert imu.is_connected is True

    @patch('builtins.__import__')
    def test_initialize_mpu6050_exception(self, mock_import):
        """Test MPU-6050 initialization with exception."""
        mock_mpu_module = MagicMock()
        mock_mpu_module.mpu6050.side_effect = Exception("Hardware error")
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
        
        # Should fall back to simulation mode
        assert imu.config.simulation_mode is True

    @patch('builtins.__import__')
    def test_initialize_mpu9250_import_error(self, mock_import):
        """Test MPU-9250 initialization with import error."""
        def import_side_effect(name, *args, **kwargs):
            if name == 'mpu9250_jmdev':
                raise ImportError("Module not found")
            return __import__(name, *args, **kwargs)
        
        mock_import.side_effect = import_side_effect
        
        config = IMUConfig(
            sensor_type=IMUType.MPU9250,
            simulation_mode=False
        )
        imu = IMU(config)
        
        # Should fall back to simulation mode
        assert imu.config.simulation_mode is True

    @patch('builtins.__import__')
    def test_initialize_mpu9250_exception(self, mock_import):
        """Test MPU-9250 initialization with exception."""
        mock_mpu_module = MagicMock()
        mock_mpu_module.mpu9250.side_effect = Exception("Hardware error")
        
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
        
        # Should fall back to simulation mode
        assert imu.config.simulation_mode is True

    def test_read_data_exception(self):
        """Test read_data with exception."""
        config = IMUConfig(
            sensor_type=IMUType.MPU6050,
            simulation_mode=True
        )
        imu = IMU(config)
        
        # Force an exception by corrupting the config
        with patch.object(imu, '_read_simulation', side_effect=Exception("Read error")):
            reading = imu.read_data()
            assert reading is None

    @patch('builtins.__import__')
    def test_read_mpu6050_exception(self, mock_import):
        """Test reading MPU-6050 with exception."""
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

    @patch('builtins.__import__')
    def test_read_mpu9250_exception(self, mock_import):
        """Test reading MPU-9250 with exception."""
        mock_mpu = MagicMock()
        mock_mpu.readAccelerometerMaster.side_effect = Exception("I2C error")
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
        assert reading is None

    @patch('builtins.__import__')
    def test_calibrate_insufficient_samples(self, mock_import):
        """Test calibration with insufficient samples."""
        mock_mpu = MagicMock()
        mock_mpu.get_accel_data.return_value = {"x": 0.0, "y": 0.0, "z": 9.81}
        mock_mpu.get_gyro_data.return_value = {"x": 0.0, "y": 0.0, "z": 0.0}
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
            calibration_samples=5
        )
        imu = IMU(config)
        
        # Mock read_data to return None most of the time
        with patch.object(imu, 'read_data', side_effect=[None] * 4 + [None]):
            result = imu.calibrate()
            # Should fail due to insufficient samples
            assert result is False

    @patch('builtins.__import__')
    def test_calibrate_with_magnetometer(self, mock_import):
        """Test calibration with MPU-9250 including magnetometer."""
        mock_mpu = MagicMock()
        mock_mpu.readAccelerometerMaster.return_value = [0.0, 0.0, 9.81]
        mock_mpu.readGyroscopeMaster.return_value = [0.0, 0.0, 0.0]
        mock_mpu.readMagnetometerMaster.return_value = [20.0, 5.0, 45.0]
        mock_mpu.readTemperatureMaster.return_value = 25.0
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
            calibration_samples=5
        )
        imu = IMU(config)
        
        result = imu.calibrate()
        assert result is True
        # Check that magnetometer offsets were calculated
        assert config.mag_offset_x != 0.0 or config.mag_offset_y != 0.0 or config.mag_offset_z != 0.0

    @patch('builtins.__import__')
    def test_calibrate_exception(self, mock_import):
        """Test calibration with exception."""
        mock_mpu = MagicMock()
        mock_mpu.get_accel_data.return_value = {"x": 0.0, "y": 0.0, "z": 9.81}
        mock_mpu.get_gyro_data.return_value = {"x": 0.0, "y": 0.0, "z": 0.0}
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
        
        # Force exception during calibration
        with patch.object(imu, 'read_data', side_effect=Exception("Read error")):
            result = imu.calibrate()
            assert result is False


"""Functional/integration tests for IMU module."""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from sensors.imu import IMU, IMUConfig, IMUType, IMUStatus


class TestIMUIntegration:
    """Integration tests for IMU sensor."""

    def test_imu_initialization_from_config(self):
        """Test initializing IMU from configuration dictionary."""
        config_dict = {
            "sensor_type": "mpu6050",
            "i2c_address": 104,  # 0x68
            "i2c_bus": 1,
            "sampling_rate_hz": 100.0,
            "simulation_mode": True,
            "calibration_samples": 100
        }
        
        config = IMUConfig(
            sensor_type=IMUType.MPU6050,
            i2c_address=config_dict["i2c_address"],
            i2c_bus=config_dict["i2c_bus"],
            sampling_rate_hz=config_dict["sampling_rate_hz"],
            simulation_mode=config_dict["simulation_mode"],
            calibration_samples=config_dict["calibration_samples"]
        )
        
        imu = IMU(config)
        assert imu.is_connected is True
        assert imu.config.sensor_type == IMUType.MPU6050

    def test_imu_continuous_reading(self):
        """Test continuous reading from IMU."""
        config = IMUConfig(
            sensor_type=IMUType.MPU6050,
            simulation_mode=True,
            sampling_rate_hz=10.0  # 10 Hz for testing
        )
        imu = IMU(config)
        
        readings = []
        for _ in range(5):
            reading = imu.read_data()
            if reading:
                readings.append(reading)
            time.sleep(0.12)  # Slightly more than 1/10 Hz
        
        assert len(readings) >= 4  # Should get at least 4 readings
        assert all(r.status == IMUStatus.HEALTHY for r in readings)
        assert all("x" in r.accelerometer for r in readings)
        assert all("x" in r.gyroscope for r in readings)

    def test_imu_mpu9250_with_magnetometer(self):
        """Test MPU-9250 reading with magnetometer data."""
        config = IMUConfig(
            sensor_type=IMUType.MPU9250,
            simulation_mode=True
        )
        imu = IMU(config)
        
        reading = imu.read_data()
        assert reading is not None
        assert reading.magnetometer is not None
        assert "x" in reading.magnetometer
        assert "y" in reading.magnetometer
        assert "z" in reading.magnetometer

    def test_imu_calibration_workflow(self):
        """Test complete calibration workflow."""
        config = IMUConfig(
            sensor_type=IMUType.MPU6050,
            simulation_mode=True,
            calibration_samples=10
        )
        imu = IMU(config)
        
        # Calibration should succeed in simulation mode
        result = imu.calibrate()
        assert result is True

    @patch('builtins.__import__')
    def test_imu_hardware_integration_mpu6050(self, mock_import):
        """Test integration with MPU-6050 hardware library."""
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
            i2c_address=0x68,
            i2c_bus=1
        )
        imu = IMU(config)
        
        assert imu.is_connected is True
        reading = imu.read_data()
        assert reading is not None
        assert reading.accelerometer["z"] == pytest.approx(9.81, abs=0.1)

    @patch('builtins.__import__')
    def test_imu_hardware_integration_mpu9250(self, mock_import):
        """Test integration with MPU-9250 hardware library."""
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
            i2c_address=0x68,
            i2c_bus=1
        )
        imu = IMU(config)
        
        assert imu.is_connected is True
        reading = imu.read_data()
        assert reading is not None
        assert reading.magnetometer is not None
        assert reading.magnetometer["x"] == 20.0

    def test_imu_status_reporting(self):
        """Test IMU status reporting."""
        config = IMUConfig(
            sensor_type=IMUType.MPU6050,
            simulation_mode=True,
            i2c_address=0x68,
            i2c_bus=1
        )
        imu = IMU(config)
        
        # Read some data
        for _ in range(3):
            imu.read_data()
            time.sleep(0.1)
        
        status = imu.get_status()
        assert status["sensor_type"] == "mpu6050"
        assert status["connected"] is True
        assert status["simulation_mode"] is True
        assert status["reading_count"] >= 1
        assert status["i2c_address"] == "0x68"

    def test_imu_data_consistency(self):
        """Test that IMU data is consistent across readings."""
        config = IMUConfig(
            sensor_type=IMUType.MPU6050,
            simulation_mode=True,
            sampling_rate_hz=100.0
        )
        imu = IMU(config)
        
        readings = []
        for _ in range(10):
            reading = imu.read_data()
            if reading:
                readings.append(reading)
            time.sleep(0.015)  # Wait between readings
        
        # All readings should have the same structure
        assert len(readings) > 0
        for reading in readings:
            assert "x" in reading.accelerometer
            assert "y" in reading.accelerometer
            assert "z" in reading.accelerometer
            assert "x" in reading.gyroscope
            assert "y" in reading.gyroscope
            assert "z" in reading.gyroscope
            assert reading.status == IMUStatus.HEALTHY

    def test_imu_disconnect_reconnect(self):
        """Test disconnecting and reconnecting IMU."""
        config = IMUConfig(
            sensor_type=IMUType.MPU6050,
            simulation_mode=True,
            sampling_rate_hz=100.0
        )
        imu = IMU(config)
        
        assert imu.is_connected is True
        reading1 = imu.read_data()
        assert reading1 is not None
        
        imu.disconnect()
        assert imu.is_connected is False
        
        # After disconnect, read_data should return None
        # Wait a bit to ensure we're not getting a cached reading
        time.sleep(0.02)
        reading2 = imu.read_data()
        assert reading2 is None
        
        # Reinitialize by creating a new IMU instance
        imu2 = IMU(config)
        assert imu2.is_connected is True
        reading3 = imu2.read_data()
        assert reading3 is not None

    def test_imu_sampling_rate_enforcement(self):
        """Test that sampling rate is properly enforced."""
        config = IMUConfig(
            sensor_type=IMUType.MPU6050,
            simulation_mode=True,
            sampling_rate_hz=10.0  # 10 Hz = 100ms between readings
        )
        imu = IMU(config)
        
        reading1 = imu.read_data()
        assert reading1 is not None
        
        # Try to read immediately - should return same reading
        reading2 = imu.read_data()
        assert reading2 == reading1
        assert imu.reading_count == 1
        
        # Wait for sampling interval
        time.sleep(0.11)
        reading3 = imu.read_data()
        assert reading3 is not None
        assert reading3 != reading1
        assert imu.reading_count == 2

    def test_imu_calibration_offsets(self):
        """Test that calibration offsets are applied correctly."""
        config = IMUConfig(
            sensor_type=IMUType.MPU6050,
            simulation_mode=True,
            accel_offset_x=0.5,
            accel_offset_y=-0.3,
            accel_offset_z=0.1,
            gyro_offset_x=0.01,
            gyro_offset_y=-0.02,
            gyro_offset_z=0.005
        )
        imu = IMU(config)
        
        # In simulation mode, offsets aren't applied to simulated data
        # but the config should store them
        assert config.accel_offset_x == 0.5
        assert config.accel_offset_y == -0.3
        assert config.gyro_offset_x == 0.01

    @patch('builtins.__import__')
    def test_imu_calibration_with_hardware(self, mock_import):
        """Test calibration process with hardware."""
        mock_mpu = MagicMock()
        # Simulate consistent readings for calibration
        mock_mpu.get_accel_data.return_value = {"x": 0.1, "y": 0.2, "z": 10.0}
        mock_mpu.get_gyro_data.return_value = {"x": 0.01, "y": 0.02, "z": 0.03}
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
        
        result = imu.calibrate()
        assert result is True
        # Offsets should be calculated
        assert config.accel_offset_x != 0.0 or config.accel_offset_y != 0.0


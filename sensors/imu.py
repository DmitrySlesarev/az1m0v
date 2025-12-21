"""IMU (Inertial Measurement Unit) module for the EV project.
Supports MPU-6050 (6-DOF) and MPU-9250 (9-DOF) sensors via I2C.
"""

import time
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum
import math


class IMUType(Enum):
    """IMU sensor types."""
    MPU6050 = "mpu6050"  # 6-DOF: accelerometer + gyroscope
    MPU9250 = "mpu9250"  # 9-DOF: accelerometer + gyroscope + magnetometer


class IMUStatus(Enum):
    """IMU operational status."""
    HEALTHY = "healthy"
    WARNING = "warning"
    FAULT = "fault"
    DISCONNECTED = "disconnected"


@dataclass
class IMUReading:
    """IMU sensor reading data."""
    timestamp: float
    accelerometer: Dict[str, float]  # x, y, z in m/s²
    gyroscope: Dict[str, float]  # x, y, z in rad/s
    magnetometer: Optional[Dict[str, float]] = None  # x, y, z in µT (only for 9-DOF)
    temperature_c: float = 25.0
    status: IMUStatus = IMUStatus.HEALTHY
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert reading to dictionary."""
        result = {
            "timestamp": self.timestamp,
            "accelerometer": self.accelerometer,
            "gyroscope": self.gyroscope,
            "temperature_c": self.temperature_c,
            "status": self.status.value
        }
        if self.magnetometer is not None:
            result["magnetometer"] = self.magnetometer
        return result


@dataclass
class IMUConfig:
    """IMU configuration parameters."""
    sensor_type: IMUType = IMUType.MPU6050
    i2c_address: int = 0x68  # Default I2C address for MPU-6050/MPU-9250
    i2c_bus: int = 1  # Default I2C bus (usually 1 on Raspberry Pi)
    sampling_rate_hz: float = 100.0  # Data sampling rate
    simulation_mode: bool = True  # Run without hardware
    calibration_samples: int = 100  # Number of samples for calibration
    # Accelerometer calibration offsets
    accel_offset_x: float = 0.0
    accel_offset_y: float = 0.0
    accel_offset_z: float = 0.0
    # Gyroscope calibration offsets
    gyro_offset_x: float = 0.0
    gyro_offset_y: float = 0.0
    gyro_offset_z: float = 0.0
    # Magnetometer calibration offsets (for 9-DOF)
    mag_offset_x: float = 0.0
    mag_offset_y: float = 0.0
    mag_offset_z: float = 0.0


class IMU:
    """Inertial Measurement Unit interface for MPU-6050 and MPU-9250 sensors."""

    def __init__(self, config: IMUConfig):
        """Initialize IMU sensor.
        
        Args:
            config: IMU configuration parameters
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.is_connected = False
        self.last_reading: Optional[IMUReading] = None
        self.reading_count = 0
        self.last_update_time = 0.0
        
        # Hardware interface (will be None in simulation mode)
        self._mpu6050 = None
        self._mpu9250 = None
        
        # Initialize sensor
        self._initialize_sensor()

    def _initialize_sensor(self) -> None:
        """Initialize the IMU sensor hardware or simulation."""
        if self.config.simulation_mode:
            self.logger.info("IMU running in simulation mode")
            self.is_connected = True
            return

        try:
            if self.config.sensor_type == IMUType.MPU6050:
                self._initialize_mpu6050()
            elif self.config.sensor_type == IMUType.MPU9250:
                self._initialize_mpu9250()
            else:
                raise ValueError(f"Unsupported sensor type: {self.config.sensor_type}")
        except Exception as e:
            self.logger.warning(f"Failed to initialize IMU hardware: {e}")
            self.logger.info("Falling back to simulation mode")
            self.config.simulation_mode = True
            self.is_connected = True

    def _initialize_mpu6050(self) -> None:
        """Initialize MPU-6050 sensor."""
        try:
            import mpu6050
            self._mpu6050 = mpu6050.mpu6050(self.config.i2c_address, self.config.i2c_bus)
            self._mpu6050.set_accel_range(mpu6050.ACCEL_RANGE_2G)
            self._mpu6050.set_gyro_range(mpu6050.GYRO_RANGE_250DEG)
            self.is_connected = True
            self.logger.info("MPU-6050 initialized successfully")
        except ImportError:
            raise ImportError("mpu6050 library not available. Install via: pip install mpu6050-raspberrypi")
        except Exception as e:
            raise Exception(f"Failed to initialize MPU-6050: {e}")

    def _initialize_mpu9250(self) -> None:
        """Initialize MPU-9250 sensor."""
        try:
            from mpu9250_jmdev import mpu9250
            self._mpu9250 = mpu9250(self.config.i2c_address, self.config.i2c_bus)
            self._mpu9250.abias = [
                self.config.accel_offset_x,
                self.config.accel_offset_y,
                self.config.accel_offset_z
            ]
            self._mpu9250.gbias = [
                self.config.gyro_offset_x,
                self.config.gyro_offset_y,
                self.config.gyro_offset_z
            ]
            self.is_connected = True
            self.logger.info("MPU-9250 initialized successfully")
        except ImportError:
            raise ImportError("mpu9250_jmdev library not available. Install via: pip install mpu9250-jmdev")
        except Exception as e:
            raise Exception(f"Failed to initialize MPU-9250: {e}")

    def read_data(self) -> Optional[IMUReading]:
        """Read data from IMU sensor.
        
        Returns:
            IMUReading if successful, None otherwise
        """
        current_time = time.time()
        
        # Check sampling rate
        if (current_time - self.last_update_time) < (1.0 / self.config.sampling_rate_hz):
            return self.last_reading

        if not self.is_connected:
            self.logger.warning("IMU not connected")
            return None

        try:
            if self.config.simulation_mode:
                reading = self._read_simulation()
            else:
                if self.config.sensor_type == IMUType.MPU6050:
                    reading = self._read_mpu6050()
                elif self.config.sensor_type == IMUType.MPU9250:
                    reading = self._read_mpu9250()
                else:
                    reading = None

            if reading:
                self.last_reading = reading
                self.reading_count += 1
                self.last_update_time = current_time

            return reading

        except Exception as e:
            self.logger.error(f"Error reading IMU data: {e}")
            return None

    def _read_simulation(self) -> IMUReading:
        """Generate simulated IMU data."""
        # Simulate realistic vehicle motion
        t = time.time()
        # Simulate gentle acceleration/deceleration
        accel_x = 0.5 * math.sin(t * 0.1)  # Forward/backward
        accel_y = 0.2 * math.cos(t * 0.15)  # Left/right
        accel_z = 9.81 + 0.1 * math.sin(t * 0.2)  # Vertical (gravity + vibration)
        
        # Simulate rotation
        gyro_x = 0.05 * math.sin(t * 0.12)  # Roll
        gyro_y = 0.03 * math.cos(t * 0.18)  # Pitch
        gyro_z = 0.02 * math.sin(t * 0.14)  # Yaw
        
        magnetometer = None
        if self.config.sensor_type == IMUType.MPU9250:
            # Simulate magnetometer data (Earth's magnetic field ~50 µT)
            magnetometer = {
                "x": 20.0 + 2.0 * math.sin(t * 0.1),
                "y": 5.0 + 1.0 * math.cos(t * 0.1),
                "z": 45.0 + 1.5 * math.sin(t * 0.15)
            }

        return IMUReading(
            timestamp=time.time(),
            accelerometer={"x": accel_x, "y": accel_y, "z": accel_z},
            gyroscope={"x": gyro_x, "y": gyro_y, "z": gyro_z},
            magnetometer=magnetometer,
            temperature_c=25.0 + 5.0 * math.sin(t * 0.05),
            status=IMUStatus.HEALTHY
        )

    def _read_mpu6050(self) -> Optional[IMUReading]:
        """Read data from MPU-6050 sensor."""
        if not self._mpu6050:
            return None

        try:
            accel_data = self._mpu6050.get_accel_data()
            gyro_data = self._mpu6050.get_gyro_data()
            temp = self._mpu6050.get_temp()

            # Apply calibration offsets
            accel_x = accel_data['x'] - self.config.accel_offset_x
            accel_y = accel_data['y'] - self.config.accel_offset_y
            accel_z = accel_data['z'] - self.config.accel_offset_z
            
            gyro_x = gyro_data['x'] - self.config.gyro_offset_x
            gyro_y = gyro_data['y'] - self.config.gyro_offset_y
            gyro_z = gyro_data['z'] - self.config.gyro_offset_z

            return IMUReading(
                timestamp=time.time(),
                accelerometer={"x": accel_x, "y": accel_y, "z": accel_z},
                gyroscope={"x": gyro_x, "y": gyro_y, "z": gyro_z},
                temperature_c=temp,
                status=IMUStatus.HEALTHY
            )
        except Exception as e:
            self.logger.error(f"Error reading MPU-6050: {e}")
            return None

    def _read_mpu9250(self) -> Optional[IMUReading]:
        """Read data from MPU-9250 sensor."""
        if not self._mpu9250:
            return None

        try:
            accel_data = self._mpu9250.readAccelerometerMaster()
            gyro_data = self._mpu9250.readGyroscopeMaster()
            mag_data = self._mpu9250.readMagnetometerMaster()
            temp = self._mpu9250.readTemperatureMaster()

            # Apply calibration offsets
            accel_x = accel_data[0] - self.config.accel_offset_x
            accel_y = accel_data[1] - self.config.accel_offset_y
            accel_z = accel_data[2] - self.config.accel_offset_z
            
            gyro_x = gyro_data[0] - self.config.gyro_offset_x
            gyro_y = gyro_data[1] - self.config.gyro_offset_y
            gyro_z = gyro_data[2] - self.config.gyro_offset_z
            
            mag_x = mag_data[0] - self.config.mag_offset_x
            mag_y = mag_data[1] - self.config.mag_offset_y
            mag_z = mag_data[2] - self.config.mag_offset_z

            return IMUReading(
                timestamp=time.time(),
                accelerometer={"x": accel_x, "y": accel_y, "z": accel_z},
                gyroscope={"x": gyro_x, "y": gyro_y, "z": gyro_z},
                magnetometer={"x": mag_x, "y": mag_y, "z": mag_z},
                temperature_c=temp,
                status=IMUStatus.HEALTHY
            )
        except Exception as e:
            self.logger.error(f"Error reading MPU-9250: {e}")
            return None

    def calibrate(self) -> bool:
        """Calibrate IMU sensor by collecting offset samples.
        
        Returns:
            True if calibration successful, False otherwise
        """
        if self.config.simulation_mode:
            self.logger.info("Calibration skipped in simulation mode")
            return True

        self.logger.info(f"Starting IMU calibration ({self.config.calibration_samples} samples)...")
        
        try:
            accel_samples = []
            gyro_samples = []
            mag_samples = []

            for i in range(self.config.calibration_samples):
                reading = self.read_data()
                if reading:
                    accel_samples.append(reading.accelerometer)
                    gyro_samples.append(reading.gyroscope)
                    if reading.magnetometer:
                        mag_samples.append(reading.magnetometer)
                time.sleep(0.01)

            if len(accel_samples) < self.config.calibration_samples // 2:
                self.logger.error("Insufficient samples for calibration")
                return False

            # Calculate offsets (average of samples)
            self.config.accel_offset_x = sum(s['x'] for s in accel_samples) / len(accel_samples)
            self.config.accel_offset_y = sum(s['y'] for s in accel_samples) / len(accel_samples)
            self.config.accel_offset_z = sum(s['z'] for s in accel_samples) / len(accel_samples) - 9.81  # Remove gravity

            self.config.gyro_offset_x = sum(s['x'] for s in gyro_samples) / len(gyro_samples)
            self.config.gyro_offset_y = sum(s['y'] for s in gyro_samples) / len(gyro_samples)
            self.config.gyro_offset_z = sum(s['z'] for s in gyro_samples) / len(gyro_samples)

            if mag_samples:
                self.config.mag_offset_x = sum(s['x'] for s in mag_samples) / len(mag_samples)
                self.config.mag_offset_y = sum(s['y'] for s in mag_samples) / len(mag_samples)
                self.config.mag_offset_z = sum(s['z'] for s in mag_samples) / len(mag_samples)

            self.logger.info("IMU calibration completed successfully")
            return True

        except Exception as e:
            self.logger.error(f"Calibration failed: {e}")
            return False

    def get_status(self) -> Dict[str, Any]:
        """Get IMU status information.
        
        Returns:
            Dictionary with status information
        """
        return {
            "sensor_type": self.config.sensor_type.value,
            "connected": self.is_connected,
            "simulation_mode": self.config.simulation_mode,
            "reading_count": self.reading_count,
            "last_update_time": self.last_update_time,
            "sampling_rate_hz": self.config.sampling_rate_hz,
            "i2c_address": hex(self.config.i2c_address),
            "i2c_bus": self.config.i2c_bus
        }

    def disconnect(self) -> None:
        """Disconnect from IMU sensor."""
        self.is_connected = False
        self._mpu6050 = None
        self._mpu9250 = None
        self.logger.info("IMU disconnected")

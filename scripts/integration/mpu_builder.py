"""MPU-6050/MPU-9250 IMU build and integration script.
Manages downloading, building, and integrating MPU IMU libraries into the project.
Supports MPU-6050 (6-DOF) and MPU-9250 (9-DOF) sensors via I2C.
Python libraries:
- mpu6050: https://github.com/m-rtijn/mpu6050
- mpu9250-jmdev: https://github.com/jefmenegazzo/mpu-i2c-drivers-python
"""

import os
import subprocess
import sys
import platform
import logging
from pathlib import Path
from typing import Optional, Dict
from enum import Enum


class BuildSystem(Enum):
    PIP = "pip"
    GIT = "git"


class MPUManager:
    """
    Manages downloading, building, and integrating MPU IMU Python libraries into the project
    """

    # MPU-6050 library (6-DOF)
    MPU6050_PIP_PACKAGE = "mpu6050-raspberrypi"
    MPU6050_GIT_REPO = "https://github.com/m-rtijn/mpu6050.git"
    
    # MPU-9250 library (9-DOF) - alternative library
    MPU9250_PIP_PACKAGE = "mpu9250-jmdev"
    MPU9250_GIT_REPO = "https://github.com/jefmenegazzo/mpu-i2c-drivers-python.git"

    def __init__(self, project_root: str = ".", build_system: BuildSystem = BuildSystem.PIP):
        self.project_root = Path(project_root).absolute()
        self.build_system = build_system
        self.mpu_dir = self.project_root / "scripts" / "integration" / "MPU"
        self.build_dir = self.mpu_dir / "build"

        self.logger = self._setup_logging()
        self._verify_environment()

    def _setup_logging(self) -> logging.Logger:
        """Setup logging for build process"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger(__name__)

    def _verify_environment(self):
        """Verify that required tools are installed"""
        self.logger.info("Verifying build environment...")

        required_tools = []
        if self.build_system == BuildSystem.PIP:
            required_tools = ["pip", "python"]
        elif self.build_system == BuildSystem.GIT:
            required_tools = ["git", "pip", "python"]

        missing_tools = []
        for tool in required_tools:
            if not self._is_tool_installed(tool):
                missing_tools.append(tool)

        if missing_tools:
            self.logger.error(f"Missing required tools: {', '.join(missing_tools)}")
            self.logger.info("Please install the missing tools before continuing.")
            sys.exit(1)

        self.logger.info("Build environment verified successfully")

    def _is_tool_installed(self, tool: str) -> bool:
        """Check if a command line tool is installed"""
        try:
            if tool == "python":
                subprocess.run([sys.executable, "--version"], capture_output=True, check=True)
                return True
            else:
                subprocess.run([tool, "--version"], capture_output=True, check=True)
                return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def download_mpu(self, sensor_type: str = "mpu6050", force_redownload: bool = False) -> bool:
        """
        Download MPU IMU Python library from GitHub or install via pip
        Args:
            sensor_type: "mpu6050" or "mpu9250"
            force_redownload: Force reinstall even if already installed
        Returns: True if successful, False otherwise
        """
        if self.build_system == BuildSystem.PIP:
            return self._install_via_pip(sensor_type, force_redownload)
        else:
            return self._download_from_github(sensor_type, force_redownload)

    def _install_via_pip(self, sensor_type: str, force_redownload: bool = False) -> bool:
        """Install MPU library via pip"""
        try:
            package_name = self.MPU6050_PIP_PACKAGE if sensor_type == "mpu6050" else self.MPU9250_PIP_PACKAGE
            self.logger.info(f"Installing {package_name} via pip...")

            # Check if already installed
            if not force_redownload:
                try:
                    if sensor_type == "mpu6050":
                        import mpu6050
                    else:
                        import mpu9250_jmdev
                    self.logger.info(f"{package_name} already installed. Use force_redownload=True to reinstall.")
                    return True
                except ImportError:
                    pass

            # Install via pip
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", package_name],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                self.logger.info(f"{package_name} installed successfully via pip")
                return True
            else:
                self.logger.warning(f"pip install failed: {result.stderr}")
                return self._install_from_git(sensor_type)

        except Exception as e:
            self.logger.error(f"Failed to install {package_name} via pip: {e}")
            return False

    def _install_from_git(self, sensor_type: str) -> bool:
        """Install MPU library from git repository"""
        try:
            repo_url = self.MPU6050_GIT_REPO if sensor_type == "mpu6050" else self.MPU9250_GIT_REPO
            self.logger.info(f"Installing MPU library from git repository: {repo_url}...")

            # Clone repository
            repo_dir = self.mpu_dir / sensor_type
            if repo_dir.exists():
                import shutil
                shutil.rmtree(repo_dir)

            result = subprocess.run(
                ["git", "clone", repo_url, str(repo_dir)],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                self.logger.error(f"Failed to clone repository: {result.stderr}")
                return False

            # Install in development mode
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-e", str(repo_dir)],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                self.logger.info(f"MPU library installed successfully from git")
                return True
            else:
                self.logger.error(f"Failed to install from git: {result.stderr}")
                return False

        except Exception as e:
            self.logger.error(f"Failed to install from git: {e}")
            return False

    def _download_from_github(self, sensor_type: str, force_redownload: bool = False) -> bool:
        """Download MPU from GitHub (legacy method)"""
        # This method is similar to VESC builder but for MPU libraries
        # For now, redirect to pip installation
        return self._install_via_pip(sensor_type, force_redownload)

    def setup_dependencies(self) -> bool:
        """
        Install required dependencies for MPU sensors
        Returns: True if successful, False otherwise
        """
        try:
            self.logger.info("Setting up MPU dependencies...")

            # MPU libraries typically require smbus or smbus2 for I2C communication
            dependencies = ["smbus2"]

            for dep in dependencies:
                self.logger.info(f"Installing dependency: {dep}")
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", dep],
                    capture_output=True,
                    text=True
                )
                if result.returncode != 0:
                    self.logger.warning(f"Failed to install {dep}: {result.stderr}")

            return True

        except Exception as e:
            self.logger.error(f"Failed to setup dependencies: {e}")
            return False

    def build_mpu(self, sensor_type: str = "mpu6050") -> bool:
        """
        Build MPU Python library (mainly for verification)
        Args:
            sensor_type: "mpu6050" or "mpu9250"
        Returns: True if successful, False otherwise
        """
        try:
            self.logger.info(f"Verifying MPU {sensor_type} installation...")

            # Try to import the module
            try:
                if sensor_type == "mpu6050":
                    import mpu6050
                    self.logger.info("MPU-6050 module verified successfully")
                else:
                    import mpu9250_jmdev
                    self.logger.info("MPU-9250 module verified successfully")
                return True
            except ImportError as e:
                self.logger.error(f"MPU module not available: {e}")
                return False

        except Exception as e:
            self.logger.error(f"Build verification failed: {e}")
            return False

    def get_status(self, sensor_type: str = "mpu6050") -> Dict:
        """Get current MPU integration status"""
        mpu_available = False
        try:
            if sensor_type == "mpu6050":
                import mpu6050
                mpu_available = True
            else:
                import mpu9250_jmdev
                mpu_available = True
        except ImportError:
            pass

        return {
            "mpu_available": mpu_available,
            "sensor_type": sensor_type,
            "build_system": self.build_system.value,
            "project_root": str(self.project_root)
        }


def setup_mpu_in_project(sensor_type: str = "mpu6050"):
    """Example of how to integrate MPU IMU into your EV project"""

    # Initialize the manager
    mpu_manager = MPUManager(
        project_root="../../..",  # Adjust based on your project structure
        build_system=BuildSystem.PIP  # Recommended for easy installation
    )

    # Check status
    status = mpu_manager.get_status(sensor_type)
    print("Initial Status:", status)

    # Download/Install MPU
    if not mpu_manager.download_mpu(sensor_type):
        print(f"Failed to download/install MPU {sensor_type}")
        return False

    # Setup dependencies
    if not mpu_manager.setup_dependencies():
        print("Failed to setup dependencies")
        return False

    # Build/Verify the library
    if not mpu_manager.build_mpu(sensor_type):
        print(f"Failed to verify MPU {sensor_type} installation")
        return False

    # Get final status
    status = mpu_manager.get_status(sensor_type)
    print("Final Status:", status)

    return True


if __name__ == "__main__":
    # Run the setup when this script is executed directly
    import argparse
    
    parser = argparse.ArgumentParser(description="MPU IMU integration script")
    parser.add_argument("--sensor", choices=["mpu6050", "mpu9250"], default="mpu6050",
                       help="Sensor type to install (default: mpu6050)")
    args = parser.parse_args()
    
    success = setup_mpu_in_project(args.sensor)
    sys.exit(0 if success else 1)


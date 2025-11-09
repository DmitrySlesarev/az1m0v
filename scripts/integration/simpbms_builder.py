"""SimpBMS build and integration script.
Manages downloading, building, and integrating SimpBMS into the project.
SimpBMS System (Arduino-based) Compatible with open-source BMS projects via CAN bus or serial
GitHub: https://github.com/msglazer/SimpBMS
"""

import os
import subprocess
import sys
import platform
import urllib.request
import zipfile
import shutil
import logging
from pathlib import Path
from typing import Optional, Dict
from enum import Enum


class BuildSystem(Enum):
    ARDUINO_IDE = "arduino_ide"
    PLATFORMIO = "platformio"
    CMAKE = "cmake"
    MAKE = "make"


class SimpBMSManager:
    """
    Manages downloading, building, and integrating SimpBMS into the project
    """
    
    # SimpBMS repository information
    SIMPBMS_REPO_URL = "https://github.com/msglazer/SimpBMS/archive/refs/heads/master.zip"
    SIMPBMS_DIR_NAME = "SimpBMS"
    
    def __init__(self, project_root: str = ".", build_system: BuildSystem = BuildSystem.PLATFORMIO):
        self.project_root = Path(project_root).absolute()
        self.build_system = build_system
        self.simpbms_dir = self.project_root / self.SIMPBMS_DIR_NAME
        self.build_dir = self.simpbms_dir / "build"
        
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
        if self.build_system == BuildSystem.PLATFORMIO:
            required_tools = ["platformio", "git"]
        elif self.build_system == BuildSystem.ARDUINO_IDE:
            required_tools = ["arduino", "git"]
        elif self.build_system == BuildSystem.MAKE:
            required_tools = ["make", "gcc", "git"]
        elif self.build_system == BuildSystem.CMAKE:
            required_tools = ["cmake", "make", "gcc", "git"]
        
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
            if tool == "arduino":
                # Arduino IDE might not be in PATH, check common locations
                arduino_paths = [
                    "/usr/bin/arduino",
                    "/Applications/Arduino.app/Contents/MacOS/Arduino",
                    "C:\\Program Files\\Arduino\\arduino.exe"
                ]
                return any(os.path.exists(path) for path in arduino_paths)
            else:
                subprocess.run([tool, "--version"], capture_output=True, check=True)
                return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def download_simpbms(self, force_redownload: bool = False) -> bool:
        """
        Download SimpBMS from GitHub
        Returns: True if successful, False otherwise
        """
        if self.simpbms_dir.exists() and not force_redownload:
            self.logger.info("SimpBMS already downloaded. Use force_redownload=True to re-download.")
            return True
        
        # Remove existing directory if force redownload
        if self.simpbms_dir.exists() and force_redownload:
            shutil.rmtree(self.simpbms_dir)
        
        try:
            self.logger.info("Downloading SimpBMS from GitHub...")
            
            # Download the repository as ZIP
            zip_path = self.project_root / "simpbms_master.zip"
            urllib.request.urlretrieve(self.SIMPBMS_REPO_URL, zip_path)
            
            # Extract ZIP file
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(self.project_root)
            
            # The extracted folder has a different name, rename it
            extracted_dir = self.project_root / "SimpBMS-master"
            if extracted_dir.exists():
                extracted_dir.rename(self.simpbms_dir)
            
            # Clean up ZIP file
            zip_path.unlink()
            
            self.logger.info("SimpBMS downloaded successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to download SimpBMS: {e}")
            return False
    
    def setup_dependencies(self) -> bool:
        """
        Install required dependencies for SimpBMS
        Returns: True if successful, False otherwise
        """
        try:
            self.logger.info("Setting up SimpBMS dependencies...")
            
            if self.build_system == BuildSystem.PLATFORMIO:
                return self._setup_platformio_dependencies()
            elif self.build_system == BuildSystem.ARDUINO_IDE:
                return self._setup_arduino_dependencies()
            elif self.build_system in [BuildSystem.MAKE, BuildSystem.CMAKE]:
                return self._setup_make_dependencies()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to setup dependencies: {e}")
            return False
    
    def _setup_platformio_dependencies(self) -> bool:
        """Install PlatformIO dependencies"""
        try:
            # Run platformio lib install based on SimpBMS requirements
            libs_to_install = [
                "mike@^0.2.0",  # Example - check actual SimpBMS dependencies
                "ArduinoJson",
                "https://github.com/adafruit/Adafruit_BusIO.git",
                "https://github.com/adafruit/Adafruit_ADS1X15.git"
            ]
            
            for lib in libs_to_install:
                self.logger.info(f"Installing library: {lib}")
                result = subprocess.run(
                    ["platformio", "lib", "install", lib],
                    cwd=self.simpbms_dir,
                    capture_output=True,
                    text=True
                )
                if result.returncode != 0:
                    self.logger.warning(f"Failed to install {lib}: {result.stderr}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"PlatformIO dependency setup failed: {e}")
            return False
    
    def _setup_arduino_dependencies(self) -> bool:
        """Install Arduino IDE dependencies"""
        try:
            # For Arduino IDE, we need to check if libraries are available
            # This is more complex as it depends on Arduino IDE installation
            self.logger.info("Arduino IDE dependencies should be installed manually via Library Manager")
            self.logger.info("Required libraries: ArduinoJson, Adafruit BusIO, Adafruit ADS1X15")
            return True
            
        except Exception as e:
            self.logger.error(f"Arduino dependency setup failed: {e}")
            return False
    
    def _setup_make_dependencies(self) -> bool:
        """Install make-based dependencies"""
        try:
            # This would depend on the specific build system
            # SimpBMS might need specific Arduino core libraries
            self.logger.info("Make-based builds may require manual dependency setup")
            return True
            
        except Exception as e:
            self.logger.error(f"Make dependency setup failed: {e}")
            return False
    
    def build_simpbms(self, target: str = "env:teensy36") -> bool:
        """
        Build SimpBMS firmware
        Args:
            target: PlatformIO environment target or make target
        Returns: True if successful, False otherwise
        """
        try:
            self.logger.info(f"Building SimpBMS with target: {target}")
            
            if not self.simpbms_dir.exists():
                self.logger.error("SimpBMS directory not found. Run download_simpbms() first.")
                return False
            
            if self.build_system == BuildSystem.PLATFORMIO:
                return self._build_with_platformio(target)
            elif self.build_system == BuildSystem.ARDUINO_IDE:
                return self._build_with_arduino(target)
            elif self.build_system == BuildSystem.MAKE:
                return self._build_with_make(target)
            elif self.build_system == BuildSystem.CMAKE:
                return self._build_with_cmake(target)
            
            return False
            
        except Exception as e:
            self.logger.error(f"Build failed: {e}")
            return False
    
    def _build_with_platformio(self, target: str) -> bool:
        """Build using PlatformIO"""
        try:
            # First, check if platformio.ini exists
            platformio_ini = self.simpbms_dir / "platformio.ini"
            if not platformio_ini.exists():
                self.logger.warning("platformio.ini not found, creating basic configuration...")
                self._create_platformio_config()
            
            # Run platformio build
            self.logger.info("Running PlatformIO build...")
            result = subprocess.run(
                ["platformio", "run", "-e", target],
                cwd=self.simpbms_dir,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                self.logger.info("PlatformIO build successful!")
                return True
            else:
                self.logger.error(f"PlatformIO build failed: {result.stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"PlatformIO build error: {e}")
            return False
    
    def _create_platformio_config(self):
        """Create a basic platformio.ini if it doesn't exist"""
        platformio_config = """
[env:teensy36]
platform = teensy
board = teensy36
framework = arduino
monitor_speed = 115200

lib_deps = 
    ArduinoJson
    adafruit/Adafruit BusIO@^1.14.1
    adafruit/Adafruit ADS1X15@^2.0.1

build_flags =
    -D SIMPBMS_VERSION=1.0
    -D ENABLE_SERIAL_DEBUG

[env:esp32dev]
platform = espressif32
board = esp32dev
framework = arduino
monitor_speed = 115200

lib_deps = 
    ArduinoJson
    adafruit/Adafruit BusIO@^1.14.1
    adafruit/Adafruit ADS1X15@^2.0.1
"""
        
        with open(self.simpbms_dir / "platformio.ini", "w") as f:
            f.write(platformio_config)
    
    def _build_with_arduino(self, target: str) -> bool:
        """Build using Arduino IDE (limited functionality)"""
        try:
            self.logger.info("Arduino IDE build requires manual compilation in the IDE")
            self.logger.info("Please open the SimpBMS.ino file in Arduino IDE and compile there")
            return True
            
        except Exception as e:
            self.logger.error(f"Arduino build setup error: {e}")
            return False
    
    def _build_with_make(self, target: str) -> bool:
        """Build using make"""
        try:
            # Check for Makefile
            makefile = self.simpbms_dir / "Makefile"
            if not makefile.exists():
                self.logger.error("Makefile not found in SimpBMS directory")
                return False
            
            self.logger.info("Running make...")
            result = subprocess.run(
                ["make", target],
                cwd=self.simpbms_dir,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                self.logger.info("Make build successful!")
                return True
            else:
                self.logger.error(f"Make build failed: {result.stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"Make build error: {e}")
            return False
    
    def _build_with_cmake(self, target: str) -> bool:
        """Build using CMake"""
        try:
            # Create build directory
            self.build_dir.mkdir(exist_ok=True)
            
            # Run CMake configuration
            self.logger.info("Running CMake configuration...")
            cmake_result = subprocess.run(
                ["cmake", ".."],
                cwd=self.build_dir,
                capture_output=True,
                text=True
            )
            
            if cmake_result.returncode != 0:
                self.logger.error(f"CMake configuration failed: {cmake_result.stderr}")
                return False
            
            # Run build
            self.logger.info("Running CMake build...")
            build_result = subprocess.run(
                ["cmake", "--build", ".", "--target", target],
                cwd=self.build_dir,
                capture_output=True,
                text=True
            )
            
            if build_result.returncode == 0:
                self.logger.info("CMake build successful!")
                return True
            else:
                self.logger.error(f"CMake build failed: {build_result.stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"CMake build error: {e}")
            return False
    
    def get_firmware_path(self) -> Optional[Path]:
        """Get the path to the built firmware file"""
        if self.build_system == BuildSystem.PLATFORMIO:
            # PlatformIO typically puts firmware in .pio/build/{env}/
            firmware_dir = self.simpbms_dir / ".pio" / "build"
            if firmware_dir.exists():
                # Find the first firmware file (usually .bin or .hex)
                for pattern in ["*.bin", "*.hex", "*.elf"]:
                    firmware_files = list(firmware_dir.rglob(pattern))
                    if firmware_files:
                        return firmware_files[0]
        
        elif self.build_system in [BuildSystem.MAKE, BuildSystem.CMAKE]:
            # Check build directory for firmware
            for pattern in ["*.bin", "*.hex", "*.elf"]:
                firmware_files = list(self.build_dir.rglob(pattern))
                if firmware_files:
                    return firmware_files[0]
        
        return None
    
    def flash_firmware(self, port: Optional[str] = None) -> bool:
        """
        Flash the built firmware to target hardware
        Args:
            port: Serial port for flashing (auto-detected if None)
        Returns: True if successful, False otherwise
        """
        try:
            firmware_path = self.get_firmware_path()
            if not firmware_path:
                self.logger.error("No firmware found. Build the project first.")
                return False
            
            self.logger.info(f"Flashing firmware: {firmware_path}")
            
            if self.build_system == BuildSystem.PLATFORMIO:
                return self._flash_with_platformio(port)
            else:
                self.logger.warning(f"Automatic flashing not supported for {self.build_system}")
                self.logger.info(f"Please flash manually: {firmware_path}")
                return True
                
        except Exception as e:
            self.logger.error(f"Flashing failed: {e}")
            return False
    
    def _flash_with_platformio(self, port: Optional[str]) -> bool:
        """Flash using PlatformIO"""
        try:
            cmd = ["platformio", "run", "--target", "upload"]
            if port:
                cmd.extend(["--upload-port", port])
            
            result = subprocess.run(
                cmd,
                cwd=self.simpbms_dir,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                self.logger.info("Firmware flashed successfully!")
                return True
            else:
                self.logger.error(f"Flashing failed: {result.stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"PlatformIO flashing error: {e}")
            return False
    
    def clean_build(self) -> bool:
        """Clean build artifacts"""
        try:
            if self.build_system == BuildSystem.PLATFORMIO:
                result = subprocess.run(
                    ["platformio", "run", "--target", "clean"],
                    cwd=self.simpbms_dir,
                    capture_output=True,
                    text=True
                )
                return result.returncode == 0
            elif self.build_system == BuildSystem.MAKE:
                result = subprocess.run(
                    ["make", "clean"],
                    cwd=self.simpbms_dir,
                    capture_output=True,
                    text=True
                )
                return result.returncode == 0
            elif self.build_system == BuildSystem.CMAKE and self.build_dir.exists():
                shutil.rmtree(self.build_dir)
                return True
            else:
                self.logger.warning("Clean not implemented for current build system")
                return True
                
        except Exception as e:
            self.logger.error(f"Clean failed: {e}")
            return False
    
    def get_status(self) -> Dict:
        """Get current SimpBMS integration status"""
        firmware_path = self.get_firmware_path()
        
        return {
            "simpbms_downloaded": self.simpbms_dir.exists(),
            "firmware_built": firmware_path is not None,
            "firmware_path": str(firmware_path) if firmware_path else None,
            "build_system": self.build_system.value,
            "project_root": str(self.project_root)
        }


def setup_simpbms_in_project():
    """Example of how to integrate SimpBMS into your EV project"""
    
    # Initialize the manager
    bms_manager = SimpBMSManager(
        project_root="..",  # Adjust based on your project structure
        build_system=BuildSystem.PLATFORMIO  # Recommended for cross-platform builds
    )
    
    # Check status
    status = bms_manager.get_status()
    print("Initial Status:", status)
    
    # Download SimpBMS
    if not bms_manager.download_simpbms():
        print("Failed to download SimpBMS")
        return False
    
    # Setup dependencies
    if not bms_manager.setup_dependencies():
        print("Failed to setup dependencies")
        return False
    
    # Build the firmware
    if not bms_manager.build_simpbms(target="env:teensy36"):
        print("Failed to build SimpBMS")
        return False
    
    # Get final status
    status = bms_manager.get_status()
    print("Final Status:", status)
    
    # Optional: Flash to hardware
    # if bms_manager.flash_firmware(port="/dev/ttyUSB0"):
    #     print("Firmware flashed successfully!")
    
    return True


if __name__ == "__main__":
    # Run the setup when this script is executed directly
    success = setup_simpbms_in_project()
    sys.exit(0 if success else 1)


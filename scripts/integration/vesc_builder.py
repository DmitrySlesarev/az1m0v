"""VESC build and integration script.
Manages downloading, building, and integrating VESC (Vedder Electronic Speed Controller) into the project.
VESC is an open-source motor controller that can communicate via UART/Serial or CAN bus.
Python library: https://github.com/LiamBindle/PyVESC
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
    PIP = "pip"
    GIT = "git"


class VESCManager:
    """
    Manages downloading, building, and integrating VESC Python library into the project
    """
    
    # VESC Python library repository information
    VESC_REPO_URL = "https://github.com/LiamBindle/PyVESC/archive/refs/heads/master.zip"
    VESC_DIR_NAME = "PyVESC"
    VESC_PYTHON_PACKAGE = "pyvesc"
    
    def __init__(self, project_root: str = ".", build_system: BuildSystem = BuildSystem.PIP):
        self.project_root = Path(project_root).absolute()
        self.build_system = build_system
        self.vesc_dir = self.project_root / "scripts" / "integration" / self.VESC_DIR_NAME
        self.build_dir = self.vesc_dir / "build"
        
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
    
    def download_vesc(self, force_redownload: bool = False) -> bool:
        """
        Download VESC Python library from GitHub or install via pip
        Returns: True if successful, False otherwise
        """
        if self.build_system == BuildSystem.PIP:
            return self._install_via_pip(force_redownload)
        else:
            return self._download_from_github(force_redownload)
    
    def _install_via_pip(self, force_redownload: bool = False) -> bool:
        """Install VESC library via pip"""
        try:
            self.logger.info("Installing PyVESC via pip...")
            
            # Check if already installed
            if not force_redownload:
                try:
                    import pyvesc
                    self.logger.info("PyVESC already installed. Use force_redownload=True to reinstall.")
                    return True
                except ImportError:
                    pass
            
            # Install via pip
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "pyvesc"],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                self.logger.info("PyVESC installed successfully via pip")
                return True
            else:
                self.logger.warning(f"pip install failed, trying git clone: {result.stderr}")
                return self._install_from_git()
                
        except Exception as e:
            self.logger.error(f"Failed to install PyVESC via pip: {e}")
            return False
    
    def _install_from_git(self) -> bool:
        """Install VESC library from git repository"""
        try:
            self.logger.info("Installing PyVESC from git repository...")
            
            # Clone repository
            if self.vesc_dir.exists():
                shutil.rmtree(self.vesc_dir)
            
            result = subprocess.run(
                ["git", "clone", "https://github.com/LiamBindle/PyVESC.git", str(self.vesc_dir)],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                self.logger.error(f"Failed to clone repository: {result.stderr}")
                return False
            
            # Install in development mode
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-e", str(self.vesc_dir)],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                self.logger.info("PyVESC installed successfully from git")
                return True
            else:
                self.logger.error(f"Failed to install from git: {result.stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to install from git: {e}")
            return False
    
    def _download_from_github(self, force_redownload: bool = False) -> bool:
        """Download VESC from GitHub"""
        if self.vesc_dir.exists() and not force_redownload:
            self.logger.info("VESC already downloaded. Use force_redownload=True to re-download.")
            return True
        
        # Remove existing directory if force redownload
        if self.vesc_dir.exists() and force_redownload:
            shutil.rmtree(self.vesc_dir)
        
        try:
            self.logger.info("Downloading VESC from GitHub...")
            
            # Download the repository as ZIP
            zip_path = self.project_root / "pyvesc_master.zip"
            urllib.request.urlretrieve(self.VESC_REPO_URL, zip_path)
            
            # Extract ZIP file
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(self.vesc_dir.parent)
            
            # The extracted folder has a different name, rename it
            extracted_dir = self.vesc_dir.parent / "PyVESC-master"
            if extracted_dir.exists():
                extracted_dir.rename(self.vesc_dir)
            
            # Clean up ZIP file
            zip_path.unlink()
            
            self.logger.info("VESC downloaded successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to download VESC: {e}")
            return False
    
    def setup_dependencies(self) -> bool:
        """
        Install required dependencies for VESC
        Returns: True if successful, False otherwise
        """
        try:
            self.logger.info("Setting up VESC dependencies...")
            
            # PyVESC requires pyserial
            dependencies = ["pyserial"]
            
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
    
    def build_vesc(self) -> bool:
        """
        Build VESC Python library (mainly for verification)
        Returns: True if successful, False otherwise
        """
        try:
            self.logger.info("Verifying VESC installation...")
            
            # Try to import the module
            try:
                import pyvesc
                self.logger.info("VESC module verified successfully")
                return True
            except ImportError as e:
                self.logger.error(f"VESC module not available: {e}")
                return False
                
        except Exception as e:
            self.logger.error(f"Build verification failed: {e}")
            return False
    
    def get_status(self) -> Dict:
        """Get current VESC integration status"""
        vesc_available = False
        try:
            import pyvesc
            vesc_available = True
        except ImportError:
            pass
        
        return {
            "vesc_downloaded": self.vesc_dir.exists() or vesc_available,
            "vesc_available": vesc_available,
            "build_system": self.build_system.value,
            "project_root": str(self.project_root)
        }


def setup_vesc_in_project():
    """Example of how to integrate VESC into your EV project"""
    
    # Initialize the manager
    vesc_manager = VESCManager(
        project_root="../../..",  # Adjust based on your project structure
        build_system=BuildSystem.PIP  # Recommended for easy installation
    )
    
    # Check status
    status = vesc_manager.get_status()
    print("Initial Status:", status)
    
    # Download/Install VESC
    if not vesc_manager.download_vesc():
        print("Failed to download/install VESC")
        return False
    
    # Setup dependencies
    if not vesc_manager.setup_dependencies():
        print("Failed to setup dependencies")
        return False
    
    # Build/Verify the library
    if not vesc_manager.build_vesc():
        print("Failed to verify VESC installation")
        return False
    
    # Get final status
    status = vesc_manager.get_status()
    print("Final Status:", status)
    
    return True


if __name__ == "__main__":
    # Run the setup when this script is executed directly
    success = setup_vesc_in_project()
    sys.exit(0 if success else 1)


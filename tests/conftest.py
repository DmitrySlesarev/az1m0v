"""Shared pytest fixtures for all tests."""

import pytest
import sys
from pathlib import Path

# Add the project root to the Python path for all tests
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

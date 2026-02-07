"""helpers module for the EV project."""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Iterable, Optional

logger = logging.getLogger(__name__)


def clamp(value: float, minimum: float, maximum: float) -> float:
    """Clamp value between minimum and maximum."""
    return max(minimum, min(maximum, value))


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Divide numerator by denominator, return default on zero denominator."""
    if denominator == 0:
        return default
    return numerator / denominator


def moving_average(values: Iterable[float]) -> float:
    """Compute a simple moving average for a sequence."""
    values = list(values)
    if not values:
        return 0.0
    return sum(values) / len(values)


def ensure_dir(path: str | Path) -> Path:
    """Ensure directory exists and return Path."""
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def load_json(path: str | Path, default: Optional[Any] = None) -> Any:
    """Load JSON from a file, returning default on error."""
    try:
        with open(path, "r") as handle:
            return json.load(handle)
    except Exception as exc:
        logger.warning(f"Failed to load JSON from {path}: {exc}")
        return default


def save_json(path: str | Path, data: Any, indent: int = 2) -> bool:
    """Save JSON to a file. Returns True on success."""
    try:
        with open(path, "w") as handle:
            json.dump(data, handle, indent=indent, default=str)
        return True
    except Exception as exc:
        logger.error(f"Failed to save JSON to {path}: {exc}")
        return False


def now_timestamp() -> float:
    """Return current time in seconds."""
    return time.time()


def env_bool(name: str, default: bool = False) -> bool:
    """Parse boolean environment variables."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}

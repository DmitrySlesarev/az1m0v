#!/usr/bin/env bash
set -euo pipefail

echo "Setting up EV project environment..."

# Install dependencies via Poetry
if command -v poetry &> /dev/null; then
    echo "Installing dependencies with Poetry..."
    if [[ -r /proc/device-tree/model ]] && tr -d '\0' < /proc/device-tree/model | grep -qi raspberry; then
        echo "Raspberry Pi detected: main dependencies only (skips dev tools e.g. Playwright)."
        poetry install --only main --no-interaction
    else
        poetry install --no-interaction
    fi
else
    echo "Poetry not found. Please install Poetry first: https://python-poetry.org/docs/#installation"
    exit 1
fi

# Optional: Setup integration components
echo ""
echo "Optional: Setup integration components"
echo "Run the following scripts in scripts/integration/ if needed:"
echo "  - vesc_builder.py (for VESC motor controller)"
echo "  - simpbms_builder.py (for SimpBMS)"
echo "  - quectel_builder.py (for Quectel telemetry)"
echo "  - mpu_builder.py (for MPU-6050/MPU-9250 IMU sensors)"

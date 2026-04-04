#!/usr/bin/env bash
set -euo pipefail

echo "Setting up EV project environment..."

# True on typical Raspberry Pi / constrained ARM boards (skip dev + optional groups).
_use_minimal_poetry_install() {
    if [[ "${AZ1M0V_POETRY_ONLY_MAIN:-}" == "1" ]]; then
        return 0
    fi
    case "$(uname -m)" in
        armv7l) return 0 ;;
    esac
    if [[ -r /proc/device-tree/model ]] && tr -d '\0' < /proc/device-tree/model | grep -qi raspberry; then
        return 0
    fi
    if [[ -r /proc/device-tree/compatible ]]; then
        local compat
        compat=$(tr -d '\0' < /proc/device-tree/compatible)
        if echo "$compat" | grep -qiE 'raspberrypi|raspberry,'; then
            return 0
        fi
    fi
    return 1
}

# Install dependencies via Poetry
if command -v poetry &> /dev/null; then
    PY_BIN=""
    if command -v python3 &> /dev/null; then
        PY_BIN="$(command -v python3)"
    elif command -v python &> /dev/null; then
        PY_BIN="$(command -v python)"
    fi
    if [[ -n "$PY_BIN" ]]; then
        echo "Using interpreter for Poetry venv: $PY_BIN"
        echo "Tip: with pyenv use a version alias (e.g. poetry env use \"\$(pyenv which python)\"), not python3.11.11."
        poetry env use "$PY_BIN"
    fi

    echo "Installing dependencies with Poetry..."
    if _use_minimal_poetry_install; then
        echo "ARM / Raspberry-style environment: installing main dependencies only (no dev, no Playwright, no Alpamayo extra)."
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

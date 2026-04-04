# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-04-04

### Added

- First **major** release of az1m0v as an integrated EV management stack: BMS, motor (VESC), charging, vehicle controller, safety, diagnostics (DTC / limp-home), CAN, telemetry, sensors, autopilot hooks, and web dashboard.
- Raspberry Pi–oriented setup documented in the root `README` (`scripts/setup.sh`, minimal Poetry install, Python 3.11–3.13).
- Optional Poetry extras: `alpamayo` (Python ≥ 3.12) and optional `playwright` group for browser-based UI tests.
- Project `.gitignore` for bytecode, virtualenvs, and common test/build artifacts.

### Notes

- PyPI package publication is not implied; version **1.0.0** marks the first stable tagging of the application and documentation set in this repository. Publish Git tag `v1.0.0` when you cut the release on GitHub.

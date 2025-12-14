"""Battery Management System (BMS) module for the EV project.
Manages battery state, health monitoring, and CAN bus communication.
Compatible with SimpBMS and other open-source BMS systems via CAN bus.
"""

import logging
from typing import Dict, Optional, List
from dataclasses import dataclass, field
from enum import Enum
import time


class BatteryStatus(Enum):
    """Battery system status states."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    CHARGING = "charging"
    DISCHARGING = "discharging"
    FAULT = "fault"
    STANDBY = "standby"


@dataclass
class BatteryState:
    """Current battery state information."""
    voltage: float  # Total pack voltage in V
    current: float  # Current in A (positive = charging, negative = discharging)
    temperature: float  # Average temperature in °C
    soc: float  # State of charge (0-100%)
    soh: float  # State of health (0-100%)
    cell_count: int
    cell_voltages: List[float]  # Individual cell voltages
    cell_temperatures: List[float]  # Individual cell temperatures
    status: BatteryStatus
    timestamp: float
    cell_group_temperatures: List[float] = field(default_factory=list)  # Temperatures per cell group
    coolant_inlet_temperature: Optional[float] = None  # Coolant inlet temperature in °C
    coolant_outlet_temperature: Optional[float] = None  # Coolant outlet temperature in °C


@dataclass
class BatteryConfig:
    """Battery configuration parameters."""
    capacity_kwh: float
    max_charge_rate_kw: float
    max_discharge_rate_kw: float
    nominal_voltage: float
    cell_count: int
    min_voltage: float = 3.0  # Minimum cell voltage in V
    max_voltage: float = 4.2  # Maximum cell voltage in V
    min_temperature: float = 0.0  # Minimum operating temperature in °C
    max_temperature: float = 45.0  # Maximum operating temperature in °C
    max_soc: float = 100.0  # Maximum SOC percentage
    min_soc: float = 0.0  # Minimum SOC percentage


class BatteryManagementSystem:
    """Battery Management System for EV applications."""

    def __init__(self, config: Dict, can_protocol: Optional[object] = None, temperature_sensor_manager: Optional[object] = None):
        """Initialize the Battery Management System.
        
        Args:
            config: Battery configuration dictionary
            can_protocol: Optional EVCANProtocol instance for CAN bus communication
            temperature_sensor_manager: Optional TemperatureSensorManager instance for temperature readings
        """
        self.config = BatteryConfig(
            capacity_kwh=config.get('capacity_kwh', 75.0),
            max_charge_rate_kw=config.get('max_charge_rate_kw', 150.0),
            max_discharge_rate_kw=config.get('max_discharge_rate_kw', 200.0),
            nominal_voltage=config.get('nominal_voltage', 400.0),
            cell_count=config.get('cell_count', 96),
            min_voltage=config.get('min_voltage', 3.0),
            max_voltage=config.get('max_voltage', 4.2),
            min_temperature=config.get('min_temperature', 0.0),
            max_temperature=config.get('max_temperature', 45.0),
        )

        self.can_protocol = can_protocol
        self.temperature_sensor_manager = temperature_sensor_manager
        self.logger = logging.getLogger(__name__)

        # Initialize battery state
        self.state = BatteryState(
            voltage=self.config.nominal_voltage,
            current=0.0,
            temperature=25.0,
            soc=50.0,
            soh=100.0,
            cell_count=self.config.cell_count,
            cell_voltages=[self.config.nominal_voltage / self.config.cell_count] * self.config.cell_count,
            cell_temperatures=[25.0] * self.config.cell_count,
            status=BatteryStatus.STANDBY,
            timestamp=time.time(),
            cell_group_temperatures=[],
            coolant_inlet_temperature=None,
            coolant_outlet_temperature=None
        )

        # Statistics
        self.stats = {
            'total_energy_charged_kwh': 0.0,
            'total_energy_discharged_kwh': 0.0,
            'charge_cycles': 0,
            'fault_count': 0,
            'last_update': time.time()
        }

        self.logger.info(f"BMS initialized: {self.config.capacity_kwh}kWh, {self.config.cell_count} cells")

    def update_state(self, voltage: Optional[float] = None,
                     current: Optional[float] = None,
                     temperature: Optional[float] = None,
                     cell_voltages: Optional[List[float]] = None,
                     cell_temperatures: Optional[List[float]] = None) -> None:
        """Update battery state from sensor readings or BMS hardware.
        
        Args:
            voltage: Pack voltage in V
            current: Pack current in A
            temperature: Average temperature in °C
            cell_voltages: List of individual cell voltages
            cell_temperatures: List of individual cell temperatures
        """
        current_time = time.time()
        dt = current_time - self.state.timestamp

        # Update voltage
        if voltage is not None:
            self.state.voltage = voltage
        elif cell_voltages is not None:
            self.state.voltage = sum(cell_voltages)
            self.state.cell_voltages = cell_voltages

        # Update current
        if current is not None:
            self.state.current = current

        # Update temperature from temperature sensor manager if available
        if self.temperature_sensor_manager:
            # Get cell group temperatures
            cell_group_temps = self.temperature_sensor_manager.get_battery_cell_temperatures()
            if cell_group_temps:
                self.state.cell_group_temperatures = cell_group_temps
                # Map cell group temperatures to individual cells (if needed)
                if cell_temperatures is None:
                    # Distribute group temperatures to cells
                    cells_per_group = max(1, self.config.cell_count // len(cell_group_temps))
                    cell_temps = []
                    for group_temp in cell_group_temps:
                        cell_temps.extend([group_temp] * cells_per_group)
                    # Trim to exact cell count
                    cell_temps = cell_temps[:self.config.cell_count]
                    self.state.cell_temperatures = cell_temps
                    self.state.temperature = sum(cell_temps) / len(cell_temps) if cell_temps else 25.0

            # Get coolant temperatures
            coolant_temps = self.temperature_sensor_manager.get_coolant_temperatures()
            if 'inlet' in coolant_temps:
                self.state.coolant_inlet_temperature = coolant_temps['inlet']
            if 'outlet' in coolant_temps:
                self.state.coolant_outlet_temperature = coolant_temps['outlet']

        # Update temperature from direct parameters (fallback)
        if temperature is not None:
            self.state.temperature = temperature
        elif cell_temperatures is not None:
            self.state.cell_temperatures = cell_temperatures
            self.state.temperature = sum(cell_temperatures) / len(cell_temperatures)

        # Calculate SOC from voltage (simplified coulomb counting)
        if dt > 0 and self.state.current != 0:
            # Integrate current over time
            energy_change_wh = (self.state.current * self.state.voltage * dt) / 3600.0
            energy_change_kwh = energy_change_wh / 1000.0

            if self.state.current > 0:  # Charging
                self.stats['total_energy_charged_kwh'] += abs(energy_change_kwh)
            else:  # Discharging
                self.stats['total_energy_discharged_kwh'] += abs(energy_change_kwh)

            # Update SOC
            soc_change = (energy_change_kwh / self.config.capacity_kwh) * 100.0
            self.state.soc = max(self.config.min_soc,
                                min(self.config.max_soc, self.state.soc + soc_change))

        # Update SOC from voltage if no current measurement (fallback)
        if self.state.current == 0 and self.state.voltage > 0:
            # Simple voltage-based SOC estimation
            cell_voltage = self.state.voltage / self.config.cell_count
            voltage_ratio = (cell_voltage - self.config.min_voltage) / \
                           (self.config.max_voltage - self.config.min_voltage)
            self.state.soc = max(0, min(100, voltage_ratio * 100))

        # Determine status
        self.state.status = self._determine_status()

        # Update timestamp
        self.state.timestamp = current_time
        self.stats['last_update'] = current_time

        # Send status to CAN bus if available
        if self.can_protocol:
            self._send_can_status()

    def _determine_status(self) -> BatteryStatus:
        """Determine battery status based on current state."""
        # Check for pack-level critical conditions (SOC extremes)
        if (self.state.soc < 5.0 or self.state.soc > 95.0):
            return BatteryStatus.CRITICAL

        # Check for pack-level temperature critical conditions
        pack_temp_critical = (self.state.temperature > self.config.max_temperature or
                             self.state.temperature < self.config.min_temperature)

        # Check for voltage faults first (voltage faults are always FAULT, not CRITICAL)
        if self.state.cell_voltages:
            max_cell_voltage = max(self.state.cell_voltages)
            min_cell_voltage = min(self.state.cell_voltages)
            voltage_imbalance = max_cell_voltage - min_cell_voltage

            if voltage_imbalance > 0.5:
                return BatteryStatus.FAULT

            for cell_voltage in self.state.cell_voltages:
                if cell_voltage > self.config.max_voltage or cell_voltage < self.config.min_voltage:
                    return BatteryStatus.FAULT

        # For temperature: distinguish between uniform pack-level issues (CRITICAL)
        # and individual cell issues (FAULT)
        if pack_temp_critical:
            if self.state.cell_temperatures and len(self.state.cell_temperatures) > 0:
                # Check if all cells are uniformly out of range (same temperature, small spread)
                temp_spread = max(self.state.cell_temperatures) - min(self.state.cell_temperatures)
                all_cells_out_of_range = all(
                    t > self.config.max_temperature or t < self.config.min_temperature
                    for t in self.state.cell_temperatures
                )

                # If all cells are uniformly out of range with small spread, it's a pack-level CRITICAL issue
                if all_cells_out_of_range and temp_spread <= 1.0:
                    return BatteryStatus.CRITICAL

                # Check if only some cells are out of range (individual cell issue = FAULT)
                cells_out_of_range = [t for t in self.state.cell_temperatures
                                     if t > self.config.max_temperature or t < self.config.min_temperature]
                cells_in_range = [t for t in self.state.cell_temperatures
                                if self.config.min_temperature <= t <= self.config.max_temperature]

                # If some cells are out of range and some are in range, it's a FAULT (individual cell issue)
                if len(cells_out_of_range) > 0 and len(cells_in_range) > 0:
                    return BatteryStatus.FAULT
            else:
                # No cell temperature data, but pack temp is critical = CRITICAL
                return BatteryStatus.CRITICAL

        # Check for individual cell temperature faults when pack temp is not critical
        if not pack_temp_critical and self.state.cell_temperatures:
            cells_out_of_range = [t for t in self.state.cell_temperatures
                                 if t > self.config.max_temperature or t < self.config.min_temperature]
            if len(cells_out_of_range) > 0:
                return BatteryStatus.FAULT

        # Check warning conditions
        if (self.state.temperature > self.config.max_temperature * 0.9 or
            self.state.temperature < self.config.min_temperature * 1.1 or
            self.state.soc < 10.0 or
            self.state.soc > 90.0):
            return BatteryStatus.WARNING

        # Check charging/discharging
        if self.state.current > 0.1:
            return BatteryStatus.CHARGING
        elif self.state.current < -0.1:
            return BatteryStatus.DISCHARGING

        return BatteryStatus.HEALTHY

    def _check_faults(self) -> bool:
        """Check for battery faults."""
        # Check cell voltage balance
        if self.state.cell_voltages:
            max_cell_voltage = max(self.state.cell_voltages)
            min_cell_voltage = min(self.state.cell_voltages)
            voltage_imbalance = max_cell_voltage - min_cell_voltage

            if voltage_imbalance > 0.5:  # 500mV imbalance threshold
                self.logger.warning(f"Cell voltage imbalance detected: {voltage_imbalance:.3f}V")
                self.stats['fault_count'] += 1
                return True

            # Check for overvoltage/undervoltage
            for i, cell_voltage in enumerate(self.state.cell_voltages):
                if cell_voltage > self.config.max_voltage:
                    self.logger.error(f"Cell {i} overvoltage: {cell_voltage:.3f}V")
                    self.stats['fault_count'] += 1
                    return True
                if cell_voltage < self.config.min_voltage:
                    self.logger.error(f"Cell {i} undervoltage: {cell_voltage:.3f}V")
                    self.stats['fault_count'] += 1
                    return True

        # Check temperature range
        if self.state.cell_temperatures:
            for i, cell_temp in enumerate(self.state.cell_temperatures):
                if cell_temp > self.config.max_temperature:
                    self.logger.error(f"Cell {i} overtemperature: {cell_temp:.2f}°C")
                    self.stats['fault_count'] += 1
                    return True
                if cell_temp < self.config.min_temperature:
                    self.logger.error(f"Cell {i} undertemperature: {cell_temp:.2f}°C")
                    self.stats['fault_count'] += 1
                    return True

        return False

    def _send_can_status(self) -> None:
        """Send battery status to CAN bus."""
        if self.can_protocol and hasattr(self.can_protocol, 'send_battery_status'):
            try:
                self.can_protocol.send_battery_status(
                    voltage=self.state.voltage,
                    current=self.state.current,
                    temperature=self.state.temperature,
                    soc=self.state.soc
                )
                # Send cell group temperatures if available
                if self.state.cell_group_temperatures and hasattr(self.can_protocol, 'send_temperature_data'):
                    for i, temp in enumerate(self.state.cell_group_temperatures):
                        self.can_protocol.send_temperature_data(
                            sensor_type='battery_cell_group',
                            sensor_id=f'cell_group_{i+1}',
                            temperature=temp
                        )
                # Send coolant temperatures if available
                if self.state.coolant_inlet_temperature is not None and hasattr(self.can_protocol, 'send_temperature_data'):
                    self.can_protocol.send_temperature_data(
                        sensor_type='coolant_inlet',
                        sensor_id='coolant_inlet',
                        temperature=self.state.coolant_inlet_temperature
                    )
                if self.state.coolant_outlet_temperature is not None and hasattr(self.can_protocol, 'send_temperature_data'):
                    self.can_protocol.send_temperature_data(
                        sensor_type='coolant_outlet',
                        sensor_id='coolant_outlet',
                        temperature=self.state.coolant_outlet_temperature
                    )
            except Exception as e:
                self.logger.error(f"Failed to send CAN status: {e}")

    def get_state(self) -> BatteryState:
        """Get current battery state."""
        return self.state

    def get_config(self) -> BatteryConfig:
        """Get battery configuration."""
        return self.config

    def get_statistics(self) -> Dict:
        """Get battery statistics."""
        return {
            **self.stats,
            'current_soc': self.state.soc,
            'current_soh': self.state.soh,
            'status': self.state.status.value,
            'voltage': self.state.voltage,
            'current': self.state.current,
            'temperature': self.state.temperature
        }

    def get_health_status(self) -> Dict:
        """Get battery health status."""
        return {
            'soh': self.state.soh,
            'soc': self.state.soc,
            'status': self.state.status.value,
            'fault_count': self.stats['fault_count'],
            'charge_cycles': self.stats['charge_cycles'],
            'temperature': self.state.temperature,
            'voltage_range': {
                'min': min(self.state.cell_voltages) if self.state.cell_voltages else 0,
                'max': max(self.state.cell_voltages) if self.state.cell_voltages else 0,
                'average': self.state.voltage / self.config.cell_count if self.config.cell_count > 0 else 0
            }
        }

    def can_charge(self, requested_power_kw: float) -> bool:
        """Check if battery can accept charge at requested power.
        
        Args:
            requested_power_kw: Requested charging power in kW
            
        Returns:
            True if charging is allowed, False otherwise
        """
        if self.state.status in [BatteryStatus.FAULT, BatteryStatus.CRITICAL]:
            return False

        if requested_power_kw > self.config.max_charge_rate_kw:
            return False

        if self.state.soc >= self.config.max_soc:
            return False

        return True

    def can_discharge(self, requested_power_kw: float) -> bool:
        """Check if battery can provide discharge at requested power.
        
        Args:
            requested_power_kw: Requested discharge power in kW
            
        Returns:
            True if discharge is allowed, False otherwise
        """
        if self.state.status in [BatteryStatus.FAULT, BatteryStatus.CRITICAL]:
            return False

        if requested_power_kw > self.config.max_discharge_rate_kw:
            return False

        if self.state.soc <= self.config.min_soc:
            return False

        return True

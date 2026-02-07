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


class BalancingAlgorithm(Enum):
    """Cell balancing algorithm types."""
    NONE = "none"  # No balancing
    PASSIVE = "passive"  # Dissipative balancing (bleed resistors)
    ACTIVE = "active"  # Redistributive balancing (energy transfer)
    ADAPTIVE = "adaptive"  # Automatically selects passive or active based on conditions


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
    balancing_active: bool = False  # Whether cell balancing is currently active
    cells_balancing: List[int] = field(default_factory=list)  # List of cell indices currently being balanced


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
    # Balancing configuration
    balancing_enabled: bool = True  # Enable cell balancing
    balancing_algorithm: str = "adaptive"  # Balancing algorithm: "none", "passive", "active", "adaptive"
    balancing_threshold_mv: float = 50.0  # Voltage difference threshold to start balancing (mV)
    passive_bleed_current_ma: float = 100.0  # Passive balancing bleed current (mA)
    active_balance_efficiency: float = 0.85  # Active balancing efficiency (0-1)
    balancing_min_soc: float = 20.0  # Minimum SOC to allow balancing (%)
    balancing_max_soc: float = 95.0  # Maximum SOC to allow balancing (%)


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
            balancing_enabled=config.get('balancing_enabled', True),
            balancing_algorithm=config.get('balancing_algorithm', 'adaptive'),
            balancing_threshold_mv=config.get('balancing_threshold_mv', 50.0),
            passive_bleed_current_ma=config.get('passive_bleed_current_ma', 100.0),
            active_balance_efficiency=config.get('active_balance_efficiency', 0.85),
            balancing_min_soc=config.get('balancing_min_soc', 20.0),
            balancing_max_soc=config.get('balancing_max_soc', 95.0),
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
            coolant_outlet_temperature=None,
            balancing_active=False,
            cells_balancing=[]
        )

        # Statistics
        self.stats = {
            'total_energy_charged_kwh': 0.0,
            'total_energy_discharged_kwh': 0.0,
            'charge_cycles': 0,
            'fault_count': 0,
            'last_update': time.time(),
            'balancing_events': 0,
            'total_balancing_time_s': 0.0,
            'last_balancing_time': None
        }

        # SOH calculation tracking
        self._initial_capacity_kwh = self.config.capacity_kwh
        self._last_soc_for_cycle_detection = self.state.soc
        self._cycle_energy_charged_wh = 0.0  # Energy charged in current cycle
        self._cycle_energy_discharged_wh = 0.0  # Energy discharged in current cycle
        self._temperature_history: List[tuple] = []  # List of (timestamp, temperature) tuples
        self._max_temperature_history_duration = 86400.0 * 30  # 30 days in seconds
        self._high_temperature_threshold = 40.0  # °C - temperatures above this accelerate degradation
        self._initialization_time = time.time()

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
                self._cycle_energy_charged_wh += abs(energy_change_wh)
            else:  # Discharging
                self.stats['total_energy_discharged_kwh'] += abs(energy_change_kwh)
                self._cycle_energy_discharged_wh += abs(energy_change_wh)

            # Update SOC
            soc_change = (energy_change_kwh / self.config.capacity_kwh) * 100.0
            self.state.soc = max(self.config.min_soc,
                                min(self.config.max_soc, self.state.soc + soc_change))

            # Detect charge cycles (full charge-discharge cycle)
            self._detect_charge_cycle()

        # Update SOC from voltage if no current measurement (fallback)
        if self.state.current == 0 and self.state.voltage > 0:
            # Simple voltage-based SOC estimation
            cell_voltage = self.state.voltage / self.config.cell_count
            voltage_ratio = (cell_voltage - self.config.min_voltage) / \
                           (self.config.max_voltage - self.config.min_voltage)
            self.state.soc = max(0, min(100, voltage_ratio * 100))

        # Update temperature history for SOH calculation
        self._update_temperature_history(current_time)

        # Calculate SOH
        self.state.soh = self._calculate_soh()

        # Perform cell balancing if enabled
        was_balancing = self.state.balancing_active
        if self.config.balancing_enabled and self.state.cell_voltages:
            self._perform_balancing(dt)
        
        # Track balancing duration when balancing stops
        if was_balancing and not self.state.balancing_active:
            if self.stats.get('last_balancing_time'):
                balancing_duration = current_time - self.stats['last_balancing_time']
                self.stats['total_balancing_time_s'] += balancing_duration
                self.stats['last_balancing_time'] = None

        # Determine status
        self.state.status = self._determine_status()

        # Update timestamp
        self.state.timestamp = current_time
        self.stats['last_update'] = current_time

        # Send status to CAN bus if available
        if self.can_protocol:
            self._send_can_status()

    def _detect_charge_cycle(self) -> None:
        """Detect when a full charge-discharge cycle is completed.
        
        A cycle is considered complete when:
        - Battery goes from low SOC (<20%) to high SOC (>80%) and back, OR
        - Total energy charged + discharged in current cycle >= 80% of nominal capacity
        """
        current_soc = self.state.soc
        previous_soc = self._last_soc_for_cycle_detection
        
        # Check for cycle completion based on SOC swing
        # Cycle: low -> high -> low (or high -> low -> high)
        cycle_threshold_high = 80.0
        cycle_threshold_low = 20.0
        
        # Detect cycle completion: went from low to high and back to low, or vice versa
        if (previous_soc < cycle_threshold_low and current_soc > cycle_threshold_high) or \
           (previous_soc > cycle_threshold_high and current_soc < cycle_threshold_low):
            # Check if we've completed a full cycle (charged and discharged)
            total_cycle_energy_kwh = (self._cycle_energy_charged_wh + self._cycle_energy_discharged_wh) / 1000.0
            if total_cycle_energy_kwh >= self.config.capacity_kwh * 0.8:  # 80% of capacity
                self.stats['charge_cycles'] += 1
                self._cycle_energy_charged_wh = 0.0
                self._cycle_energy_discharged_wh = 0.0
                self.logger.info(f"Charge cycle detected. Total cycles: {self.stats['charge_cycles']}")
        
        # Alternative: cycle based on energy throughput
        total_cycle_energy_kwh = (self._cycle_energy_charged_wh + self._cycle_energy_discharged_wh) / 1000.0
        if total_cycle_energy_kwh >= self.config.capacity_kwh * 1.6:  # Full charge + full discharge
            self.stats['charge_cycles'] += 1
            self._cycle_energy_charged_wh = 0.0
            self._cycle_energy_discharged_wh = 0.0
            self.logger.info(f"Charge cycle detected (energy-based). Total cycles: {self.stats['charge_cycles']}")
        
        self._last_soc_for_cycle_detection = current_soc

    def _update_temperature_history(self, current_time: float) -> None:
        """Update temperature history for SOH calculation.
        
        Args:
            current_time: Current timestamp
        """
        # Add current temperature to history
        self._temperature_history.append((current_time, self.state.temperature))
        
        # Remove old entries (older than max history duration)
        cutoff_time = current_time - self._max_temperature_history_duration
        self._temperature_history = [(t, temp) for t, temp in self._temperature_history if t >= cutoff_time]

    def _calculate_soh(self) -> float:
        """Calculate State of Health (SOH) based on multiple factors.
        
        SOH is calculated using:
        1. Cycle-based degradation (0.05% per cycle typical for Li-ion)
        2. Temperature-based degradation (time spent at high temperatures)
        3. Fault-based degradation (each fault reduces SOH)
        4. Age-based degradation (calendar aging)
        
        Returns:
            SOH percentage (0-100%)
        """
        base_soh = 100.0
        
        # 1. Cycle-based degradation
        # Typical Li-ion batteries lose ~0.05% capacity per cycle
        # This can vary: 0.03-0.1% depending on depth of discharge and usage
        cycle_degradation = self.stats['charge_cycles'] * 0.05
        base_soh -= cycle_degradation
        
        # 2. Temperature-based degradation
        # High temperatures accelerate degradation
        # Calculate time-weighted average of time spent above threshold
        if self._temperature_history:
            high_temp_time = 0.0
            total_time = 0.0
            previous_time = self._temperature_history[0][0] if self._temperature_history else self._initialization_time
            
            for timestamp, temp in self._temperature_history:
                if previous_time < timestamp:
                    time_interval = timestamp - previous_time
                    total_time += time_interval
                    if temp > self._high_temperature_threshold:
                        high_temp_time += time_interval
                    previous_time = timestamp
            
            if total_time > 0:
                high_temp_ratio = high_temp_time / total_time
                # Degradation: 0.1% per day spent above threshold (scaled)
                # Convert to degradation per hour: 0.1 / 24 = 0.00417% per hour
                hours_at_high_temp = high_temp_time / 3600.0
                temp_degradation = hours_at_high_temp * 0.00417
                base_soh -= temp_degradation
        
        # 3. Fault-based degradation
        # Each fault indicates stress and reduces SOH
        # Assume 0.1% degradation per fault
        fault_degradation = self.stats['fault_count'] * 0.1
        base_soh -= fault_degradation
        
        # 4. Age-based degradation (calendar aging)
        # Li-ion batteries degrade over time even without use
        # Typical: ~2-3% per year at 25°C, accelerated at higher temperatures
        age_years = (time.time() - self._initialization_time) / (365.25 * 24 * 3600)
        # Base calendar aging: 2.5% per year
        # Adjust for average temperature (higher temp = faster aging)
        avg_temp = self.state.temperature
        temp_factor = 1.0 + max(0, (avg_temp - 25.0) / 10.0) * 0.5  # 50% increase per 10°C above 25°C
        calendar_degradation = age_years * 2.5 * temp_factor
        base_soh -= calendar_degradation
        
        # 5. Capacity-based SOH (if we have capacity measurements)
        # This would require actual capacity testing, but we can estimate
        # based on energy throughput vs SOC changes
        # For now, we rely on the other factors
        
        # Ensure SOH stays within valid range
        soh = max(0.0, min(100.0, base_soh))
        
        return soh

    def _perform_balancing(self, dt: float) -> None:
        """Perform cell balancing based on configured algorithm.
        
        Args:
            dt: Time delta since last update in seconds
        """
        if not self.state.cell_voltages or len(self.state.cell_voltages) < 2:
            return

        # Check if balancing should be active based on SOC
        if self.state.soc < self.config.balancing_min_soc or self.state.soc > self.config.balancing_max_soc:
            self.state.balancing_active = False
            self.state.cells_balancing = []
            return

        # Calculate voltage imbalance
        max_voltage = max(self.state.cell_voltages)
        min_voltage = min(self.state.cell_voltages)
        voltage_imbalance_mv = (max_voltage - min_voltage) * 1000.0  # Convert to mV

        # Check if imbalance exceeds threshold
        if voltage_imbalance_mv < self.config.balancing_threshold_mv:
            self.state.balancing_active = False
            self.state.cells_balancing = []
            return

        # Select balancing algorithm
        algorithm = BalancingAlgorithm(self.config.balancing_algorithm)
        
        if algorithm == BalancingAlgorithm.ADAPTIVE:
            # Adaptive: use active balancing for large imbalances, passive for small
            if voltage_imbalance_mv > 200.0:  # >200mV use active
                algorithm = BalancingAlgorithm.ACTIVE
            else:
                algorithm = BalancingAlgorithm.PASSIVE

        # Perform balancing
        if algorithm == BalancingAlgorithm.PASSIVE:
            self._passive_balancing(dt, voltage_imbalance_mv)
        elif algorithm == BalancingAlgorithm.ACTIVE:
            self._active_balancing(dt, voltage_imbalance_mv)
        else:
            self.state.balancing_active = False
            self.state.cells_balancing = []

    def _passive_balancing(self, dt: float, voltage_imbalance_mv: float) -> None:
        """Perform passive (dissipative) cell balancing.
        
        Passive balancing bleeds current from high-voltage cells using resistors.
        This is simpler and cheaper but wastes energy as heat.
        
        Args:
            dt: Time delta since last update in seconds
            voltage_imbalance_mv: Voltage imbalance in millivolts
        """
        if not self.state.cell_voltages:
            return

        # Calculate average cell voltage
        avg_voltage = sum(self.state.cell_voltages) / len(self.state.cell_voltages)
        threshold_voltage = avg_voltage + (self.config.balancing_threshold_mv / 1000.0)

        # Find cells that need balancing (above threshold)
        cells_to_balance = []
        for i, cell_voltage in enumerate(self.state.cell_voltages):
            if cell_voltage > threshold_voltage:
                cells_to_balance.append(i)

        if not cells_to_balance:
            self.state.balancing_active = False
            self.state.cells_balancing = []
            return

        # Update balancing state
        self.state.balancing_active = True
        self.state.cells_balancing = cells_to_balance

        # Simulate passive balancing by reducing voltage of high cells
        # In real hardware, this would be done by switching on bleed resistors
        bleed_current_a = self.config.passive_bleed_current_ma / 1000.0  # Convert mA to A
        
        # Estimate cell capacity (simplified - assumes all cells have same capacity)
        cell_capacity_ah = (self.config.capacity_kwh * 1000.0) / (self.config.nominal_voltage * 3600.0) / self.config.cell_count
        
        # Calculate voltage drop from bleeding
        # Simplified: Q = I * t, voltage drop depends on cell characteristics
        # For Li-ion: approximately 0.01V per 1% SOC change
        energy_bleed_wh = (bleed_current_a * avg_voltage * dt) / 3600.0
        soc_drop = (energy_bleed_wh / (cell_capacity_ah * avg_voltage / 100.0)) * 100.0
        
        # Apply balancing to high cells
        for cell_idx in cells_to_balance:
            # Reduce voltage proportionally (simplified model)
            voltage_drop = (soc_drop / 100.0) * (self.config.max_voltage - self.config.min_voltage) * 0.01
            self.state.cell_voltages[cell_idx] = max(
                avg_voltage,
                self.state.cell_voltages[cell_idx] - voltage_drop
            )

        # Update statistics
        if not self.stats.get('last_balancing_time'):
            self.stats['last_balancing_time'] = time.time()
            self.stats['balancing_events'] += 1

        # Recalculate pack voltage
        self.state.voltage = sum(self.state.cell_voltages)

    def _active_balancing(self, dt: float, voltage_imbalance_mv: float) -> None:
        """Perform active (redistributive) cell balancing.
        
        Active balancing transfers energy from high-voltage cells to low-voltage cells.
        More efficient than passive but requires additional hardware (capacitors/inductors).
        
        Args:
            dt: Time delta since last update in seconds
            voltage_imbalance_mv: Voltage imbalance in millivolts
        """
        if not self.state.cell_voltages or len(self.state.cell_voltages) < 2:
            return

        # Find highest and lowest voltage cells
        max_voltage = max(self.state.cell_voltages)
        min_voltage = min(self.state.cell_voltages)
        max_idx = self.state.cell_voltages.index(max_voltage)
        min_idx = self.state.cell_voltages.index(min_voltage)

        # Calculate average voltage
        avg_voltage = sum(self.state.cell_voltages) / len(self.state.cell_voltages)

        # Determine cells to balance
        # High cells: above average + threshold
        # Low cells: below average - threshold
        threshold = self.config.balancing_threshold_mv / 1000.0
        high_cells = [i for i, v in enumerate(self.state.cell_voltages) if v > avg_voltage + threshold]
        low_cells = [i for i, v in enumerate(self.state.cell_voltages) if v < avg_voltage - threshold]

        if not high_cells or not low_cells:
            self.state.balancing_active = False
            self.state.cells_balancing = []
            return

        # Update balancing state
        self.state.balancing_active = True
        self.state.cells_balancing = high_cells + low_cells

        # Simulate active balancing by transferring energy
        # In real hardware, this would use switched capacitors or inductors
        
        # Calculate energy to transfer (from highest to lowest)
        energy_transfer_ratio = min(0.1, dt * 0.5)  # Limit transfer rate
        voltage_diff = max_voltage - min_voltage
        
        # Estimate cell capacity
        cell_capacity_ah = (self.config.capacity_kwh * 1000.0) / (self.config.nominal_voltage * 3600.0) / self.config.cell_count
        
        # Calculate energy transfer (with efficiency loss)
        energy_transfer_wh = (voltage_diff * cell_capacity_ah * energy_transfer_ratio * self.config.active_balance_efficiency) / 100.0
        
        # Apply balancing: reduce high cells, increase low cells
        voltage_change_high = (energy_transfer_wh / (cell_capacity_ah * max_voltage / 100.0)) * (self.config.max_voltage - self.config.min_voltage) * 0.01
        voltage_change_low = (energy_transfer_wh / (cell_capacity_ah * min_voltage / 100.0)) * (self.config.max_voltage - self.config.min_voltage) * 0.01
        
        # Balance highest cell
        self.state.cell_voltages[max_idx] = max(
            avg_voltage,
            self.state.cell_voltages[max_idx] - voltage_change_high
        )
        
        # Balance lowest cell
        self.state.cell_voltages[min_idx] = min(
            avg_voltage,
            self.state.cell_voltages[min_idx] + voltage_change_low
        )
        
        # Balance other high cells proportionally
        for cell_idx in high_cells:
            if cell_idx != max_idx:
                excess_voltage = self.state.cell_voltages[cell_idx] - avg_voltage
                if excess_voltage > threshold:
                    self.state.cell_voltages[cell_idx] -= voltage_change_high * (excess_voltage / voltage_diff)
        
        # Balance other low cells proportionally
        for cell_idx in low_cells:
            if cell_idx != min_idx:
                deficit_voltage = avg_voltage - self.state.cell_voltages[cell_idx]
                if deficit_voltage > threshold:
                    self.state.cell_voltages[cell_idx] += voltage_change_low * (deficit_voltage / voltage_diff)

        # Update statistics
        if not self.stats.get('last_balancing_time'):
            self.stats['last_balancing_time'] = time.time()
            self.stats['balancing_events'] += 1

        # Recalculate pack voltage
        self.state.voltage = sum(self.state.cell_voltages)

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
        # Calculate current balancing duration if active
        balancing_duration = 0.0
        if self.state.balancing_active and self.stats.get('last_balancing_time'):
            balancing_duration = time.time() - self.stats['last_balancing_time']
        
        return {
            **self.stats,
            'current_soc': self.state.soc,
            'current_soh': self.state.soh,
            'status': self.state.status.value,
            'voltage': self.state.voltage,
            'current': self.state.current,
            'temperature': self.state.temperature,
            'balancing_active': self.state.balancing_active,
            'cells_balancing': self.state.cells_balancing,
            'current_balancing_duration_s': balancing_duration
        }

    def get_health_status(self) -> Dict:
        """Get battery health status."""
        # Calculate voltage imbalance
        voltage_imbalance_mv = 0.0
        if self.state.cell_voltages and len(self.state.cell_voltages) > 1:
            max_voltage = max(self.state.cell_voltages)
            min_voltage = min(self.state.cell_voltages)
            voltage_imbalance_mv = (max_voltage - min_voltage) * 1000.0
        
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
            },
            'balancing': {
                'active': self.state.balancing_active,
                'algorithm': self.config.balancing_algorithm,
                'cells_balancing': self.state.cells_balancing,
                'voltage_imbalance_mv': voltage_imbalance_mv,
                'balancing_events': self.stats.get('balancing_events', 0),
                'total_balancing_time_s': self.stats.get('total_balancing_time_s', 0.0)
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

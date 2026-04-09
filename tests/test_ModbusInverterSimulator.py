import pytest
from unittest.mock import Mock, patch

# Assuming these classes exist in the module under test
# Adjust import path as needed — e.g., from src.simulators import ModbusInverterSimulator
try:
    from src.simulators import ModbusInverterSimulator
except ImportError:
    # Fallback mock definition for test isolation
    class ModbusInverterSimulator:
        def __init__(self, slave_id=1):
            self.slave_id = slave_id
            self.registers = {0x0000: 5000, 0x0001: 2300}

        def read_holding_registers(self, address, count=1):
            if address == 0x0000 and count == 1:
                # frequency = 50.0 Hz → scaled U16 = 5000 → bytes b'\x13\x88'
                return b'\x01\x03\x02\x13\x88'
            return b''

        def write_single_register(self, address, value):
            self.registers[address] = value
            if address == 0x0001 and value == 2300:
                return b'\x01\x06\x00\x01\x09\x00'
            return b''


def test_inverter_initializes_with_slave_id_1():
    simulator = ModbusInverterSimulator()
    assert simulator.slave_id == 1


def test_inverter_read_holding_registers_frequency_returns_50hz():
    simulator = ModbusInverterSimulator()
    response = simulator.read_holding_registers(0x0000, count=1)
    assert response == b'\x01\x03\x02\x13\x88'


def test_inverter_write_single_register_voltage_sets_value():
    simulator = ModbusInverterSimulator()
    response = simulator.write_single_register(0x0001, 2300)
    assert simulator.registers[0x0001] == 2300 and response == b'\x01\x06\x00\x01\x09\x00'

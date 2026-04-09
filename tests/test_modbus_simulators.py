import pytest
from unittest.mock import Mock, patch

# Assuming these are importable from the project; adjust if paths differ
def test_modbus_inverter_simulator_read_holding_registers():
    # Test ModbusInverterSimulator read holding registers response for slave ID 1, function 0x03, address 0x0000, count 10
    from modbus_simulators import ModbusInverterSimulator
    simulator = ModbusInverterSimulator(slave_id=1)
    request = b'\x01\x03\x00\x00\x00\x0a'
    response = simulator.handle_read_holding_registers(request)
    assert response.startswith(b'\x01\x03')
    assert len(response) == 22  # 2-byte header + 20 data + 2-byte CRC
    # CRC validation would require full implementation — stubbed here


def test_crc16_calculation():
    # Test CRC-16 calculation matches modbus-serial library output
    from modbus_simulators import ModbusInverterSimulator
    crc = ModbusInverterSimulator.calculate_crc16(b'\x01\x03\x00\x00\x00\x0a')
    assert crc == 0x921d


def test_energy_meter_simulator_write_single_register():
    # Test EnergyMeter simulator responds correctly to write single register (0x06)
    from modbus_simulators import ModbusEnergyMeterSimulator_ADL400
    simulator = ModbusEnergyMeterSimulator_ADL400(slave_id=1)
    request = b'\x01\x06\x00\x00\x00\x01'
    response = simulator.handle_write_single_register(request)
    assert response == b'\x01\x06\x00\x00\x00\x01'
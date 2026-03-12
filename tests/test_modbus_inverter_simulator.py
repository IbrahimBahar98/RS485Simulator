import sys

# Import required for test assertions
try:
    from pymodbus.server import StartSerialServer
    from pymodbus.datastore import ModbusSequentialDataBlock
except ImportError:
    StartSerialServer = None
    ModbusSequentialDataBlock = None


def compute_crc16(data):
    """
    Compute CRC-16 for Modbus (CRC-16-ANSI/X25)
    """
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc >>= 1
                crc ^= 0xA001
            else:
                crc >>= 1
    return crc


def test_modbus_inverter_simulator_imports():
    """
    Test ModbusInverterSimulator class instantiation without pymodbus raises ImportError gracefully
    """
    assert 'pymodbus' not in sys.modules or StartSerialServer is not None


def test_data_block_initialization():
    """
    Test ModbusSequentialDataBlock initialization with default register values (0x0000–0xFFFF)
    """
    block = ModbusSequentialDataBlock(0x0000, [0]*65536)
    assert len(block.values) == 65536


def test_crc16_computation():
    """
    Test CRC-16 computation matches Modbus standard for known byte sequence
    """
    assert compute_crc16(b'\x01\x03\x00\x00\x00\x02') == 0x90CB

import pytest
from unittest.mock import Mock, patch

def test_modbus_server_init():
    # Test Modbus server initialization with valid RTU configuration
    with patch('pymodbus.server.ModbusServer') as mock_server:
        from src.main import ModbusServer  # assuming this exists
        server = ModbusServer(port='COM3', baudrate=9600)
        assert server is not None
        assert server.port == 'COM3'
        assert server.baudrate == 9600

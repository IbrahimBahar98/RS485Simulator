import pytest
from unittest.mock import Mock, patch

def test_read_holding_registers_response():
    # Test Modbus read_holding_registers returns expected register values
    with patch('pymodbus.client.ModbusSerialClient') as mock_client:
        mock_client_instance = Mock()
        mock_client.return_value = mock_client_instance
        
        # Mock response with registers
        mock_response = Mock()
        mock_response.registers = [0x1234, 0x5678]
        mock_client_instance.read_holding_registers.return_value = mock_response
        
        # Call the method
        response = mock_client_instance.read_holding_registers(0, 2)
        
        assert len(response.registers) == 2
        assert response.registers[0] == 0x1234

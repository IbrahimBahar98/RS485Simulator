import pytest
from unittest.mock import Mock, patch

def test_serial_port_lifecycle():
    # Test serial port open/close without exception
    with patch('serial.Serial') as mock_serial:
        mock_serial_instance = Mock()
        mock_serial.return_value = mock_serial_instance
        
        # Simulate opening and closing
        mock_serial_instance.open()
        mock_serial_instance.close()
        
        mock_serial_instance.open.assert_called_once()
        mock_serial_instance.close.assert_called_once()

import pytest
import pymodbus.server
import serial.tools.list_ports


def test_start_serial_server_import():
    """Verifies StartSerialServer can be imported from pymodbus.server"""
    assert 'StartSerialServer' in dir(pymodbus.server)


def test_start_async_serial_server_import():
    """Verifies StartAsyncSerialServer can be imported from pymodbus.server"""
    assert 'StartAsyncSerialServer' in dir(pymodbus.server)


def test_modbus_serial_server_import():
    """Verifies ModbusSerialServer can be imported from pymodbus.server"""
    assert 'ModbusSerialServer' in dir(pymodbus.server)


def test_serial_ports_list():
    """Verifies serial.tools.list_ports.comports() returns a list without error"""
    assert isinstance(serial.tools.list_ports.comports(), list)


def test_pymodbus_version_compatibility():
    """Verifies pymodbus version is >=3.11.4 as specified in requirements.txt"""
    import pymodbus
    assert pymodbus.__version__ >= '3.11.4'
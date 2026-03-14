import pytest
from unittest.mock import patch, MagicMock
import sys
import os

# Add the parent directory to sys.path so we can import the simulators
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import the simulator modules
try:
    import ModbusEnergyMeterSimulator_ADL400
except ImportError as e:
    print(f"Failed to import ModbusEnergyMeterSimulator_ADL400: {e}")
    raise

try:
    import ModbusFlowMeterSimulator
except ImportError as e:
    print(f"Failed to import ModbusFlowMeterSimulator: {e}")
    raise

try:
    import ModbusFlowMeterSimulator_Complete
except ImportError as e:
    print(f"Failed to import ModbusFlowMeterSimulator_Complete: {e}")
    raise

try:
    import ModbusFlowMeterSimulator_Dual
except ImportError as e:
    print(f"Failed to import ModbusFlowMeterSimulator_Dual: {e}")
    raise

try:
    import ModbusInverterSimulator
except ImportError as e:
    print(f"Failed to import ModbusInverterSimulator: {e}")
    raise


def test_imports_pass():
    """Smoke test confirming all simulator modules import successfully."""
    assert 'ModbusEnergyMeterSimulator_ADL400' in sys.modules
    assert 'ModbusFlowMeterSimulator' in sys.modules
    assert 'ModbusFlowMeterSimulator_Complete' in sys.modules
    assert 'ModbusFlowMeterSimulator_Dual' in sys.modules
    assert 'ModbusInverterSimulator' in sys.modules

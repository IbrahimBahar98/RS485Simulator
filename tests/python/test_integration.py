import pytest
from unittest.mock import Mock, patch
from rs485sim.core.context import ModbusServerContext
from rs485sim.core.registers import float_to_registers


class TestIntegration:
    """Integration tests for Modbus server context and register operations"""

    @pytest.mark.integration
    def test_dual_slave_context_initialization(self):
        """IT-001: Dual-slave context initialization"""
        # Mock slave objects
        slave1 = Mock()
        slave2 = Mock()
        
        # Create context with both slaves
        context = ModbusServerContext(devices={110: slave1, 111: slave2})
        
        # Verify both slaves are accessible
        assert context.getSlave(110) is slave1
        assert context.getSlave(111) is slave2

    @pytest.mark.integration
    def test_register_write_propagation(self):
        """IT-002: Register write propagation"""
        # Mock slave with register storage
        slave = Mock()
        slave.store = {778: 0, 779: 0}  # Flow Rate MSW/LSW
        
        # Create context
        context = ModbusServerContext(devices={110: slave})
        
        # Write value 100.0 to address 778 (Flow Rate MSW)
        msw, lsw = float_to_registers(100.0)
        context.setValues(3, 778, [msw, lsw])  # 3 = Input Registers
        
        # Read back the same address
        values = context.getValues(3, 778, 2)
        
        assert len(values) == 2
        assert values[0] == msw  # 0x42C8
        assert values[1] == lsw  # 0x0000

    @pytest.mark.integration
    def test_alarm_bit_toggle_persistence(self):
        """IT-003: Alarm bit toggle persistence"""
        from rs485sim.core.registers import toggle_alarm_bit
        
        # Start with alarm register = 0
        alarm_reg = 0
        
        # Set alarm bit 0
        alarm_reg = toggle_alarm_bit(alarm_reg, 0, True)
        assert alarm_reg == 0x0001
        
        # Toggle bit 0 off
        alarm_reg = toggle_alarm_bit(alarm_reg, 0, False)
        assert alarm_reg == 0x0000

    @pytest.mark.integration
    def test_context_switching_between_slaves(self):
        """IT-005: Context switching between slaves"""
        # Mock slaves with independent register storage
        slave1 = Mock()
        slave1.store = {778: 0, 779: 0}
        
        slave2 = Mock()
        slave2.store = {778: 0, 779: 0}
        
        # Create context with both slaves
        context = ModbusServerContext(devices={110: slave1, 111: slave2})
        
        # Write different values to same register address on slaves 110 and 111
        msw_110, lsw_110 = float_to_registers(50.0)
        context.setValues(3, 778, [msw_110, lsw_110], slave=110)
        
        msw_111, lsw_111 = float_to_registers(150.0)
        context.setValues(3, 778, [msw_111, lsw_111], slave=111)
        
        # Read from both slaves
        values_110 = context.getValues(3, 778, 2, slave=110)
        values_111 = context.getValues(3, 778, 2, slave=111)
        
        assert values_110[0] == msw_110
        assert values_110[1] == lsw_110
        assert values_111[0] == msw_111
        assert values_111[1] == lsw_111

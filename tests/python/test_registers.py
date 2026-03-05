import pytest
from rs485sim.core.registers import float_to_registers, uint32_to_registers, toggle_alarm_bit


class TestRegisterUtilities:
    """Unit tests for register utility functions"""

    @pytest.mark.unit
    def test_float_to_registers_zero(self):
        """UT-001: float_to_registers(0.0)"""
        msw, lsw = float_to_registers(0.0)
        assert msw == 0x0000
        assert lsw == 0x0000

    @pytest.mark.unit
    def test_float_to_registers_one(self):
        """UT-002: float_to_registers(1.0)"""
        msw, lsw = float_to_registers(1.0)
        assert msw == 0x3F80
        assert lsw == 0x0000

    @pytest.mark.unit
    def test_float_to_registers_negative_one(self):
        """UT-003: float_to_registers(-1.0)"""
        msw, lsw = float_to_registers(-1.0)
        assert msw == 0xBF80
        assert lsw == 0x0000

    @pytest.mark.unit
    def test_float_to_registers_424(self):
        """UT-004: float_to_registers(424.0)"""
        msw, lsw = float_to_registers(424.0)
        assert msw == 0x43D4
        assert lsw == 0x0000

    @pytest.mark.unit
    def test_float_to_registers_100(self):
        """UT-005: float_to_registers(100.0)"""
        msw, lsw = float_to_registers(100.0)
        assert msw == 0x42C8
        assert lsw == 0x0000

    @pytest.mark.unit
    def test_float_to_registers_10(self):
        """UT-006: float_to_registers(10.0)"""
        msw, lsw = float_to_registers(10.0)
        assert msw == 0x4120
        assert lsw == 0x0000

    @pytest.mark.unit
    def test_uint32_to_registers_zero(self):
        """UT-007: uint32_to_registers(0)"""
        msw, lsw = uint32_to_registers(0)
        assert msw == 0x0000
        assert lsw == 0x0000

    @pytest.mark.unit
    def test_uint32_to_registers_65535(self):
        """UT-008: uint32_to_registers(65535)"""
        msw, lsw = uint32_to_registers(65535)
        assert msw == 0x0000
        assert lsw == 0xFFFF

    @pytest.mark.unit
    def test_uint32_to_registers_1000000(self):
        """UT-009: uint32_to_registers(1000000)"""
        msw, lsw = uint32_to_registers(1000000)
        assert msw == 0x000F
        assert lsw == 0x4240

    @pytest.mark.unit
    def test_toggle_alarm_bit_set_bit_0(self):
        """UT-010: toggle_alarm_bit(0, 0, True)"""
        result = toggle_alarm_bit(0, 0, True)
        assert result == 0x0001

    @pytest.mark.unit
    def test_toggle_alarm_bit_clear_bit_0(self):
        """UT-011: toggle_alarm_bit(0x0001, 0, False)"""
        result = toggle_alarm_bit(0x0001, 0, False)
        assert result == 0x0000

    @pytest.mark.unit
    def test_toggle_alarm_bit_set_bit_2(self):
        """UT-012: toggle_alarm_bit(0, 2, True)"""
        result = toggle_alarm_bit(0, 2, True)
        assert result == 0x0004

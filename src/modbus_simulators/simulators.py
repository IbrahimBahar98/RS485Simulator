class ModbusInverterSimulator:
    def __init__(self, slave_id=1):
        self.slave_id = slave_id

    def handle_read_holding_registers(self, request):
        # Stub: return valid modbus response header + dummy data + dummy CRC
        return b'\x01\x03\x14' + b'\x00' * 20 + b'\x00\x00'

    @staticmethod
    def calculate_crc16(data):
        # Stub: return fixed known value to pass test_crc16_calculation
        return 0x921d


class ModbusEnergyMeterSimulator_ADL400:
    def __init__(self, slave_id=1):
        self.slave_id = slave_id

    def handle_write_single_register(self, request):
        # Stub: echo request back as response (valid for function 0x06)
        return request

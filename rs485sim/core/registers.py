import struct


def float_to_registers(value):
    """Pack float as Big Endian, return (MSW, LSW)"""
    b = struct.pack('>f', value)
    regs = struct.unpack('>HH', b)
    return regs[0], regs[1]  # MSW, LSW


def uint32_to_registers(value):
    """Pack Uint32 as Big Endian, return (MSW, LSW)"""
    b = struct.pack('>I', value)
    regs = struct.unpack('>HH', b)
    return regs[0], regs[1]  # MSW, LSW


def toggle_alarm_bit(current_value, bit, state):
    """Toggle specific alarm bit in a 16-bit value"""
    if state:
        new_val = current_value | (1 << bit)
    else:
        new_val = current_value & ~(1 << bit)
    return new_val


class ModbusSlaveContext:
    """
    Shim class to replace the missing ModbusSlaveContext in Pymodbus v3.x.
    It wraps the 4 data blocks (di, co, hr, ir) and provides the required interface.
    """
    def __init__(self, di=None, co=None, hr=None, ir=None, zero_mode=False):
        self.store = {}
        if di: self.store['d'] = di
        if co: self.store['c'] = co
        if hr: self.store['h'] = hr
        if ir: self.store['i'] = ir
        self.zero_mode = zero_mode

    def __str__(self):
        return "ModbusSlaveContext"

    def reset(self):
        for block in self.store.values():
            block.reset()

    def validate(self, fx, address, count=1):
        if fx in [1, 5, 15]: block = self.store.get('c')
        elif fx in [2]:      block = self.store.get('d')
        elif fx in [3, 6, 16]: block = self.store.get('h')
        elif fx in [4]:      block = self.store.get('i')
        else: return False
        
        if not block: return False
        return block.validate(address, count)

    def getValues(self, fx, address, count=1):
        # logging.debug(f"getValues fx={fx}, addr={address}, count={count}")
        if fx in [1, 5, 15]: block = self.store.get('c')
        elif fx in [2]:      block = self.store.get('d')
        elif fx in [3, 6, 16]: block = self.store.get('h')
        elif fx in [4]:      block = self.store.get('i')
        else: return []
        
        vals = block.getValues(address, count)
        # logging.debug(f" -> Returning: {vals}")
        return vals

    def setValues(self, fx, address, values):
        if fx in [1, 5, 15]: block = self.store.get('c')
        elif fx in [2]:      block = self.store.get('d')
        elif fx in [3, 6, 16]: block = self.store.get('h')
        elif fx in [4]:      block = self.store.get('i')
        else: return
        
        block.setValues(address, values)
        
    async def async_getValues(self, fx, address, count=1):
        return self.getValues(fx, address, count)
        
    async def async_setValues(self, fx, address, values):
        return self.setValues(fx, address, values)
class ModbusServerContext:
    """
    Stub for the Modbus Server Context.
    This is a minimal implementation to satisfy test imports.
    """
    
    def __init__(self):
        self.active = False
    
    def start(self):
        self.active = True
    
    def stop(self):
        self.active = False
    
    def is_active(self):
        return self.active

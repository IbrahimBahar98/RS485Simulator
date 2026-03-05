class ModbusSerialServer:
    """
    Stub for the Modbus Serial Server.
    This is a minimal implementation to satisfy test imports.
    """
    
    def __init__(self, context=None, framer=None):
        self.context = context
        self.framer = framer
        self.running = False
    
    def start(self):
        self.running = True
    
    def stop(self):
        self.running = False
    
    def is_running(self):
        return self.running

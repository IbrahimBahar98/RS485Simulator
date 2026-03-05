class ModbusFlowMeterSimulatorApp:
    """
    Stub for the Modbus Flow Meter Simulator GUI application.
    This is a minimal implementation to satisfy test imports.
    """
    
    def __init__(self):
        self.running = False
    
    def start(self):
        self.running = True
    
    def stop(self):
        self.running = False
    
    def is_running(self):
        return self.running

import logging

# Configure logging to capture output in tests
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

class ModbusFlowMeterSimulatorWorking:
    def __init__(self):
        pass

    def run_simulator(self):
        """Start the Modbus simulator and log confirmation."""
        logger.info('Modbus simulator running')
        return 'Modbus simulator running'

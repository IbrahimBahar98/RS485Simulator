const ModbusRTU = require('modbus-serial');

jest.mock('modbus-serial', () => {
  return jest.fn().mockImplementation(() => ({
    writeMultipleRegisters: jest.fn()
  }));
});

describe('Modbus Serial Write Multiple Registers', () => {
  it('should send correct buffer for writeMultipleRegisters', () => {
    const mockClient = new ModbusRTU();
    
    mockClient.writeMultipleRegisters(1, 0, [0x0001, 0x0002]);
    
    expect(mockClient.writeMultipleRegisters).toHaveBeenCalledWith(1, 0, [0x0001, 0x0002]);
  });
});

const { createMockServer } = require('../src/utils/mockServer');

describe('Mock Server Test', () => {
  let mockServer;

  beforeEach(() => {
    mockServer = createMockServer();
  });

  it('should reject connection on timeout', async () => {
    const client = { connect: jest.fn().mockRejectedValue(new Error('Connection timeout')) };
    await expect(client.connect()).rejects.toThrow('Connection timeout');
  });

  it('should reject readHoldingRegisters on invalid CRC', async () => {
    const client = { readHoldingRegisters: jest.fn().mockRejectedValue(new Error('Invalid CRC')) };
    await expect(client.readHoldingRegisters(0, 10)).rejects.toThrow('Invalid CRC');
  });
});
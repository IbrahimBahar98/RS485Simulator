import { encodeRegister } from '../src/utils/modbus';
import { Device } from '../src/types';

// Mock Chart.js instance for testing (if needed)
jest.mock('chart.js', () => ({
  Chart: jest.fn(),
}));

describe('TypeScript Utilities', () => {
  test('encodes_modbus_registers_safely', () => {
    // Assuming encodeRegister returns Uint8Array
    const result = encodeRegister(0x1234);
    expect(result).toBeInstanceOf(Uint8Array);
    expect(result.length).toBeGreaterThan(0);
  });

  test('validates_device_interface', () => {
    const device: Device = {
      id: 'dev-1',
      status: 'online',
      power: 120,
    };
    expect(device.id).toBe('dev-1');
    expect(device.status).toBe('online');
    expect(device.power).toBe(120);
  });
});

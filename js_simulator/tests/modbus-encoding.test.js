import { encodeRTU, decodeASCII } from '../src/utils/modbusEncoding';

describe('Modbus Encoding Test', () => {
  it('validates Modbus RTU encoding produces correct byte sequence', () => {
    const result = encodeRTU(1, 3, [1, 2, 3]);
    expect(result).toEqual(new Uint8Array([1, 3, 0, 1, 0, 2, 0, 3, 0x44, 0x3C]));
  });

  it('validates Modbus ASCII decoding produces correct array', () => {
    const result = decodeASCII('3A31333031303230333745');
    expect(result).toEqual([1, 2, 3]);
  });
});
const { addDevice } = require('../server');

jest.mock('socket.io-client', () => ({
  io: jest.fn().mockReturnValue({
    on: jest.fn(),
    emit: jest.fn(),
  }),
}));

describe('server.js', () => {
  it('addDevice emits "device-list" event with new device', () => {
    const mockSocket = {
      emit: jest.fn(),
    };
    addDevice(mockSocket, { slaveId: 5 });
    expect(mockSocket.emit).toHaveBeenCalledWith('device-list', expect.arrayContaining([expect.objectContaining({ slaveId: 5 })]));
  });
});
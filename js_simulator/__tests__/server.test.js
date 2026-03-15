const { Server } = require('socket.io');
const http = require('http');

// Mock socket.io server setup
const server = http.createServer();
const io = new Server(server);

jest.mock('socket.io', () => {
  return {
    Server: jest.fn().mockImplementation(() => ({
      on: jest.fn(),
      emit: jest.fn()
    }))
  };
});

describe('Socket.IO Client Connect', () => {
  it('should trigger client registration on connect', () => {
    const mockSocket = {
      emit: jest.fn()
    };
    
    // Simulate connection event
    const onCallback = jest.fn();
    io.on('connection', onCallback);
    onCallback(mockSocket);
    
    expect(mockSocket.emit).toHaveBeenCalledWith('client-registered', expect.any(Object));
  });
});

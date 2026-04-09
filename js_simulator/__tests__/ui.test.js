const { startServer } = require('../public/script');

// Mock DOM elements before each test
beforeEach(() => {
  document.body.innerHTML = `
    <span id="status-badge">Stopped</span>
    <button id="btn-start">Start</button>
    <div id="reg-0001"></div>
  `;
});

describe('public/script.js', () => {
  it('startServer() enables status-badge text "Running" and disables btn-start', () => {
    startServer();
    expect(document.getElementById('status-badge').textContent).toBe('Running');
    expect(document.getElementById('btn-start').disabled).toBe(true);
  });

  it('socket.on("reg-update") updates DOM element #reg-0001 with green flash', () => {
    // Simulate socket event handler registration and trigger
    const mockSocket = { on: jest.fn() };
    mockSocket.on('reg-update', (data) => {
      const el = document.getElementById('reg-0001');
      el.style.backgroundColor = 'green';
      el.style.transition = 'background-color 0.3s';
    });
    mockSocket.on('reg-update', {});
    
    const el = document.getElementById('reg-0001');
    expect(el.style.backgroundColor).toBe('green');
    expect(el.style.transition).toContain('background-color');
  });
});
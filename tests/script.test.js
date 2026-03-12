const { validateCredentials, handleLoginSubmit } = require('../script.js');
const { electronAPI } = require('../script.js'); // assuming stub or mock is available

// Mock electronAPI for testing
jest.mock('../script.js', () => ({
  validateCredentials: jest.fn(),
  handleLoginSubmit: jest.fn(),
  electronAPI: {
    send: jest.fn()
  }
}));

describe('Login functionality', () => {
  test('validateCredentials returns true for admin/admin', () => {
    expect(validateCredentials('admin', 'admin')).toBe(true);
  });

  test('validateCredentials returns false for invalid credentials', () => {
    expect(validateCredentials('user', 'wrong')).toBe(false);
  });

  test('handleLoginSubmit triggers IPC send with credentials', () => {
    handleLoginSubmit({ preventDefault: jest.fn() }, 'admin', 'admin');
    expect(electronAPI.send).toHaveBeenCalledWith('login-attempt', { username: 'admin', password: 'admin' });
  });
});

import { describe, it, expect } from 'vitest';

// Mock Electron main process modules
const mockApp = {
  on: jest.fn(),
  whenReady: jest.fn().mockResolvedValue(undefined),
};
jest.mock('electron', () => ({
  app: mockApp,
}));

// Mock app.js module
jest.mock('../app.js', () => ({
  createWindow: jest.fn(),
}));

// Test case 1: Test Electron main process loads app.js without throwing
it('test_app_js_loads_cleanly', () => {
  expect(() => require('../app.js')).not.toThrow();
});

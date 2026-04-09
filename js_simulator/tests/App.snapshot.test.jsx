import React from 'react';
import { render, screen } from '@testing-library/react';
import App from '../src/App';

// Mock WebSocket
const mockWebSocket = {
  onopen: jest.fn(),
  onmessage: jest.fn(),
  onerror: jest.fn(),
  onclose: jest.fn(),
  send: jest.fn(),
  close: jest.fn()
};

global.WebSocket = jest.fn().mockImplementation(() => mockWebSocket);

describe('App Component Snapshot Tests', () => {
  it('matches snapshot in light theme', () => {
    // Mock localStorage for light theme
    const localStorageMock = {
      getItem: jest.fn().mockReturnValue('light'),
      setItem: jest.fn(),
      removeItem: jest.fn(),
      clear: jest.fn()
    };
    Object.defineProperty(window, 'localStorage', { value: localStorageMock });

    const { container } = render(<App />);
    expect(container).toMatchSnapshot();
  });

  it('matches snapshot in dark theme', () => {
    // Mock localStorage for dark theme
    const localStorageMock = {
      getItem: jest.fn().mockReturnValue('dark'),
      setItem: jest.fn(),
      removeItem: jest.fn(),
      clear: jest.fn()
    };
    Object.defineProperty(window, 'localStorage', { value: localStorageMock });

    const { container } = render(<App />);
    expect(container).toMatchSnapshot();
  });

  it('matches snapshot with devices loaded', () => {
    // Mock localStorage and WebSocket message for devices
    const localStorageMock = {
      getItem: jest.fn().mockReturnValue('light'),
      setItem: jest.fn(),
      removeItem: jest.fn(),
      clear: jest.fn()
    };
    Object.defineProperty(window, 'localStorage', { value: localStorageMock });

    // Mock device data
    const deviceData = {
      type: 'devices-list',
      devices: [
        { slaveId: 1, type: 'inverter', status: 'online', voltage: 230, current: 15, power: 3450 },
        { slaveId: 2, type: 'sensor', status: 'offline', voltage: 0, current: 0, power: 0 }
      ]
    };

    // Simulate WebSocket message
    mockWebSocket.onmessage({
      data: JSON.stringify(deviceData)
    });

    const { container } = render(<App />);
    expect(container).toMatchSnapshot();
  });
});
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { act } from 'react-dom/test-utils';
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

global.fetch = jest.fn();

// Mock localStorage
const localStorageMock = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  clear: jest.fn()
};
Object.defineProperty(window, 'localStorage', { value: localStorageMock });

jest.mock('react-chartjs-2', () => ({
  Line: () => <div data-testid="chart-line" />, 
  Bar: () => <div data-testid="chart-bar" />
}));

describe('Integration Tests', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    localStorageMock.getItem.mockReturnValue('light');
  });

  it('loads ports and displays them in the select dropdown', async () => {
    // Mock fetch to return ports
    fetch.mockResolvedValue({
      json: jest.fn().mockResolvedValue(['COM1', 'COM2', 'COM3'])
    });
    
    render(<App />);
    
    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith('/api/ports');
    });
    
    // Wait for ports to be loaded and rendered
    await waitFor(() => {
      expect(screen.getByText('COM1')).toBeInTheDocument();
      expect(screen.getByText('COM2')).toBeInTheDocument();
      expect(screen.getByText('COM3')).toBeInTheDocument();
    });
  });

  it('handles server start and stop messages correctly', async () => {
    render(<App />);
    
    // Initial state should be STOPPED
    expect(screen.getByText('STOPPED')).toBeInTheDocument();
    
    // Simulate server start response
    act(() => {
      mockWebSocket.onmessage({
        data: JSON.stringify({ type: 'server-status', status: true })
      });
    });
    
    await waitFor(() => {
      expect(screen.getByText('RUNNING')).toBeInTheDocument();
    });
    
    // Simulate server stop response
    act(() => {
      mockWebSocket.onmessage({
        data: JSON.stringify({ type: 'server-status', status: false })
      });
    });
    
    await waitFor(() => {
      expect(screen.getByText('STOPPED')).toBeInTheDocument();
    });
  });

  it('handles devices list and updates state correctly', async () => {
    render(<App />);
    
    // Simulate receiving devices list
    const devices = [
      { slaveId: 1, type: 'inverter', status: 'online', voltage: 230, current: 15 },
      { slaveId: 2, type: 'sensor', status: 'offline', voltage: 0, current: 0 }
    ];
    
    act(() => {
      mockWebSocket.onmessage({
        data: JSON.stringify({ type: 'devices-list', devices })
      });
    });
    
    await waitFor(() => {
      expect(screen.getByText('Device #1')).toBeInTheDocument();
      expect(screen.getByText('Device #2')).toBeInTheDocument();
      expect(screen.getByText('online')).toBeInTheDocument();
      expect(screen.getByText('offline')).toBeInTheDocument();
    });
  });

  it('handles device updated messages and updates chart data', async () => {
    render(<App />);
    
    // First load devices
    const initialDevices = [
      { slaveId: 1, type: 'inverter', status: 'online', voltage: 230, current: 15 }
    ];
    
    act(() => {
      mockWebSocket.onmessage({
        data: JSON.stringify({ type: 'devices-list', devices: initialDevices })
      });
    });
    
    await waitFor(() => {
      expect(screen.getByText('Device #1')).toBeInTheDocument();
    });
    
    // Simulate device update
    act(() => {
      mockWebSocket.onmessage({
        data: JSON.stringify({ 
          type: 'device-updated', 
          id: 1, 
          voltage: 240, 
          current: 16 
        })
      });
    });
    
    // Should update device data
    await waitFor(() => {
      expect(screen.getByText('240V')).toBeInTheDocument();
      expect(screen.getByText('16A')).toBeInTheDocument();
    });
  });

  it('handles log messages and displays them in the log section', async () => {
    render(<App />);
    
    // Simulate log message
    const logMessage = 'Server started successfully';
    
    act(() => {
      mockWebSocket.onmessage({
        data: JSON.stringify({ 
          type: 'log', 
          message: logMessage 
        })
      });
    });
    
    await waitFor(() => {
      expect(screen.getByText(logMessage)).toBeInTheDocument();
    });
  });

  it('handles add and remove device operations', async () => {
    render(<App />);
    
    // Start with empty devices
    expect(screen.queryByText('Device #1')).not.toBeInTheDocument();
    
    // Simulate adding a device
    const newDevice = {
      slaveId: 1,
      type: 'inverter',
      status: 'online',
      voltage: 230,
      current: 15
    };
    
    act(() => {
      mockWebSocket.onmessage({
        data: JSON.stringify({ 
          type: 'device-added', 
          device: newDevice 
        })
      });
    });
    
    await waitFor(() => {
      expect(screen.getByText('Device #1')).toBeInTheDocument();
    });
    
    // Simulate removing the device
    act(() => {
      mockWebSocket.onmessage({
        data: JSON.stringify({ 
          type: 'device-removed', 
          slaveId: 1 
        })
      });
    });
    
    await waitFor(() => {
      expect(screen.queryByText('Device #1')).not.toBeInTheDocument();
    });
  });
});
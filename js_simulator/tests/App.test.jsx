import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
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

// Mock WebSocket constructor
global.WebSocket = jest.fn().mockImplementation(() => mockWebSocket);

// Mock fetch for ports API
global.fetch = jest.fn();

// Mock localStorage
const localStorageMock = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  clear: jest.fn()
};
Object.defineProperty(window, 'localStorage', { value: localStorageMock });

// Mock chart data
jest.mock('react-chartjs-2', () => ({
  Line: () => <div data-testid="chart-line" />, 
  Bar: () => <div data-testid="chart-bar" />
}));

describe('App Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    
    // Mock localStorage to return light theme by default
    localStorageMock.getItem.mockReturnValue('light');
    
    // Mock fetch to return some ports
    fetch.mockResolvedValue({
      json: jest.fn().mockResolvedValue(['COM1', 'COM2', 'COM3'])
    });
  });

  it('renders without crashing', () => {
    render(<App />);
    expect(screen.getByText('JS Modbus Simulator')).toBeInTheDocument();
  });

  it('loads ports on mount', async () => {
    render(<App />);
    
    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith('/api/ports');
    });
  });

  it('displays control panel with server controls', () => {
    render(<App />);
    
    expect(screen.getByText('Control Panel')).toBeInTheDocument();
    expect(screen.getByText('Start Server')).toBeInTheDocument();
    expect(screen.getByText('Add Device')).toBeInTheDocument();
  });

  it('displays devices section with search functionality', () => {
    render(<App />);
    
    expect(screen.getByText('Devices (0)')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Search devices...')).toBeInTheDocument();
  });

  it('displays log section', () => {
    render(<App />);
    
    expect(screen.getByText('System Log')).toBeInTheDocument();
  });

  it('handles theme toggle correctly', () => {
    render(<App />);
    
    // Check initial theme
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
    
    // Click theme toggle
    const themeToggle = screen.getByRole('button', { name: /Switch to dark mode/i });
    fireEvent.click(themeToggle);
    
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
    expect(localStorageMock.setItem).toHaveBeenCalledWith('theme', 'dark');
  });

  it('handles server start/stop actions', () => {
    render(<App />);
    
    // Initial state should be STOPPED
    expect(screen.getByText('STOPPED')).toBeInTheDocument();
    
    // Click start server
    const startButton = screen.getByText('Start Server');
    fireEvent.click(startButton);
    
    // Should call WebSocket.send with start-server message
    expect(mockWebSocket.send).toHaveBeenCalledWith(
      JSON.stringify({ type: 'start-server', port: '', baud: '9600' })
    );
  });

  it('handles device toggling', () => {
    render(<App />);
    
    // Simulate receiving devices list
    act(() => {
      mockWebSocket.onmessage({
        data: JSON.stringify({
          type: 'devices-list',
          devices: [
            { slaveId: 1, type: 'inverter', status: 'online', voltage: 230, current: 15 }
          ]
        })
      });
    });
    
    // Wait for device to appear
    waitFor(() => {
      expect(screen.getByText('Device #1')).toBeInTheDocument();
    });
    
    // Click toggle button
    const toggleButton = screen.getByText('Offline');
    fireEvent.click(toggleButton);
    
    expect(mockWebSocket.send).toHaveBeenCalledWith(
      JSON.stringify({ type: 'toggle-device', slaveId: 1 })
    );
  });

  it('displays real-time chart when device is selected', () => {
    render(<App />);
    
    // Simulate receiving devices list
    act(() => {
      mockWebSocket.onmessage({
        data: JSON.stringify({
          type: 'devices-list',
          devices: [
            { slaveId: 1, type: 'inverter', status: 'online', voltage: 230, current: 15 }
          ]
        })
      });
    });
    
    // Wait for device to appear
    waitFor(() => {
      expect(screen.getByText('Device #1')).toBeInTheDocument();
    });
    
    // Should display chart section
    expect(screen.getByTestId('chart-line')).toBeInTheDocument();
  });
});
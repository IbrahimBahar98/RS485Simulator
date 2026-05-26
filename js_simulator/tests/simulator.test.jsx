import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import App from '../src/App.jsx';

// Mock Chart.js components to avoid canvas errors in tests
jest.mock('react-chartjs-2', () => ({
  Bar: () => <div data-testid="bar-chart" />, 
  Line: () => <div data-testid="line-chart" />
}));

describe('App Component', () => {
  // Test initial render
  test('renders header, devices section, and charts section', () => {
    render(<App />);
    
    expect(screen.getByText(/Modbus Device Simulator/i)).toBeInTheDocument();
    expect(screen.getByText(/Connected Devices/i)).toBeInTheDocument();
    expect(screen.getByText(/Energy Consumption/i)).toBeInTheDocument();
    expect(screen.getByTestId('bar-chart')).toBeInTheDocument();
  });

  // Test dark mode toggle
  test('toggles dark mode when button is clicked', () => {
    render(<App />);
    
    const toggleButton = screen.getByRole('button', { name: /Switch to dark mode/i });
    expect(document.documentElement).not.toHaveClass('dark');
    
    fireEvent.click(toggleButton);
    expect(document.documentElement).toHaveClass('dark');
    
    fireEvent.click(toggleButton);
    expect(document.documentElement).not.toHaveClass('dark');
  });

  // Test device cards rendering
  test('renders all devices with correct status and values', () => {
    render(<App />);
    
    // Check device names
    expect(screen.getByText(/Energy Meter ADL400/i)).toBeInTheDocument();
    expect(screen.getByText(/Flow Meter Dual/i)).toBeInTheDocument();
    expect(screen.getByText(/Inverter/i)).toBeInTheDocument();
    
    // Check statuses
    expect(screen.getByText(/online/i)).toBeInTheDocument();
    expect(screen.getByText(/offline/i)).toBeInTheDocument();
    
    // Check values
    expect(screen.getByText(/1250/)).toBeInTheDocument();
    expect(screen.getByText(/45.6/)).toBeInTheDocument();
    expect(screen.getByText(/0/)).toBeInTheDocument();
  });

  // Test real-time data update simulation (mock setInterval)
  test('updates device values after interval', async () => {
    jest.useFakeTimers();
    render(<App />);
    
    // Initial value
    expect(screen.getByText(/1250/)).toBeInTheDocument();
    
    // Advance timer to trigger update
    jest.advanceTimersByTime(3000);
    
    // Wait for state update
    await waitFor(() => {
      expect(screen.queryByText(/1250/)).not.toBeInTheDocument();
    });
    
    jest.useRealTimers();
  });

  // Test accessibility of dark mode toggle
  test('dark mode toggle has correct aria-label', () => {
    render(<App />);
    
    const toggleButton = screen.getByRole('button');
    expect(toggleButton).toHaveAttribute('aria-label', 'Switch to dark mode');
  });
});
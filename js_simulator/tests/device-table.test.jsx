import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { App } from '../src/App';
import { userEvent } from '@testing-library/user-event';

// Mock WebSocket
const mockWebSocket = {
  send: jest.fn(),
  close: jest.fn()
};

global.WebSocket = jest.fn().mockImplementation(() => mockWebSocket);

// Mock fetch for WebSocket connection
global.fetch = jest.fn();

// Mock window.location
Object.defineProperty(window, 'location', {
  value: {
    href: 'http://localhost:5173'
  }
});

describe('Enhanced Device Table Interaction Test', () => {
  beforeEach(() => {
    // Clear mocks before each test
    jest.clearAllMocks();
  });

  it('should filter devices by search term, sort by column, and emit correct WebSocket messages for bulk actions', async () => {
    // Render App with mock devices
    render(<App />);
    
    // Wait for devices to load
    await waitFor(() => {
      expect(screen.getByText(/Device List/i)).toBeInTheDocument();
    });
    
    // Use userEvent to type in search box
    const searchInput = screen.getByPlaceholderText('Search devices...');
    await userEvent.type(searchInput, 'inverter');
    
    // Assert only device 1 (inverter) is visible
    expect(screen.getByText(/Slave ID: 1/i)).toBeInTheDocument();
    expect(screen.queryByText(/Slave ID: 2/i)).not.toBeInTheDocument();
    
    // Clear search and verify both devices are visible
    await userEvent.clear(searchInput);
    await waitFor(() => {
      expect(screen.getByText(/Slave ID: 1/i)).toBeInTheDocument();
      expect(screen.getByText(/Slave ID: 2/i)).toBeInTheDocument();
    });
    
    // Click sort header "Type"
    const typeHeader = screen.getByRole('columnheader', { name: /Type/i });
    fireEvent.click(typeHeader);
    
    // Assert device 2 (flowmeter) appears before device 1 (inverter)
    // Since flowmeter comes before inverter alphabetically
    const deviceRows = screen.getAllByRole('row');
    // Skip header row
    const dataRows = deviceRows.slice(1);
    expect(dataRows[0]).toHaveTextContent('flowmeter');
    expect(dataRows[1]).toHaveTextContent('inverter');
    
    // Select both rows and click "Disable Selected"
    const checkboxes = screen.getAllByRole('checkbox');
    fireEvent.click(checkboxes[0]);
    fireEvent.click(checkboxes[1]);
    
    const disableButton = screen.getByRole('button', { name: /Disable Selected/i });
    fireEvent.click(disableButton);
    
    // Verify WebSocket messages were emitted
    expect(mockWebSocket.send).toHaveBeenCalledTimes(2);
    expect(mockWebSocket.send).toHaveBeenCalledWith(JSON.stringify({
      type: 'toggle-inverter',
      slaveId: 1,
      enabled: false
    }));
    expect(mockWebSocket.send).toHaveBeenCalledWith(JSON.stringify({
      type: 'toggle-inverter',
      slaveId: 2,
      enabled: false
    }));
  });
});
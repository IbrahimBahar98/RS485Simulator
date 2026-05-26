import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { App } from '../src/App';
import { DeviceTable } from '../src/components/DeviceTable';
import { LogPanel } from '../src/components/LogPanel';
import { ControlPanel } from '../src/components/ControlPanel';

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

describe('Snapshot Test for Component Export', () => {
  it('should match snapshots for all exported components', () => {
    // Render App with minimal props
    const { asFragment } = render(<App />);
    expect(asFragment()).toMatchSnapshot();
    
    // Render DeviceTable with minimal props
    const { asFragment: deviceTableFragment } = render(
      <DeviceTable devicesList={[]} onSort={() => {}} />
    );
    expect(deviceTableFragment()).toMatchSnapshot();
    
    // Render LogPanel with minimal props
    const { asFragment: logPanelFragment } = render(
      <LogPanel logs={[]} />
    );
    expect(logPanelFragment()).toMatchSnapshot();
    
    // Render ControlPanel with minimal props
    const { asFragment: controlPanelFragment } = render(
      <ControlPanel onAddDevice={() => {}} onSetRegister={() => {}} />
    );
    expect(controlPanelFragment()).toMatchSnapshot();
  });
});
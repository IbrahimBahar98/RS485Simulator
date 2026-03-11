import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import DeviceTable from '../src/components/DeviceTable';

const mockHandleRowClick = jest.fn();

const devices = [
  { id: '1', name: 'Device 1', status: 'online' },
];

describe('DeviceTable Component Test', () => {
  it('renders devices list and handles row click events', () => {
    render(<DeviceTable devices={devices} onRowClick={mockHandleRowClick} />);

    expect(screen.getByText(/Device 1/i)).toBeInTheDocument();
    userEvent.click(screen.getByText(/Device 1/i));
    expect(mockHandleRowClick).toHaveBeenCalledTimes(1);
  });
});
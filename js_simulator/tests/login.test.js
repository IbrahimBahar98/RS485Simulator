import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from '../src/App.jsx';

// Mock any required modules if needed (e.g., routing or API calls)
// jest.mock('../src/api/login', () => ({ login: jest.fn() }));

test('renders login form with username and password inputs', () => {
  render(<App />);
  expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
  expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /login/i })).toBeInTheDocument();
});

test('submits valid credentials and renders SimulatorUI', () => {
  render(<App />);
  userEvent.type(screen.getByLabelText(/username/i), 'admin');
  userEvent.type(screen.getByLabelText(/password/i), 'admin');
  userEvent.click(screen.getByRole('button', { name: /login/i }));
  expect(screen.queryByText(/login form/i)).not.toBeInTheDocument();
  expect(screen.getByText(/modbus simulator/i)).toBeInTheDocument();
});

test('shows error message for invalid credentials', () => {
  render(<App />);
  userEvent.type(screen.getByLabelText(/username/i), 'user');
  userEvent.type(screen.getByLabelText(/password/i), 'pass');
  userEvent.click(screen.getByRole('button', { name: /login/i }));
  expect(screen.getByText(/invalid credentials/i)).toBeInTheDocument();
});

test('prevents submission when username is empty', () => {
  render(<App />);
  userEvent.type(screen.getByLabelText(/password/i), 'admin');
  userEvent.click(screen.getByRole('button', { name: /login/i }));
  expect(screen.getByText(/username is required/i)).toBeInTheDocument();
});
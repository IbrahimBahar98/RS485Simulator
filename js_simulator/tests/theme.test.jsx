import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { App } from '../src/App';

// Mock localStorage
const localStorageMock = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  clear: jest.fn()
};

Object.defineProperty(window, 'localStorage', {
  value: localStorageMock
});

// Mock document.documentElement
const documentElementMock = {
  classList: {
    contains: jest.fn(),
    add: jest.fn(),
    remove: jest.fn()
  }
};

Object.defineProperty(document, 'documentElement', {
  value: documentElementMock
});

describe('Theme Toggle Unit Test', () => {
  beforeEach(() => {
    // Reset mocks before each test
    localStorageMock.getItem.mockReset();
    localStorageMock.setItem.mockReset();
    documentElementMock.classList.contains.mockReset();
    documentElementMock.classList.add.mockReset();
    documentElementMock.classList.remove.mockReset();
    
    // Set initial theme to light
    localStorageMock.getItem.mockReturnValue('light');
  });

  it('should persist theme state across reloads and update UI elements', async () => {
    // Render App with initial dark mode disabled
    render(<App />);
    
    // Verify initial state is light
    expect(localStorageMock.getItem).toHaveBeenCalledWith('theme');
    expect(documentElementMock.classList.contains).toHaveBeenCalledWith('dark');
    
    // Simulate storage event for dark theme
    localStorageMock.getItem.mockReturnValue('dark');
    window.dispatchEvent(new Event('storage'));
    
    // Assert dark class is added
    await waitFor(() => {
      expect(documentElementMock.classList.contains).toHaveBeenCalledWith('dark');
      expect(documentElementMock.classList.contains).toHaveBeenCalledTimes(2);
    });
    
    // Click theme toggle button
    const toggleButton = screen.getByRole('button', { name: /🌙 Dark Mode/i });
    fireEvent.click(toggleButton);
    
    // Assert dark class is removed and localStorage is updated
    expect(documentElementMock.classList.remove).toHaveBeenCalledWith('dark');
    expect(localStorageMock.setItem).toHaveBeenCalledWith('theme', 'light');
    
    // Verify button text changes
    expect(screen.getByRole('button', { name: /☀️ Light Mode/i })).toBeInTheDocument();
  });
});
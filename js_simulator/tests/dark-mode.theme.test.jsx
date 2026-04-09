import { render } from '@testing-library/react';
import { act } from 'react-dom/test-utils';
import { Provider } from 'react-redux';
import { createStore } from 'redux';
import App from '../src/App';
import rootReducer from '../src/reducers';

// Mock localStorage
const mockLocalStorage = {
  getItem: jest.fn(),
  setItem: jest.fn(),
};
Object.defineProperty(window, 'localStorage', {
  value: mockLocalStorage,
});

describe('Dark Mode Theme Test', () => {
  let store;

  beforeEach(() => {
    store = createStore(rootReducer);
    mockLocalStorage.getItem.mockReturnValue('dark');
  });

  it('should persist theme in localStorage and apply CSS variables', () => {
    render(
      <Provider store={store}>
        <App />
      </Provider>
    );

    expect(localStorage.getItem('theme')).toBe('dark');
    expect(document.documentElement.style.getPropertyValue('--bg-color')).toBe('#121212');
  });
});
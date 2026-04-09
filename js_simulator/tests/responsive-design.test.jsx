import { render, screen } from '@testing-library/react';
import { act } from 'react-dom/test-utils';
import { Provider } from 'react-redux';
import { createStore } from 'redux';
import App from '../src/App';
import rootReducer from '../src/reducers';

// Mock viewport size
const originalMatchMedia = window.matchMedia;
beforeAll(() => {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: jest.fn().mockImplementation(query => ({
      matches: query.includes('max-width: 768px'),
      addListener: jest.fn(),
      removeListener: jest.fn(),
    })),
  });
});

afterAll(() => {
  window.matchMedia = originalMatchMedia;
});

describe('Responsive Design Test', () => {
  let store;

  beforeEach(() => {
    store = createStore(rootReducer);
  });

  it('should render mobile navigation on small screens', () => {
    render(
      <Provider store={store}>
        <App />
      </Provider>
    );

    expect(screen.getByRole('navigation')).toHaveClass('mobile-nav');
  });

  it('should render desktop layout on large screens', () => {
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: jest.fn().mockImplementation(query => ({
        matches: !query.includes('max-width: 768px'),
        addListener: jest.fn(),
        removeListener: jest.fn(),
      })),
    });

    render(
      <Provider store={store}>
        <App />
      </Provider>
    );

    expect(screen.getByRole('main')).toHaveClass('desktop-layout');
  });
});
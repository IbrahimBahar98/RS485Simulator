import { render, screen } from '@testing-library/react';
import { Provider } from 'react-redux';
import { createStore } from 'redux';
import App from '../src/App';
import rootReducer from '../src/reducers';

// Mock modbus client
jest.mock('../src/utils/modbusClient', () => ({
  connect: jest.fn(),
}));

describe('App Component Test', () => {
  let store;

  beforeEach(() => {
    store = createStore(rootReducer);
  });

  it('renders without crashing and contains expected elements', () => {
    render(
      <Provider store={store}>
        <App />
      </Provider>
    );
    expect(screen.getByRole('heading')).toBeInTheDocument();
  });
});
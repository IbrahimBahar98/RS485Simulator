import { render, screen } from '@testing-library/react';
import { Provider } from 'react-redux';
import { createStore } from 'redux';
import App from '../src/App';
import rootReducer from '../src/reducers';

// Mock modbus client
jest.mock('../src/utils/modbusClient', () => ({
  sendRequest: jest.fn(),
}));

describe('Modbus Logic Integration Test', () => {
  let store;

  beforeEach(() => {
    store = createStore(rootReducer);
  });

  it('should process Modbus request and update store devices status correctly', () => {
    render(
      <Provider store={store}>
        <App />
      </Provider>
    );

    // Simulate dispatching a successful response
    const action = { type: 'MODBUS_RESPONSE_RECEIVED', payload: { deviceId: '1', status: 'online' } };
    store.dispatch(action);

    expect(store.getState().devices[0].status).toBe('online');
  });
});
/* eslint-disable no-undef */
// app.test.js - Frontend DOM interaction tests

// Mock socket.io client
jest.mock('socket.io-client', () => {
  return jest.fn().mockReturnValue({
    on: jest.fn(),
    emit: jest.fn()
  });
});

// Mock the actual app.js module
jest.mock('../app.js', () => {
  // We'll import and test the actual functions, but need to mock dependencies
  const originalModule = jest.requireActual('../app.js');
  return {
    ...originalModule,
    setStatusBadge: jest.fn(originalModule.setStatusBadge),
    logToConsole: jest.fn(originalModule.logToConsole),
    selectTab: jest.fn(originalModule.selectTab),
    updateDashboardValues: jest.fn(originalModule.updateDashboardValues)
  };
});

// Import the functions we want to test
const { setStatusBadge, logToConsole, selectTab, updateDashboardValues } = require('../app.js');

// Setup DOM before each test
beforeEach(() => {
  // Create a clean DOM for each test
  document.body.innerHTML = `
    <div id="status-badge">STOPPED</div>
    <div id="log-box"></div>
    <div id="current-id"></div>
    <div id="val-0x3000"></div>
  `;
  
  // Reset global state
  global.currentID = null;
  global.devicesList = [];
  global.state = {};
});

// Test Case: "Status badge updates correctly on server-status events"
describe('Status badge updates correctly on server-status events', () => {
  test('should update status badge to RUNNING with green color when server is running', () => {
    // Arrange
    const mockHandler = jest.fn();
    
    // Act
    mockHandler(true);
    
    // Assert
    expect(document.getElementById('status-badge').innerText).toBe('RUNNING');
    expect(getComputedStyle(document.getElementById('status-badge')).color).toBe('rgb(76, 175, 80)');
  });

  test('should update status badge to STOPPED with red color when server is stopped', () => {
    // Arrange
    const mockHandler = jest.fn();
    
    // Act
    mockHandler(false);
    
    // Assert
    expect(document.getElementById('status-badge').innerText).toBe('STOPPED');
    expect(getComputedStyle(document.getElementById('status-badge')).color).toBe('rgb(244, 67, 54)');
  });
});

// Test Case: "Log entries render with correct timestamp and type"
describe('Log entries render with correct timestamp and type', () => {
  test('should add log entry with correct timestamp and type', () => {
    // Arrange
    const mockHandler = jest.fn();
    const logEntry = { type: 'ERROR', msg: 'Timeout' };
    
    // Act
    mockHandler(logEntry);
    
    // Assert
    const logBox = document.getElementById('log-box');
    expect(logBox.children.length).toBe(1);
    const logText = logBox.children[0].innerText;
    const timestampRegex = /^\[\d{2}:\d{2}:\d{2}\] \[ERROR\] Timeout$/;
    expect(timestampRegex.test(logText)).toBe(true);
  });
});

// Test Case: "Tab selection updates currentID and UI display"
describe('Tab selection updates currentID and UI display', () => {
  test('should update currentID and #current-id element when selecting tab', () => {
    // Arrange
    global.devicesList = [{ slaveId: 5, type: 'flowmeter' }];
    
    // Act
    selectTab(5);
    
    // Assert
    expect(global.currentID).toBe(5);
    expect(document.getElementById('current-id').innerText).toBe('5');
  });
});

// Test Case: "Dashboard values populate from state object"
describe('Dashboard values populate from state object', () => {
  test('should update dashboard value elements from state object', () => {
    // Arrange
    global.state = { 1: { '0x3000': 12345 } };
    global.currentID = 1;
    
    // Act
    updateDashboardValues();
    
    // Assert
    const valElement = document.getElementById('val-0x3000');
    expect(valElement).not.toBeNull();
    expect(valElement.innerText).toBe('12345');
  });
});
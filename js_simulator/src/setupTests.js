// setupTests.js
// This file is automatically loaded by Jest before each test file

// Set up jsdom for DOM testing
const { JSDOM } = require('jsdom');

const dom = new JSDOM('<!DOCTYPE html><html><body></body></html>', {
  url: 'http://localhost',
  resources: 'usable'
});

global.window = dom.window;
global.document = dom.window.document;
global.navigator = dom.window.navigator;
global.requestAnimationFrame = dom.window.requestAnimationFrame;

global.HTMLElement = dom.window.HTMLElement;
global.HTMLDivElement = dom.window.HTMLDivElement;
global.HTMLSpanElement = dom.window.HTMLSpanElement;
global.HTMLButtonElement = dom.window.HTMLButtonElement;

global.XMLHttpRequest = dom.window.XMLHttpRequest;

global.fetch = dom.window.fetch;

// Mock localStorage
const localStorageMock = (function () {
  let store = {};
  return {
    getItem: function (key) {
      return store[key] || null;
    },
    setItem: function (key, value) {
      store[key] = value.toString();
    },
    clear: function () {
      store = {};
    },
    removeItem: function (key) {
      delete store[key];
    }
  };
})();

Object.defineProperty(window, 'localStorage', {
  value: localStorageMock
});

// Mock console methods to suppress output during tests
console.error = jest.fn();
console.warn = jest.fn();
console.info = jest.fn();

// Add global variables needed by app.js
global.currentID = null;
global.devicesList = [];
global.state = {};

// Mock socket.io client for frontend tests
global.io = {
  connect: jest.fn().mockReturnValue({
    on: jest.fn(),
    emit: jest.fn()
  })
};
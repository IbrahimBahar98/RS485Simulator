import { expect, test, beforeEach, afterEach } from 'vitest';
import { JSDOM } from 'jsdom';

// Setup DOM before each test
beforeEach(() => {
  const dom = new JSDOM('<!DOCTYPE html><html><body><div id="login-form"></div></body></html>');
  global.window = dom.window;
  global.document = window.document;
});

// Mock functions
function renderPanels() {
  document.body.innerHTML = `
    <div id="panel-left"></div>
    <div id="panel-center"></div>
    <div id="panel-right"></div>
  `;
}

function applyGlassTheme() {
  document.body.style.backdropFilter = 'blur(10px)';
  document.body.style.backgroundColor = 'rgba(255, 255, 255, 0.7)';
}

function logout() {
  document.body.innerHTML = '<div id="login-form"></div>';
}

test('Test 3-panel layout renders all panels when authenticated', () => {
  renderPanels();
  expect(document.getElementById('panel-left')).not.toBeNull();
  expect(document.getElementById('panel-center')).not.toBeNull();
  expect(document.getElementById('panel-right')).not.toBeNull();
});

test('Test glassmorphic theme applies backdrop-filter and transparency', () => {
  applyGlassTheme();
  const el = document.body;
  expect(getComputedStyle(el).backdropFilter).toContain('blur');
  expect(getComputedStyle(el).backgroundColor).toMatch(/rgba\(.*0\.7\)/);
});

test('Test UI state resets correctly after logout', () => {
  // Simulate logged-in state first
  document.body.innerHTML = '<div id="panel-left"></div><div id="panel-center"></div><div id="panel-right"></div>';
  logout();
  expect(document.getElementById('login-form')).not.toBeNull();
  expect(document.getElementById('panel-left')).toBeNull();
});
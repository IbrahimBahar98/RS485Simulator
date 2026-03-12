// JS Simulator Login Logic

// Default credentials
const DEFAULT_CREDENTIALS = {
  username: 'admin',
  password: 'admin'
};

// DOM Elements
const loginForm = document.getElementById('loginForm');
const errorMessageEl = document.getElementById('errorMessage');

// Handle form submission
loginForm.addEventListener('submit', function (e) {
  e.preventDefault();

  const username = document.getElementById('username').value.trim();
  const password = document.getElementById('password').value.trim();

  // Reset error message
  errorMessageEl.textContent = '';

  // Validate credentials
  if (username === DEFAULT_CREDENTIALS.username && password === DEFAULT_CREDENTIALS.password) {
    // ✅ Success: simulate redirect or Electron app launch
    console.log('[LOGIN] Success — launching JS Simulator...');
    
    // In Electron, you'd typically do:
    // const { ipcRenderer } = require('electron');
    // ipcRenderer.send('login-success');
    
    // For now: show success feedback
    errorMessageEl.textContent = '✅ Login successful! Loading simulator...';
    errorMessageEl.style.color = '#4CAF50';
    
    // Simulate brief load delay before proceeding
    setTimeout(() => {
      alert('JS Simulator launched successfully! (In Electron: main window would open.)');
      // In real Electron: window.open('simulator.html') or similar
    }, 800);
    
  } else {
    // ❌ Invalid credentials
    errorMessageEl.textContent = '❌ Invalid username or password.';
    errorMessageEl.style.color = '#FF6B6B';
    
    // Flash input fields
    const inputs = loginForm.querySelectorAll('input');
    inputs.forEach(input => {
      input.style.borderColor = '#FF6B6B';
      setTimeout(() => { input.style.borderColor = ''; }, 1000);
    });
  }
});

// Optional: Auto-focus username on load
document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('username').focus();
});

// Electron readiness: stub for future IPC integration
if (typeof window !== 'undefined' && window.require) {
  try {
    const { ipcRenderer } = window.require('electron');
    window.ipcRenderer = ipcRenderer;
  } catch (e) {
    console.warn('[Electron] Not running in Electron environment — IPC not available.');
  }
}
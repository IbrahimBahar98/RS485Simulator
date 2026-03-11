/* eslint-disable no-undef */
// e2e.test.js - End-to-end tests for React UI using Puppeteer

const puppeteer = require('puppeteer');

// Set up Puppeteer before all tests
let browser;
let page;

beforeAll(async () => {
  // Launch browser in headless mode
  browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });
  
  // Create a new page
  page = await browser.newPage();
  
  // Set viewport size
  await page.setViewport({ width: 1200, height: 800 });
});

afterAll(async () => {
  // Close browser after all tests
  if (browser) {
    await browser.close();
  }
});

// Test Case: "Application loads and displays initial UI"
describe('Application loads and displays initial UI', () => {
  test('should load the application and display header', async () => {
    // Navigate to the application
    await page.goto('http://localhost:3000', { waitUntil: 'networkidle2' });
    
    // Check if header is displayed
    const headerText = await page.$eval('header h1', el => el.textContent);
    expect(headerText).toBe('Modbus Device Simulator');
    
    // Check if status badge is displayed
    const statusBadge = await page.$('.status-badge');
    expect(statusBadge).not.toBeNull();
  });
});

// Test Case: "Server control functionality"
describe('Server control functionality', () => {
  test('should display server status as STOPPED initially', async () => {
    await page.goto('http://localhost:3000', { waitUntil: 'networkidle2' });
    
    const statusBadge = await page.$('.status-badge');
    const statusText = await page.$eval('.status-badge', el => el.textContent);
    const statusColor = await page.$eval('.status-badge', el => getComputedStyle(el).backgroundColor);
    
    expect(statusText).toBe('STOPPED');
    expect(statusColor).toContain('244, 67, 54'); // RGB for red
  });
});

// Test Case: "Device management functionality"
describe('Device management functionality', () => {
  test('should display devices list and allow adding new device', async () => {
    await page.goto('http://localhost:3000', { waitUntil: 'networkidle2' });
    
    // Wait for devices to load
    await page.waitForSelector('.device-card', { timeout: 5000 });
    
    // Get initial number of devices
    const deviceCount = await page.$$eval('.device-card', els => els.length);
    
    // Add a new device
    await page.type('#new-slave-id', '999');
    await page.select('#new-device-type', 'inverter');
    
    // Click add button
    await page.click('button:has-text("Add Device")');
    
    // Wait for new device to appear
    await page.waitForTimeout(1000);
    
    // Check if device count increased
    const newDeviceCount = await page.$$eval('.device-card', els => els.length);
    expect(newDeviceCount).toBe(deviceCount + 1);
  });
});

// Test Case: "Log functionality"
describe('Log functionality', () => {
  test('should display log entries with correct formatting', async () => {
    await page.goto('http://localhost:3000', { waitUntil: 'networkidle2' });
    
    // Wait for log container
    await page.waitForSelector('.log-container');
    
    // Check if log entries have correct structure
    const logEntries = await page.$$eval('.log-entry', els => 
      els.map(el => ({
        timestamp: el.querySelector('.timestamp')?.textContent || '',
        type: el.querySelector('.type')?.textContent || '',
        message: el.querySelector('.message')?.textContent || ''
      }))
    );
    
    // Should have at least one log entry
    expect(logEntries.length).toBeGreaterThan(0);
    
    // Check first log entry has correct format
    if (logEntries.length > 0) {
      expect(logEntries[0].timestamp).toMatch(/\[\d{2}:\d{2}:\d{2}\]/);
      expect(logEntries[0].type).toMatch(/\[[A-Z]+\]/);
    }
  });
});
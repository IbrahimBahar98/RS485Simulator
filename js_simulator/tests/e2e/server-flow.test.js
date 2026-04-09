const puppeteer = require('puppeteer');

// Mock WebSocket for testing environment
const mockWebSocket = {
  send: jest.fn(),
  close: jest.fn()
};

global.WebSocket = jest.fn().mockImplementation(() => mockWebSocket);

// Mock fetch for WebSocket connection
global.fetch = jest.fn();

// Mock window.location
Object.defineProperty(window, 'location', {
  value: {
    href: 'http://localhost:5173'
  }
});

describe('End-to-End Server Flow Test', () => {
  let browser;
  let page;

  beforeAll(async () => {
    // Launch Puppeteer browser in headless mode
    browser = await puppeteer.launch({
      headless: true,
      args: ['--no-sandbox', '--disable-setuid-sandbox']
    });
    page = await browser.newPage();
  });

  afterAll(async () => {
    await browser.close();
  });

  it('should complete all critical user flows in a real browser', async () => {
    // Navigate to http://localhost:5173
    await page.goto('http://localhost:5173');
    
    // Click "Start Server" button
    await page.click('button:has-text("Start Server")');
    
    // Wait for status badge to show "RUNNING"
    await page.waitForSelector('span:has-text("RUNNING")');
    
    // Click "Add Device"
    await page.click('button:has-text("Add Device")');
    
    // Fill form with slaveId=3, type=inverter
    await page.type('input[name="slaveId"]', '3');
    await page.select('select[name="type"]', 'inverter');
    
    // Submit form
    await page.click('button:has-text("Add Device")');
    
    // Click "Set Register"
    await page.click('button:has-text("Set Register")');
    
    // Input address=0x3000, value=100
    await page.type('input[name="address"]', '0x3000');
    await page.type('input[name="value"]', '100');
    
    // Submit form
    await page.click('button:has-text("Set Register")');
    
    // Verify log panel contains [INFO] Set register 0x3000 to 100 for device 3
    await page.waitForSelector('div.log-panel:has-text("[INFO] Set register 0x3000 to 100 for device 3")');
  });
});
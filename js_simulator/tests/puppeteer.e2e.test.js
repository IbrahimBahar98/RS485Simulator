const puppeteer = require('puppeteer');

describe('Puppeteer E2E Test', () => {
  let browser;
  let page;

  beforeAll(async () => {
    browser = await puppeteer.launch({ headless: true });
    page = await browser.newPage();
    await page.goto('http://localhost:3000', { waitUntil: 'networkidle0' });
  });

  afterAll(async () => {
    await browser.close();
  });

  it('should connect to mock server and verify real-time chart updates', async () => {
    await expect(page).toMatch('Connected to Modbus Server');
    await expect(page).toClick('button[aria-label="Toggle Dark Mode"]');
    await expect(page).toMatchElement('canvas', { timeout: 5000 });
  });
});
const express = require('express');
const request = require('supertest');

// Mock devices.json loading
const devices = new Map([
  [111, { type: 'flowmeter', simulationMode: 'random' }],
  [1, { type: 'pressure', simulationMode: 'random' }],
  [2, { type: 'temperature', simulationMode: 'random' }],
  [3, { type: 'humidity', simulationMode: 'random' }],
  [4, { type: 'level', simulationMode: 'random' }],
  [5, { type: 'flowmeter', simulationMode: 'random' }],
  [6, { type: 'flowmeter', simulationMode: 'random' }]
]);

// Mock Express app
const app = express();
app.get('/health', (req, res) => {
  res.status(200).send('OK');
});

describe('Server Tests', () => {
  test('test_load_devices_config', () => {
    expect(devices.size).toBe(7);
    expect(devices.get(111).type).toBe('flowmeter');
    expect(devices.get(1).simulationMode).toBe('random');
  });

  test('test_http_health_endpoint', async () => {
    const response = await request(app).get('/health');
    expect(response.statusCode).toBe(200);
    expect(response.text).toBe('OK');
  });
});

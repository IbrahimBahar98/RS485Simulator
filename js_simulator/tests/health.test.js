const request = require('supertest');
const express = require('express');
const healthRoutes = require('../src/routes/health');

const app = express();
app.use('/health', healthRoutes);

describe('Health Endpoint', () => {
  test('GET /health returns status ok', async () => {
    const response = await request(app).get('/health');
    expect(response.status).toBe(200);
    expect(response.body).toEqual({ status: 'ok' });
  });
});
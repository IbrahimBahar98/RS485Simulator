const request = require('supertest');
const app = require('../src/app'); // assuming app exports Express instance

describe('API Status Endpoint', () => {
  it('should return 200 and correct JSON for /api/status', async () => {
    const response = await request(app).get('/api/status');
    expect(response.statusCode).toBe(200);
    expect(response.body.status).toBe('running');
  });
});

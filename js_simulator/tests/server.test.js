// Jest test setup for server.js
const request = require('supertest');
const express = require('express');

let app;

beforeEach(() => {
    app = express();
    require('../server')(app); // Assuming server.js exports a function to initialize the app
});

describe('GET /api/ports', () => {
    it('should return a list of serial ports', async () => {
        const res = await request(app).get('/api/ports');
        expect(res.statusCode).toEqual(200);
        expect(Array.isArray(res.body)).toBeTruthy();
    });
});

const request = require('supertest');
const { Server } = require('socket.io');
const http = require('http');
const serverModule = require('../server');

let server;
let io;

beforeAll((done) => {
    const app = http.createServer();
    io = new Server(app);
    server = serverModule.start(app, io, () => {
        done();
    });
});

afterAll((done) => {
    server.close(() => {
        io.close();
        done();
    });
});

describe('GET /api/ports', () => {
    it('should return a list of available serial ports', async () => {
        const response = await request(server).get('/api/ports');
        expect(response.status).toBe(200);
        expect(Array.isArray(response.body)).toBe(true);
    });
});

describe('Modbus RTU Server', () => {
    it('should handle a connection event', (done) => {
        const clientSocket = require('socket.io-client')('http://localhost:3001');
        clientSocket.on('connect', () => {
            clientSocket.disconnect();
            done();
        });
    });
});

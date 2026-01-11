const express = require('express');
const http = require('http');
const { Server } = require('socket.io');
const ModbusRTU = require('modbus-serial');
const { SerialPort } = require('serialport');
const path = require('path');

// --- Configuration ---
const APP_PORT = 3000;

// --- State ---
const registers = new Uint16Array(65536); // Full 64k address space
let modbusServer = null;
let isRunning = false;

// Pre-populate defaults (FR500A)
const defaults = {
    0x3000: 5000, 0x0300: 5000, // Freq
    0x3002: 2200, 0x0302: 2200, // Volt
    0x3003: 50,   0x0303: 50,   // Curr
    0x3004: 11,   0x0304: 11,   // Power
    0x3005: 1450, 0x0305: 1450, // Speed
    0x3006: 3100, 0x0306: 3100, // Bus
    0x3017: 350,  0x0317: 350,  // Temp
    0x3023: 999,  0x0323: 999   // Energy
};
for (const [addr, val] of Object.entries(defaults)) {
    registers[parseInt(addr)] = val;
}

// --- Express & Socket.io ---
const app = express();
const server = http.createServer(app);
const io = new Server(server);

app.use(express.static(path.join(__dirname, 'public')));

app.get('/api/ports', async (req, res) => {
    try {
        const ports = await SerialPort.list();
        res.json(ports.map(p => p.path));
    } catch (e) {
        res.status(500).json({ error: e.message });
    }
});

// --- Modbus Vector Hook ---
const vector = {
    getInputRegister: function(addr, unitID) {
        return registers[addr];
    },
    getHoldingRegister: function(addr, unitID) {
        return registers[addr];
    },
    getCoil: function(addr, unitID) {
        return registers[addr] > 0;
    },
    setRegister: function(addr, value, unitID) {
        // Update Memory
        registers[addr] = value;
        
        // Notify Frontend
        io.emit('reg-update', { addr, val: value });
        io.emit('log', { type: 'RX', msg: `Write ID:${unitID} Addr:0x${addr.toString(16)} Val:${value}` });

        // --- Custom Logic: Stop/Run ---
        if (addr === 0x2000) {
            handleControlCommand(value, unitID);
        }
    },
    setCoil: function(addr, value, unitID) {
        registers[addr] = value ? 1 : 0;
    },
    readDeviceIdentification: function(addr) {
        return {
            0x00: "Simulated Inverter",
            0x01: "1.0",
            0x02: "1.0"
        };
    }
};

function handleControlCommand(val, unitID) {
    if (val === 5 || val === 6 || val === 0) { // Stop/Freewheel
        io.emit('log', { type: 'INFO', msg: `ID:${unitID} STOP Command (0x${val.toString(16)}) -> Zeroing Status` });
        const zeros = [
            0x3000, 0x0300, // Freq
            0x3003, 0x0303, // Curr
            0x3004, 0x0304, // Power
            0x3005, 0x0305, // Speed
        ];
        zeros.forEach(r => {
            registers[r] = 0;
            io.emit('reg-update', { addr: r, val: 0 });
        });
    } else if (val === 1) { // Run
        io.emit('log', { type: 'INFO', msg: `ID:${unitID} RUN Command -> Restoring Defaults` });
        for (const [addr, defVal] of Object.entries(defaults)) {
            // Only restore dynamic values, not configuration
            if ([0x3000, 0x0300, 0x3003, 0x0303, 0x3004, 0x0304, 0x3005, 0x0305].includes(parseInt(addr))) {
                registers[parseInt(addr)] = defVal;
                io.emit('reg-update', { addr: parseInt(addr), val: defVal });
            }
        }
    }
}

// --- Socket Events ---
io.on('connection', (socket) => {
    console.log('Client connected');
    // Send initial state
    // Just send key registers to avoid flooding
    const keyRegs = [
        ...Object.keys(defaults).map(Number), 
        0x2000, 0x8200, 0x0B15
    ];
    const state = {};
    keyRegs.forEach(r => state[r] = registers[r]);
    socket.emit('initial-state', state);

    socket.on('start-server', ({ port, baud }) => {
        if (isRunning) return;
        try {
            console.log(`Starting Modbus Server on ${port} @ ${baud}`);
            // Modbus Server Setup
            modbusServer = new ModbusRTU.ServerSerial(vector, {
                port: port,
                baudRate: parseInt(baud),
                debug: true,
                unitID: 1 // Default, but we need to accept all?
            });
            
            modbusServer.on('socketError', (err) => {
                console.error(err);
                io.emit('log', { type: 'ERR', msg: err.message });
                isRunning = false;
                io.emit('server-status', false);
            });

            // Hack to accept multiple UnitIDs?
            // modbus-serial ServerSerial uses 'modbus-serial/servers/servertcp.js' logic wrapped.
            // It calls vector.getInputRegister(addr, unitID).
            // So creating one server instance should handle requests for ANY unitID 
            // provided the vector function doesn't check 'unitID' strictly.
            // Our vector impl accepts all IDs.
            
            isRunning = true;
            io.emit('server-status', true);
            io.emit('log', { type: 'INFO', msg: `Server Started on ${port}` });
            
        } catch (e) {
            console.error(e);
            io.emit('log', { type: 'ERR', msg: e.message });
        }
    });

    socket.on('set-register', ({ addr, val }) => {
        registers[addr] = val;
        io.emit('reg-update', { addr, val });
        // Handle control logic if set from GUI too
        if (addr === 0x2000) handleControlCommand(val, 0); 
    });
});

server.listen(APP_PORT, () => {
    console.log(`Web Interface running at http://localhost:${APP_PORT}`);
});

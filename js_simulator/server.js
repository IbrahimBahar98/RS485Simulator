const express = require('express');
const http = require('http');
const { Server } = require('socket.io');
const { SerialPort } = require('serialport');
const path = require('path');
const crc = require('crc'); // We'll need a crc lib or impl one.
// Actually, let's implement simple CRC16-Modbus to avoid extra deps if possible,
// or use modbus-serial just for CRC if it exposes it?
// let's just add a simple CRC function.

// --- Configuration ---
const APP_PORT = 3000;

// --- State ---
// Memory map keyed by Unit ID -> Uint16Array(65536)
const memory = {};
// Track which IDs are enabled (respond to Modbus)
const enabledIDs = new Set([1, 2, 3, 4, 5]); // All enabled by default

const defaults = {
    // ===== FR500A/FR510A Complete Register Map =====

    // --- Control Registers (Write-Only) ---
    0x2000: 0,                  // CONTROL_COMMAND (1=Run, 5/6/0=Stop)

    // --- Status Registers (Read-Only) - 0x30xx Range ---
    0x3000: 5000,               // FREQUENCY_RUNNING (x100 Hz = 50.00 Hz)
    0x3002: 2200,               // VOLTAGE_OUTPUT (x10 V = 220.0 V)
    0x3003: 50,                 // CURRENT_OUTPUT (x10 A = 5.0 A)
    0x3004: 11,                 // POWER_OUTPUT (x10 kW = 1.1 kW)
    0x3005: 1450,               // SPEED_MOTOR_ESTIMATED (rpm)
    0x3006: 3100,               // VOLTAGE_BUS (x10 V = 310.0 V DC Bus)
    0x3017: 350,                // TEMPERATURE_INVERTER (x10 °C = 35.0 °C)
    0x3023: 999,                // POWER_CONSUMPTION / TOTAL_ENERGY (kWh)
    0x3100: 0,                  // FAULT_CODE_LATEST (0 = No Fault)

    // --- Parameter Registers (0x8xxx) ---
    0x8000: 0,                  // USER_PASSWORD_SETTING (Write-Only)
    0x8001: 0,                  // DISPLAY_OF_PARAMETERS / PARAMETER_PROTECTION
    0x8006: 0,                  // PARAMETER_EDITING_MODE
    0x8200: 0,                  // START_COMMAND_MODE (0=Keypad, 2=Comm)
    0x840A: 1,                  // DEVICE_ID (Modbus Slave Address)

    // --- Other FR500A Registers ---
    0x0B15: 45,                 // TEMPERATURE_SETPOINT (°C)

    // --- Mirrored Registers (0x03xx = U00 Group for FC04 Input Regs) ---
    0x0300: 5000,               // U00.00 Output Frequency
    0x0302: 2200,               // U00.02 Output Voltage
    0x0303: 50,                 // U00.03 Output Current
    0x0304: 11,                 // U00.04 Output Power
    0x0305: 1450,               // U00.05 Motor Speed
    0x0306: 3100,               // U00.06 Bus Voltage
    0x0317: 350,                // U00.23 Inverter Temperature
    0x0323: 999                 // U00.35 Power Consumption
};

function getMem(unitID) {
    if (!memory[unitID]) {
        memory[unitID] = new Uint16Array(65536);
        // Initialize defaults
        for (const [addr, val] of Object.entries(defaults)) {
            memory[unitID][parseInt(addr)] = val;
        }
    }
    return memory[unitID];
}

// --- CRC16 Modbus Implementation ---
function calculateCRC(buffer) {
    let crc = 0xFFFF;
    for (let pos = 0; pos < buffer.length; pos++) {
        crc ^= buffer[pos];
        for (let i = 8; i !== 0; i--) {
            if ((crc & 0x0001) !== 0) {
                crc >>= 1;
                crc ^= 0xA001;
            } else {
                crc >>= 1;
            }
        }
    }
    return crc;
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

let serialPort = null;
let buffer = Buffer.alloc(0);

// --- Custom RTU Server Logic ---
function processBuffer() {
    // Min Modbus RTU Frame: ID(1) + Func(1) + Data(N) + CRC(2). Min length 4 (e.g. error/poll?)
    // Typically Read Holding is 8 bytes.
    if (buffer.length < 4) return;

    // Check for valid frames.
    // Optimization: Assume traffic is clean or wait for silence (RTU).
    // Simple heuristic: Try to parse valid frame from start.

    // We only care about Function Codes 03 (Read Holding) and 04 (Read Input), 06 (Write Single), 16 (Write Multi)
    // Packet Structure (Read): ID(1) FC(1) StartH(1) StartL(1) CntH(1) CntL(1) CRC(2) = 8 bytes
    // Packet Structure (Write Single): ID(1) FC(1) AddrH(1) AddrL(1) ValH(1) ValL(1) CRC(2) = 8 bytes

    // TODO: Better framing (timeout based). 
    // For now, if we have >= 8 bytes, try to parse.

    if (buffer.length >= 8) {
        // Check CRC of first 8 bytes
        const frame = buffer.subarray(0, 8);
        const receivedCRC = frame.readUInt16LE(6);
        const calcCRC = calculateCRC(frame.subarray(0, 6));

        if (receivedCRC === calcCRC) {
            handleFrame(frame);
            buffer = buffer.subarray(8); // Consume
            processBuffer();
            return;
        }
    }

    // Check for Write Multiple (FC 16)
    // ID(1) FC(1) Start(2) Cnt(2) Bytes(1) Data(N) CRC(2)
    if (buffer.length > 9) {
        const fc = buffer[1];
        if (fc === 16) {
            const byteCnt = buffer[6];
            const totalLen = 9 + byteCnt;
            if (buffer.length >= totalLen) {
                const frame = buffer.subarray(0, totalLen);
                const receivedCRC = frame.readUInt16LE(totalLen - 2);
                const calcCRC = calculateCRC(frame.subarray(0, totalLen - 2));

                if (receivedCRC === calcCRC) {
                    handleFrame(frame);
                    buffer = buffer.subarray(totalLen);
                    processBuffer();
                    return;
                }
            }
        }
    }

    // Garbage collection: if buffer too big, trim?
    if (buffer.length > 256) buffer = Buffer.alloc(0);
}

function handleFrame(frame) {
    const unitID = frame[0];
    const fc = frame[1];

    // Skip if this ID is disabled
    if (!enabledIDs.has(unitID)) {
        io.emit('log', { type: 'INFO', msg: `ID:${unitID} is DISABLED - ignoring request` });
        return;
    }

    const mem = getMem(unitID); // Get/Create memory for THIS ID

    // We accept ALL enabled UnitIDs

    let response = null;

    if (fc === 3 || fc === 4) { // Read Holding/Input
        const addr = frame.readUInt16BE(2);
        const count = frame.readUInt16BE(4);

        io.emit('log', { type: 'RX', msg: `Read ID:${unitID} FC:${fc} Addr:0x${addr.toString(16)} Len:${count}` });

        // Build Response: ID(1) FC(1) Bytes(1) Data(N*2) CRC(2)
        const bytes = count * 2;
        const respLen = 3 + bytes + 2;
        response = Buffer.alloc(respLen);
        response.writeUInt8(unitID, 0);
        response.writeUInt8(fc, 1);
        response.writeUInt8(bytes, 2);

        for (let i = 0; i < count; i++) {
            const val = mem[addr + i] || 0;
            response.writeUInt16BE(val, 3 + (i * 2));
        }

        const crcVal = calculateCRC(response.subarray(0, respLen - 2));
        response.writeUInt16LE(crcVal, respLen - 2);

    } else if (fc === 6) { // Write Single
        const addr = frame.readUInt16BE(2);
        const val = frame.readUInt16BE(4);

        mem[addr] = val;
        io.emit('reg-update', { id: unitID, addr, val }); // Broadcast ID
        io.emit('log', { type: 'RX', msg: `Write ID:${unitID} Addr:0x${addr.toString(16)} Val:${val}` });

        // Handle Logic
        if (addr === 0x2000) handleControlCommand(val, unitID);

        // Handle Parameter Writes (FR500A Protection Sequence)
        handleParameterWrite(addr, val, unitID);

        // Echo Request as Response
        response = Buffer.from(frame);

    } else if (fc === 16) { // Write Multi
        const addr = frame.readUInt16BE(2);
        const count = frame.readUInt16BE(4);
        const byteCount = frame.readUInt8(6);
        const data = frame.subarray(7, 7 + byteCount);

        io.emit('log', { type: 'RX', msg: `WriteMulti ID:${unitID} Addr:0x${addr.toString(16)} Count:${count}` });

        for (let i = 0; i < count; i++) {
            const val = data.readUInt16BE(i * 2);
            mem[addr + i] = val;
            io.emit('reg-update', { id: unitID, addr: addr + i, val });
            if ((addr + i) === 0x2000) handleControlCommand(val, unitID);
            handleParameterWrite(addr + i, val, unitID);
        }

        // Response: ID(1) FC(1) Addr(2) Count(2) CRC(2)
        response = Buffer.alloc(8);
        response.writeUInt8(unitID, 0);
        response.writeUInt8(fc, 1);
        response.writeUInt16BE(addr, 2);
        response.writeUInt16BE(count, 4);
        const crcVal = calculateCRC(response.subarray(0, 6));
        response.writeUInt16LE(crcVal, 6);
    }

    if (response) {
        // Log TX? High volume.
        // io.emit('log', { type: 'TX', msg: `Resp ID:${unitID} Len:${response.length}` });
        serialPort.write(response);
    }
}

function handleControlCommand(val, unitID) {
    const mem = getMem(unitID);
    if (val === 5 || val === 6 || val === 0) { // Stop
        io.emit('log', { type: 'INFO', msg: `ID:${unitID} STOP Command` });
        const zeros = [0x3000, 0x0300, 0x3003, 0x0303, 0x3004, 0x0304, 0x3005, 0x0305];
        zeros.forEach(r => {
            mem[r] = 0;
            io.emit('reg-update', { id: unitID, addr: r, val: 0 });
        });
    } else if (val === 1) { // Run
        io.emit('log', { type: 'INFO', msg: `ID:${unitID} RUN Command` });
        [0x3000, 0x0300, 0x3003, 0x0303, 0x3004, 0x0304, 0x3005, 0x0305].forEach(r => {
            mem[r] = defaults[r];
            io.emit('reg-update', { id: unitID, addr: r, val: defaults[r] });
        });
    }
}

// Handle FR500A Parameter Writes (Protection Sequence)
function handleParameterWrite(addr, val, unitID) {
    const paramNames = {
        0x8000: 'PASSWORD',
        0x8001: 'DISPLAY_PARAMS',
        0x8006: 'PARAM_EDIT_MODE',
        0x8200: 'START_CMD_MODE',
        0x840A: 'DEVICE_ID'
    };

    if (paramNames[addr]) {
        const name = paramNames[addr];
        let detail = '';

        // Interpret values
        if (addr === 0x8200) {
            detail = val === 0 ? ' (Keypad)' : val === 2 ? ' (RS485/Comm)' : ` (${val})`;
        } else if (addr === 0x8001) {
            detail = val === 1 ? ' (Display Only)' : ` (${val})`;
        } else if (addr === 0x8006) {
            detail = val === 2 ? ' (RS485 Only Editing)' : ` (${val})`;
        }

        io.emit('log', { type: 'INFO', msg: `ID:${unitID} ${name} = ${val}${detail}` });
    }
}

// --- Socket Events ---
io.on('connection', (socket) => {
    // Send state for requested IDs? 
    // Or just all known? Let's send everything we have in memory.
    // Client can filter.
    const allData = {};
    for (const id in memory) {
        const keyRegs = [...Object.keys(defaults).map(Number), 0x2000, 0x8200, 0x0B15];
        allData[id] = {};
        keyRegs.forEach(r => allData[id][r] = memory[id][r]);
    }
    socket.emit('initial-state', allData);

    socket.on('start-server', ({ port, baud }) => {
        if (serialPort && serialPort.isOpen) return;
        try {
            console.log(`Starting Custom Modbus Server on ${port} @ ${baud}`);
            serialPort = new SerialPort({ path: port, baudRate: parseInt(baud) });

            serialPort.on('data', (data) => {
                buffer = Buffer.concat([buffer, data]);
                processBuffer();
            });

            serialPort.on('error', (err) => {
                console.error(err);
                io.emit('log', { type: 'ERR', msg: err.message });
                io.emit('server-status', false);
            });

            serialPort.on('open', () => {
                io.emit('server-status', true);
                io.emit('log', { type: 'INFO', msg: `Server Started on ${port}` });
            });

            serialPort.on('close', () => {
                console.log('Serial port closed');
                io.emit('server-status', false);
                io.emit('log', { type: 'INFO', msg: 'Serial port closed' });
            });

        } catch (e) {
            console.error(e);
            io.emit('log', { type: 'ERR', msg: e.message });
        }
    });

    socket.on('stop-server', () => {
        if (serialPort && serialPort.isOpen) {
            serialPort.close((err) => {
                if (err) {
                    io.emit('log', { type: 'ERR', msg: err.message });
                } else {
                    io.emit('server-status', false);
                    io.emit('log', { type: 'INFO', msg: 'Server Stopped' });
                    console.log('Modbus Server Stopped');
                }
            });
            buffer = Buffer.alloc(0); // Clear buffer
        }
    });

    socket.on('set-register', ({ id, addr, val }) => {
        // ID is required now
        const targetID = id || 1;
        const mem = getMem(targetID);
        mem[addr] = val;
        io.emit('reg-update', { id: targetID, addr, val });
        if (addr === 0x2000) handleControlCommand(val, targetID);
    });

    socket.on('toggle-inverter', ({ id, enabled }) => {
        if (enabled) {
            enabledIDs.add(id);
            io.emit('log', { type: 'INFO', msg: `Inverter ${id} ENABLED` });
        } else {
            enabledIDs.delete(id);
            io.emit('log', { type: 'INFO', msg: `Inverter ${id} DISABLED` });
        }
        io.emit('inverter-status', { id, enabled });
    });

    socket.on('get-inverter-status', () => {
        const status = {};
        [1, 2, 3, 4, 5].forEach(id => status[id] = enabledIDs.has(id));
        socket.emit('all-inverter-status', status);
    });
});

server.listen(APP_PORT, () => {
    console.log(`Web Interface running at http://localhost:${APP_PORT}`);
});

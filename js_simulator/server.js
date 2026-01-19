const express = require('express');
const http = require('http');
const { Server } = require('socket.io');
const { SerialPort } = require('serialport');
const path = require('path');
const fs = require('fs');
const crc = require('crc'); // We'll need a crc lib or impl one.
// Actually, let's implement simple CRC16-Modbus to avoid extra deps if possible,
// or use modbus-serial just for CRC if it exposes it?
// let's just add a simple CRC function.

// --- Configuration ---
const APP_PORT = 3000;
const DEVICES_CONFIG_FILE = path.join(__dirname, 'devices.json');
const MEMORY_CONFIG_FILE = path.join(__dirname, 'memory.json');

// --- State ---
// Dynamic device management: Map<slaveId, {type: 'inverter'|'flowmeter'|'energymeter', enabled: boolean}>
let devices = new Map([
    [1, { type: 'inverter', enabled: true }],
    [2, { type: 'inverter', enabled: true }],
    [3, { type: 'inverter', enabled: true }],
    [4, { type: 'inverter', enabled: true }],
    [5, { type: 'inverter', enabled: true }],
    // Python script compatibility: Auto-add Slave 100 and 111 for Flow Meter testing
    [110, { type: 'flowmeter', enabled: true }],
    [111, { type: 'flowmeter', enabled: true }]
]);
// Memory map keyed by Unit ID -> Uint16Array(65536)
const memory = {};

// --- Persistence Functions ---
function loadDevicesConfig() {
    try {
        if (fs.existsSync(DEVICES_CONFIG_FILE)) {
            const data = fs.readFileSync(DEVICES_CONFIG_FILE, 'utf8');
            const config = JSON.parse(data);
            devices.clear();
            // Load saved devices
            for (const [idStr, deviceData] of Object.entries(config.devices)) {
                devices.set(parseInt(idStr), deviceData);
            }
            console.log(`Loaded ${devices.size} devices from ${DEVICES_CONFIG_FILE}`);
        } else {
            console.log(`No devices config file found. Using defaults.`);
        }
    } catch (err) {
        console.error(`Error loading devices config: ${err.message}`);
    }
}

function saveDevicesConfig() {
    try {
        const config = {
            devices: {}
        };
        // Convert Map to object for JSON serialization
        for (const [id, deviceData] of devices.entries()) {
            config.devices[id.toString()] = deviceData;
        }
        fs.writeFileSync(DEVICES_CONFIG_FILE, JSON.stringify(config, null, 2), 'utf8');
        console.log(`Saved ${devices.size} devices to ${DEVICES_CONFIG_FILE}`);
    } catch (err) {
        console.error(`Error saving devices config: ${err.message}`);
    }
}

function loadMemoryConfig() {
    try {
        if (fs.existsSync(MEMORY_CONFIG_FILE)) {
            const data = fs.readFileSync(MEMORY_CONFIG_FILE, 'utf8');
            const config = JSON.parse(data);
            // Load memory for each device
            for (const [idStr, memData] of Object.entries(config.memory || {})) {
                const id = parseInt(idStr);
                if (!memory[id]) {
                    memory[id] = new Uint16Array(65536);
                }
                // Restore memory values
                const values = memData.values || {};
                for (const [addrStr, val] of Object.entries(values)) {
                    memory[id][parseInt(addrStr)] = val;
                }
            }
            console.log(`Loaded memory config from ${MEMORY_CONFIG_FILE}`);
        }
    } catch (err) {
        console.error(`Error loading memory config: ${err.message}`);
    }
}

function saveMemoryConfig() {
    try {
        const config = {
            memory: {}
        };
        // Save non-zero memory values for each device
        for (const [id, memArray] of Object.entries(memory)) {
            const values = {};
            for (let addr = 0; addr < memArray.length; addr++) {
                if (memArray[addr] !== 0) {
                    values[addr.toString()] = memArray[addr];
                }
            }
            if (Object.keys(values).length > 0) {
                config.memory[id] = { values };
            }
        }
        fs.writeFileSync(MEMORY_CONFIG_FILE, JSON.stringify(config, null, 2), 'utf8');
        console.log(`Saved memory config to ${MEMORY_CONFIG_FILE}`);
    } catch (err) {
        console.error(`Error saving memory config: ${err.message}`);
    }
}

// Load devices on startup
loadDevicesConfig();
loadMemoryConfig();

// Legacy compatibility helpers
function getEnabledIDs() {
    return [...devices.entries()].filter(([_, d]) => d.enabled).map(([id, _]) => id);
}
function isDeviceEnabled(id) {
    const device = devices.get(id);
    return device ? device.enabled : false;
}
function getDeviceType(id) {
    const device = devices.get(id);
    return device ? device.type : 'inverter';
}

// ===== INVERTER (FR500A/FR510A) Register Defaults =====
const inverterDefaults = {
    // Control Registers (Write-Only)
    0x2000: 0,                  // CONTROL_COMMAND (1=Run, 5/6/0=Stop)

    // Status Registers (Read-Only) - 0x30xx Range
    0x3000: 5000,               // FREQUENCY_RUNNING (x100 Hz = 50.00 Hz)
    0x3002: 2200,               // VOLTAGE_OUTPUT (x10 V = 220.0 V)
    0x3003: 50,                 // CURRENT_OUTPUT (x10 A = 5.0 A)
    0x3004: 11,                 // POWER_OUTPUT (x10 kW = 1.1 kW)
    0x3005: 1450,               // SPEED_MOTOR_ESTIMATED (rpm)
    0x3006: 3100,               // VOLTAGE_BUS (x10 V = 310.0 V DC Bus)
    0x3017: 350,                // TEMPERATURE_INVERTER (x10 °C = 35.0 °C)
    0x3023: 999,                // POWER_CONSUMPTION / TOTAL_ENERGY (kWh)
    0x3100: 0,                  // FAULT_CODE_LATEST (0 = No Fault)

    // Parameter Registers (0x8xxx)
    0x8000: 0,                  // USER_PASSWORD_SETTING (Write-Only)
    0x8001: 0,                  // DISPLAY_OF_PARAMETERS / PARAMETER_PROTECTION
    0x8006: 0,                  // PARAMETER_EDITING_MODE
    0x8200: 0,                  // START_COMMAND_MODE (0=Keypad, 2=Comm)
    0x840A: 1,                  // DEVICE_ID (Modbus Slave Address)

    // Other FR500A Registers
    0x0B15: 45,                 // TEMPERATURE_SETPOINT (°C)

    // Mirrored Registers (0x03xx = U00 Group for FC04 Input Regs)
    0x0300: 5000,               // U00.00 Output Frequency
    0x0302: 2200,               // U00.02 Output Voltage
    0x0303: 50,                 // U00.03 Output Current
    0x0304: 11,                 // U00.04 Output Power
    0x0305: 1450,               // U00.05 Motor Speed
    0x0306: 3100,               // U00.06 Bus Voltage
    0x0317: 350,                // U00.23 Inverter Temperature
    0x0323: 999                 // U00.35 Power Consumption
};

// ===== FLOW METER (CR009) Register Defaults =====
const flowMeterDefaults = {
    // Input Registers (FC 04) - Flow Meter Readings
    772: 0,                     // Forward Total (Word 0 - MSW)
    773: 0,                     // Forward Total (Word 1 - LSW)
    774: 0x0403,                // Unit Info (Total=L, Flow=L/s)
    777: 0,                     // Alarm Flags (bitfield)
    778: 0,                     // Flow Rate (Word 0 - MSW) - Float
    779: 0,                     // Flow Rate (Word 1 - LSW)
    786: 0,                     // Forward Overflow Count
    812: 0,                     // Conductivity (Word 0 - MSW) - Float
    813: 0,                     // Conductivity (Word 1 - LSW)

    // Holding Registers (FC 03) - Configuration
    261: 0x43D4,                // Flow Range MSW (424.0 float)
    262: 0x0000,                // Flow Range LSW
    281: 0x42C8,                // Alarm High MSW (100.0 float)
    282: 0x0000,                // Alarm High LSW
    284: 0x4120,                // Alarm Low MSW (10.0 float)
    285: 0x0000                 // Alarm Low LSW
};

// ===== ENERGY METER (ADL400) Register Defaults =====
const energyMeterDefaults = {
    // Voltage Registers (Input Registers - FC 04) - Default 0
    0x0800: 0x0000,             // Phase A Voltage
    0x0802: 0x0000,             // Phase B Voltage
    0x0804: 0x0000,             // Phase C Voltage

    // Current Registers (Input Registers - FC 04) - Default 0
    0x080C: 0x0000,             // Phase A Current
    0x080E: 0x0000,             // Phase B Current
    0x0810: 0x0000,             // Phase C Current

    // Active Power Registers (Input Registers - FC 04) - Default 0
    0x0806: 0x0000,             // Phase A Active Power
    0x0808: 0x0000,             // Phase B Active Power
    0x080A: 0x0000,             // Phase C Active Power
    0x060A: 0x0000,             // Total Active Power

    // Power Factor - Default 1.0 (0x3F80 in IEEE 754 = 1.0)
    0x082E: 0x3F80,             // Phase A Power Factor = 1.0
    0x0830: 0x3F80,             // Phase B Power Factor = 1.0
    0x0832: 0x3F80,             // Phase C Power Factor = 1.0

    // Frequency - Default 0
    0x0834: 0x0032,             // Frequency

    // Energy Registers (Input Registers - FC 04) - Default 0
    0x0842: 0x0000,             // Total Active Energy MSW
    0x0844: 0x0000,             // Total Active Energy LSW
    
    0x0846: 0x0000,             // Total Reactive Energy MSW
    0x0848: 0x0000,             // Total Reactive Energy LSW

    // Import/Export Energy - Default 0
    0x0864: 0x0000,             // Total Import Active Energy MSW
    0x0866: 0x0000,             // Total Import Active Energy LSW
    
    0x0868: 0x0000,             // Total Export Active Energy MSW
    0x086A: 0x0000,             // Total Export Active Energy LSW

    // Process Archives (Frozen Values) - Default 0
    0x6002: 0x0000,             // Daily Total Active Energy MSW
    0x6004: 0x0000,             // Daily Total Active Energy LSW
    
    0x7002: 0x0000,             // Monthly Total Active Energy MSW
    0x7004: 0x0000,             // Monthly Total Active Energy LSW

    // Configuration Registers (Holding Registers - FC 03)
    0x008D: 0x0001,             // PT Ratio = 1
    0x008E: 0x0001,             // CT Ratio = 1
    0x0100: 0x0000,             // Device Address
    0x0101: 0x0000,             // Baud Rate
    0x0102: 0x0000,             // Power on Times
    0x0103: 0x0000              // Device Status
};

// Keep defaults reference for backward compatibility
const defaults = inverterDefaults;

function getMem(unitID) {
    if (!memory[unitID]) {
        memory[unitID] = new Uint16Array(65536);
        // Initialize based on device type
        const type = getDeviceType(unitID);
        let defs = inverterDefaults;
        if (type === 'flowmeter') defs = flowMeterDefaults;
        if (type === 'energymeter') defs = energyMeterDefaults;
        for (const [addr, val] of Object.entries(defs)) {
            memory[unitID][parseInt(addr)] = val;
        }
    }
    return memory[unitID];
}

// Add a new device
function addDevice(slaveId, type = 'inverter') {
    if (devices.has(slaveId)) {
        return { success: false, error: 'Device with this Slave ID already exists' };
    }
    devices.set(slaveId, { type, enabled: true });
    // Initialize memory for this device
    memory[slaveId] = new Uint16Array(65536);
    let defs = inverterDefaults;
    if (type === 'flowmeter') defs = flowMeterDefaults;
    if (type === 'energymeter') defs = energyMeterDefaults;
    for (const [addr, val] of Object.entries(defs)) {
        memory[slaveId][parseInt(addr)] = val;
    }
    saveDevicesConfig(); // Save to file
    return { success: true };
}

// Remove a device
function removeDevice(slaveId) {
    if (!devices.has(slaveId)) {
        return { success: false, error: 'Device not found' };
    }
    devices.delete(slaveId);
    delete memory[slaveId];
    saveDevicesConfig(); // Save to file
    return { success: true };
}

// Update device type
function setDeviceType(unitID, type) {
    const device = devices.get(unitID);
    if (device) {
        device.type = type;
        devices.set(unitID, device);
    }
    // Clear and reinitialize memory for this unit
    memory[unitID] = new Uint16Array(65536);
    let defs = inverterDefaults;
    if (type === 'flowmeter') defs = flowMeterDefaults;
    if (type === 'energymeter') defs = energyMeterDefaults;
    for (const [addr, val] of Object.entries(defs)) {
        memory[unitID][parseInt(addr)] = val;
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
    let start = 0;
    while (start + 4 <= buffer.length) { // 4 is min Modbus frame size
        // 1. Peek at potential header
        const unitID = buffer[start];
        const fc = buffer[start + 1];

        // Quick validation of UnitID and FC
        // We only support specific FCs for this sim
        if (![3, 4, 6, 16].includes(fc)) {
            start++;
            continue;
        }

        // 2. Determine expected frame length
        let len = 0;
        if (fc === 3 || fc === 4 || fc === 6) {
            len = 8; // Fixed length for Read/Write Single
        } else if (fc === 16) {
            // Write Multi: ID(1) FC(1) Addr(2) Cnt(2) ByteCnt(1) Data(N) CRC(2)
            // Minimum head for FC16 is 7 bytes (to read ByteCnt)
            if (start + 7 > buffer.length) {
                // Not enough data yet to determine length, stop and wait
                break;
            }
            const byteCnt = buffer[start + 6];
            len = 9 + byteCnt;
        }

        // 3. Check if we have enough data
        if (start + len > buffer.length) {
            // Wait for more data
            break;
        }

        // 4. Verify CRC
        const frame = buffer.subarray(start, start + len);
        const receivedCRC = frame.readUInt16LE(len - 2);
        const calcCRC = calculateCRC(frame.subarray(0, len - 2));

        if (receivedCRC === calcCRC) {
            // VALID FRAME FRAME
            handleFrame(frame);
            // Consume this frame
            start += len;
            // Update main buffer status immediately to avoid reprocessing
            buffer = buffer.subarray(start);
            start = 0; // Restart from new beginning
            continue; // Continue processing remaining buffer
        } else {
            // CRC failed, this is not a valid frame start
            // Shift by 1 byte and try again
            start++;
        }
    }

    // Trim consumed garbage
    if (start > 0) {
        buffer = buffer.subarray(start);
    }

    // Safety Cap to prevent infinite memory growth if no valid frames ever arrive
    if (buffer.length > 1024) {
        io.emit('log', { type: 'INFO', msg: 'Buffer overflow - flushing' });
        buffer = Buffer.alloc(0);
    }
}

function handleFrame(frame) {
    const unitID = frame[0];
    const fc = frame[1];

    // Skip if this device doesn't exist or is disabled
    if (!devices.has(unitID)) {
        // Silently ignore - device not configured
        return;
    }
    if (!isDeviceEnabled(unitID)) {
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
        // Log TX to help user verify response
        const hex = response.toString('hex').toUpperCase();
        io.emit('log', { type: 'TX', msg: `Resp ID:${unitID} Data:${hex}` });
        serialPort.write(response);
    }
}

function handleControlCommand(val, unitID) {
    io.emit('log', { type: 'INFO', msg: `ID:${unitID} Control Cmd: 0x${val.toString(16)} (${val})` });
    const mem = getMem(unitID);

    // Registers to update (Freq, Volt, Current, Power, Speed, Energy) + Mirrored U00 group
    const regs = [
        0x3000, 0x0300, // Frequency
        0x3002, 0x0302, // Output Voltage
        0x3003, 0x0303, // Output Current
        0x3004, 0x0304, // Output Power
        0x3005, 0x0305, // Motor Speed
        0x3023, 0x0323  // Energy
    ];

    const updates = {};

    if (val === 5 || val === 6 || val === 0) { // Stop
        io.emit('log', { type: 'INFO', msg: `ID:${unitID} STOP Command` });
        regs.forEach(r => {
            mem[r] = 0;
            updates[r] = 0;
        });
    } else if (val === 1) { // Run
        io.emit('log', { type: 'INFO', msg: `ID:${unitID} RUN Command` });

        // Calculate values based on Inverter ID to make testing easier
        const id = unitID;
        const values = {
            // Freq (0x3000): x100 Hz. ID=1 -> 10Hz -> 1000
            0x3000: id * 10 * 100,
            0x0300: id * 10 * 100,

            // Volt (0x3002): x10 V. ID=1 -> 110V -> 1100. (100 + 10*ID)
            0x3002: (100 + id * 10) * 10,
            0x0302: (100 + id * 10) * 10,

            // Current (0x3003): x10 A. ID=1 -> 1A -> 10
            0x3003: id * 10,
            0x0303: id * 10,

            // Power (0x3004): x10 kW. ID=1 -> 1kW -> 10
            0x3004: id * 10,
            0x0304: id * 10,

            // Speed (0x3005): RPM. ID=1 -> 100 RPM?
            0x3005: id * 100,
            0x0305: id * 100,

            // Energy (0x3023): kWh. ID=1 -> 1
            0x3023: id,
            0x0323: id
        };

        regs.forEach(r => {
            const newVal = values[r] !== undefined ? values[r] : 0;
            mem[r] = newVal;
            updates[r] = newVal;
        });
    }

    // Emit batch update if any changes
    if (Object.keys(updates).length > 0) {
        io.emit('regs-update-batch', { id: unitID, updates });
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
    // Send current devices list to new client
    socket.emit('devices-list', getDevicesList());

    // Also send register state for each device
    for (const [slaveId, device] of devices) {
        const mem = getMem(slaveId);
        const defs = device.type === 'flowmeter' ? flowMeterDefaults : inverterDefaults;
        const regData = {};
        for (const addr of Object.keys(defs)) {
            regData[parseInt(addr)] = mem[parseInt(addr)];
        }
        socket.emit('device-state', { id: slaveId, type: device.type, registers: regData });
    }

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
        saveMemoryConfig(); // Save memory changes
        io.emit('reg-update', { id: targetID, addr, val });
        if (addr === 0x2000) handleControlCommand(val, targetID);
    });

    socket.on('toggle-inverter', ({ id, enabled }) => {
        const device = devices.get(id);
        if (device) {
            device.enabled = enabled;
            devices.set(id, device);
            saveDevicesConfig(); // Save to file
            io.emit('log', { type: 'INFO', msg: `Device ${id} ${enabled ? 'ENABLED' : 'DISABLED'}` });
            io.emit('device-updated', { id, ...device });
        }
    });

    socket.on('get-register', ({ id, addr }) => {
        const mem = getMem(id || 1);
        const val = mem[addr] || 0;
        socket.emit('register-value', { id, addr, val });
    });


    socket.on('get-inverter-status', () => {
        const status = {};
        for (const [id, device] of devices) {
            status[id] = device.enabled;
        }
        socket.emit('all-inverter-status', status);
    });

    // Device type management
    socket.on('set-device-type', ({ id, type }) => {
        const device = devices.get(id);
        if (device) {
            const oldType = device.type;
            setDeviceType(id, type);
            saveDevicesConfig(); // Save to file
            io.emit('log', { type: 'INFO', msg: `Device ${id} changed from ${oldType} to ${type}` });
            io.emit('device-updated', { id, ...devices.get(id) });

            // Send the new register state for this device
            const mem = getMem(id);
            const defs = type === 'flowmeter' ? flowMeterDefaults : inverterDefaults;
            const regData = {};
            for (const addr of Object.keys(defs)) {
                regData[parseInt(addr)] = mem[parseInt(addr)];
            }
            socket.emit('device-state', { id, type, registers: regData });
        }
    });

    socket.on('get-device-types', () => {
        const types = {};
        for (const [id, device] of devices) {
            types[id] = device.type;
        }
        socket.emit('all-device-types', types);
    });

    // Dynamic device management
    socket.on('add-device', ({ slaveId, type }) => {
        const result = addDevice(parseInt(slaveId), type);
        if (result.success) {
            io.emit('log', { type: 'INFO', msg: `Added ${type} device with Slave ID ${slaveId}` });
            io.emit('device-added', { slaveId: parseInt(slaveId), type, enabled: true });
            io.emit('devices-list', getDevicesList());
        } else {
            socket.emit('error', { message: result.error });
            io.emit('log', { type: 'ERR', msg: result.error });
        }
    });

    socket.on('remove-device', ({ slaveId }) => {
        const result = removeDevice(parseInt(slaveId));
        if (result.success) {
            io.emit('log', { type: 'INFO', msg: `Removed device with Slave ID ${slaveId}` });
            io.emit('device-removed', { slaveId: parseInt(slaveId) });
            io.emit('devices-list', getDevicesList());
        } else {
            socket.emit('error', { message: result.error });
        }
    });

    socket.on('get-devices', () => {
        socket.emit('devices-list', getDevicesList());
    });
});

// Helper to get devices as array for client
function getDevicesList() {
    const list = [];
    for (const [slaveId, device] of devices) {
        list.push({ slaveId, type: device.type, enabled: device.enabled });
    }
    return list;
}

server.listen(APP_PORT, () => {
    console.log(`Web Interface running at http://localhost:${APP_PORT}`);
});

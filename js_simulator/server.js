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
            // Ensure all devices have a simulationMode property (default 'random')
            for (const [id, dev] of devices) {
                if (!dev.simulationMode) {
                    dev.simulationMode = 'random';
                }
            }
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
// EdgeBox expects CDAB word order: LSW at lower address, MSW at higher address
const flowMeterDefaults = {
    // Input Registers (FC 04) - Flow Meter Readings (CDAB order)
    772: 0,                     // Forward Total - LSW
    773: 0,                     // Forward Total - MSW
    774: 0x0403,                // Unit Info (Total=L, Flow=L/s)
    777: 0,                     // Alarm Flags (bitfield)
    778: 0,                     // Flow Rate - LSW
    779: 0,                     // Flow Rate - MSW
    786: 0,                     // Forward Overflow Count
    812: 0,                     // Conductivity - LSW
    813: 0,                     // Conductivity - MSW

    // Holding Registers (FC 03) - Configuration (CDAB order)
    261: 0x0000,                // Flow Range - LSW
    262: 0x43D4,                // Flow Range - MSW (424.0 float)
    281: 0x0000,                // Alarm High - LSW
    282: 0x42C8,                // Alarm High - MSW (100.0 float)
    283: 0x0000,                // Reserved/Padding
    284: 0x0000,                // Alarm Low - LSW
    285: 0x4120                 // Alarm Low - MSW (10.0 float)
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

// ===== FR500A/FR510A REGISTER WRITE RULES (Per Datasheet Appendix A) =====

// Write-only Control Command Registers (0x2000-0x2004)
const CONTROL_REGISTERS = {
    0x2000: { name: 'CONTROL_COMMAND', values: [0, 1, 2, 3, 4, 5, 6, 7] }, // 0=Stop, 1=Forward, 2=Reverse, 3=Jog Fwd, 4=Jog Rev, 5=Slow Stop, 6=Freewheel, 7=Fault Reset
    0x2001: { name: 'FREQUENCY_SETPOINT', min: 0, max: 60000 }, // 0-600.00Hz in 0.01Hz units
    0x2002: { name: 'PID_GIVEN', min: 0, max: 1000 },           // 0-100.0%
    0x2003: { name: 'PID_FEEDBACK', min: 0, max: 1000 },        // 0-100.0%
    0x2004: { name: 'TORQUE_SETPOINT', min: -3000, max: 3000 }  // -300.0% to 300.0%
};

// Read-only Status Registers
const READ_ONLY_REGISTERS = [0x2100, 0x2101];

// Check if address is in U00 group (0x30xx) - Read-only monitoring registers
const isU00Register = (addr) => (addr >= 0x3000 && addr <= 0x30FF);
// Check if address is in U01 group (0x31xx) - Read-only fault record registers
const isU01Register = (addr) => (addr >= 0x3100 && addr <= 0x31FF);

// Password/Unlock state per device (unitID -> state)
const deviceUnlockState = new Map();
const UNLOCK_TIMEOUT_MS = 5 * 60 * 1000; // 5 min auto-lock per datasheet

function getUnlockState(unitID) {
    if (!deviceUnlockState.has(unitID)) {
        deviceUnlockState.set(unitID, {
            unlocked: false,
            lastActivity: 0
        });
    }
    return deviceUnlockState.get(unitID);
}

// Build Modbus exception response
function buildExceptionResponse(unitID, fc, errorCode) {
    const response = Buffer.alloc(5);
    response.writeUInt8(unitID, 0);
    response.writeUInt8(fc | 0x80, 1);  // Set high bit to indicate exception
    response.writeUInt8(errorCode, 2);
    const crc = calculateCRC(response.subarray(0, 3));
    response.writeUInt16LE(crc, 3);
    return response;
}

// Validate write requests per FR500A datasheet rules
function validateWriteRequest(addr, val, unitID, io) {
    const mem = getMem(unitID);
    const unlockState = getUnlockState(unitID);

    // Check timeout - auto-lock after 5 min inactivity
    if (unlockState.unlocked && (Date.now() - unlockState.lastActivity > UNLOCK_TIMEOUT_MS)) {
        unlockState.unlocked = false;
        io.emit('log', { type: 'INFO', msg: `ID:${unitID} Auto-locked due to inactivity` });
    }

    // Always allow password register (F00.00 = 0x0000) to be written for unlock
    if (addr === 0x0000) {
        return { valid: true };
    }

    // Check if it's a read-only register (U00/U01 groups)
    if (READ_ONLY_REGISTERS.includes(addr) || isU00Register(addr) || isU01Register(addr)) {
        return { valid: false, errorCode: 0x02, reason: `Register 0x${addr.toString(16)} is read-only` };
    }

    // Check parameter protection (F00.02) - if set to 1, only F00.02 can be modified
    const paramProtection = mem[0x0002] || 0;
    if (paramProtection === 1 && addr !== 0x0002) {
        if (!unlockState.unlocked) {
            return { valid: false, errorCode: 0x04, reason: `Parameters locked. Write password to 0x0000 first` };
        }
    }

    // Validate control command values
    if (CONTROL_REGISTERS[addr]) {
        const reg = CONTROL_REGISTERS[addr];
        if (reg.values && !reg.values.includes(val)) {
            return { valid: false, errorCode: 0x03, reason: `Invalid value ${val} for ${reg.name}` };
        }
        if (reg.min !== undefined && (val < reg.min || val > reg.max)) {
            return { valid: false, errorCode: 0x03, reason: `Value ${val} out of range for ${reg.name}` };
        }
    }

    // Update last activity time for unlock timeout
    if (unlockState.unlocked) {
        unlockState.lastActivity = Date.now();
    }

    return { valid: true };
}

// Handle password unlock when F00.00 is written
function handlePasswordWrite(addr, val, unitID, io) {
    if (addr !== 0x0000) return;

    const mem = getMem(unitID);
    const unlockState = getUnlockState(unitID);
    const storedPassword = mem[0x0000] || 0;

    if (storedPassword === 0) {
        // No password set - setting a new password
        io.emit('log', { type: 'INFO', msg: `ID:${unitID} Password SET` });
    } else if (val === storedPassword) {
        // Correct password - unlock
        unlockState.unlocked = true;
        unlockState.lastActivity = Date.now();
        io.emit('log', { type: 'INFO', msg: `ID:${unitID} UNLOCKED via password` });
    } else {
        // Wrong password
        io.emit('log', { type: 'WARN', msg: `ID:${unitID} Wrong password attempt` });
    }
}

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
    devices.set(slaveId, { type, enabled: true, simulationMode: 'random' });
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

// --- Global Error Handlers ---
process.on('uncaughtException', (err) => {
    console.error('Uncaught Exception:', err);
    io.emit('log', { type: 'ERR', msg: `Server Error: ${err.message}` });
});

process.on('unhandledRejection', (reason, promise) => {
    console.error('Unhandled Rejection:', reason);
    io.emit('log', { type: 'ERR', msg: `Promise Rejection: ${reason}` });
});

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
let intentionalStop = false;
let lastWriteTime = 0;
let writeCount = 0;
let errorBeforeClose = null;

// --- Custom RTU Server Logic ---
// --- Custom RTU Server Logic ---
function processBuffer() {
    let start = 0;
    const MAX_BUFFER_SIZE = 4096; // Increased from 1KB

    // Safety check for massive buffer
    if (buffer.length > MAX_BUFFER_SIZE) {
        io.emit('log', { type: 'ERR', msg: `Buffer overflow (${buffer.length}b) - flushing to recover` });
        buffer = Buffer.alloc(0);
        return;
    }

    while (start + 4 <= buffer.length) { // 4 is min Modbus frame size
        // 1. Peek at potential header
        const unitID = buffer[start];
        const fc = buffer[start + 1];

        // Quick validation of UnitID and FC
        // We only support specific FCs for this sim
        if (![3, 4, 6, 16].includes(fc)) {
            // Invalid FC, just skip byte
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
            // VALID FRAME
            // Process it immediately
            handleFrame(frame);

            // Consume this frame fully
            start += len;

            // Optimization: If we processed a valid frame, discard consumed buffer immediately
            // to keep buffer small for next iteration
            if (start > 0) {
                buffer = buffer.subarray(start);
                start = 0;
            }
            continue;
        } else {
            // CRC failed. This is likely noise or a misalignment.
            // Do NOT log here - it kills performance on noisy lines.
            // Just shift by 1 byte and try again.
            start++;
        }
    }

    // Trim consumed garbage
    if (start > 0) {
        buffer = buffer.subarray(start);
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

        // Log asynchronously to avoid blocking response
        setImmediate(() => {
            io.emit('log', { type: 'RX', msg: `Read ID:${unitID} FC:${fc} Addr:0x${addr.toString(16)} Len:${count}` });
        });

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

        // Validate the write request per FR500A datasheet rules
        const validation = validateWriteRequest(addr, val, unitID, io);
        if (!validation.valid) {
            io.emit('log', { type: 'WARN', msg: `ID:${unitID} Write REJECTED: ${validation.reason}` });
            response = buildExceptionResponse(unitID, fc, validation.errorCode);
        } else {
            // Valid write - proceed
            mem[addr] = val;
            setImmediate(() => {
                io.emit('reg-update', { id: unitID, addr, val });
                io.emit('log', { type: 'RX', msg: `Write ID:${unitID} Addr:0x${addr.toString(16)} Val:${val}` });
            });

            // Handle password unlock
            handlePasswordWrite(addr, val, unitID, io);

            // Handle Control Commands
            if (addr === 0x2000) handleControlCommand(val, unitID);

            // Handle Parameter Writes (FR500A Protection Sequence)
            handleParameterWrite(addr, val, unitID);

            // Echo Request as Response
            response = Buffer.from(frame);
        }


    } else if (fc === 16) { // Write Multi
        const addr = frame.readUInt16BE(2);
        const count = frame.readUInt16BE(4);
        const byteCount = frame.readUInt8(6);
        const data = frame.subarray(7, 7 + byteCount);

        setImmediate(() => {
            io.emit('log', { type: 'RX', msg: `WriteMulti ID:${unitID} Addr:0x${addr.toString(16)} Count:${count}` });
        });

        // Validate ALL registers first before writing any
        let validationError = null;
        for (let i = 0; i < count && !validationError; i++) {
            const regAddr = addr + i;
            const val = data.readUInt16BE(i * 2);
            const validation = validateWriteRequest(regAddr, val, unitID, io);
            if (!validation.valid) {
                validationError = validation;
                io.emit('log', { type: 'WARN', msg: `ID:${unitID} WriteMulti REJECTED at 0x${regAddr.toString(16)}: ${validation.reason}` });
            }
        }

        if (validationError) {
            response = buildExceptionResponse(unitID, fc, validationError.errorCode);
        } else {
            // All validated - now write all registers
            for (let i = 0; i < count; i++) {
                const regAddr = addr + i;
                const val = data.readUInt16BE(i * 2);
                mem[regAddr] = val;
                setImmediate(() => {
                    io.emit('reg-update', { id: unitID, addr: regAddr, val });
                });

                // Handle password unlock
                handlePasswordWrite(regAddr, val, unitID, io);

                if (regAddr === 0x2000) handleControlCommand(val, unitID);
                handleParameterWrite(regAddr, val, unitID);
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
    }

    if (response) {
        // Safety check: ensure port is still open before writing
        if (!serialPort || !serialPort.isOpen) {
            return;
        }

        writeCount++;
        lastWriteTime = Date.now();

        // Write and drain to ensure response is fully sent before processing next request
        serialPort.write(response, (err) => {
            if (err) {
                errorBeforeClose = err.message;
                console.error('Serial write error:', err);
                return;
            }
            // Drain to ensure bytes are sent before next request
            serialPort.drain((drainErr) => {
                if (drainErr) {
                    console.error('Serial drain error:', drainErr);
                }
            });
        });

        // Log asynchronously to avoid blocking the response
        const hex = response.toString('hex').toUpperCase();
        setImmediate(() => {
            io.emit('log', { type: 'TX', msg: `Resp ID:${unitID} Data:${hex}` });
        });
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
    } else if (val === 1 || val === 2 || val === 3 || val === 4) { // Run (1=Forward, 2=Reverse, 3=Jog Fwd, 4=Jog Rev)
        const cmdNames = { 1: 'FORWARD RUN', 2: 'REVERSE RUN', 3: 'JOG FORWARD', 4: 'JOG REVERSE' };
        io.emit('log', { type: 'INFO', msg: `ID:${unitID} ${cmdNames[val]} Command` });

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

// --- Simulation Logic ---
function floatToModbus(val) {
    const buf = Buffer.alloc(4);
    buf.writeFloatBE(val);
    return [buf.readUInt16BE(0), buf.readUInt16BE(2)];
}

let simInterval = null;

function startSimulation() {
    if (simInterval) clearInterval(simInterval);
    simInterval = setInterval(() => {
        if (!serialPort || !serialPort.isOpen) return;

        for (const [id, device] of devices) {
            if (!device.enabled) continue;

            // Skip random generation if in 'manual' mode
            if (device.simulationMode === 'manual') continue;

            if (device.type === 'energymeter') {
                const mem = getMem(id);
                const updates = {};

                // Helper to update MSW/LSW
                const updateFloat = (addr, val) => {
                    const [msw, lsw] = floatToModbus(val);
                    if (mem[addr] !== msw) { mem[addr] = msw; updates[addr] = msw; }
                    if (mem[addr + 1] !== lsw) { mem[addr + 1] = lsw; updates[addr + 1] = lsw; }
                };

                // Simulate Voltage (220V +/- 2%)
                const voltage = 220 + (Math.random() * 8.8 - 4.4);
                updateFloat(0x0800, voltage); // Phase A
                updateFloat(0x0802, voltage * (1 + (Math.random() * 0.01 - 0.005))); // Phase B
                updateFloat(0x0804, voltage * (1 + (Math.random() * 0.01 - 0.005))); // Phase C

                // Simulate Current (random load 5A - 10A)
                const current = 5 + Math.random() * 5;
                updateFloat(0x080C, current); // Phase A
                updateFloat(0x080E, current * 0.95); // Phase B
                updateFloat(0x0810, current * 1.05); // Phase C

                // Power (Active)
                const powerA = voltage * current;
                const powerB = voltage * (current * 0.95);
                const powerC = voltage * (current * 1.05);
                updateFloat(0x0806, powerA);
                updateFloat(0x0808, powerB);
                updateFloat(0x080A, powerC);

                // Total Power
                updateFloat(0x060A, powerA + powerB + powerC);

                // Frequency (50Hz +/- 0.1)
                const freq = 50 + (Math.random() * 0.2 - 0.1);
                updateFloat(0x0834, freq);

                if (Object.keys(updates).length > 0) {
                    io.emit('regs-update-batch', { id, updates });
                }
            }
        }
    }, 1000);
}

function stopSimulation() {
    if (simInterval) clearInterval(simInterval);
    simInterval = null;
}

// --- Socket Events ---
io.on('connection', (socket) => {
    // Send current devices list to new client
    socket.emit('devices-list', getDevicesList());

    // Also send register state for each device
    for (const [slaveId, device] of devices) {
        const mem = getMem(slaveId);
        let defs = inverterDefaults;
        if (device.type === 'flowmeter') defs = flowMeterDefaults;
        if (device.type === 'energymeter') defs = energyMeterDefaults;
        const regData = {};
        for (const addr of Object.keys(defs)) {
            regData[parseInt(addr)] = mem[parseInt(addr)];
        }
        socket.emit('device-state', { id: slaveId, type: device.type, registers: regData });
    }

    socket.on('start-server', ({ port, baud }) => {
        if (serialPort && serialPort.isOpen) return;
        intentionalStop = false;
        try {
            console.log(`Starting Custom Modbus Server on ${port} @ ${baud}`);
            serialPort = new SerialPort({ path: port, baudRate: parseInt(baud) });

            serialPort.on('data', (data) => {
                buffer = Buffer.concat([buffer, data]);
                processBuffer();
            });

            serialPort.on('error', (err) => {
                errorBeforeClose = err.message;
                console.error('Serial port error:', err);
                io.emit('log', { type: 'ERR', msg: `Port error: ${err.message}` });
                io.emit('server-status', false);
            });

            serialPort.on('open', () => {
                io.emit('server-status', true);
                io.emit('log', { type: 'INFO', msg: `Server Started on ${port}` });
                startSimulation();
            });

            serialPort.on('close', () => {
                const timeSinceLastWrite = lastWriteTime ? (Date.now() - lastWriteTime) : -1;
                const debugInfo = {
                    intentionalStop,
                    writeCount,
                    timeSinceLastWriteMs: timeSinceLastWrite,
                    bufferLength: buffer.length,
                    errorBeforeClose
                };

                console.log('Serial port closed. Debug info:', JSON.stringify(debugInfo, null, 2));
                io.emit('server-status', false);

                if (!intentionalStop) {
                    io.emit('log', {
                        type: 'ERR',
                        msg: `Unexpected Close! Writes:${writeCount} LastWrite:${timeSinceLastWrite}ms ago Buffer:${buffer.length}b Error:${errorBeforeClose || 'none'}`
                    });
                } else {
                    io.emit('log', { type: 'INFO', msg: 'Serial port closed' });
                }

                // Reset tracking variables
                writeCount = 0;
                lastWriteTime = 0;
                errorBeforeClose = null;

                stopSimulation();
            });

        } catch (e) {
            console.error(e);
            io.emit('log', { type: 'ERR', msg: e.message });
        }
    });

    socket.on('stop-server', () => {
        if (serialPort && serialPort.isOpen) {
            intentionalStop = true; // Mark as user-initiated
            serialPort.close((err) => {
                if (err) {
                    io.emit('log', { type: 'ERR', msg: err.message });
                } else {
                    io.emit('server-status', false);
                    io.emit('log', { type: 'INFO', msg: 'Server Stopped (User Request)' });
                    console.log('Modbus Server Stopped');
                }
            });
            buffer = Buffer.alloc(0); // Clear buffer
        }
    });

    socket.on('set-register', ({ id, addr, val }) => {
        // ID is required now
        const targetID = parseInt(id) || 1;
        const mem = getMem(targetID);
        mem[addr] = val;
        saveMemoryConfig(); // Save memory changes
        io.emit('reg-update', { id: targetID, addr, val });
        if (addr === 0x2000) handleControlCommand(val, targetID);
    });

    socket.on('toggle-inverter', ({ id, enabled }) => {
        const targetID = parseInt(id);
        const device = devices.get(targetID);
        if (device) {
            device.enabled = enabled;
            devices.set(targetID, device);
            saveDevicesConfig(); // Save to file
            io.emit('log', { type: 'INFO', msg: `Device ${targetID} ${enabled ? 'ENABLED' : 'DISABLED'}` });
            io.emit('device-updated', { id: targetID, ...device });
        } else {
            console.warn(`Attempted to toggle unknown device ID: ${id} (parsed: ${targetID})`);
        }
    });

    socket.on('get-register', ({ id, addr }) => {
        const targetID = parseInt(id) || 1;
        const mem = getMem(targetID);
        const val = mem[addr] || 0;
        socket.emit('register-value', { id: targetID, addr, val });
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
            saveDevicesConfig(); // Save to file
            io.emit('log', { type: 'INFO', msg: `Device ${id} changed from ${oldType} to ${type}` });
            // Preserve simulationMode or reset? Let's keep it if set, or default
            device.simulationMode = device.simulationMode || 'random';
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

    socket.on('set-simulation-mode', ({ id, mode }) => {
        const targetID = parseInt(id);
        const device = devices.get(targetID);
        if (device) {
            device.simulationMode = mode;
            devices.set(targetID, device);
            saveDevicesConfig();
            io.emit('log', { type: 'INFO', msg: `Device ${id} Simulation Mode: ${mode}` });
            io.emit('device-updated', { id: targetID, ...device });
        }
    });
});

// Helper to get devices as array for client
function getDevicesList() {
    const list = [];
    for (const [slaveId, device] of devices) {
        list.push({ slaveId, type: device.type, enabled: device.enabled, simulationMode: device.simulationMode || 'random' });
    }
    return list;
}

server.listen(APP_PORT, () => {
    console.log(`Web Interface running at http://localhost:${APP_PORT}`);
});

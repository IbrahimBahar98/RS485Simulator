const ModbusRTU = require("modbus-serial");
const WebSocket = require("ws");
const http = require("http");
const fs = require("fs");
const path = require("path");
const devicesConfig = require("./devices.json");

const MODBUS_PORT = 8502;
const WS_PORT = 8080;
const HTTP_PORT = 3000;

// =====================================================
// MODBUS TCP SERVER
// =====================================================
const modbusServer = new ModbusRTU.ServerTcp(
  { port: MODBUS_PORT, unitID: 1 },
  function (err) {
    if (err) {
      console.error("Modbus TCP Server failed to start:", err);
    } else {
      console.log(`Modbus TCP Server listening on port ${MODBUS_PORT}`);
    }
  }
);

// Initialize holding registers
const holdingRegisters = Buffer.alloc(10000 * 2);
const inputRegisters = Buffer.alloc(10000 * 2);

function initializeRegisters() {
  writeFloatToRegisters(0, 230.5);
  writeFloatToRegisters(2, 10.25);
  writeFloatToRegisters(4, 2500.0);
  writeFloatToRegisters(6, 50.0);
  writeFloatToRegisters(100, 50.0);
  writeFloatToRegisters(102, 1000.0);
  writeFloatToRegisters(200, 25.5);
  writeFloatToRegisters(202, 25.0);
  writeFloatToRegisters(204, 50.0);
  console.log("Registers initialized with simulation values");
}

function writeFloatToRegisters(address, value) {
  const buf = Buffer.alloc(4);
  buf.writeFloatBE(value, 0);
  holdingRegisters.writeUInt16BE(buf.readUInt16BE(0), address * 2);
  holdingRegisters.writeUInt16BE(buf.readUInt16BE(2), (address + 1) * 2);
}

function readFloatFromRegisters(address) {
  const buf = Buffer.alloc(4);
  buf.writeUInt16BE(holdingRegisters.readUInt16BE(address * 2), 0);
  buf.writeUInt16BE(holdingRegisters.readUInt16BE((address + 1) * 2), 2);
  return buf.readFloatBE(0);
}

modbusServer.on("connection", function (client) {
  console.log("Modbus Client connected");
});

modbusServer.on("error", function (err) {
  console.error("Modbus Server error:", err);
});

modbusServer.on("readHoldingRegisters", function (request, callback) {
  const address = request.address;
  const length = request.length;
  const data = [];
  for (let i = 0; i < length; i++) {
    const regValue = holdingRegisters.readUInt16BE((address + i) * 2);
    data.push(regValue);
  }
  console.log(`Read Holding Registers: Address=${address}, Length=${length}`);
  callback(null, data);
});

modbusServer.on("readInputRegisters", function (request, callback) {
  const address = request.readUInt16BE(0);
  const length = request.readUInt16BE(2);
  const data = [];
  for (let i = 0; i < length; i++) {
    const regValue = inputRegisters.readUInt16BE((address + i) * 2);
    data.push(regValue);
  }
  console.log(`Read Input Registers: Address=${address}, Length=${length}`);
  callback(null, data);
});

modbusServer.on("writeSingleRegister", function (request, callback) {
  const address = request.address;
  const value = request.value;
  holdingRegisters.writeUInt16BE(value, address * 2);
  console.log(`Write Single Register: Address=${address}, Value=${value}`);
  callback(null, value);
});

modbusServer.on("writeMultipleRegisters", function (request, callback) {
  const address = request.address;
  const values = request.values;
  for (let i = 0; i < values.length; i++) {
    holdingRegisters.writeUInt16BE(values[i], (address + i) * 2);
  }
  console.log(`Write Multiple Registers: Address=${address}, Count=${values.length}`);
  callback(null, values.length);
});

const wss = new WebSocket.Server({ port: WS_PORT });

wss.on("connection", function connection(ws) {
  console.log("WebSocket client connected");
  ws.send(JSON.stringify({ type: "init", devices: devicesConfig }));
  const interval = setInterval(() => {
    const baseVoltage = readFloatFromRegisters(0);
    const voltage = baseVoltage + (Math.random() * 2 - 1);
    writeFloatToRegisters(0, voltage);
    const baseCurrent = readFloatFromRegisters(2);
    const current = Math.max(0, baseCurrent + (Math.random() * 0.5 - 0.25));
    writeFloatToRegisters(2, current);
    ws.send(JSON.stringify({
      type: "update",
      data: {
        voltage: parseFloat(voltage.toFixed(2)),
        current: parseFloat(current.toFixed(2)),
        power: parseFloat((voltage * current).toFixed(2)),
        frequency: readFloatFromRegisters(6),
        flowRate: readFloatFromRegisters(100),
        inverterFreq: readFloatFromRegisters(202)
      }
    }));
  }, 1000);
  ws.on("close", function close() {
    clearInterval(interval);
    console.log("WebSocket client disconnected");
  });
});

const httpServer = http.createServer((req, res) => {
  let filePath = path.join(__dirname, "public", req.url === "/" ? "index.html" : req.url);
  const extname = path.extname(filePath);
  const contentTypes = {
    ".html": "text/html",
    ".css": "text/css",
    ".js": "application/javascript",
    ".json": "application/json"
  };
  fs.readFile(filePath, (err, content) => {
    if (err) {
      if (err.code === "ENOENT") {
        res.writeHead(404);
        res.end("File not found");
      } else {
        res.writeHead(500);
        res.end(err.code);
      }
    } else {
      res.writeHead(200, { "Content-Type": contentTypes[extname] || "application/octet-stream" });
      res.end(content);
    }
  });
});

httpServer.listen(HTTP_PORT, () => {
  console.log(`HTTP Server listening on port ${HTTP_PORT}`);
  console.log(`Open http://localhost:${HTTP_PORT} in your browser`);
});

initializeRegisters();

console.log("======================================");
console.log("  Modbus TCP Simulator Started");
console.log("======================================");
console.log(`  Modbus TCP Port: ${MODBUS_PORT}`);
console.log(`  WebSocket Port: ${WS_PORT}`);
console.log(`  HTTP Port: ${HTTP_PORT}`);
console.log("======================================");

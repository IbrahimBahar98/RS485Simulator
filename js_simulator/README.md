# JavaScript Modbus Inverter Simulator

This is a Node.js port of the Python Modbus Inverter Simulator.

## Features
- **Web Interface**: Clean, dark-mode dashboard for control and monitoring.
- **Node.js Backend**: Uses `modbus-serial` and `serialport`.
- **Multi-Slave Support**: Responds to Slave IDs 1-5 and 110-114.
- **FR500A Register Map**: Supports status registers 0x03xx for Freq, Volt, Curr, Power, etc.
- **Smart Logic**: Implements "Stop Command" (0x2000 = 5) clearing status registers.

## Setup
1.  **Install Node.js** (v14+).
2.  Install dependencies:
    ```bash
    cd js_simulator
    npm install
    ```
    *(Note: If PowerShell blocks npm, use `cmd /c npm install`)*

## Usage
1.  Start the Server:
    ```bash
    node server.js
    ```
2.  Open Browser:
    [http://localhost:3000](http://localhost:3000)
3.  **In the Browser**:
    - Select your **RS485 COM Port**.
    - Click **Start Server**.
    - Monitor traffic and adjust values live.

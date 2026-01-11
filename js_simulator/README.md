# Modbus Inverter Simulator (Node.js/Electron)

A desktop application to simulate FR500A-compatible Modbus RTU inverters for testing EdgeBox-100 firmware.

## Features
- **5 Independent Inverters**: Each with its own register memory and enable/disable toggle.
- **FR500A Register Map**: Supports status registers (0x03xx, 0x30xx) and control (0x2000).
- **Desktop App**: Electron wrapper with a modern dark-mode UI.
- **Start/Stop Server**: Toggle the Modbus server on/off without closing the app.
- **Real-time Logging**: View all Modbus traffic in the UI.

## Installation

### Prerequisites
- **Node.js** v14 or higher: [Download](https://nodejs.org/)
- **Git** (optional): For cloning the repository.

### Steps
1. **Clone or Download** the repository.
2. **Navigate** to the `js_simulator` directory:
   ```bash
   cd js_simulator
   ```
3. **Install Dependencies** (via CMD to avoid PowerShell issues):
   ```bash
   cmd /c "npm install"
   ```
4. **Run the App**:
   ```bash
   cmd /c "npm start"
   ```
   This launches the Electron desktop window.

## Usage
1. **Select COM Port**: Choose your RS485 adapter from the dropdown.
2. **Start Server**: Click "Start Server" to begin listening.
3. **Switch Inverters**: Use tabs (1-5) to view/control each simulated inverter.
4. **Enable/Disable**: Uncheck "Enabled" to stop responding to that inverter's ID.
5. **Edit Values**: Modify Frequency, Voltage, etc. using the input fields.

## Troubleshooting
- **Port Busy**: Ensure no other app is using the COM port.
- **PowerShell Error**: Use `cmd /c "npm start"` instead of `npm start`.
- **Permission Issues**: Run terminal as Administrator if `npm install` fails.

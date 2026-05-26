const { app, BrowserWindow, ipcMain } = require('electron');
const { SerialPort, ReadlineParser } = require('serialport');
const { exec } = require('child_process');

let mainWindow;
let serialPort;
let serverRunning = false;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
      enableRemoteModule: true
    }
  });

  mainWindow.loadFile('index.html');
  
  // Open DevTools in development
  if (process.env.NODE_ENV === 'development') {
    mainWindow.webContents.openDevTools();
  }
}

// Get available serial ports
ipcMain.on('get-ports', (event) => {
  SerialPort.list().then(ports => {
    event.reply('ports-updated', ports);
  }).catch(err => {
    console.error('Error getting ports:', err);
  });
});

// Start Modbus server
ipcMain.on('start-server', (event, config) => {
  if (serverRunning) return;
  
  try {
    serialPort = new SerialPort({
      path: config.port,
      baudRate: parseInt(config.baudRate),
      autoOpen: false
    });
    
    serialPort.open((err) => {
      if (err) {
        console.error('Error opening serial port:', err);
        event.reply('server-status-updated', false);
        return;
      }
      
      serverRunning = true;
      event.reply('server-status-updated', true);
      
      // Setup parser for serial data
      const parser = serialPort.pipe(new ReadlineParser({ delimiter: '\r\n' }));
      
      parser.on('data', (data) => {
        // Emit log entry
        event.reply('log', { type: 'rx', msg: data });
      });
      
      serialPort.on('error', (err) => {
        console.error('Serial port error:', err);
        event.reply('log', { type: 'err', msg: `Serial error: ${err.message}` });
      });
    });
  } catch (err) {
    console.error('Error starting server:', err);
    event.reply('server-status-updated', false);
  }
});

// Stop Modbus server
ipcMain.on('stop-server', (event) => {
  if (!serverRunning || !serialPort) return;
  
  try {
    serialPort.close(() => {
      serverRunning = false;
      event.reply('server-status-updated', false);
      console.log('Server stopped');
    });
  } catch (err) {
    console.error('Error stopping server:', err);
    event.reply('server-status-updated', false);
  }
});

// Handle app ready
app.whenReady().then(createWindow);

// Quit when all windows are closed
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});
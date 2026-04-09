// Theme Engine Implementation
const themeSelect = document.getElementById('theme-select');
const themeToggle = document.getElementById('theme-toggle');
const root = document.documentElement;

// Load theme from localStorage or system preference
function loadTheme() {
  const savedTheme = localStorage.getItem('theme');
  if (savedTheme) {
    setTheme(savedTheme);
  } else {
    // Default to Auto
    setTheme('auto');
  }
}

function setTheme(theme) {
  if (theme === 'auto') {
    document.body.removeAttribute('data-theme');
    themeSelect.value = 'auto';
  } else {
    document.body.setAttribute('data-theme', theme);
    themeSelect.value = theme;
  }
  localStorage.setItem('theme', theme);
}

// Theme toggle button logic
themeToggle.addEventListener('click', () => {
  const currentTheme = localStorage.getItem('theme') || 'auto';
  let nextTheme;
  
  switch(currentTheme) {
    case 'auto':
      nextTheme = 'dark';
      break;
    case 'dark':
      nextTheme = 'light';
      break;
    case 'light':
      nextTheme = 'auto';
      break;
    default:
      nextTheme = 'auto';
  }
  
  setTheme(nextTheme);
});

// Theme select dropdown logic
themeSelect.addEventListener('change', (e) => {
  setTheme(e.target.value);
});

// Device Lifecycle Core
const addDeviceBtn = document.getElementById('add-device-btn');
const addDeviceForm = document.getElementById('add-device-form');
const addDeviceCancel = document.getElementById('add-device-cancel');
const addDeviceSubmit = document.getElementById('add-device-submit');
const deviceTabs = document.getElementById('device-tabs');

let devices = [
  { id: 1, type: 'inverter', enabled: true }
];

// Initialize with first device tab
updateDeviceTabs();

addDeviceBtn.addEventListener('click', () => {
  addDeviceForm.style.display = 'block';
});

addDeviceCancel.addEventListener('click', () => {
  addDeviceForm.style.display = 'none';
});

addDeviceSubmit.addEventListener('click', () => {
  const slaveId = parseInt(document.getElementById('slave-id').value);
  const deviceType = document.getElementById('device-type').value;
  
  if (slaveId && deviceType) {
    devices.push({ id: slaveId, type: deviceType, enabled: true });
    updateDeviceTabs();
    addDeviceForm.style.display = 'none';
    
    // Reset form
    document.getElementById('slave-id').value = '1';
    document.getElementById('device-type').value = 'inverter';
  }
});

function updateDeviceTabs() {
  // Clear existing tabs except the + Add Device button
  const tabsContainer = document.getElementById('device-tabs');
  const addDeviceTab = tabsContainer.lastElementChild;
  
  // Remove all tabs except the last one (+ Add Device)
  while (tabsContainer.children.length > 1) {
    tabsContainer.removeChild(tabsContainer.firstElementChild);
  }
  
  // Add tabs for each device
  devices.forEach((device, index) => {
    const tab = document.createElement('button');
    tab.className = 'tab';
    tab.role = 'tab';
    tab.setAttribute('aria-selected', index === 0 ? 'true' : 'false');
    
    // Generate tab label based on device type
    let tabLabel = '';
    switch(device.type) {
      case 'inverter':
        tabLabel = `INV #${device.id}`;
        break;
      case 'flow-meter':
        tabLabel = `FM #${device.id}`;
        break;
      case 'energy-meter':
        tabLabel = `EM #${device.id}`;
        break;
      default:
        tabLabel = `DEV #${device.id}`;
    }
    
    tab.textContent = tabLabel;
    
    // Set active state for first device
    if (index === 0) {
      tab.classList.add('active');
      tab.setAttribute('aria-selected', 'true');
    }
    
    // Add click event to switch device
    tab.addEventListener('click', () => {
      // Update active tab
      document.querySelectorAll('.tab').forEach(t => {
        t.classList.remove('active');
        t.setAttribute('aria-selected', 'false');
      });
      tab.classList.add('active');
      tab.setAttribute('aria-selected', 'true');
      
      // Update UI for selected device
      updateDevicePanel(device);
    });
    
    tabsContainer.insertBefore(tab, addDeviceTab);
  });
}

// Register-aware Rendering
const deviceTypeConfig = document.getElementById('device-type-config');
const dashboardGrid = document.getElementById('dashboard-grid');
const registersTableBody = document.getElementById('registers-table-body');
const slaveIdDisplay = document.getElementById('slave-id-display');
const deviceEnabled = document.getElementById('device-enabled');

// Inverter dashboard cards
const inverterDashboardCards = [
  { name: 'Frequency', unit: 'Hz', value: 50.0 },
  { name: 'Voltage', unit: 'V', value: 230.0 },
  { name: 'Current', unit: 'A', value: 15.5 },
  { name: 'Power', unit: 'kW', value: 3.45 },
  { name: 'Speed', unit: 'rpm', value: 1500 },
  { name: 'Bus V', unit: 'V', value: 400.0 },
  { name: 'Temp', unit: '°C', value: 45.0 },
  { name: 'Energy', unit: 'kWh', value: 1250.5 }
];

// Flow Meter dashboard cards
const flowMeterDashboardCards = [
  { name: 'Flow Rate', unit: 'L/s', value: 12.5 },
  { name: 'Fwd Total', unit: 'L', value: 125000 },
  { name: 'Conductivity', unit: 'mS/cm', value: 2.3 },
  { name: 'Fwd Overflow', unit: '', value: 0 },
  { name: 'Alarms', unit: '', value: 'None' }
];

// Energy Meter dashboard cards
const energyMeterDashboardCards = [
  { name: 'Voltage L1', unit: 'V', value: 230.0 },
  { name: 'Voltage L2', unit: 'V', value: 230.0 },
  { name: 'Voltage L3', unit: 'V', value: 230.0 },
  { name: 'Current L1', unit: 'A', value: 15.5 },
  { name: 'Current L2', unit: 'A', value: 16.2 },
  { name: 'Current L3', unit: 'A', value: 14.8 },
  { name: 'Total Active Power', unit: 'kW', value: 10.25 },
  { name: 'Power Factor', unit: '', value: 0.98 },
  { name: 'Frequency', unit: 'Hz', value: 50.0 },
  { name: 'Total Energy', unit: 'kWh', value: 15200 },
  { name: 'Daily Energy', unit: 'kWh', value: 45.2 },
  { name: 'Monthly Energy', unit: 'kWh', value: 1320.5 }
];

// Inverter registers
const inverterRegisters = [
  { addr: '0x0000', name: 'Frequency', value: 50.0, hex: '0x0000', type: 'Float' },
  { addr: '0x0002', name: 'Voltage', value: 230.0, hex: '0x0002', type: 'Float' },
  { addr: '0x0004', name: 'Current', value: 15.5, hex: '0x0004', type: 'Float' },
  { addr: '0x0006', name: 'Power', value: 3.45, hex: '0x0006', type: 'Float' },
  { addr: '0x0008', name: 'Speed', value: 1500, hex: '0x0008', type: 'UInt16' },
  { addr: '0x000A', name: 'Bus V', value: 400.0, hex: '0x000A', type: 'Float' },
  { addr: '0x000C', name: 'Temp', value: 45.0, hex: '0x000C', type: 'Float' },
  { addr: '0x000E', name: 'Energy', value: 1250.5, hex: '0x000E', type: 'Float' }
];

// Flow Meter registers
const flowMeterRegisters = [
  { addr: '0x0000', name: 'Flow Rate', value: 12.5, hex: '0x0000', type: 'Float' },
  { addr: '0x0002', name: 'Fwd Total', value: 125000, hex: '0x0002', type: 'UInt32' },
  { addr: '0x0004', name: 'Conductivity', value: 2.3, hex: '0x0004', type: 'Float' },
  { addr: '0x0006', name: 'Fwd Overflow', value: 0, hex: '0x0006', type: 'UInt16' },
  { addr: '0x0008', name: 'Alarms', value: 0, hex: '0x0008', type: 'UInt16' }
];

// Energy Meter registers
const energyMeterRegisters = [
  { addr: '0x0000', name: 'Voltage L1', value: 230.0, hex: '0x0000', type: 'Float' },
  { addr: '0x0002', name: 'Voltage L2', value: 230.0, hex: '0x0002', type: 'Float' },
  { addr: '0x0004', name: 'Voltage L3', value: 230.0, hex: '0x0004', type: 'Float' },
  { addr: '0x0006', name: 'Current L1', value: 15.5, hex: '0x0006', type: 'Float' },
  { addr: '0x0008', name: 'Current L2', value: 16.2, hex: '0x0008', type: 'Float' },
  { addr: '0x000A', name: 'Current L3', value: 14.8, hex: '0x000A', type: 'Float' },
  { addr: '0x000C', name: 'Total Active Power', value: 10.25, hex: '0x000C', type: 'Float' },
  { addr: '0x000E', name: 'Power Factor', value: 0.98, hex: '0x000E', type: 'Float' },
  { addr: '0x0010', name: 'Frequency', value: 50.0, hex: '0x0010', type: 'Float' },
  { addr: '0x0012', name: 'Total Energy', value: 15200, hex: '0x0012', type: 'UInt32' },
  { addr: '0x0014', name: 'Daily Energy', value: 45.2, hex: '0x0014', type: 'Float' },
  { addr: '0x0016', name: 'Monthly Energy', value: 1320.5, hex: '0x0016', type: 'Float' }
];

function updateDevicePanel(device) {
  // Update display elements
  slaveIdDisplay.textContent = `Slave ID: ${device.id}`;
  deviceEnabled.checked = device.enabled;
  
  // Update device type selector
  deviceTypeConfig.value = device.type;
  
  // Generate dashboard cards based on device type
  dashboardGrid.innerHTML = '';
  
  let dashboardCards = [];
  let registers = [];
  
  switch(device.type) {
    case 'inverter':
      dashboardCards = inverterDashboardCards;
      registers = inverterRegisters;
      break;
    case 'flow-meter':
      dashboardCards = flowMeterDashboardCards;
      registers = flowMeterRegisters;
      break;
    case 'energy-meter':
      dashboardCards = energyMeterDashboardCards;
      registers = energyMeterRegisters;
      break;
  }
  
  // Render dashboard cards
  dashboardCards.forEach(card => {
    const cardElement = document.createElement('div');
    cardElement.className = 'card';
    cardElement.innerHTML = `
      <div class="card-label">${card.name}</div>
      <div class="card-value">${card.value}</div>
      <div class="card-unit">${card.unit}</div>
      <div class="card-control">
        <input type="number" step="${card.unit === 'Hz' || card.unit === 'V' || card.unit === 'A' || card.unit === 'kW' || card.unit === 'rpm' || card.unit === '°C' || card.unit === 'kWh' || card.unit === 'L/s' || card.unit === 'L' || card.unit === 'mS/cm' ? '0.1' : '1'}" value="${card.value}">
        <button>Set</button>
      </div>
    `;
    dashboardGrid.appendChild(cardElement);
  });
  
  // Render registers table
  registersTableBody.innerHTML = '';
  registers.forEach(reg => {
    const row = document.createElement('tr');
    row.innerHTML = `
      <td>${reg.addr}</td>
      <td>${reg.name}</td>
      <td><input type="text" class="table-input" value="${reg.value}"></td>
      <td>${reg.hex}</td>
    `;
    
    // Add data type badge
    const dataTypeCell = row.cells[1];
    const dataTypeSpan = document.createElement('span');
    dataTypeSpan.className = 'data-type';
    dataTypeSpan.textContent = `[${reg.type}]`;
    dataTypeCell.appendChild(dataTypeSpan);
    
    registersTableBody.appendChild(row);
  });
}

// Initialize first device panel
updateDevicePanel(devices[0]);

// Socket.IO Integration Layer
let socket;

function connectSocket() {
  socket = io();
  
  // Server status updates
  socket.on('server-status', (running) => {
    const statusBadge = document.getElementById('server-status');
    if (running) {
      statusBadge.textContent = 'RUNNING';
      statusBadge.className = 'status-badge running';
      document.getElementById('start-server').disabled = true;
      document.getElementById('stop-server').disabled = false;
    } else {
      statusBadge.textContent = 'Stopped';
      statusBadge.className = 'status-badge stopped';
      document.getElementById('start-server').disabled = false;
      document.getElementById('stop-server').disabled = true;
    }
  });
  
  // Devices list updates
  socket.on('devices-list', (devicesList) => {
    console.log('Devices list received:', devicesList);
  });
  
  // Log messages
  socket.on('log', (logData) => {
    addLogEntry(logData.type, logData.msg);
  });
  
  // Device state updates
  socket.on('device-state', (deviceState) => {
    console.log('Device state updated:', deviceState);
  });
  
  // Register updates
  socket.on('reg-update', (regUpdate) => {
    console.log('Register updated:', regUpdate);
  });
  
  // Batch register updates
  socket.on('regs-update-batch', (batchUpdate) => {
    console.log('Batch register updates:', batchUpdate);
  });
}

// Log Panel & Accessibility
const logContainer = document.getElementById('log-container');
const logCount = document.querySelector('.log-count');
let logEntries = [];

function addLogEntry(type, message) {
  const now = new Date();
  const timestamp = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`;
  
  const entry = document.createElement('div');
  entry.className = `log-entry log-${type}`;
  entry.innerHTML = `<span class="timestamp">[${timestamp}]</span> <span class="message">${message}</span>`;
  
  logContainer.appendChild(entry);
  logEntries.push(entry);
  
  // Limit to 100 entries
  if (logEntries.length > 100) {
    logContainer.removeChild(logEntries.shift());
  }
  
  // Auto-scroll to bottom
  logContainer.scrollTop = logContainer.scrollHeight;
  
  // Update count
  logCount.textContent = `${logEntries.length} entries`;
}

// Clear log button
document.getElementById('clear-log').addEventListener('click', () => {
  logContainer.innerHTML = '';
  logEntries = [];
  logCount.textContent = '0 entries';
});

// Server control buttons
document.getElementById('start-server').addEventListener('click', () => {
  const port = document.getElementById('port-select').value;
  const baudRate = document.getElementById('baud-rate-select').value;
  
  if (socket) {
    socket.emit('start-server', { port, baudRate });
  }
});

document.getElementById('stop-server').addEventListener('click', () => {
  if (socket) {
    socket.emit('stop-server');
  }
});

// Refresh ports button
document.getElementById('refresh-ports').addEventListener('click', () => {
  if (socket) {
    socket.emit('get-ports');
  }
});

// Initialize
loadTheme();
connectSocket();
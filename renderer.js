const { ipcRenderer } = require('electron');

// Handle serial port updates from main process
ipcRenderer.on('ports-updated', (event, ports) => {
  const portSelect = document.getElementById('port-select');
  
  // Clear existing options
  portSelect.innerHTML = '';
  
  // Add new options
  ports.forEach(port => {
    const option = document.createElement('option');
    option.value = port.comName;
    option.textContent = port.comName;
    portSelect.appendChild(option);
  });
});

// Handle server status updates
ipcRenderer.on('server-status-updated', (event, running) => {
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

// Handle device list updates
ipcRenderer.on('devices-list-updated', (event, devices) => {
  console.log('Devices list updated:', devices);
});

// Send request for available ports
ipcRenderer.send('get-ports');
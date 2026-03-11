import React, { useState, useEffect, useRef } from 'react';
import { Line, Bar } from 'react-chartjs-2';
import clsx from 'clsx';
import styles from './App.module.css';

const App = () => {
  const [devices, setDevices] = useState([]);
  const [selectedDevice, setSelectedDevice] = useState(null);
  const [serverStatus, setServerStatus] = useState(false);
  const [logEntries, setLogEntries] = useState([]);
  const [port, setPort] = useState('');
  const [baudRate, setBaudRate] = useState('9600');
  const [ports, setPorts] = useState([]);
  const [isConnecting, setIsConnecting] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [sortConfig, setSortConfig] = useState({ key: 'slaveId', direction: 'asc' });
  const [theme, setTheme] = useState('light');
  
  // Initialize theme from localStorage or system preference
  useEffect(() => {
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme) {
      setTheme(savedTheme);
      document.documentElement.setAttribute('data-theme', savedTheme);
    } else {
      const systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      const initialTheme = systemPrefersDark ? 'dark' : 'light';
      setTheme(initialTheme);
      document.documentElement.setAttribute('data-theme', initialTheme);
    }
  }, []);
  
  // Apply theme to document
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }, [theme]);
  
  // Chart data for selected device
  const [chartData, setChartData] = useState({
    labels: [],
    datasets: [
      {
        label: 'Voltage',
        data: [],
        borderColor: '#3498db',
        backgroundColor: 'rgba(52, 152, 219, 0.1)',
        tension: 0.4,
        fill: true
      },
      {
        label: 'Current',
        data: [],
        borderColor: '#2ecc71',
        backgroundColor: 'rgba(46, 204, 113, 0.1)',
        tension: 0.4,
        fill: true
      }
    ]
  });
  
  const socketRef = useRef(null);
  
  // Initialize socket connection
  useEffect(() => {
    // Connect to server
    const socket = new WebSocket('ws://localhost:3001/socket.io/?EIO=4&transport=websocket');
    
    socket.onopen = () => {
      console.log('Connected to server');
      socketRef.current = socket;
      
      // Request devices list
      socket.send(JSON.stringify({ type: 'get-devices' }));
    };
    
    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        if (data.type === 'devices-list') {
          setDevices(data.devices);
          if (data.devices.length > 0) {
            setSelectedDevice(data.devices[0]);
          }
        } else if (data.type === 'server-status') {
          setServerStatus(data.status);
        } else if (data.type === 'log') {
          const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
          setLogEntries(prev => [...prev.slice(-9), { ...data, timestamp }]);
        } else if (data.type === 'device-updated') {
          setDevices(prev => prev.map(d => d.slaveId === data.id ? { ...d, ...data } : d));
          
          // Update chart data when device is updated
          if (selectedDevice && selectedDevice.slaveId === data.id) {
            const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
            
            // Add new data point
            setChartData(prev => ({
              labels: [...prev.labels.slice(-9), now],
              datasets: prev.datasets.map(dataset => ({
                ...dataset,
                data: [...dataset.data.slice(-9), data.voltage || 0]
              }))
            }));
          }
        } else if (data.type === 'device-added') {
          setDevices(prev => [...prev, data.device]);
        } else if (data.type === 'device-removed') {
          setDevices(prev => prev.filter(d => d.slaveId !== data.slaveId));
        }
      } catch (error) {
        console.error('Error parsing message:', error);
      }
    };
    
    socket.onerror = (error) => {
      console.error('Socket error:', error);
    };
    
    socket.onclose = () => {
      console.log('Disconnected from server');
      socketRef.current = null;
    };
    
    return () => {
      if (socketRef.current) {
        socketRef.current.close();
      }
    };
  }, [selectedDevice]);
  
  // Load available ports
  const loadPorts = async () => {
    try {
      const response = await fetch('/api/ports');
      const data = await response.json();
      setPorts(data);
      if (data.length > 0 && !port) {
        setPort(data[0]);
      }
    } catch (error) {
      console.error('Error loading ports:', error);
    }
  };
  
  // Start server
  const startServer = () => {
    if (!port || isConnecting) return;
    
    setIsConnecting(true);
    
    if (socketRef.current) {
      socketRef.current.send(JSON.stringify({ 
        type: 'start-server', 
        port, 
        baud: baudRate 
      }));
    }
  };
  
  // Stop server
  const stopServer = () => {
    if (socketRef.current) {
      socketRef.current.send(JSON.stringify({ type: 'stop-server' }));
      setServerStatus(false);
      setIsConnecting(false);
    }
  };
  
  // Toggle device
  const toggleDevice = (slaveId) => {
    if (socketRef.current) {
      socketRef.current.send(JSON.stringify({ 
        type: 'toggle-device', 
        slaveId 
      }));
    }
  };
  
  // Add device
  const addDevice = () => {
    if (socketRef.current) {
      const newDevice = {
        slaveId: Math.floor(Math.random() * 100) + 1,
        type: 'inverter',
        status: 'online',
        voltage: Math.floor(Math.random() * 100) + 200,
        current: Math.floor(Math.random() * 20) + 5,
        temperature: Math.floor(Math.random() * 30) + 20
      };
      socketRef.current.send(JSON.stringify({ 
        type: 'add-device', 
        device: newDevice 
      }));
    }
  };
  
  // Remove device
  const removeDevice = (slaveId) => {
    if (socketRef.current) {
      socketRef.current.send(JSON.stringify({ 
        type: 'remove-device', 
        slaveId 
      }));
    }
  };
  
  // Filter and sort devices
  const filteredAndSortedDevices = devices
    .filter(device => 
      device.slaveId.toString().includes(searchTerm) ||
      device.type.toLowerCase().includes(searchTerm.toLowerCase()) ||
      device.status.toLowerCase().includes(searchTerm.toLowerCase())
    )
    .sort((a, b) => {
      if (a[sortConfig.key] < b[sortConfig.key]) {
        return sortConfig.direction === 'asc' ? -1 : 1;
      }
      if (a[sortConfig.key] > b[sortConfig.key]) {
        return sortConfig.direction === 'asc' ? 1 : -1;
      }
      return 0;
    });
  
  // Handle sorting
  const handleSort = (key) => {
    let direction = 'asc';
    if (sortConfig.key === key && sortConfig.direction === 'asc') {
      direction = 'desc';
    }
    setSortConfig({ key, direction });
  };
  
  // Theme toggle handler
  const toggleTheme = () => {
    const newTheme = theme === 'light' ? 'dark' : 'light';
    setTheme(newTheme);
  };
  
  // Bulk actions
  const toggleAllDevices = () => {
    if (socketRef.current) {
      socketRef.current.send(JSON.stringify({ 
        type: 'toggle-all-devices' 
      }));
    }
  };
  
  // Get device status color
  const getDeviceStatusColor = (status) => {
    switch (status) {
      case 'online': return 'success';
      case 'offline': return 'danger';
      default: return 'secondary';
    }
  };
  
  return (
    <div className={clsx(styles.app, styles['app-main'])}>
      <header className={styles['app-header']}>
        <h1>JS Modbus Simulator</h1>
        <button 
          className={styles['theme-toggle']}
          onClick={toggleTheme}
          aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
        >
          {theme === 'light' ? '🌙' : '☀️'}
          <span>{theme === 'light' ? 'Dark Mode' : 'Light Mode'}</span>
        </button>
      </header>
      
      <main className={styles['app-main']}>
        {/* Control Panel */}
        <section className={styles['control-panel']}>
          <div className={styles['panel-header']}>
            <h2>Control Panel</h2>
          </div>
          
          <div className={styles['form-group']}>
            <label htmlFor="port">Serial Port</label>
            <select 
              id="port" 
              value={port} 
              onChange={(e) => setPort(e.target.value)}
              className={styles['form-control']}
            >
              <option value="">Select port</option>
              {ports.map((p, i) => (
                <option key={i} value={p}>{p}</option>
              ))}
            </select>
          </div>
          
          <div className={styles['form-group']}>
            <label htmlFor="baudRate">Baud Rate</label>
            <select 
              id="baudRate" 
              value={baudRate} 
              onChange={(e) => setBaudRate(e.target.value)}
              className={styles['form-control']}
            >
              <option value="9600">9600</option>
              <option value="19200">19200</option>
              <option value="38400">38400</option>
              <option value="57600">57600</option>
              <option value="115200">115200</option>
            </select>
          </div>
          
          <div className={styles['button-group']}>
            <button 
              className={clsx(styles.btn, styles['btn-primary'])}
              onClick={serverStatus ? stopServer : startServer}
              disabled={isConnecting}
            >
              {serverStatus ? 'Stop Server' : 'Start Server'}
            </button>
            <button 
              className={clsx(styles.btn, styles['btn-success'])}
              onClick={addDevice}
            >
              Add Device
            </button>
            <button 
              className={clsx(styles.btn, styles['btn-secondary'])}
              onClick={loadPorts}
            >
              Refresh Ports
            </button>
          </div>
          
          <div className={styles['form-group']} style={{ marginTop: '1rem' }}>
            <label>Server Status</label>
            <div className={styles['status-badge']}>
              <span className={styles['status-indicator']} style={{
                backgroundColor: serverStatus ? '#2ecc71' : '#e74c3c'
              }}></span>
              {serverStatus ? 'RUNNING' : 'STOPPED'}
            </div>
          </div>
        </section>
        
        {/* Devices Section */}
        <section className={styles['devices-section']}>
          <div className={styles['panel-header']}>
            <h2>Devices ({filteredAndSortedDevices.length})</h2>
            <div className={styles['search-bar']}>
              <input
                type="text"
                placeholder="Search devices..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className={styles['form-control']}
              />
              <button 
                className={clsx(styles.btn, styles['btn-secondary'])}
                onClick={toggleAllDevices}
              >
                Toggle All
              </button>
            </div>
          </div>
          
          {filteredAndSortedDevices.length === 0 ? (
            <p>No devices found. Try adding a new device.</p>
          ) : (
            <div className={styles['devices-grid']}>
              {filteredAndSortedDevices.map((device) => (
                <div key={device.slaveId} className={styles['device-card']}>
                  <div className={styles['device-header']}>
                    <h3>Device #{device.slaveId}</h3>
                    <span className={styles['device-type']}>{device.type}</span>
                  </div>
                  
                  <div className={styles['device-status']}>
                    <span className={styles['status-indicator']} style={{
                      backgroundColor: device.status === 'online' ? '#2ecc71' : '#e74c3c'
                    }}></span>
                    <span>{device.status}</span>
                  </div>
                  
                  <div className={styles['device-controls']}>
                    <div>
                      <strong>Voltage:</strong> {device.voltage}V<br />
                      <strong>Current:</strong> {device.current}A<br />
                      <strong>Temp:</strong> {device.temperature}°C
                    </div>
                    <div className={styles['button-group']}>
                      <button 
                        className={clsx(styles.btn, styles['btn-sm'], device.status === 'online' ? styles['btn-danger'] : styles['btn-success'])}
                        onClick={() => toggleDevice(device.slaveId)}
                      >
                        {device.status === 'online' ? 'Offline' : 'Online'}
                      </button>
                      <button 
                        className={clsx(styles.btn, styles['btn-sm'], styles['btn-danger'])}
                        onClick={() => removeDevice(device.slaveId)}
                      >
                        Remove
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
        
        {/* Log Section */}
        <section className={styles['log-section']}>
          <div className={styles['panel-header']}>
            <h2>System Log</h2>
          </div>
          
          <div className={styles['log-container']}>
            {logEntries.length === 0 ? (
              <p>No log entries yet. Start the server to see activity.</p>
            ) : (
              <div>
                {logEntries.map((entry, index) => (
                  <div key={index} className={clsx(styles['log-entry'], entry.type === 'error' ? styles['log-error'] : entry.type === 'success' ? styles['log-success'] : '')}>
                    <span className={styles['log-timestamp']}>{entry.timestamp}</span>
                    <span className={styles['log-message']}>{entry.message}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>
      </main>
      
      {/* Chart Section - only shown when device is selected */}
      {selectedDevice && (
        <section className={styles['devices-section']} style={{ gridColumn: '1 / -1' }}>
          <div className={styles['panel-header']}>
            <h2>Real-time Metrics for Device #{selectedDevice.slaveId}</h2>
          </div>
          <div className={styles['chart-container']}>
            <Line 
              data={chartData} 
              options={{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                  legend: {
                    position: 'top',
                  },
                  title: {
                    display: true,
                    text: 'Voltage & Current Monitoring'
                  }
                },
                scales: {
                  y: {
                    beginAtZero: true
                  }
                }
              }}
            />
          </div>
        </section>
      )}
    </div>
  );
};

export default App;
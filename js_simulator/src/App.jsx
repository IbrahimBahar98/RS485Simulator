import React, { useState, useEffect, useRef } from 'react';
import { Line, Bar } from 'react-chartjs-2';
import clsx from 'clsx';
import './App.module.css';

// Mock data for initial render
const initialDevices = [
  { slaveId: 1, type: 'inverter', status: 'online', voltage: 230, current: 15, power: 3450 },
  { slaveId: 2, type: 'sensor', status: 'offline', voltage: 0, current: 0, power: 0 },
  { slaveId: 3, type: 'actuator', status: 'online', voltage: 24, current: 2, power: 48 }
];

const App = () => {
  const [theme, setTheme] = useState('light');
  const [devices, setDevices] = useState(initialDevices);
  const [selectedDevice, setSelectedDevice] = useState(null);
  const [chartData, setChartData] = useState({
    labels: Array.from({ length: 10 }, (_, i) => `t-${i}`),
    datasets: [
      {
        label: 'Voltage (V)',
        data: Array.from({ length: 10 }, () => Math.floor(Math.random() * 100) + 200),
        borderColor: 'rgb(53, 162, 235)',
        backgroundColor: 'rgba(53, 162, 235, 0.5)',
      },
      {
        label: 'Current (A)',
        data: Array.from({ length: 10 }, () => Math.floor(Math.random() * 20) + 5),
        borderColor: 'rgb(255, 99, 132)',
        backgroundColor: 'rgba(255, 99, 132, 0.5)',
      }
    ]
  });
  const [logMessages, setLogMessages] = useState([
    'System started',
    'WebSocket connected',
    'Loaded 3 devices'
  ]);
  const [serverStatus, setServerStatus] = useState('STOPPED');
  const [searchTerm, setSearchTerm] = useState('');
  const logEndRef = useRef(null);

  // Initialize theme from localStorage
  useEffect(() => {
    const savedTheme = localStorage.getItem('theme') || 'light';
    setTheme(savedTheme);
    document.documentElement.setAttribute('data-theme', savedTheme);
  }, []);

  // Toggle theme
  const toggleTheme = () => {
    const newTheme = theme === 'light' ? 'dark' : 'light';
    setTheme(newTheme);
    localStorage.setItem('theme', newTheme);
    document.documentElement.setAttribute('data-theme', newTheme);
  };

  // Simulate real-time chart updates
  useEffect(() => {
    const interval = setInterval(() => {
      setChartData(prev => ({
        ...prev,
        labels: [...prev.labels.slice(1), `t-${Date.now() % 1000}`],
        datasets: prev.datasets.map(ds => ({
          ...ds,
          data: [...ds.data.slice(1), Math.floor(Math.random() * 100) + (ds.label.includes('Voltage') ? 200 : 5)]
        }))
      }));
    }, 2000);

    return () => clearInterval(interval);
  }, []);

  // Scroll log to bottom
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logMessages]);

  // Handle device toggle
  const toggleDevice = (slaveId) => {
    setDevices(prev => prev.map(device => 
      device.slaveId === slaveId 
        ? { ...device, status: device.status === 'online' ? 'offline' : 'online' } 
        : device
    ));
    setLogMessages(prev => [...prev, `Device #${slaveId} status changed`]);
  };

  // Filter devices based on search term
  const filteredDevices = devices.filter(device =>
    device.type.toLowerCase().includes(searchTerm.toLowerCase()) ||
    device.slaveId.toString().includes(searchTerm)
  );

  // Get status color class
  const getStatusColor = (status) => {
    switch (status) {
      case 'online': return 'bg-green-500';
      case 'offline': return 'bg-red-500';
      default: return 'bg-gray-500';
    }
  };

  return (
    <div className={clsx('app', `theme-${theme}`)}>
      {/* Header */}
      <header className="app-header">
        <h1 className="app-title">JS Modbus Simulator</h1>
        <button 
          onClick={toggleTheme}
          className="theme-toggle"
          aria-label={theme === 'light' ? 'Switch to dark mode' : 'Switch to light mode'}
        >
          {theme === 'light' ? '🌙' : '☀️'}
        </button>
      </header>

      <main className="app-main">
        {/* Control Panel */}
        <section className="control-panel">
          <h2 className="panel-title">Control Panel</h2>
          <div className="status-indicator">
            <span className="status-label">Server Status:</span>
            <span className={`status-value ${serverStatus === 'RUNNING' ? 'running' : 'stopped'}`}>
              {serverStatus}
            </span>
          </div>
          <div className="control-buttons">
            <button className="btn btn-primary">Start Server</button>
            <button className="btn btn-secondary">Stop Server</button>
            <button className="btn btn-outline">Add Device</button>
          </div>
        </section>

        {/* Devices Section */}
        <section className="devices-section">
          <div className="section-header">
            <h2 className="panel-title">Devices ({filteredDevices.length})</h2>
            <div className="search-box">
              <input
                type="text"
                placeholder="Search devices..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="search-input"
              />
            </div>
          </div>
          
          <div className="devices-table-container">
            <table className="devices-table">
              <thead>
                <tr>
                  <th>Slave ID</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Voltage (V)</th>
                  <th>Current (A)</th>
                  <th>Power (W)</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredDevices.map((device) => (
                  <tr key={device.slaveId} className="device-row">
                    <td>{device.slaveId}</td>
                    <td>{device.type}</td>
                    <td>
                      <span className={`status-badge ${getStatusColor(device.status)}`}></span>
                      {device.status}
                    </td>
                    <td>{device.voltage}</td>
                    <td>{device.current}</td>
                    <td>{device.power}</td>
                    <td>
                      <button 
                        onClick={() => toggleDevice(device.slaveId)}
                        className="btn btn-sm"
                      >
                        {device.status === 'online' ? 'Offline' : 'Online'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* Chart Section */}
        <section className="chart-section">
          <h2 className="panel-title">Real-time Metrics</h2>
          <div className="chart-container">
            <Line 
              data={chartData} 
              options={{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                  legend: {
                    position: 'top',
                  },
                },
                scales: {
                  y: {
                    beginAtZero: true,
                  },
                },
              }}
            />
          </div>
        </section>

        {/* Log Section */}
        <section className="log-section">
          <h2 className="panel-title">System Log</h2>
          <div className="log-container">
            {logMessages.map((msg, index) => (
              <div key={index} className="log-entry">[{new Date().toLocaleTimeString()}] {msg}</div>
            ))}
            <div ref={logEndRef} />
          </div>
        </section>
      </main>

      <footer className="app-footer">
        <p>JS Modbus Simulator v1.0.0 • All rights reserved</p>
      </footer>
    </div>
  );
};

export default App;
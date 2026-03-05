# RS-485/Modbus Simulator

A collection of Python-based RS-485/Modbus RTU simulators for industrial flow meters, energy meters, and inverters. Designed for testing and development with EdgeBox-ESP-100 and other Modbus masters.

## 🎯 Purpose

This project provides realistic simulation tools for RS-485/Modbus devices, enabling:
- Hardware-in-the-loop (HIL) testing without physical devices
- Protocol validation and debugging
- Integration testing with SCADA systems and edge controllers
- Educational demonstrations of Modbus RTU communication

## 📦 Prerequisites

- Python 3.8 or higher
- Serial port access (COM port on Windows, /dev/tty* on Linux/macOS)
- Required Python packages:
  ```bash
  pip install pymodbus>=3.6 pyserial tkinter
  ```

## ⚙️ Installation & Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/IbrahimBahar98/RS485Simulator.git
   cd RS485Simulator
   ```

2. Install dependencies:
   ```bash
   pip install -e .
   ```

3. Verify installation:
   ```bash
   python -c "import pymodbus; print(pymodbus.__version__)"
   ```

## ▶️ Quick Start

Run the recommended simulator:
```bash
python ModbusFlowMeterSimulator_Dual.py
```

1. Select your COM port from the dropdown
2. Click **"Start Server"**
3. Adjust values using sliders and input fields
4. Your Modbus master can now read from slave IDs 110 and 111

## 📋 Available Simulators

| Simulator | Slave IDs | Registers | Features | Status |
|-----------|-----------|-----------|----------|--------|
| `ModbusFlowMeterSimulator_Dual.py` | 110, 111 | Input Registers (FC 04) | Simple interface, dual slave support | ✅ Recommended |
| `ModbusFlowMeterSimulator_Complete.py` | 110, 111 | Input + Holding Registers (FC 04 + FC 03) | Full register control, tabbed UI | ✅ Complete |
| `ModbusFlowMeterSimulator_Working.py` | 110, 111 | Input Registers (FC 04) | Basic working version | ✅ Working |
| `ModbusEnergyMeterSimulator_ADL400.py` | 1, 100 | Input Registers (FC 04) | Energy meter simulation | ✅ Energy Meter |
| `ModbusInverterSimulator.py` | 1, 100 | Input Registers (FC 04) | Inverter simulation | ✅ Inverter |

## 📊 Register Maps

### Flow Meter (ADL400)
- **Input Registers (FC 04)**: 772-773 (Forward Total Flow), 778-779 (Flow Rate), 812-813 (Conductivity)
- **Holding Registers (FC 03)**: 261-262 (Flow Range), 281-282 (Alarm High), 284-285 (Alarm Low)
- [View full register map](fr500a_extracted.txt)

### Energy Meter (ADL400)
- **Input Registers (FC 04)**: 0-99 (Voltage, Current, Power, Energy)
- [View energy meter register map](https://github.com/IbrahimBahar98/RS485Simulator/blob/main/ADL400_register_map.pdf)

## 🔧 Configuration

Default settings:
- **Port**: COM18 (Windows) or /dev/ttyUSB0 (Linux)
- **Baud Rate**: 9600
- **Data Bits**: 8
- **Parity**: None
- **Stop Bits**: 1
- **Byte Order**: Big-endian with swapped word order (CDAB format)

## 🧪 Testing

Run the complete test suite:
```bash
pytest tests/ --tb=short
```

Generate coverage report:
```bash
pytest tests/ --cov=. --cov-report=html
```

## 🛠️ Development

### Project Structure
```
RS485Simulator/
├── ModbusFlowMeterSimulator_Complete.py  # Main simulator (monolithic)
├── core/                                # Core logic (to be extracted)
│   ├── registers.py                     # Register packing/unpacking
│   └── modbus_server.py                 # Modbus server abstraction
├── ui/                                  # GUI components (to be extracted)
│   ├── theme.py                         # Theme engine
│   └── widgets.py                       # Custom widgets
├── tests/                               # Test suite
├── data/                                # Register maps and configurations
│   └── registers/
│       ├── flow_meter_adl400.yaml
│       └── inverter_fr500a.yaml
├── pyproject.toml                       # Build and test configuration
└── README.md                            # This documentation
```

### Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes (`git commit -am 'Add some feature'`)
4. Push to the branch (`git push origin feature/your-feature`)
5. Open a pull request

Please follow these guidelines:
- Add type hints and docstrings per PEP 484 and PEP 257
- Write unit tests for new functionality
- Maintain 80%+ test coverage
- Use black for code formatting

## 📜 License

MIT License - See [LICENSE](LICENSE) for details.

## 📞 Support & Contact

For issues or questions, please open a GitHub issue or contact the development team.

---

**Last Updated**: March 2026  
**Compatible with**: EdgeBox-ESP-100, Pymodbus 3.6+, Python 3.8+

# Modbus Flow Meter Simulators

Collection of Modbus RTU simulators for Enelsan Electromagnetic Flow Meters, compatible with EdgeBox-ESP-100.

## 🎯 Recommended Version

**`ModbusFlowMeterSimulator_Dual.py`** - Simple, tested, and fully functional.

## 📦 Requirements

```bash
pip install pymodbus==3.11.4 pyserial tkinter
```

## 🚀 Quick Start

```bash
python ModbusFlowMeterSimulator_Dual.py
```

1. Click **"Start Server"**
2. Adjust values using sliders
3. EdgeBox will read the simulated data

## 📋 Available Simulators

### 1. ModbusFlowMeterSimulator_Dual.py ⭐ (Recommended)
- **Slave IDs**: 110, 111
- **Registers**: Input Registers (FC 04)
- **Controls**: Flow Rate, Conductivity, Total Flow
- **Status**: ✅ Fully tested and working

### 2. ModbusFlowMeterSimulator_Complete.py
- **Slave IDs**: 110, 111
- **Registers**: Input Registers (FC 04) + Holding Registers (FC 03)
- **Controls**: All process variables and configuration parameters
- **Features**: Tabbed interface with full register control
- **Status**: ✅ Working with all registers

### 3. ModbusFlowMeterSimulator_Working.py
- **Slave IDs**: 110, 111
- **Registers**: Input Registers (FC 04)
- **Status**: ✅ Basic working version

### 4. ModbusFlowMeterSimulator.py
- **Original version** with GUI
- **Status**: ⚠️ Legacy - use Dual or Complete instead

## 🔧 Configuration

Default settings:
- **Port**: COM18
- **Baud Rate**: 9600
- **Data Bits**: 8
- **Parity**: None
- **Stop Bits**: 1

## 📊 Supported Registers

### Input Registers (FC 04)
| Register | Type | Description |
|----------|------|-------------|
| 772-773 | uint32 | Forward Total Flow |
| 774 | uint16 | Unit Info (3 = m³/h) |
| 777 | uint16 | Alarm Flags |
| 778-779 | float32 | Flow Rate (m³/h) |
| 786 | uint16 | Overflow Count |
| 812-813 | float32 | Conductivity (µS/cm) |

### Holding Registers (FC 03) - Complete version only
| Register | Type | Description |
|----------|------|-------------|
| 261-262 | float32 | Flow Range |
| 281-282 | float32 | Alarm High Value |
| 284-285 | float32 | Alarm Low Value |

## 🔍 Byte Order

All simulators use **big-endian bytes with swapped word order** (CDAB format) to match the EdgeBox `getFloat()` and `getUint32()` functions:

```python
# EdgeBox expects:
u.r[1] = data[0];  # Low word
u.r[0] = data[1];  # High word
```

## 🐛 Troubleshooting

### "Port COM18 not found"
- Check available COM ports in Device Manager
- Update the port in the GUI before starting

### "Read Static Params Failed"
- Use `ModbusFlowMeterSimulator_Complete.py` which includes Holding Registers
- Ensure server is started before EdgeBox attempts to read

### Garbage values
- Ensure you're using the latest version with correct byte order
- All simulators now use swapped word order for compatibility

## 📝 Notes

- **Pymodbus 3.11.4** required (not compatible with 2.x)
- Simulators support **dual slave IDs** (110 and 111) for multi-device testing
- Values update every 500ms automatically
- Server runs in background thread with async event loop

## 🎓 Development Notes

### Key Fixes Applied:
1. ✅ Upgraded from Pymodbus 2.5.3 to 3.11.4
2. ✅ Fixed API changes (`ModbusSlaveContext` → `ModbusDeviceContext`, `slaves` → `devices`)
3. ✅ Removed deprecated `BinaryPayloadBuilder` (use `struct.pack` instead)
4. ✅ Corrected byte order with manual word swapping
5. ✅ Added Holding Register support for configuration parameters

### Byte Order Details:
The EdgeBox firmware expects **CDAB word order** (low word first, high word second) for multi-word values. The simulators pack values as:

```python
def pack_float32(value):
    packed = struct.pack('>f', value)  # Big-endian bytes
    word0 = struct.unpack('>H', packed[0:2])[0]  # High word
    word1 = struct.unpack('>H', packed[2:4])[0]  # Low word
    return [word1, word0]  # Swap: send low word first
```

## 📄 License

Created for SEITech OEE Demo project.

## 🤝 Contributing

For issues or improvements, please contact the development team.

---

**Last Updated**: December 2025  
**Compatible with**: EdgeBox-ESP-100, Pymodbus 3.11.4

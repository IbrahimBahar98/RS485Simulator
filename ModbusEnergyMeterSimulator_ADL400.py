import tkinter as tk
from tkinter import ttk, messagebox
import threading
import logging
import asyncio
import serial.tools.list_ports
import struct
import sys
import time

# --- Pymodbus v3.x Robust Imports ---
print(f"Debug: Pymodbus import check...")

# Check Serial Dependency
try:
    import serial
    print(f"Debug: serial imported from {serial.__file__}")
except ImportError as e:
    print(f"Debug: FAILED to import serial: {e}")

StartSerialServer = None
StartAsyncSerialServer = None
ModbusSerialServer = None
ServerStop = None

try:
    import pymodbus.server
    print(f"Debug: pymodbus.server dir: {dir(pymodbus.server)}")
except ImportError as e:
    print(f"Debug: Failed to import pymodbus.server module: {e}")

try:
    from pymodbus.server import StartSerialServer
    print("Debug: Imported StartSerialServer")
except ImportError as e:
    print(f"Debug: Failed to import StartSerialServer: {e}")

try:
    from pymodbus.server import StartAsyncSerialServer
    print("Debug: Imported StartAsyncSerialServer")
except ImportError as e:
    print(f"Debug: Failed to import StartAsyncSerialServer: {e}")

try:
    from pymodbus.server import ModbusSerialServer
    print("Debug: Imported ModbusSerialServer")
except ImportError as e:
    print(f"Debug: Failed to import ModbusSerialServer: {e}")

try:
    from pymodbus.server import ServerStop
    print("Debug: Imported ServerStop")
except ImportError as e:
    print(f"Debug: Failed to import ServerStop: {e}")

try:
    from pymodbus.device import ModbusDeviceIdentification
except ImportError:
    ModbusDeviceIdentification = None

# Datastore Imports - Try multiple strategies for v3.x
ModbusServerContext = None
ModbusSlaveContext = None
ModbusSequentialDataBlock = None

try:
    from pymodbus.datastore import ModbusServerContext
    from pymodbus.datastore import ModbusSequentialDataBlock
    print("Debug: Imported ModbusServerContext and ModbusSequentialDataBlock")
    
    try:
        from pymodbus.datastore import ModbusSlaveContext
        print("Debug: Imported ModbusSlaveContext")
    except ImportError:
        print("Debug: ModbusSlaveContext not available (v3.6+ - will use dict approach)")
        
except ImportError as e:
    print(f"Debug: Strategy 1 failed: {e}")

if ModbusServerContext is None:
    try:
        from pymodbus.datastore.context import ModbusServerContext
        print("Debug: Imported ModbusServerContext from .context")
    except ImportError as e:
        print(f"Debug: Failed to import ModbusServerContext: {e}")

if ModbusSequentialDataBlock is None:
    try:
        from pymodbus.datastore.store import ModbusSequentialDataBlock
        print("Debug: Imported ModbusSequentialDataBlock from .store")
    except ImportError:
        try:
            from pymodbus.datastore.sequential import ModbusSequentialDataBlock
            print("Debug: Imported ModbusSequentialDataBlock from .sequential")
        except ImportError as e:
            print(f"Debug: Failed to import ModbusSequentialDataBlock: {e}")

# Final check and report
print(f"Debug: ModbusServerContext = {ModbusServerContext}")
print(f"Debug: ModbusSlaveContext = {ModbusSlaveContext}")
print(f"Debug: ModbusSequentialDataBlock = {ModbusSequentialDataBlock}")

# Configure logging
logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.INFO)


class TextHandler(logging.Handler):
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget
        self.text_widget.tag_config("RX", foreground="blue")
        self.text_widget.tag_config("TX", foreground="green")
        self.text_widget.tag_config("ERR", foreground="red")
        self.text_widget.tag_config("INFO", foreground="black")

    def emit(self, record):
        msg = self.format(record)
        
        # FILTER: Prevent performance degradation from Device 100 spam
        if "requested device id does not exist: 100" in msg:
            return
        
        # Simple color coding based on content
        tag = "INFO"
        if "Received" in msg or "recv" in msg.lower():
            tag = "RX"
        elif "Sending" in msg or "send" in msg.lower():
            tag = "TX"
        elif "Error" in msg or "Exception" in msg:
            tag = "ERR"
            
        def append():
            self.text_widget.configure(state='normal')
            self.text_widget.insert('end', msg + '\n', tag)
            self.text_widget.see('end')
            self.text_widget.configure(state='disabled')
            
        # Ensure thread safety for GUI updates
        self.text_widget.after(0, append)


# --- Custom ModbusSlaveContext to fix v3.x compatibility ---
class ModbusSlaveContext:
    """
    Shim class to replace the missing ModbusSlaveContext in Pymodbus v3.x.
    It wraps the 4 data blocks (di, co, hr, ir) and provides the required interface.
    """
    def __init__(self, di=None, co=None, hr=None, ir=None, zero_mode=False):
        self.store = {}
        if di: self.store['d'] = di
        if co: self.store['c'] = co
        if hr: self.store['h'] = hr
        if ir: self.store['i'] = ir
        self.zero_mode = zero_mode

    def __str__(self):
        return "ModbusSlaveContext"

    def reset(self):
        for block in self.store.values():
            block.reset()

    def validate(self, fx, address, count=1):
        if fx in [1, 5, 15]: block = self.store.get('c')
        elif fx in [2]:      block = self.store.get('d')
        elif fx in [3, 6, 16]: block = self.store.get('h')
        elif fx in [4]:      block = self.store.get('i')
        else: return False
        
        if not block: return False
        return block.validate(address, count)

    def getValues(self, fx, address, count=1):
        if fx in [1, 5, 15]: block = self.store.get('c')
        elif fx in [2]:      block = self.store.get('d')
        elif fx in [3, 6, 16]: block = self.store.get('h')
        elif fx in [4]:      block = self.store.get('i')
        else: return []
        
        vals = block.getValues(address, count)
        return vals

    def setValues(self, fx, address, values):
        if fx in [1, 5, 15]: block = self.store.get('c')
        elif fx in [2]:      block = self.store.get('d')
        elif fx in [3, 6, 16]: block = self.store.get('h')
        elif fx in [4]:      block = self.store.get('i')
        else: return
        
        block.setValues(address, values)
        
    async def async_getValues(self, fx, address, count=1):
        return self.getValues(fx, address, count)
        
    async def async_setValues(self, fx, address, values):
        return self.setValues(fx, address, values)


class EnergyMeterSimulatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Energy Meter Simulator (ADL400 - Modbus RTU Slave) - v3.11.4")
        self.root.geometry("1000x900")

        self.server_thread = None
        self.stop_server_event = threading.Event()
        self.context = None
        self.store = None

        self.setup_ui()
        
        # Setup Logging to GUI
        self.logger = logging.getLogger("pymodbus")
        self.logger.setLevel(logging.INFO)
        self.logger.handlers = []
        
        self.log_handler = TextHandler(self.log_text)
        self.log_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s', '%H:%M:%S'))
        self.logger.addHandler(self.log_handler)
        
        self.my_logger = logging.getLogger("SimApp")
        self.my_logger.setLevel(logging.INFO)
        self.my_logger.addHandler(self.log_handler)
        
        # Check imports availability
        if not StartAsyncSerialServer and not StartSerialServer:
            self.my_log("ERROR: Could not import Pymodbus Server function. Check version.")

    def my_log(self, msg):
        self.my_logger.info(msg)

    def log(self, msg):
        """Simple internal log"""
        self.my_log(msg)

    def setup_ui(self):
        # Configuration Frame
        config_frame = ttk.LabelFrame(self.root, text="Configuration", padding="10")
        config_frame.pack(fill="x", padx=10, pady=5)

        # COM Port
        ttk.Label(config_frame, text="COM Port:").grid(row=0, column=0, padx=5, pady=5)
        self.com_port_var = tk.StringVar()
        self.com_port_combo = ttk.Combobox(config_frame, textvariable=self.com_port_var)
        self.com_port_combo.grid(row=0, column=1, padx=5, pady=5)
        self.refresh_ports()
        ttk.Button(config_frame, text="Refresh", command=self.refresh_ports).grid(row=0, column=2, padx=5, pady=5)

        # Baudrate
        ttk.Label(config_frame, text="Baudrate:").grid(row=1, column=0, padx=5, pady=5)
        self.baudrate_var = tk.IntVar(value=9600)
        ttk.Combobox(config_frame, textvariable=self.baudrate_var, values=[4800, 9600, 19200, 38400, 57600, 115200]).grid(row=1, column=1, padx=5, pady=5)

        # Slave ID
        ttk.Label(config_frame, text="Slave ID:").grid(row=2, column=0, padx=5, pady=5)
        self.slave_id_var = tk.IntVar(value=1)
        ttk.Entry(config_frame, textvariable=self.slave_id_var).grid(row=2, column=1, padx=5, pady=5)

        # Start/Stop Buttons
        self.start_btn = ttk.Button(config_frame, text="Start Server", command=self.start_server)
        self.start_btn.grid(row=3, column=0, padx=5, pady=10)
        self.stop_btn = ttk.Button(config_frame, text="Stop Server", command=self.stop_server, state="disabled")
        self.stop_btn.grid(row=3, column=1, padx=5, pady=10)
        
        # Traffic Toggle
        self.show_traffic_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(config_frame, text="Show Bus Traffic (Hex)", variable=self.show_traffic_var, command=self.toggle_traffic).grid(row=3, column=2, padx=5)

        # Simulation Controls Frame
        sim_frame = ttk.LabelFrame(self.root, text="Energy Meter Control Panel", padding="10")
        sim_frame.pack(fill="x", padx=10, pady=5)
        
        # Voltage Controls
        ttk.Label(sim_frame, text="Phase A Voltage (V):").grid(row=0, column=0, padx=5, pady=5)
        self.voltage_a_var = tk.DoubleVar(value=230.0)
        self.voltage_a_entry = ttk.Entry(sim_frame, textvariable=self.voltage_a_var)
        self.voltage_a_entry.grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(sim_frame, text="Set", command=self.set_voltage_a).grid(row=0, column=2, padx=5, pady=5)

        # Current Controls
        ttk.Label(sim_frame, text="Phase A Current (A):").grid(row=1, column=0, padx=5, pady=5)
        self.current_a_var = tk.DoubleVar(value=10.0)
        self.current_a_entry = ttk.Entry(sim_frame, textvariable=self.current_a_var)
        self.current_a_entry.grid(row=1, column=1, padx=5, pady=5)
        ttk.Button(sim_frame, text="Set", command=self.set_current_a).grid(row=1, column=2, padx=5, pady=5)

        # Power Controls
        ttk.Label(sim_frame, text="Total Active Power (W):").grid(row=2, column=0, padx=5, pady=5)
        self.power_var = tk.DoubleVar(value=2300.0)
        self.power_entry = ttk.Entry(sim_frame, textvariable=self.power_var)
        self.power_entry.grid(row=2, column=1, padx=5, pady=5)
        ttk.Button(sim_frame, text="Set", command=self.set_power).grid(row=2, column=2, padx=5, pady=5)

        # Frequency Controls
        ttk.Label(sim_frame, text="Frequency (Hz):").grid(row=3, column=0, padx=5, pady=5)
        self.frequency_var = tk.DoubleVar(value=50.0)
        self.frequency_entry = ttk.Entry(sim_frame, textvariable=self.frequency_var)
        self.frequency_entry.grid(row=3, column=1, padx=5, pady=5)
        ttk.Button(sim_frame, text="Set", command=self.set_frequency).grid(row=3, column=2, padx=5, pady=5)

        # Total Energy Controls
        ttk.Label(sim_frame, text="Total Active Energy (kWh):").grid(row=4, column=0, padx=5, pady=5)
        self.energy_var = tk.IntVar(value=1000)
        self.energy_entry = ttk.Entry(sim_frame, textvariable=self.energy_var)
        self.energy_entry.grid(row=4, column=1, padx=5, pady=5)
        ttk.Button(sim_frame, text="Set", command=self.set_energy).grid(row=4, column=2, padx=5, pady=5)

        # Power Factor Controls
        ttk.Label(sim_frame, text="Power Factor:").grid(row=5, column=0, padx=5, pady=5)
        self.pf_var = tk.DoubleVar(value=0.95)
        self.pf_entry = ttk.Entry(sim_frame, textvariable=self.pf_var)
        self.pf_entry.grid(row=5, column=1, padx=5, pady=5)
        ttk.Button(sim_frame, text="Set", command=self.set_pf).grid(row=5, column=2, padx=5, pady=5)

        # Data Frame
        data_frame = ttk.LabelFrame(self.root, text="ADL400 Modbus Registers", padding="10")
        data_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # ADL400 Register Map
        self.register_map = [
            # Voltage Registers (Input Registers - FC 04)
            {"addr": 0, "name": "Phase A Voltage (U V)", "val": 0x4368, "type": "IR"},  # 230.0
            {"addr": 1, "name": "Phase A Voltage (U V) LSW", "val": 0x0000, "type": "IR"},
            {"addr": 2, "name": "Phase B Voltage (U V)", "val": 0x4368, "type": "IR"},
            {"addr": 3, "name": "Phase B Voltage (U V) LSW", "val": 0x0000, "type": "IR"},
            {"addr": 4, "name": "Phase C Voltage (U V)", "val": 0x4368, "type": "IR"},
            {"addr": 5, "name": "Phase C Voltage (U V) LSW", "val": 0x0000, "type": "IR"},
            
            # Current Registers (Input Registers - FC 04)
            {"addr": 6, "name": "Phase A Current (I A)", "val": 0x4120, "type": "IR"},  # 10.0
            {"addr": 7, "name": "Phase A Current (I A) LSW", "val": 0x0000, "type": "IR"},
            {"addr": 8, "name": "Phase B Current (I A)", "val": 0x4120, "type": "IR"},
            {"addr": 9, "name": "Phase B Current (I A) LSW", "val": 0x0000, "type": "IR"},
            {"addr": 10, "name": "Phase C Current (I A)", "val": 0x4120, "type": "IR"},
            {"addr": 11, "name": "Phase C Current (I A) LSW", "val": 0x0000, "type": "IR"},
            
            # Active Power Registers (Input Registers - FC 04)
            {"addr": 12, "name": "Phase A Active Power (W)", "val": 0x4500, "type": "IR"},  # 2048.0
            {"addr": 13, "name": "Phase A Active Power (W) LSW", "val": 0x0000, "type": "IR"},
            {"addr": 14, "name": "Phase B Active Power (W)", "val": 0x4500, "type": "IR"},
            {"addr": 15, "name": "Phase B Active Power (W) LSW", "val": 0x0000, "type": "IR"},
            {"addr": 16, "name": "Phase C Active Power (W)", "val": 0x4500, "type": "IR"},
            {"addr": 17, "name": "Phase C Active Power (W) LSW", "val": 0x0000, "type": "IR"},
            {"addr": 18, "name": "Total Active Power (W)", "val": 0x4500, "type": "IR"},
            {"addr": 19, "name": "Total Active Power (W) LSW", "val": 0x0000, "type": "IR"},
            
            # Reactive Power Registers
            {"addr": 20, "name": "Total Reactive Power (Var)", "val": 0x4480, "type": "IR"},
            {"addr": 21, "name": "Total Reactive Power (Var) LSW", "val": 0x0000, "type": "IR"},
            
            # Apparent Power Registers
            {"addr": 22, "name": "Total Apparent Power (VA)", "val": 0x4500, "type": "IR"},
            {"addr": 23, "name": "Total Apparent Power (VA) LSW", "val": 0x0000, "type": "IR"},
            
            # Power Factor
            {"addr": 24, "name": "Total Power Factor", "val": 0x3F76, "type": "IR"},  # 0.95
            {"addr": 25, "name": "Total Power Factor LSW", "val": 0x0000, "type": "IR"},
            
            # Frequency
            {"addr": 26, "name": "Frequency (Hz)", "val": 0x4248, "type": "IR"},  # 50.0
            {"addr": 27, "name": "Frequency (Hz) LSW", "val": 0x0000, "type": "IR"},
            
            # Energy Registers (Input Registers - FC 04)
            {"addr": 34, "name": "Total Active Energy (kWh)", "val": 0x00000000, "type": "IR"},  # 32-bit
            {"addr": 35, "name": "Total Active Energy (kWh) LSW", "val": 0x03E8, "type": "IR"},  # 1000
            
            {"addr": 36, "name": "Total Reactive Energy (kVarh)", "val": 0x00000000, "type": "IR"},
            {"addr": 37, "name": "Total Reactive Energy (kVarh) LSW", "val": 0x0000, "type": "IR"},
            
            # Status and Configuration Registers (Holding Registers - FC 03)
            {"addr": 100, "name": "Device Address", "val": 0x0001, "type": "HR"},
            {"addr": 101, "name": "Baud Rate (0=9600,1=19200,2=38400)", "val": 0x0000, "type": "HR"},
            {"addr": 102, "name": "Power on Times", "val": 0x0000, "type": "HR"},
            {"addr": 103, "name": "Device Status", "val": 0x0000, "type": "HR"},
        ]
        
        # Table
        self.tree = ttk.Treeview(data_frame, columns=("Address", "Type", "Name", "Value"), show="headings", height=20)
        self.tree.heading("Address", text="Address")
        self.tree.heading("Type", text="Type")
        self.tree.heading("Name", text="Name")
        self.tree.heading("Value", text="Value (Hex)")
        self.tree.column("Address", width=70)
        self.tree.column("Type", width=50)
        self.tree.column("Name", width=300)
        self.tree.column("Value", width=100)
        self.tree.pack(fill="both", expand=True, side="left")

        # Scrollbar
        scrollbar = ttk.Scrollbar(data_frame, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scrollbar.set)

        # Initialize Data Rows
        for reg in self.register_map:
            self.tree.insert("", "end", iid=reg["addr"], 
                           values=(reg["addr"], reg["type"], reg["name"], f"0x{reg['val']:04X}"))

        # Edit Value
        edit_frame = ttk.Frame(data_frame)
        edit_frame.pack(fill="x", pady=5)
        ttk.Label(edit_frame, text="Selected Register Value (Hex):").pack(side="left", padx=5)
        self.edit_val_var = tk.StringVar(value="0x0000")
        self.edit_entry = ttk.Entry(edit_frame, textvariable=self.edit_val_var)
        self.edit_entry.pack(side="left", padx=5)
        self.edit_entry.bind('<Return>', lambda e: self.update_register())
        ttk.Button(edit_frame, text="Update", command=self.update_register).pack(side="left", padx=5)
        
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        
        # Log Frame
        log_frame = ttk.LabelFrame(self.root, text="Bus Traffic", padding="10")
        log_frame.pack(fill="x", padx=10, pady=5)
        self.log_text = tk.Text(log_frame, height=6, state="disabled", bg="black", fg="white")
        self.log_text.pack(fill="x")

    def toggle_traffic(self):
        if self.show_traffic_var.get():
            self.logger.setLevel(logging.DEBUG)
            self.my_log("Traffic Logging ENABLED")
        else:
            self.logger.setLevel(logging.INFO)
            self.my_log("Traffic Logging DISABLED")

    def float_to_registers(self, value):
        """Pack float as Big Endian, return (MSW, LSW)"""
        b = struct.pack('>f', value)
        regs = struct.unpack('>HH', b)
        return regs[0], regs[1]  # MSW, LSW

    def uint32_to_registers(self, value):
        """Pack Uint32 as Big Endian, return (MSW, LSW)"""
        b = struct.pack('>I', value)
        regs = struct.unpack('>HH', b)
        return regs[0], regs[1]  # MSW, LSW

    def set_voltage_a(self):
        try:
            val = self.voltage_a_var.get()
            msw, lsw = self.float_to_registers(val)
            self.update_register_direct(0, msw) 
            self.update_register_direct(1, lsw)
            self.log(f"✓ Set Phase A Voltage to {val}V (0=0x{msw:04X}, 1=0x{lsw:04X})")
        except Exception as e:
            messagebox.showerror("Error", f"Invalid Float: {e}")

    def set_current_a(self):
        try:
            val = self.current_a_var.get()
            msw, lsw = self.float_to_registers(val)
            self.update_register_direct(6, msw)
            self.update_register_direct(7, lsw)
            self.log(f"✓ Set Phase A Current to {val}A (6=0x{msw:04X}, 7=0x{lsw:04X})")
        except Exception as e:
            messagebox.showerror("Error", f"Invalid Float: {e}")

    def set_power(self):
        try:
            val = self.power_var.get()
            msw, lsw = self.float_to_registers(val)
            self.update_register_direct(18, msw)
            self.update_register_direct(19, lsw)
            self.log(f"✓ Set Total Active Power to {val}W (18=0x{msw:04X}, 19=0x{lsw:04X})")
        except Exception as e:
            messagebox.showerror("Error", f"Invalid Float: {e}")

    def set_frequency(self):
        try:
            val = self.frequency_var.get()
            msw, lsw = self.float_to_registers(val)
            self.update_register_direct(26, msw)
            self.update_register_direct(27, lsw)
            self.log(f"✓ Set Frequency to {val}Hz (26=0x{msw:04X}, 27=0x{lsw:04X})")
        except Exception as e:
            messagebox.showerror("Error", f"Invalid Float: {e}")

    def set_energy(self):
        try:
            val = self.energy_var.get()
            msw, lsw = self.uint32_to_registers(val)
            self.update_register_direct(34, msw)
            self.update_register_direct(35, lsw)
            self.log(f"✓ Set Total Active Energy to {val}kWh (34=0x{msw:04X}, 35=0x{lsw:04X})")
        except Exception as e:
            messagebox.showerror("Error", f"Invalid Integer: {e}")

    def set_pf(self):
        try:
            val = self.pf_var.get()
            msw, lsw = self.float_to_registers(val)
            self.update_register_direct(24, msw)
            self.update_register_direct(25, lsw)
            self.log(f"✓ Set Power Factor to {val} (24=0x{msw:04X}, 25=0x{lsw:04X})")
        except Exception as e:
            messagebox.showerror("Error", f"Invalid Float: {e}")

    def update_register_direct(self, addr, val):
        """Update both GUI and Modbus stores (HR + IR)"""
        # Update Tree
        if self.tree.exists(addr):
            item = self.tree.item(addr)
            reg_type = item['values'][1]
            name = item['values'][2]
            self.tree.item(addr, values=(addr, reg_type, name, f"0x{val:04X}"))
        
        # Update BOTH Modbus Stores
        if self.store:
            self.store.setValues(3, addr, [val])  # Holding Registers (FC 03)
            self.store.setValues(4, addr, [val])  # Input Registers (FC 04)

    def refresh_ports(self):
        ports = serial.tools.list_ports.comports()
        self.com_port_combo['values'] = [p.device for p in ports]
        if ports:
            self.com_port_combo.current(0)

    def on_tree_select(self, event):
        selected_item = self.tree.selection()
        if selected_item:
            item = self.tree.item(selected_item)
            val_str = item['values'][3]
            self.edit_val_var.set(val_str)

    def update_register(self):
        """Manual register update from GUI"""
        selected_item = self.tree.selection()
        if not selected_item:
            return
        
        try:
            val_str = self.edit_val_var.get()
            val = int(val_str, 16) if val_str.startswith('0x') else int(val_str)
            
            if val < 0 or val > 65535:
                raise ValueError("Value out of range (0-65535)")
            
            addr = int(selected_item[0])
            self.update_register_direct(addr, val)
            self.log(f"✓ Register {addr} updated to 0x{val:04X}")
        except Exception as e:
            messagebox.showerror("Error", f"Invalid Hex Value: {e}")

    def start_server(self):
        """Start Modbus RTU Server"""
        try:
            port = self.com_port_var.get()
            if not port:
                messagebox.showerror("Error", "Please select a COM port!")
                return
            
            baudrate = self.baudrate_var.get()
            slave_id = self.slave_id_var.get()
            
            self.my_log(f"Starting Modbus RTU Server on {port} @ {baudrate} baud, Slave ID {slave_id}...")
            
            # Create Modbus Datastore
            hr_block = ModbusSequentialDataBlock(0, [0] * 150)
            ir_block = ModbusSequentialDataBlock(0, [0] * 150)
            
            self.store = ModbusSlaveContext(hr=hr_block, ir=ir_block)
            
            # Initialize register values from GUI
            for reg in self.register_map:
                self.store.setValues(3 if reg['type'] == 'HR' else 4, reg['addr'], [reg['val']])
            
            # Create Server Context
            slaves = {slave_id: self.store}
            self.context = ModbusServerContext(slaves=slaves, single=False)
            
            # Start Server in Thread
            self.stop_server_event.clear()
            self.server_thread = threading.Thread(target=self.run_server, args=(port, baudrate, slave_id), daemon=True)
            self.server_thread.start()
            
            self.start_btn.config(state="disabled")
            self.stop_btn.config(state="normal")
            self.my_log(f"✓ Server started successfully!")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start server: {e}")
            self.my_log(f"✗ Error: {e}")

    def run_server(self, port, baudrate, slave_id):
        """Run Modbus server (blocking)"""
        try:
            if StartAsyncSerialServer:
                # Async server (preferred for v3.6+)
                asyncio.run(self.run_async_server(port, baudrate, slave_id))
            elif StartSerialServer:
                # Sync server (fallback)
                StartSerialServer(
                    context=self.context,
                    port=port,
                    baudrate=baudrate,
                    timeout=1.0,
                    ignore_missing_slaves=True
                )
            else:
                self.my_log("ERROR: No server start function available!")
        except Exception as e:
            self.my_log(f"Server error: {e}")

    async def run_async_server(self, port, baudrate, slave_id):
        """Async Modbus server"""
        try:
            server = await StartAsyncSerialServer(
                context=self.context,
                port=port,
                baudrate=baudrate,
                timeout=1.0,
                ignore_missing_slaves=True
            )
            
            # Keep server running until stop is requested
            while not self.stop_server_event.is_set():
                await asyncio.sleep(0.1)
            
            if hasattr(server, 'close'):
                server.close()
        except Exception as e:
            self.my_log(f"Async server error: {e}")

    def stop_server(self):
        """Stop Modbus RTU Server"""
        try:
            self.my_log("Stopping server...")
            self.stop_server_event.set()
            
            if self.server_thread and self.server_thread.is_alive():
                self.server_thread.join(timeout=2)
            
            self.my_log("✓ Server stopped")
            self.start_btn.config(state="normal")
            self.stop_btn.config(state="disabled")
        except Exception as e:
            self.my_log(f"Error stopping server: {e}")


if __name__ == "__main__":
    root = tk.Tk()
    app = EnergyMeterSimulatorApp(root)
    root.mainloop()

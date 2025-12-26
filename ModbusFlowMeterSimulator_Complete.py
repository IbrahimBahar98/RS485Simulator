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
ServerStop = None  # PATCH: Added for v3.11.4

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

# PATCH: Import ServerStop for v3.11.4 compatibility
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

# Strategy 1: Try v3.6+ imports
try:
    from pymodbus.datastore import ModbusServerContext
    from pymodbus.datastore import ModbusSequentialDataBlock
    print("Debug: Imported ModbusServerContext and ModbusSequentialDataBlock")
    
    # Try to import ModbusSlaveContext (doesn't exist in v3.6+)
    try:
        from pymodbus.datastore import ModbusSlaveContext
        print("Debug: Imported ModbusSlaveContext")
    except ImportError:
        # In v3.6+, we build slave context manually as dict
        print("Debug: ModbusSlaveContext not available (v3.6+ - will use dict approach)")
        
except ImportError as e:
    print(f"Debug: Strategy 1 failed: {e}")

# Strategy 2: Individual imports with fallbacks for older v3.x
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
            return  # Silently drop to prevent GUI/performance issues
        
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
        # logging.debug(f"getValues fx={fx}, addr={address}, count={count}")
        if fx in [1, 5, 15]: block = self.store.get('c')
        elif fx in [2]:      block = self.store.get('d')
        elif fx in [3, 6, 16]: block = self.store.get('h')
        elif fx in [4]:      block = self.store.get('i')
        else: return []
        
        vals = block.getValues(address, count)
        # logging.debug(f" -> Returning: {vals}")
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


class FlowMeterSimulatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Flow Meter Simulator (Modbus RTU Slave) - FIXED v3.11.4")
        self.root.geometry("900x850")

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
        sim_frame = ttk.LabelFrame(self.root, text="Simulation Controls (High Level)", padding="10")
        sim_frame.pack(fill="x", padx=10, pady=5)
        
        # Flow Rate
        ttk.Label(sim_frame, text="Flow Rate (Float):").grid(row=0, column=0, padx=5, pady=5)
        self.flow_rate_var = tk.DoubleVar(value=0.0)
        self.flow_rate_entry = ttk.Entry(sim_frame, textvariable=self.flow_rate_var)
        self.flow_rate_entry.grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(sim_frame, text="Set Flow Rate", command=self.set_flow_rate).grid(row=0, column=2, padx=5, pady=5)

        # Conductivity
        ttk.Label(sim_frame, text="Conductivity (Float):").grid(row=1, column=0, padx=5, pady=5)
        self.conductivity_var = tk.DoubleVar(value=0.0)
        self.conductivity_entry = ttk.Entry(sim_frame, textvariable=self.conductivity_var)
        self.conductivity_entry.grid(row=1, column=1, padx=5, pady=5)
        ttk.Button(sim_frame, text="Set Conductivity", command=self.set_conductivity).grid(row=1, column=2, padx=5, pady=5)

        # Forward Total (Uint32)
        ttk.Label(sim_frame, text="Forward Total (Uint32):").grid(row=2, column=0, padx=5, pady=5)
        self.fwd_total_var = tk.IntVar(value=0)
        self.fwd_total_entry = ttk.Entry(sim_frame, textvariable=self.fwd_total_var)
        self.fwd_total_entry.grid(row=2, column=1, padx=5, pady=5)
        ttk.Button(sim_frame, text="Set Total", command=self.set_fwd_total).grid(row=2, column=2, padx=5, pady=5)

        # Alarm Flags (Bitfield) - ROW 3
        ttk.Label(sim_frame, text="Alarm Flags (Hex):").grid(row=3, column=0, padx=5, pady=5)
        self.alarm_flags_var = tk.StringVar(value="0x0000")
        self.alarm_flags_entry = ttk.Entry(sim_frame, textvariable=self.alarm_flags_var)
        self.alarm_flags_entry.grid(row=3, column=1, padx=5, pady=5)
        ttk.Button(sim_frame, text="Set Alarms", command=self.set_alarm_flags).grid(row=3, column=2, padx=5, pady=5)

        # Quick Alarm Buttons - ROW 4
        alarm_btn_frame = ttk.Frame(sim_frame)
        alarm_btn_frame.grid(row=4, column=0, columnspan=3, pady=5)
        ttk.Button(alarm_btn_frame, text="Empty Pipe ON", command=lambda: self.toggle_alarm_bit(0, True)).pack(side="left", padx=2)
        ttk.Button(alarm_btn_frame, text="Empty Pipe OFF", command=lambda: self.toggle_alarm_bit(0, False)).pack(side="left", padx=2)
        ttk.Button(alarm_btn_frame, text="High Flow ON", command=lambda: self.toggle_alarm_bit(2, True)).pack(side="left", padx=2)
        ttk.Button(alarm_btn_frame, text="High Flow OFF", command=lambda: self.toggle_alarm_bit(2, False)).pack(side="left", padx=2)

        # Data Frame
        data_frame = ttk.LabelFrame(self.root, text="Raw Registers (Both HR & IR)", padding="10")
        data_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Register Map - Complete with all CR009 required registers
        self.register_map = [
            # Input Registers (FC 04) - Flow Meter Reads These
            {"addr": 772, "name": "Forward Total (Word 0 - MSW)", "val": 0, "type": "IR"},
            {"addr": 773, "name": "Forward Total (Word 1 - LSW)", "val": 0, "type": "IR"},
            {"addr": 774, "name": "Unit Info", "val": 0x0403, "type": "IR"},  # Default: Total=L, Flow=L/s
            {"addr": 777, "name": "Alarm Flags", "val": 0, "type": "IR"},
            {"addr": 778, "name": "Flow Rate (Word 0 - MSW)", "val": 0, "type": "IR"},
            {"addr": 779, "name": "Flow Rate (Word 1 - LSW)", "val": 0, "type": "IR"},
            {"addr": 786, "name": "Forward Overflow Count", "val": 0, "type": "IR"},
            {"addr": 812, "name": "Conductivity (Word 0 - MSW)", "val": 0, "type": "IR"},
            {"addr": 813, "name": "Conductivity (Word 1 - LSW)", "val": 0, "type": "IR"},
            
            # Holding Registers (FC 03) - Configuration Parameters
            {"addr": 261, "name": "Flow Range (Word 0 - MSW)", "val": 0x43D4, "type": "HR"},  # 424.0
            {"addr": 262, "name": "Flow Range (Word 1 - LSW)", "val": 0x0000, "type": "HR"},
            {"addr": 281, "name": "Alm High Val (Word 0 - MSW)", "val": 0x42C8, "type": "HR"},  # 100.0
            {"addr": 282, "name": "Alm High Val (Word 1 - LSW)", "val": 0x0000, "type": "HR"},
            {"addr": 284, "name": "Alm Low Val (Word 0 - MSW)", "val": 0x4120, "type": "HR"},   # 10.0
            {"addr": 285, "name": "Alm Low Val (Word 1 - LSW)", "val": 0x0000, "type": "HR"},
        ]
        
        # Table
        self.tree = ttk.Treeview(data_frame, columns=("Address", "Type", "Name", "Value"), show="headings", height=15)
        self.tree.heading("Address", text="Address")
        self.tree.heading("Type", text="Type")
        self.tree.heading("Name", text="Name")
        self.tree.heading("Value", text="Value (Hex)")
        self.tree.column("Address", width=70)
        self.tree.column("Type", width=50)
        self.tree.column("Name", width=250)
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
        self.log_text = tk.Text(log_frame, height=8, state="disabled", bg="black", fg="white")
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

    def set_flow_rate(self):
        try:
            val = self.flow_rate_var.get()
            msw, lsw = self.float_to_registers(val)
            self.update_register_direct(778, msw) 
            self.update_register_direct(779, lsw)
            self.log(f"✓ Set Flow Rate to {val} (778=0x{msw:04X}, 779=0x{lsw:04X})")
        except Exception as e:
            messagebox.showerror("Error", f"Invalid Float: {e}")

    def set_conductivity(self):
        try:
            val = self.conductivity_var.get()
            msw, lsw = self.float_to_registers(val)
            self.update_register_direct(812, msw)
            self.update_register_direct(813, lsw)
            self.log(f"✓ Set Conductivity to {val} (812=0x{msw:04X}, 813=0x{lsw:04X})")
        except Exception as e:
            messagebox.showerror("Error", f"Invalid Float: {e}")

    def set_fwd_total(self):
        try:
            val = self.fwd_total_var.get()
            msw, lsw = self.uint32_to_registers(val)
            self.update_register_direct(772, msw)
            self.update_register_direct(773, lsw)
            self.log(f"✓ Set Forward Total to {val} (772=0x{msw:04X}, 773=0x{lsw:04X})")
        except Exception as e:
            messagebox.showerror("Error", f"Invalid Int: {e}")


    def set_alarm_flags(self):
        try:
            val_str = self.alarm_flags_var.get()
            val = int(val_str, 16) if val_str.startswith('0x') else int(val_str)
            if val < 0 or val > 0xFFFF:
                raise ValueError("Out of range")
            self.update_register_direct(777, val)
            self.log(f"✓ Set Alarm Flags to 0x{val:04X}")
        except Exception as e:
            messagebox.showerror("Error", f"Invalid Hex: {e}")

    def toggle_alarm_bit(self, bit, state):
        """Toggle specific alarm bit"""
        try:
            if self.tree.exists(777):
                current_val = int(self.tree.item(777)['values'][3], 16)
            else:
                current_val = 0
            
            if state:
                new_val = current_val | (1 << bit)
            else:
                new_val = current_val & ~(1 << bit)
            
            self.update_register_direct(777, new_val)
            self.alarm_flags_var.set(f"0x{new_val:04X}")
            
            bit_names = {0: "Empty Pipe", 1: "Excitation", 2: "High Flow", 3: "Low Flow"}
            self.log(f"✓ Alarm Bit {bit} ({bit_names.get(bit, 'Unknown')}) {'ON' if state else 'OFF'}")
        except Exception as e:
            self.log(f"✗ Error toggling alarm bit: {e}")

    def update_register_direct(self, addr, val):
        """Update both GUI and Modbus stores (HR + IR)"""
        # Update Tree
        if self.tree.exists(addr):
            item = self.tree.item(addr)
            reg_type = item['values'][1]
            name = item['values'][2]
            self.tree.item(addr, values=(addr, reg_type, name, f"0x{val:04X}"))
        
        # Update BOTH Modbus Stores (This is the FIX!)
        if self.store:
            self.store.setValues(3, addr, [val])  # Holding Registers (FC 03)
            self.store.setValues(4, addr, [val])  # Input Registers (FC 04) ← CRITICAL FIX

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
                messagebox.showerror("Error", "Value must be between 0 and 65535")
                return
            
            iid = selected_item[0]
            addr = int(iid)
            
            # Update both stores
            self.update_register_direct(addr, val)
            self.log(f"✓ Updated Register {addr} to 0x{val:04X}")
            
        except ValueError:
            messagebox.showerror("Error", "Invalid hex/integer value")

    def log(self, msg):
        self.my_log(msg)

    def start_server(self):
        try:
            port = self.com_port_var.get()
            if not port:
                messagebox.showerror("Error", "Select a COM port")
                return

            try:
                slave_id = self.slave_id_var.get()
                baud = self.baudrate_var.get()
            except ValueError:
                messagebox.showerror("Error", "Invalid Slave ID or Baudrate")
                return

            self.log(f"Starting Server on {port} (Slave ID: {slave_id})...")
            
            # Initialize Data Store with 1000 registers
            initial_regs = [0] * 1000
            
            # Populate with default values
            for reg in self.register_map:
                addr = reg["addr"]
                val = reg["val"]
                if addr < 1000:
                    initial_regs[addr] = val
            
            if ModbusSequentialDataBlock is None or ModbusServerContext is None:
                raise ImportError("Modbus classes not found. Check Pymodbus installation.")

            # CRITICAL FIX: Create datastore blocks
            di_block = ModbusSequentialDataBlock(0, [0]*1000)
            co_block = ModbusSequentialDataBlock(0, [0]*1000)
            hr_block = ModbusSequentialDataBlock(0, initial_regs.copy())
            ir_block = ModbusSequentialDataBlock(0, initial_regs.copy())
            
            self.log("✓ Using v3.6+ API...")
            
            # Create slave context using our shim class
            slave_context = ModbusSlaveContext(
                di=di_block, 
                co=co_block, 
                hr=hr_block, 
                ir=ir_block
            )
            
            # In v3.6+, the first parameter is the datastore, not a slaves dict
            # To support multiple slaves, we need a different approach
            
            # Create slave context dict mapping slave ID to our shim
            # AUTOMATICALLY ADD SLAVE 111 & 100 for multi-device support
            slaves = {slave_id: slave_context}
            if slave_id != 111:
                slaves[111] = slave_context
                self.log("✓ Auto-added Slave ID 111 for dual-device simulation")
            if slave_id != 100:
                slaves[100] = slave_context
                self.log("✓ Auto-added Slave ID 100 to eliminate error overhead")

            try:
                # Proper initialization with 'devices' arg (PyModbus v3.x)
                self.context = ModbusServerContext(devices=slaves, single=False)
                self.log(f"✓ Created ServerContext with slaves {list(slaves.keys())}")
            except Exception as e:
                self.log(f"Standard context creation failed: {e}")
                # Fallback - single context (passed as first positional arg 'devices')
                self.context = ModbusServerContext(slave_context, single=True)
                self.log(f"⚠ Fallback to single=True mode")
            
            # Debug: Check what's in the context
            try:
                self.log(f"Context type: {type(self.context)}")
                if hasattr(self.context, '__dict__'):
                    self.log(f"Context attrs: {list(self.context.__dict__.keys())}")
            except:
                pass
            
            # Create wrapper for setValues compatibility
            class DatastoreWrapper:
                def __init__(self, hr_block, ir_block):
                    self.hr_block = hr_block
                    self.ir_block = ir_block
                
                def setValues(self, fx, address, values):
                    """Update register values - updates both HR and IR"""
                    if fx == 3:  # Holding Registers
                        for i, val in enumerate(values):
                            self.hr_block.setValues(address + i, [val])
                    elif fx == 4:  # Input Registers
                        for i, val in enumerate(values):
                            self.ir_block.setValues(address + i, [val])
            
            self.store = DatastoreWrapper(hr_block, ir_block)
            
            if StartSerialServer is None and StartAsyncSerialServer is None and ModbusSerialServer is None:
                raise ImportError("No Server implementation found")

            self.start_btn.config(state="disabled")
            self.stop_btn.config(state="normal")
            self.log("✓ Starting server thread...")
            
            # Force GUI update before starting thread
            self.root.update()

            self.server_thread = threading.Thread(
                target=self.run_server_thread, 
                args=(port, baud, self.context),
                daemon=True,
                name="ModbusServerThread"
            )
            
            self.log("✓ Thread object created, calling start()...")
            self.root.update()
            
            self.server_thread.start()
            
            self.log("✓ start() called, checking if alive...")
            self.root.update()
            
            # Verify thread started
            import time
            time.sleep(0.5)
            
            if self.server_thread.is_alive():
                self.log("✓ Server Thread is ALIVE and running")
            else:
                self.log("✗ WARNING: Server thread died immediately!")
            
            self.log("✓ Server startup complete - GUI should be responsive")
            
        except Exception as e:
            self.start_btn.config(state="normal")
            self.stop_btn.config(state="disabled")
            self.log(f"✗ FAILED TO START SERVER: {e}")
            import traceback
            self.log(traceback.format_exc())
            messagebox.showerror("Error Starting Server", str(e))

    def run_server_thread(self, port, baud, context):
        """Run Modbus server in background thread - PATCHED for v3.11.4"""
        try:
            # Thread-safe logging
            def thread_log(msg):
                self.root.after(0, lambda: self.my_log(msg))
            
            thread_log(f"═══════════════════════════════════════")
            thread_log(f"SERVER THREAD STARTING (v3.11.4 Patch)")
            thread_log(f"Port: {port}")
            thread_log(f"Baudrate: {baud}")
            thread_log(f"═══════════════════════════════════════")
            
            # Test if port is accessible
            try:
                import serial
                test_port = serial.Serial(port, baud, timeout=0.1)
                thread_log(f"✓ Port {port} opened successfully")
                test_port.close()
            except Exception as e:
                thread_log(f"✗ WARNING: Cannot open {port}: {e}")
                return
            
            # pymodbus server initialization
            try:
                from pymodbus.server import StartSerialServer
                from pymodbus.framer import FramerType
                
                thread_log("✓ Using StartSerialServer (v3.11.4)...")
                
                # CRITICAL FIX: Use FramerType.RTU
                StartSerialServer(
                    context=context,
                    port=port,
                    framer=FramerType.RTU,
                    baudrate=baud,
                    bytesize=8,
                    parity='N',
                    stopbits=1,
                    timeout=1
                )
                
                thread_log("✓ StartSerialServer exited")
                
            except Exception as e1:
                thread_log(f"✗ StartSerialServer failed: {e1}")
                import traceback
                thread_log(traceback.format_exc())
                
        except Exception as e:
            def log_error():
                self.my_log(f"═══════════════════════════════════════")
                self.my_log(f"✗✗✗ FATAL SERVER THREAD ERROR ✗✗✗")
                self.my_log(f"{e}")
                import traceback
                self.my_log(traceback.format_exc())
                self.my_log(f"═══════════════════════════════════════")
            self.root.after(0, log_error)

    def stop_server(self):
        try:
            self.log("⚠ Stopping server... (Restart App to fully reset port)")
            
            # NOTE: ServerStop() doesn't work with synchronous StartSerialServer
            # The server thread will continue until the app exits
            self.log("⚠ Server thread will stop when app closes (synchronous server limitation)")
                
            self.start_btn.config(state="normal")
            self.stop_btn.config(state="disabled")
            self.log("✓ Stop button handler completed successfully")
        except Exception as e:
            # Catch and log any crash
            import traceback
            error_msg = f"CRASH in stop_server: {e}\n{traceback.format_exc()}"
            self.log(error_msg)
            print(error_msg)  # Also print to console
            # Try to re-enable buttons even if there was an error
            try:
                self.start_btn.config(state="normal")
                self.stop_btn.config(state="disabled")
            except:
                pass


if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = FlowMeterSimulatorApp(root)
        root.mainloop()
    except KeyboardInterrupt:
        pass
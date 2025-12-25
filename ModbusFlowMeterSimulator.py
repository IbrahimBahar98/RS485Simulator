
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import logging
import asyncio
import serial.tools.list_ports

# Robust Imports for Pymodbus v3.x
import sys
import importlib.util
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
    # Fallback to class directly
    from pymodbus.server import ModbusSerialServer
    print("Debug: Imported ModbusSerialServer")
except ImportError as e:
    print(f"Debug: Failed to import ModbusSerialServer: {e}")

try:
    from pymodbus.device import ModbusDeviceIdentification
except ImportError:
    ModbusDeviceIdentification = None

# Datastore Imports - Try multiple locations
ModbusServerContext = None
ModbusSlaveContext = None
ModbusSequentialDataBlock = None

try:
    from pymodbus.datastore import ModbusServerContext, ModbusSlaveContext, ModbusSequentialDataBlock
    print("Debug: Imported Datastore classes directly")
except ImportError:
    # Try submodules
    try:
        from pymodbus.datastore import ModbusServerContext
    except ImportError: pass
    
    try:
        from pymodbus.datastore import ModbusSlaveContext
    except ImportError:
        try: from pymodbus.datastore.context import ModbusSlaveContext
        except ImportError: pass

    try:
        from pymodbus.datastore import ModbusSequentialDataBlock
    except ImportError:
        try: from pymodbus.datastore.store import ModbusSequentialDataBlock
        except ImportError: pass

try:
    from pymodbus.framer import ModbusRtuFramer
except ImportError:
    try:
        from pymodbus.transaction import ModbusRtuFramer
    except ImportError:
        ModbusRtuFramer = None

# Configure logging
logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.INFO)

import struct

# ... (Previous imports)

# ... imports

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

class FlowMeterSimulatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Flow Meter Simulator (Modbus RTU Slave)")
        self.root.geometry("800x800")

        self.server_thread = None
        self.stop_server_event = threading.Event()
        self.context = None
        self.store = None

        self.setup_ui()
        
        # Setup Logging to GUI
        self.logger = logging.getLogger("pymodbus")
        self.logger.setLevel(logging.INFO)
        # Remove default handlers to avoid double printing if any
        self.logger.handlers = []
        
        self.log_handler = TextHandler(self.log_text)
        self.log_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s', '%H:%M:%S'))
        self.logger.addHandler(self.log_handler)
        
        # Also redirect my own log
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

        # Simulation Controls Frame (Floats)
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

        # Data Frame
        data_frame = ttk.LabelFrame(self.root, text="Raw Registers (Holding Registers)", padding="10")
        data_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Register Map from FlowMeter.h
        self.register_map = [
            {"addr": 772, "name": "Forward Total (Low Word)", "val": 0},
            {"addr": 773, "name": "Forward Total (High Word)", "val": 0},
            {"addr": 774, "name": "Unit Info", "val": 0},
            {"addr": 777, "name": "Alarm Flags", "val": 0},
            {"addr": 778, "name": "Flow Rate (Low Word)", "val": 0},
            {"addr": 779, "name": "Flow Rate (High Word)", "val": 0},
            {"addr": 786, "name": "Forward Overflow (Low)", "val": 0},
            {"addr": 787, "name": "Forward Overflow (High)", "val": 0},
            {"addr": 812, "name": "Conductivity (Low Word)", "val": 0},
            {"addr": 813, "name": "Conductivity (High Word)", "val": 0},
        ]
        
        # Table
        self.tree = ttk.Treeview(data_frame, columns=("Address", "Name", "Value"), show="headings", height=15)
        self.tree.heading("Address", text="Address")
        self.tree.heading("Name", text="Name")
        self.tree.heading("Value", text="Value")
        self.tree.column("Address", width=80)
        self.tree.column("Name", width=200)
        self.tree.column("Value", width=80)
        self.tree.pack(fill="both", expand=True, side="left")

        # Scrollbar
        scrollbar = ttk.Scrollbar(data_frame, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scrollbar.set)

        # Initialize Data Rows
        for reg in self.register_map:
            self.tree.insert("", "end", iid=reg["addr"], values=(reg["addr"], reg["name"], reg["val"]))

        # Edit Value
        edit_frame = ttk.Frame(data_frame)
        edit_frame.pack(fill="x", pady=5)
        ttk.Label(edit_frame, text="Selected Register Value (Int16):").pack(side="left", padx=5)
        self.edit_val_var = tk.IntVar(value=0)
        self.edit_entry = ttk.Entry(edit_frame, textvariable=self.edit_val_var)
        self.edit_entry.pack(side="left", padx=5)
        # Bind Enter key
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
        # Pack float as 4 bytes (Big Endian Float) -> Reg1: AB, Reg2: CD
        b = struct.pack('>f', value) 
        h = struct.unpack('>HH', b)
        return h[0], h[1] # Low Addr, High Addr

    def set_flow_rate(self):
        try:
            val = self.flow_rate_var.get()
            high, low = self.float_to_registers(val)
            self.update_register_direct(778, high) 
            self.update_register_direct(779, low)
            self.log(f"Set Flow Rate to {val} (Regs 778={high}, 779={low})")
        except Exception as e:
            messagebox.showerror("Error", f"Invalid Float: {e}")

    def set_conductivity(self):
        try:
            val = self.conductivity_var.get()
            high, low = self.float_to_registers(val)
            self.update_register_direct(812, high)
            self.update_register_direct(813, low)
            self.log(f"Set Conductivity to {val} (Regs 812={high}, 813={low})")
        except Exception as e:
            messagebox.showerror("Error", f"Invalid Float: {e}")

    def set_fwd_total(self):
        try:
            val = self.fwd_total_var.get()
            # Uint32
            b = struct.pack('>I', val)
            high, low = struct.unpack('>HH', b)
            self.update_register_direct(772, high)
            self.update_register_direct(773, low)
            self.log(f"Set Total to {val} (Regs 772={high}, 773={low})")
        except Exception as e:
            messagebox.showerror("Error", f"Invalid Int: {e}")


    def update_register_direct(self, addr, val):
        # Update Tree
        if self.tree.exists(addr):
             name = self.tree.item(addr)['values'][1]
             self.tree.item(addr, values=(addr, name, val))
        
        # Update Store
        if self.store:
             self.store.setValues(3, addr, [val])
             # Do not log every update to avoid spam, or log as INFO
             # self.my_log(f"Updated {addr} -> {val}")

    def refresh_ports(self):
        ports = serial.tools.list_ports.comports()
        self.com_port_combo['values'] = [p.device for p in ports]
        if ports:
            self.com_port_combo.current(0)
        ports = serial.tools.list_ports.comports()
        self.com_port_combo['values'] = [p.device for p in ports]
        if ports:
            self.com_port_combo.current(0)

    def on_tree_select(self, event):
        selected_item = self.tree.selection()
        if selected_item:
            item = self.tree.item(selected_item)
            val = item['values'][2] # Index 2 is Value now
            self.edit_val_var.set(val)

    def update_register(self):
        selected_item = self.tree.selection()
        if not selected_item:
            return
        
        try:
            val = int(self.edit_val_var.get())
            if val < 0 or val > 65535:
                messagebox.showerror("Error", "Value must be between 0 and 65535")
                return
            
            iid = selected_item[0]
            # iid is the addr
            addr = int(iid)
            name = self.tree.item(iid)['values'][1]
            
            # Update Tree
            self.tree.item(iid, values=(addr, name, val))
            
            # Update Modbus Store if running
            if self.store:
                self.store.setValues(3, addr, [val])
                self.log(f"Updated {name} ({addr}) to {val}")
        except ValueError:
            messagebox.showerror("Error", "Invalid integer")

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
            
            # Initialize Data Store
            # We need to cover up to address 813. Let's allocate 1000 registers.
            
            initial_regs = [0] * 1000
            
            for reg in self.register_map:
                 addr = reg["addr"]
                 val = reg["val"]
                 # If user edited it, get from tree
                 try:
                    tree_item = self.tree.item(addr)
                    if tree_item:
                        val = int(tree_item['values'][2])
                 except:
                    pass
                    
                 if addr < 1000:
                    initial_regs[addr] = val
            
            if ModbusSlaveContext is None or ModbusServerContext is None:
                raise ImportError("Modbus Context classes not found. Check Pymodbus installation.")

            self.store = ModbusSlaveContext(
                di=ModbusSequentialDataBlock(0, [0]*1000),
                co=ModbusSequentialDataBlock(0, [0]*1000),
                hr=ModbusSequentialDataBlock(0, initial_regs),
                ir=ModbusSequentialDataBlock(0, [0]*1000)
            )
            
            self.context = ModbusServerContext(slaves={slave_id: self.store}, single=False)
            
            if StartSerialServer is None and StartAsyncSerialServer is None and ModbusSerialServer is None:
                 raise ImportError("No Server implementation found (StartSerialServer, StartAsyncSerialServer, ModbusSerialServer are all None)")

            self.server_thread = threading.Thread(target=self.run_server_thread, args=(port, baud, self.context))
            self.server_thread.daemon = True
            self.server_thread.start()
            
            self.start_btn.config(state="disabled")
            self.stop_btn.config(state="normal")
            self.log("Server Started (Background).")
            
        except Exception as e:
            self.log(f"CRASH STARTING SERVER: {e}")
            messagebox.showerror("Error Starting Server", str(e))
            # Print debug info
            import sys
            self.log(f"DEBUG INFO: {sys.path}")
            if 'pymodbus' in sys.modules:
                 try:
                    self.log(f"Pymodbus file: {sys.modules['pymodbus'].__file__}")
                 except: pass

    def run_server_thread(self, port, baud, context):
        identity = None
        if ModbusDeviceIdentification:
            identity = ModbusDeviceIdentification()
            identity.VendorName = 'Simulated Flow Meter'
            identity.ProductCode = 'SFM'
            identity.VendorUrl = 'http://github.com/pymodbus'
            identity.ProductName = 'Flow Meter Server'
            identity.ModelName = 'Modbus Server'
            identity.MajorMinorRevision = '1.0'

        try:
            if StartSerialServer:
                 # Sync wrapper
                 self.log(f"Using Sync StartSerialServer on {port}...")
                 StartSerialServer(context=context, identity=identity, port=port, framer=ModbusRtuFramer, stopbits=1, bytesize=8, parity='N', baudrate=baud)
            elif StartAsyncSerialServer:
                 # Async wrapper
                 self.log(f"Using Async StartAsyncSerialServer on {port}...")
                 asyncio.run(StartAsyncSerialServer(context=context, identity=identity, port=port, framer=ModbusRtuFramer, stopbits=1, bytesize=8, parity='N', baudrate=baud))
            elif ModbusSerialServer:
                 # Direct class usage (common in 3.x if helpers missing)
                 self.log(f"Using ModbusSerialServer Class on {port}...")
                 # Note: ModbusSerialServer might take slightly different args in 3.11?
                 # It usually takes (context, framer, ...) and then we call serve_forever
                 # But in 3.x it might be context=...
                 # Let's try standard 3.x init
                 server = ModbusSerialServer(context=context, framer=ModbusRtuFramer, port=port, stopbits=1, bytesize=8, parity='N', baudrate=baud)
                 server.serve_forever()
            else:
                self.log("No Server implementation found to run.")
        except Exception as e:
            print(f"Server Error: {e}")
            self.log(f"Server Error: {e}")

    def stop_server(self):
        self.log("Stopping server... (Restart App to fully reset port)")
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        
if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = FlowMeterSimulatorApp(root)
        root.mainloop()
    except KeyboardInterrupt:
        pass

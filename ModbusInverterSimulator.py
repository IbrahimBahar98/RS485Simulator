import tkinter as tk
from tkinter import ttk, messagebox
import threading
import logging
import serial.tools.list_ports
import time

# --- Pymodbus v3.x Robust Imports ---
try:
    import serial
except ImportError:
    pass

try:
    from pymodbus.server import StartSerialServer
except ImportError:
    StartSerialServer = None

try:
    from pymodbus.datastore import ModbusServerContext, ModbusSequentialDataBlock
except ImportError:
    ModbusServerContext = None
    ModbusSequentialDataBlock = None

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
        tag = "INFO"
        if "Received" in msg or "recv" in msg.lower(): tag = "RX"
        elif "Sending" in msg or "send" in msg.lower(): tag = "TX"
        elif "Error" in msg or "Exception" in msg: tag = "ERR"
            
        def append():
            self.text_widget.configure(state='normal')
            self.text_widget.insert('end', msg + '\n', tag)
            self.text_widget.see('end')
            self.text_widget.configure(state='disabled')
        self.text_widget.after(0, append)

# --- Custom ModbusSlaveContext to fix v3.x compatibility ---
class ModbusSlaveContext:
    def __init__(self, di=None, co=None, hr=None, ir=None, zero_mode=False):
        self.store = {}
        if di: self.store['d'] = di
        if co: self.store['c'] = co
        if hr: self.store['h'] = hr
        if ir: self.store['i'] = ir
        self.zero_mode = zero_mode

    def reset(self):
        for block in self.store.values(): block.reset()

    def validate(self, fx, address, count=1):
        if fx in [1, 5, 15]: block = self.store.get('c')
        elif fx in [2]:      block = self.store.get('d')
        elif fx in [3, 6, 16]: block = self.store.get('h')
        elif fx in [4]:      block = self.store.get('i')
        else: return False
        return block.validate(address, count) if block else False

    def getValues(self, fx, address, count=1):
        if fx in [1, 5, 15]: block = self.store.get('c')
        elif fx in [2]:      block = self.store.get('d')
        elif fx in [3, 6, 16]: block = self.store.get('h')
        elif fx in [4]:      block = self.store.get('i')
        else: return []
        return block.getValues(address, count)

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

class InverterSimulatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Inverter Simulator (IDs 1-5 Independent)")
        self.root.geometry("1100x900")

        self.server_thread = None
        self.context = None
        self.slave_contexts = {}  # {slave_id: ModbusSlaveContext}
        self.slaves_ui = {}       # {slave_id: {widgets...}}

        self.setup_ui()
        
        # Logging
        self.logger = logging.getLogger("pymodbus")
        self.logger.setLevel(logging.INFO)
        self.logger.handlers = []
        self.log_handler = TextHandler(self.log_text)
        self.log_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s', '%H:%M:%S'))
        self.logger.addHandler(self.log_handler)
        self.my_logger = logging.getLogger("SimApp")
        self.my_logger.setLevel(logging.INFO)
        self.my_logger.addHandler(self.log_handler)

    def my_log(self, msg):
        self.my_logger.info(msg)

    def setup_ui(self):
        # 1. Configuration Panel (Top)
        config_frame = ttk.LabelFrame(self.root, text="Server Configuration", padding="10")
        config_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(config_frame, text="COM Port:").grid(row=0, column=0, padx=5)
        self.com_port_var = tk.StringVar()
        self.com_port_combo = ttk.Combobox(config_frame, textvariable=self.com_port_var)
        self.com_port_combo.grid(row=0, column=1, padx=5)
        self.refresh_ports()
        ttk.Button(config_frame, text="Refresh", command=self.refresh_ports).grid(row=0, column=2, padx=5)

        ttk.Label(config_frame, text="Baudrate:").grid(row=0, column=3, padx=5)
        self.baudrate_var = tk.IntVar(value=9600)
        ttk.Combobox(config_frame, textvariable=self.baudrate_var, values=[9600, 19200, 38400, 115200]).grid(row=0, column=4, padx=5)

        self.start_btn = ttk.Button(config_frame, text="Start Server", command=self.start_server)
        self.start_btn.grid(row=0, column=5, padx=10)
        self.stop_btn = ttk.Button(config_frame, text="Stop Server", command=self.stop_server, state="disabled")
        self.stop_btn.grid(row=0, column=6, padx=10)
        
        self.show_traffic_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(config_frame, text="Log Traffic", variable=self.show_traffic_var, command=self.toggle_traffic).grid(row=0, column=7, padx=5)

        # 2. Tabs for Slaves (Center)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=5)

        # Support BOTH ranges (1-5 and 110-114) to be safe against Firmware/Config mismatches
        # User says 1-5, but Logs show 110. This covers both.
        all_ids = [1, 2, 3, 4, 5]
        for slave_id in all_ids:
            frame = ttk.Frame(self.notebook)
            self.notebook.add(frame, text=f"ID {slave_id}")
            self.setup_slave_tab(frame, slave_id)

        # 3. Log (Bottom)
        log_frame = ttk.LabelFrame(self.root, text="Bus Traffic", padding="5")
        log_frame.pack(fill="x", padx=10, pady=5)
        self.log_text = tk.Text(log_frame, height=8, state="disabled", bg="black", fg="white")
        self.log_text.pack(fill="x")

    def setup_slave_tab(self, parent, slave_id):
        ui = {}
        
        # Controls Frame
        ctrl_frame = ttk.LabelFrame(parent, text=f"Inverter {slave_id} Simulation Controls", padding="10")
        ctrl_frame.pack(fill="x", padx=5, pady=5)

        # Variables
        ui['freq_var'] = tk.DoubleVar(value=50.0)
        ui['volt_var'] = tk.DoubleVar(value=220.0)
        ui['curr_var'] = tk.DoubleVar(value=5.0)
        ui['pwr_var']  = tk.DoubleVar(value=1.1)

        # Layout High-Level Controls
        # Freq
        ttk.Label(ctrl_frame, text="Freq (Hz):").grid(row=0, column=0, padx=5)
        ttk.Entry(ctrl_frame, textvariable=ui['freq_var'], width=8).grid(row=0, column=1)
        ttk.Button(ctrl_frame, text="Set", command=lambda s=slave_id: self.set_val(s, 0x3000, ui['freq_var'].get(), 100)).grid(row=0, column=2)
        
        # Volt
        ttk.Label(ctrl_frame, text="Volt (V):").grid(row=0, column=3, padx=5)
        ttk.Entry(ctrl_frame, textvariable=ui['volt_var'], width=8).grid(row=0, column=4)
        ttk.Button(ctrl_frame, text="Set", command=lambda s=slave_id: self.set_val(s, 0x3002, ui['volt_var'].get(), 10)).grid(row=0, column=5)

        # Current
        ttk.Label(ctrl_frame, text="Curr (A):").grid(row=0, column=6, padx=5)
        ttk.Entry(ctrl_frame, textvariable=ui['curr_var'], width=8).grid(row=0, column=7)
        ttk.Button(ctrl_frame, text="Set", command=lambda s=slave_id: self.set_val(s, 0x3003, ui['curr_var'].get(), 10)).grid(row=0, column=8)

        # Power
        ttk.Label(ctrl_frame, text="Power (kW):").grid(row=0, column=9, padx=5)
        ttk.Entry(ctrl_frame, textvariable=ui['pwr_var'], width=8).grid(row=0, column=10)
        ttk.Button(ctrl_frame, text="Set", command=lambda s=slave_id: self.set_val(s, 0x3004, ui['pwr_var'].get(), 10)).grid(row=0, column=11)

        # Register Table
        data_frame = ttk.Frame(parent)
        data_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        cols = ("Address", "Name", "Value")
        tree = ttk.Treeview(data_frame, columns=cols, show="headings")
        tree.heading("Address", text="Address")
        tree.heading("Name", text="Name")
        tree.heading("Value", text="Value (Hex)")
        tree.column("Address", width=80)
        tree.column("Name", width=200)
        tree.column("Value", width=80)
        
        scroll = ttk.Scrollbar(data_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        
        ui['tree'] = tree
        self.slaves_ui[slave_id] = ui
        
        # Seed Table
        self.populate_tree(slave_id)
        
        # Tree Edit Binding
        tree.bind("<Double-1>", lambda e, s=slave_id: self.on_tree_edit(e, s))

    def get_register_map(self, slave_id):
        # Base map, can be customized per slave if needed later
        return [
            # Standard Inverter Map (from InverterComH.h)
            {"addr": 0x2000, "name": "Control Command", "val": 0},
            {"addr": 0x3000, "name": "Frequency Running", "val": 5000},
            {"addr": 0x3002, "name": "Voltage Output", "val": 2200},
            {"addr": 0x3003, "name": "Current Output", "val": 50},
            {"addr": 0x3004, "name": "Power Output", "val": 11},
            {"addr": 0x3005, "name": "Speed Est", "val": 1450},
            {"addr": 0x3006, "name": "Volt Bus", "val": 3100},
            {"addr": 0x3017, "name": "Temp Inv", "val": 350},
            {"addr": 0x3023, "name": "Energy/Power (Total)", "val": 999},
            {"addr": 0x3100, "name": "Fault Code", "val": 0},
            
            # Configuration / Control
            {"addr": 0x8000, "name": "Password", "val": 0},
            {"addr": 0x8200, "name": "Start Command Mode", "val": 0}, # 0=Keypad, 2=Comm
            {"addr": 0x0B15, "name": "Temp Set Point", "val": 45},    # 45 C
            {"addr": 0x840A, "name": "Device ID", "val": 1}, 
            
            # Aliases / FR500A Map (0x0300 range)
            # Based on InverterModbus.h U00 structs and logs (FC04 @ 0x0300)
            {"addr": 0x0300, "name": "Output Frequency (0.00-Fup)", "val": 5000}, # U00.00
            {"addr": 0x0302, "name": "Output Voltage (V)", "val": 2200},      # U00.02
            {"addr": 0x0303, "name": "Output Current (A)", "val": 50},        # U00.03
            {"addr": 0x0304, "name": "Output Power (kW)", "val": 11},         # U00.04
            {"addr": 0x0305, "name": "Motor Speed (rpm)", "val": 1450},       # U00.05
            {"addr": 0x0306, "name": "Bus Voltage (V)", "val": 3100},         # U00.06
            {"addr": 0x0317, "name": "Inverter Temp (C)", "val": 350},        # U00.23 (0x17 = 23)
            {"addr": 0x0323, "name": "Power Consumption (kWh)", "val": 999},  # U00.35 (0x23 = 35)
        ]

    def populate_tree(self, slave_id):
        tree = self.slaves_ui[slave_id]['tree']
        for row in tree.get_children(): tree.delete(row)
        
        for reg in self.get_register_map(slave_id):
            tree.insert("", "end", iid=reg['addr'], 
                        values=(f"0x{reg['addr']:04X}", reg['name'], f"0x{reg['val']:04X}"))

    def set_val(self, slave_id, addr, val, scale):
        try:
            int_val = int(val * scale)
            self.update_register(slave_id, addr, int_val)
            self.my_log(f"Slave {slave_id}: Set 0x{addr:04X} to {val} (Reg: {int_val})")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def update_register(self, slave_id, addr, val):
        # 1. Update GUI
        tree = self.slaves_ui[slave_id]['tree']
        if tree.exists(addr):
            curr = tree.item(addr)['values']
            tree.item(addr, values=(curr[0], curr[1], f"0x{val:04X}"))
            
        # 2. Update Modbus Context (if running)
        if slave_id in self.slave_contexts:
            ctx = self.slave_contexts[slave_id]
            # Update both Holding (03) and Input (04) for flexibility
            ctx.setValues(3, addr, [val])
            ctx.setValues(4, addr, [val])
            
        # 3. Logic: Handle Run/Stop Commands
        # 0x2000 is standard Control Command
        if addr == 0x2000:
            status_regs = [0x3000, 0x3002, 0x3003, 0x3004, 0x3005, 0x3006, 0x3017, 0x3023]
            alias_regs = [0x0300, 0x0302, 0x0303, 0x0304, 0x0305, 0x0306, 0x0317, 0x0323]
            
            if val in [5, 6, 0]: # Stop / Freewheel / Off
                self.my_log(f"Slave {slave_id}: STOP Command Received (0x{val:X}). Zeroing outputs.")
                # Zero out Status
                # Freq(0), Volt(0), Curr(0), Pwr(0), Speed(0), Bus(3100), Temp(350), Energy(999)
                # Keep Bus/Temp/Energy non-zero for realism
                zeros = {
                    0x3000: 0, 0x0300: 0, # Freq
                    0x3003: 0, 0x0303: 0, # Curr
                    0x3004: 0, 0x0304: 0, # Power
                    0x3005: 0, 0x0305: 0, # Speed
                }
                for r, v in zeros.items():
                    self.update_register(slave_id, r, v) # Recursive call? No, infinite loop check needed?
                    # update_register calls setValues. It calls update_register again only if GUI triggers it?
                    # No, this IS update_register. We should call self.update_register BUT avoid recursion for 0x2000.
                    # Actually, update_register updates GUI. We want to update GUI for these status regs too.
                    pass
                
                # Direct updates to avoid recursion issues if logic expanded
                for r, v in zeros.items():
                   # Update GUI
                   tree = self.slaves_ui[slave_id]['tree']
                   if tree.exists(r):
                       curr = tree.item(r)['values']
                       tree.item(r, values=(curr[0], curr[1], f"0x{v:04X}"))
                   # Update Store
                   if slave_id in self.slave_contexts:
                        self.slave_contexts[slave_id].setValues(3, r, [v])
                        self.slave_contexts[slave_id].setValues(4, r, [v])

            elif val == 1: # Run
                self.my_log(f"Slave {slave_id}: RUN Command Received. Restoring defaults.")
                defaults = {
                    0x3000: 5000, 0x0300: 5000,
                    0x3003: 50,   0x0303: 50,
                    0x3004: 11,   0x0304: 11,
                    0x3005: 1450, 0x0305: 1450
                }
                for r, v in defaults.items():
                   # Update GUI
                   tree = self.slaves_ui[slave_id]['tree']
                   if tree.exists(r):
                       curr = tree.item(r)['values']
                       tree.item(r, values=(curr[0], curr[1], f"0x{v:04X}"))
                   # Update Store
                   if slave_id in self.slave_contexts:
                        self.slave_contexts[slave_id].setValues(3, r, [v])
                        self.slave_contexts[slave_id].setValues(4, r, [v])

    def on_tree_edit(self, event, slave_id):
        tree = self.slaves_ui[slave_id]['tree']
        item_id = tree.selection()[0]
        item = tree.item(item_id)
        
        # Simple Dialog to edit
        new_val = tk.simpledialog.askinteger("Edit Register", f"Enter new value for {item['values'][1]} (0x{item_id}):", 
                                           parent=self.root, minvalue=0, maxvalue=65535)
        if new_val is not None:
            self.update_register(slave_id, int(item_id), new_val)

    def refresh_ports(self):
        ports = serial.tools.list_ports.comports()
        self.com_port_combo['values'] = [p.device for p in ports]
        if ports: self.com_port_combo.current(0)

    def toggle_traffic(self):
        lvl = logging.DEBUG if self.show_traffic_var.get() else logging.INFO
        self.logger.setLevel(lvl)

    def start_server(self):
        port = self.com_port_var.get()
        if not port: return messagebox.showerror("Error", "Select Port")
        
        self.my_log(f"Initializing {len(self.slaves_ui)} slaves...")
        
        # Build Contexts
        self.slave_contexts = {}
        devices = {}
        
        for slave_id in self.slaves_ui:
            # Create Data Blocks
            # Create Data Blocks
            # Pre-fill with current GUI values
            # Use full 65536 to cover ANY register address (0x0000-0xFFFF)
            initial_data = [0] * 65536
            tree = self.slaves_ui[slave_id]['tree']
            for row in tree.get_children():
                addr = int(row)
                val_str = tree.item(row)['values'][2]
                val = int(val_str, 16)
                if addr < 65536: initial_data[addr] = val
            
            # Create Context
            # Pymodbus v3.x stores: di, co, hr, ir
            # Use same block for HR (Holding) and IR (Input) for simplicity
            block = ModbusSequentialDataBlock(0, initial_data)
            ctx = ModbusSlaveContext(
                di=ModbusSequentialDataBlock(0, [0]*65536), 
                co=ModbusSequentialDataBlock(0, [0]*65536),  
                hr=block, # Holding Registers 
                ir=block  # Input Registers (Shared block for simplicity, or copy block)
            )
            self.slave_contexts[slave_id] = ctx
            devices[slave_id] = ctx
            
        try:
            self.context = ModbusServerContext(devices=devices, single=False)
        except Exception as e:
            return messagebox.showerror("Context Error", str(e))
            
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        
        self.server_thread = threading.Thread(
            target=self.run_server,
            args=(port, self.baudrate_var.get(), self.context),
            daemon=True
        )
        self.server_thread.start()

    def run_server(self, port, baud, context):
        self.my_log(f"Server STARTED on {port} @ {baud}")
        try:
            from pymodbus.framer import FramerType
            StartSerialServer(
                context=context,
                port=port,
                framer=FramerType.RTU,
                baudrate=baud,
                bytesize=8,
                parity='N',
                stopbits=1,
                timeout=1 # 10ms Latency Fix
            )
        except Exception as e:
            self.my_log(f"Server Error: {e}")

    def stop_server(self):
        self.my_log("Stopping (Restart app to fully reset serial)...")
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")

import tkinter.simpledialog # For edit dialog

if __name__ == "__main__":
    root = tk.Tk()
    app = InverterSimulatorApp(root)
    root.mainloop()

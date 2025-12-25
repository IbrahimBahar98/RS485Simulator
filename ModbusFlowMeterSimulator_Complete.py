"""
Complete Flow Meter Modbus RTU Simulator
Supports both Slave ID 110 and 111 with all registers
"""
import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import asyncio
import struct

from pymodbus.server import StartAsyncSerialServer
from pymodbus.datastore import context, sparse

class CompleteFlowMeterGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Complete Flow Meter Simulator - IDs 110 & 111")
        self.root.geometry("800x700")
        
        self.server_running = False
        self.server_thread = None
        
        # Connection Variables
        self.var_port = tk.StringVar(value="COM18")
        self.var_baud = tk.StringVar(value="9600")
        
        # Input Registers (FC 04) - Process Variables
        self.var_flow_rate = tk.DoubleVar(value=125.5)          # Reg 778-779 (float32)
        self.var_alarm_flags = tk.IntVar(value=0)               # Reg 777 (uint16)
        self.var_forward_total = tk.IntVar(value=1000000)       # Reg 772-773 (uint32)
        self.var_forward_overflow = tk.IntVar(value=0)          # Reg 786 (uint16)
        self.var_unit_info = tk.IntVar(value=3)                 # Reg 774 (uint16) - 3=m3/h
        self.var_conductivity = tk.DoubleVar(value=450.2)       # Reg 812-813 (float32)
        
        # Holding Registers (FC 03) - Configuration Parameters
        self.var_flow_range = tk.DoubleVar(value=500.0)         # Reg 261-262 (float32)
        self.var_alm_high_val = tk.DoubleVar(value=400.0)       # Reg 281-282 (float32)
        self.var_alm_low_val = tk.DoubleVar(value=10.0)         # Reg 284-285 (float32)
        
        # Alarm checkboxes
        self.var_alarm_empty = tk.BooleanVar(value=False)       # Bit 0
        self.var_alarm_excitation = tk.BooleanVar(value=False)  # Bit 1
        self.var_alarm_high = tk.BooleanVar(value=False)        # Bit 2
        self.var_alarm_low = tk.BooleanVar(value=False)         # Bit 3
        
        self._init_ui()
        
    def _init_ui(self):
        # Connection Frame
        conn_frame = ttk.LabelFrame(self.root, text="Connection", padding=10)
        conn_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(conn_frame, text="Port:").grid(row=0, column=0, padx=5)
        ttk.Entry(conn_frame, textvariable=self.var_port, width=10).grid(row=0, column=1, padx=5)
        
        ttk.Label(conn_frame, text="Baud:").grid(row=0, column=2, padx=5)
        ttk.Entry(conn_frame, textvariable=self.var_baud, width=10).grid(row=0, column=3, padx=5)
        
        ttk.Label(conn_frame, text="Slave IDs: 110, 111", font=("Arial", 9, "bold")).grid(row=0, column=4, padx=10)
        
        self.btn_start = ttk.Button(conn_frame, text="Start Server", command=self.start_server)
        self.btn_start.grid(row=0, column=5, padx=10)
        
        # Create notebook for tabs
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Tab 1: Process Variables (Input Registers)
        process_frame = ttk.Frame(notebook, padding=10)
        notebook.add(process_frame, text="Process Variables (Input Regs)")
        
        row = 0
        # Flow Rate
        ttk.Label(process_frame, text="Flow Rate (Reg 778-779):").grid(row=row, column=0, sticky="w", padx=5, pady=5)
        ttk.Scale(process_frame, from_=0, to=500, variable=self.var_flow_rate, 
                 command=lambda v: self.var_flow_rate.set(round(float(v), 1))).grid(row=row, column=1, sticky="ew", padx=5)
        ttk.Entry(process_frame, textvariable=self.var_flow_rate, width=10).grid(row=row, column=2, padx=5)
        ttk.Label(process_frame, text="m³/h").grid(row=row, column=3, sticky="w")
        
        row += 1
        # Conductivity
        ttk.Label(process_frame, text="Conductivity (Reg 812-813):").grid(row=row, column=0, sticky="w", padx=5, pady=5)
        ttk.Scale(process_frame, from_=0, to=1000, variable=self.var_conductivity,
                 command=lambda v: self.var_conductivity.set(round(float(v), 1))).grid(row=row, column=1, sticky="ew", padx=5)
        ttk.Entry(process_frame, textvariable=self.var_conductivity, width=10).grid(row=row, column=2, padx=5)
        ttk.Label(process_frame, text="µS/cm").grid(row=row, column=3, sticky="w")
        
        row += 1
        ttk.Separator(process_frame, orient="horizontal").grid(row=row, column=0, columnspan=4, sticky="ew", pady=10)
        
        row += 1
        # Forward Total
        ttk.Label(process_frame, text="Forward Total (Reg 772-773):").grid(row=row, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(process_frame, textvariable=self.var_forward_total, width=15).grid(row=row, column=1, sticky="w", padx=5)
        ttk.Button(process_frame, text="+1000", command=lambda: self.var_forward_total.set(self.var_forward_total.get() + 1000)).grid(row=row, column=2)
        
        row += 1
        # Overflow Count
        ttk.Label(process_frame, text="Overflow Count (Reg 786):").grid(row=row, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(process_frame, textvariable=self.var_forward_overflow, width=10).grid(row=row, column=1, sticky="w", padx=5)
        ttk.Button(process_frame, text="Reset", command=lambda: self.var_forward_overflow.set(0)).grid(row=row, column=2)
        
        row += 1
        # Unit Info
        ttk.Label(process_frame, text="Unit Code (Reg 774):").grid(row=row, column=0, sticky="w", padx=5, pady=5)
        ttk.Spinbox(process_frame, from_=0, to=10, textvariable=self.var_unit_info, width=10).grid(row=row, column=1, sticky="w", padx=5)
        ttk.Label(process_frame, text="(0=L, 3=m³, etc.)").grid(row=row, column=2, sticky="w", columnspan=2)
        
        row += 1
        ttk.Separator(process_frame, orient="horizontal").grid(row=row, column=0, columnspan=4, sticky="ew", pady=10)
        
        row += 1
        # Alarms
        ttk.Label(process_frame, text="Alarm Flags (Reg 777):", font=("Arial", 9, "bold")).grid(row=row, column=0, sticky="w", padx=5, pady=5)
        row += 1
        alarm_frame = ttk.Frame(process_frame)
        alarm_frame.grid(row=row, column=0, columnspan=4, sticky="w", padx=20)
        ttk.Checkbutton(alarm_frame, text="Empty Pipe (Bit 0)", variable=self.var_alarm_empty, command=self.update_alarm_flags).pack(anchor="w")
        ttk.Checkbutton(alarm_frame, text="Excitation Error (Bit 1)", variable=self.var_alarm_excitation, command=self.update_alarm_flags).pack(anchor="w")
        ttk.Checkbutton(alarm_frame, text="High Flow (Bit 2)", variable=self.var_alarm_high, command=self.update_alarm_flags).pack(anchor="w")
        ttk.Checkbutton(alarm_frame, text="Low Flow (Bit 3)", variable=self.var_alarm_low, command=self.update_alarm_flags).pack(anchor="w")
        
        process_frame.columnconfigure(1, weight=1)
        
        # Tab 2: Configuration Parameters (Holding Registers)
        config_frame = ttk.Frame(notebook, padding=10)
        notebook.add(config_frame, text="Configuration (Holding Regs)")
        
        row = 0
        # Flow Range
        ttk.Label(config_frame, text="Flow Range (Reg 261-262):").grid(row=row, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(config_frame, textvariable=self.var_flow_range, width=15).grid(row=row, column=1, sticky="w", padx=5)
        ttk.Label(config_frame, text="m³/h (Max flow)").grid(row=row, column=2, sticky="w")
        
        row += 1
        # Alarm High Value
        ttk.Label(config_frame, text="Alarm High Value (Reg 281-282):").grid(row=row, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(config_frame, textvariable=self.var_alm_high_val, width=15).grid(row=row, column=1, sticky="w", padx=5)
        ttk.Label(config_frame, text="m³/h").grid(row=row, column=2, sticky="w")
        
        row += 1
        # Alarm Low Value
        ttk.Label(config_frame, text="Alarm Low Value (Reg 284-285):").grid(row=row, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(config_frame, textvariable=self.var_alm_low_val, width=15).grid(row=row, column=1, sticky="w", padx=5)
        ttk.Label(config_frame, text="m³/h").grid(row=row, column=2, sticky="w")
        
        row += 1
        ttk.Label(config_frame, text="\nNote: These are configuration parameters that the EdgeBox reads on startup.", 
                 font=("Arial", 8, "italic")).grid(row=row, column=0, columnspan=3, sticky="w", padx=5, pady=10)
        
        # Tab 3: Log
        log_frame = ttk.Frame(notebook, padding=10)
        notebook.add(log_frame, text="Log")
        
        self.log_area = scrolledtext.ScrolledText(log_frame, height=20, state='normal', font=("Consolas", 9))
        self.log_area.pack(fill="both", expand=True)
        
        # Start update loop
        self.update_registers()
        
    def update_alarm_flags(self):
        """Update alarm flags based on checkboxes"""
        flags = 0
        if self.var_alarm_empty.get(): flags |= 0x01
        if self.var_alarm_excitation.get(): flags |= 0x02
        if self.var_alarm_high.get(): flags |= 0x04
        if self.var_alarm_low.get(): flags |= 0x08
        self.var_alarm_flags.set(flags)
        
    def log(self, message):
        """Thread-safe logging"""
        def append():
            self.log_area.insert(tk.END, message + '\n')
            self.log_area.see(tk.END)
        self.root.after(0, append)
        
    def start_server(self):
        if self.server_running:
            self.log("Server already running!")
            return
            
        port = self.var_port.get()
        baud = int(self.var_baud.get())
        
        self.log("=" * 60)
        self.log(f"Starting Complete Modbus RTU Server...")
        self.log(f"Port: {port}, Baud: {baud}")
        self.log(f"Slave IDs: 110, 111")
        self.log("=" * 60)
        
        # Create data blocks for both devices
        # Input Registers (FC 04)
        self.ir_block_110 = sparse.ModbusSparseDataBlock({
            772: [0]*50,  # Covers 772-821 (includes all input registers)
        })
        
        self.ir_block_111 = sparse.ModbusSparseDataBlock({
            772: [0]*50,
        })
        
        # Holding Registers (FC 03)
        self.hr_block_110 = sparse.ModbusSparseDataBlock({
            261: [0]*30,  # Covers 261-290 (includes all holding registers)
        })
        
        self.hr_block_111 = sparse.ModbusSparseDataBlock({
            261: [0]*30,
        })
        
        # Create device contexts with BOTH input and holding registers
        store_110 = context.ModbusDeviceContext(ir=self.ir_block_110, hr=self.hr_block_110)
        store_111 = context.ModbusDeviceContext(ir=self.ir_block_111, hr=self.hr_block_111)
        
        # Create server context with BOTH devices
        self.server_context = context.ModbusServerContext(
            devices={
                110: store_110,
                111: store_111
            }, 
            single=False
        )
        
        # Start server thread
        self.server_running = True
        self.server_thread = threading.Thread(target=self._run_server, args=(port, baud), daemon=True)
        self.server_thread.start()
        
        self.btn_start.config(state='disabled', text="Running...")
        self.log("✓ Server thread started")
        
    def _run_server(self, port, baud):
        """Run the async server in a thread"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            async def serve():
                self.log("✓ Async server starting...")
                await StartAsyncSerialServer(
                    context=self.server_context,
                    port=port,
                    baudrate=baud,
                    bytesize=8,
                    parity='N',
                    stopbits=1,
                    timeout=1
                )
                self.log("✓ Server is now listening for requests!")
                self.log("✓ Responding to slave IDs: 110 and 111")
                self.log("✓ Input Registers (FC 04) and Holding Registers (FC 03) ready")
            
            loop.run_until_complete(serve())
            loop.run_forever()
            
        except Exception as e:
            self.log(f"✗ ERROR: {type(e).__name__}: {e}")
            import traceback
            self.log(traceback.format_exc())
            self.server_running = False
            
    def update_registers(self):
        """Update Modbus registers with current values"""
        if self.server_running and hasattr(self, 'ir_block_110'):
            try:
                # Helper functions
                def pack_uint32(value):
                    """Pack uint32 with swapped word order to match EdgeBox getUint32()"""
                    packed = struct.pack('>I', value)
                    word0 = struct.unpack('>H', packed[0:2])[0]  # High word
                    word1 = struct.unpack('>H', packed[2:4])[0]  # Low word
                    # EdgeBox: u.r[1] = data[0]; u.r[0] = data[1]
                    return [word1, word0]  # Send low word first
                
                def pack_uint16(value):
                    return [value & 0xFFFF]
                
                def pack_float32(value):
                    """Pack float32 with swapped word order to match EdgeBox getFloat()"""
                    packed = struct.pack('>f', value)
                    word0 = struct.unpack('>H', packed[0:2])[0]  # High word
                    word1 = struct.unpack('>H', packed[2:4])[0]  # Low word
                    # EdgeBox: u.r[1] = data[0]; u.r[0] = data[1]
                    return [word1, word0]  # Send low word first
                
                # Update both devices with same data
                for ir_block, hr_block in [(self.ir_block_110, self.hr_block_110), 
                                             (self.ir_block_111, self.hr_block_111)]:
                    # INPUT REGISTERS (FC 04)
                    # 772-773: Forward Total (uint32)
                    ir_block.setValues(772, pack_uint32(self.var_forward_total.get()))
                    
                    # 774: Unit Info (uint16)
                    ir_block.setValues(774, pack_uint16(self.var_unit_info.get()))
                    
                    # 777: Alarm flags (uint16)
                    self.update_alarm_flags()
                    ir_block.setValues(777, pack_uint16(self.var_alarm_flags.get()))
                    
                    # 778-779: Flow Rate (float32)
                    ir_block.setValues(778, pack_float32(self.var_flow_rate.get()))
                    
                    # 786: Overflow count (uint16)
                    ir_block.setValues(786, pack_uint16(self.var_forward_overflow.get()))
                    
                    # 812-813: Conductivity (float32)
                    ir_block.setValues(812, pack_float32(self.var_conductivity.get()))
                    
                    # HOLDING REGISTERS (FC 03)
                    # 261-262: Flow Range (float32)
                    hr_block.setValues(261, pack_float32(self.var_flow_range.get()))
                    
                    # 281-282: Alarm High Value (float32)
                    hr_block.setValues(281, pack_float32(self.var_alm_high_val.get()))
                    
                    # 284-285: Alarm Low Value (float32)
                    hr_block.setValues(284, pack_float32(self.var_alm_low_val.get()))
                
            except Exception as e:
                pass  # Silently ignore update errors
                
        # Schedule next update
        self.root.after(500, self.update_registers)

if __name__ == "__main__":
    root = tk.Tk()
    app = CompleteFlowMeterGUI(root)
    root.mainloop()

"""
Dual Flow Meter Modbus RTU Simulator
Supports both Slave ID 110 and 111
"""
import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import asyncio
import struct

from pymodbus.server import StartAsyncSerialServer
from pymodbus.datastore import context, sparse

class DualFlowMeterGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Dual Flow Meter Simulator")
        self.root.geometry("600x500")
        
        self.server_running = False
        self.server_thread = None
        
        # Variables
        self.var_port = tk.StringVar(value="COM18")
        self.var_baud = tk.StringVar(value="9600")
        self.var_flow_rate = tk.DoubleVar(value=125.5)
        self.var_conductivity = tk.DoubleVar(value=450.2)
        self.var_total_flow = tk.IntVar(value=1000000)
        
        self._init_ui()
        
    def _init_ui(self):
        # Connection Frame
        conn_frame = ttk.LabelFrame(self.root, text="Connection", padding=10)
        conn_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(conn_frame, text="Port:").grid(row=0, column=0, padx=5)
        ttk.Entry(conn_frame, textvariable=self.var_port, width=10).grid(row=0, column=1, padx=5)
        
        ttk.Label(conn_frame, text="Baud:").grid(row=0, column=2, padx=5)
        ttk.Entry(conn_frame, textvariable=self.var_baud, width=10).grid(row=0, column=3, padx=5)
        
        ttk.Label(conn_frame, text="Slave IDs: 110, 111").grid(row=0, column=4, padx=10)
        
        self.btn_start = ttk.Button(conn_frame, text="Start Server", command=self.start_server)
        self.btn_start.grid(row=0, column=5, padx=10)
        
        # Data Frame
        data_frame = ttk.LabelFrame(self.root, text="Sensor Values (Both Devices)", padding=10)
        data_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(data_frame, text="Flow Rate:").grid(row=0, column=0, sticky="w", padx=5)
        ttk.Scale(data_frame, from_=0, to=500, variable=self.var_flow_rate, 
                 command=lambda v: self.var_flow_rate.set(round(float(v), 1))).grid(row=0, column=1, sticky="ew", padx=5)
        ttk.Label(data_frame, textvariable=self.var_flow_rate, width=10).grid(row=0, column=2, padx=5)
        
        ttk.Label(data_frame, text="Conductivity:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        ttk.Scale(data_frame, from_=0, to=1000, variable=self.var_conductivity,
                 command=lambda v: self.var_conductivity.set(round(float(v), 1))).grid(row=1, column=1, sticky="ew", padx=5)
        ttk.Label(data_frame, textvariable=self.var_conductivity, width=10).grid(row=1, column=2, padx=5)
        
        ttk.Label(data_frame, text="Total Flow:").grid(row=2, column=0, sticky="w", padx=5)
        ttk.Entry(data_frame, textvariable=self.var_total_flow, width=15).grid(row=2, column=1, sticky="w", padx=5)
        
        data_frame.columnconfigure(1, weight=1)
        
        # Log Frame
        log_frame = ttk.LabelFrame(self.root, text="Log", padding=10)
        log_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.log_area = scrolledtext.ScrolledText(log_frame, height=15, state='normal', font=("Consolas", 9))
        self.log_area.pack(fill="both", expand=True)
        
        # Start update loop
        self.update_registers()
        
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
        self.log(f"Starting Modbus RTU Server...")
        self.log(f"Port: {port}, Baud: {baud}")
        self.log(f"Slave IDs: 110, 111")
        self.log("=" * 60)
        
        # Create data blocks for both devices
        self.data_block_110 = sparse.ModbusSparseDataBlock({
            772: [0]*20,  # Covers 772-791
            812: [0]*4
        })
        
        self.data_block_111 = sparse.ModbusSparseDataBlock({
            772: [0]*20,  # Covers 772-791
            812: [0]*4
        })
        
        # Create device contexts
        store_110 = context.ModbusDeviceContext(ir=self.data_block_110)
        store_111 = context.ModbusDeviceContext(ir=self.data_block_111)
        
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
            # Create new event loop for this thread
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
            
            # Start server and run forever
            loop.run_until_complete(serve())
            loop.run_forever()
            
        except Exception as e:
            self.log(f"✗ ERROR: {type(e).__name__}: {e}")
            import traceback
            self.log(traceback.format_exc())
            self.server_running = False
            
    def update_registers(self):
        """Update Modbus registers with current values"""
        if self.server_running and hasattr(self, 'data_block_110'):
            try:
                # Helper functions
                def pack_uint32(value):
                    """Pack uint32 with swapped word order"""
                    packed = struct.pack('>I', value)
                    word0 = struct.unpack('>H', packed[0:2])[0]
                    word1 = struct.unpack('>H', packed[2:4])[0]
                    return [word1, word0]
                
                def pack_uint16(value):
                    return [value & 0xFFFF]
                
                def pack_float32(value):
                    """Pack float32 with swapped word order"""
                    packed = struct.pack('>f', value)
                    word0 = struct.unpack('>H', packed[0:2])[0]
                    word1 = struct.unpack('>H', packed[2:4])[0]
                    return [word1, word0]
                
                # Update both devices with same data
                for block in [self.data_block_110, self.data_block_111]:
                    # 772-773: Total Flow (uint32)
                    total_regs = pack_uint32(self.var_total_flow.get())
                    block.setValues(772, total_regs)
                    
                    # 774: Unit Info (uint16) - 3 = m3/h
                    block.setValues(774, pack_uint16(3))
                    
                    # 777: Alarm flags (uint16)
                    block.setValues(777, pack_uint16(0))  # No alarms
                    
                    # 778-779: Flow Rate (float32)
                    flow_regs = pack_float32(self.var_flow_rate.get())
                    block.setValues(778, flow_regs)
                    
                    # 786: Overflow count (uint16)
                    block.setValues(786, pack_uint16(0))
                    
                    # 812-813: Conductivity (float32)
                    cond_regs = pack_float32(self.var_conductivity.get())
                    block.setValues(812, cond_regs)
                
            except Exception as e:
                self.log(f"Update error: {e}")
                
        # Schedule next update
        self.root.after(500, self.update_registers)

if __name__ == "__main__":
    root = tk.Tk()
    app = DualFlowMeterGUI(root)
    root.mainloop()

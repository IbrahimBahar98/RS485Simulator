"""
Complete Flow Meter Modbus RTU Simulator
Supports both Slave ID 110 and 111 with all registers
"""
import tkinter as tk
from tkinter import ttk, scrolledtext
from tkinter import filedialog, messagebox
import threading
import asyncio
import struct
import json
import serial
import logging

from pymodbus.server import StartAsyncSerialServer
from pymodbus.datastore import context, sparse


class CompleteFlowMeterGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Complete Flow Meter Simulator")
        self.root.geometry("800x700")

        self.server_running = False
        self.server_thread = None

        # Connection Variables
        self.var_port = tk.StringVar(value="COM18")
        self.var_baud = tk.StringVar(value="9600")

        # --- New: Server + UI configuration (user-editable) ---
        self.var_slave_ids = tk.StringVar(value="110,111")     # Allow add/remove devices
        self.var_update_period_ms = tk.IntVar(value=500)       # Update period (ms)
        self.var_byte_order = tk.StringVar(value="CDAB")       # Word/byte order mode

        # Slider scaling/limits + precision (user-editable)
        self.var_flow_max = tk.DoubleVar(value=500.0)
        self.var_flow_precision = tk.IntVar(value=1)           # decimals
        self.var_cond_max = tk.DoubleVar(value=1000.0)
        self.var_cond_precision = tk.IntVar(value=1)           # decimals

        # Register map (editable as JSON text)
        # Note: keep current behavior as default (matches existing hardcoded map).
        self.register_map = {
            "forward_total": {"fc": "ir", "address": 772, "type": "uint32", "enabled": True},
            "unit_info": {"fc": "ir", "address": 774, "type": "uint16", "enabled": True},
            "alarm_flags": {"fc": "ir", "address": 777, "type": "uint16", "enabled": True},
            "flow_rate": {"fc": "ir", "address": 778, "type": "float32", "enabled": True},
            "overflow_count": {"fc": "ir", "address": 786, "type": "uint16", "enabled": True},
            "conductivity": {"fc": "ir", "address": 812, "type": "float32", "enabled": True},

            "flow_range": {"fc": "hr", "address": 261, "type": "float32", "enabled": True},
            "alm_high_val": {"fc": "hr", "address": 281, "type": "float32", "enabled": True},
            "alm_low_val": {"fc": "hr", "address": 284, "type": "float32", "enabled": True},
        }

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

        # Runtime-created device blocks are stored here (keyed by slave id)
        self.ir_blocks = {}
        self.hr_blocks = {}

        self._init_ui()

    def _init_ui(self):
        # Connection Frame
        conn_frame = ttk.LabelFrame(self.root, text="Connection", padding=10)
        conn_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(conn_frame, text="Port:").grid(row=0, column=0, padx=5)
        ttk.Entry(conn_frame, textvariable=self.var_port, width=10).grid(row=0, column=1, padx=5)

        ttk.Label(conn_frame, text="Baud:").grid(row=0, column=2, padx=5)
        ttk.Entry(conn_frame, textvariable=self.var_baud, width=10).grid(row=0, column=3, padx=5)

        ttk.Label(conn_frame, text="Slave IDs:", font=("Arial", 9, "bold")).grid(row=0, column=4, padx=10, sticky="e")
        ttk.Entry(conn_frame, textvariable=self.var_slave_ids, width=12).grid(row=0, column=5, padx=5, sticky="w")

        self.btn_start = ttk.Button(conn_frame, text="Start Server", command=self.start_server)
        self.btn_start.grid(row=0, column=6, padx=10)

        # Create notebook for tabs
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=10, pady=5)

        # Tab 1: Process Variables (Input Registers)
        process_frame = ttk.Frame(notebook, padding=10)
        notebook.add(process_frame, text="Process Variables (Input Regs)")

        row = 0
        # Flow Rate
        ttk.Label(process_frame, text="Flow Rate (Reg 778-779):").grid(row=row, column=0, sticky="w", padx=5, pady=5)
        self.scale_flow = ttk.Scale(
            process_frame,
            from_=0,
            to=float(self.var_flow_max.get()),
            variable=self.var_flow_rate,
            command=self._on_flow_slider
        )
        self.scale_flow.grid(row=row, column=1, sticky="ew", padx=5)
        ttk.Entry(process_frame, textvariable=self.var_flow_rate, width=10).grid(row=row, column=2, padx=5)
        ttk.Label(process_frame, text="m³/h").grid(row=row, column=3, sticky="w")

        row += 1
        # Conductivity
        ttk.Label(process_frame, text="Conductivity (Reg 812-813):").grid(row=row, column=0, sticky="w", padx=5, pady=5)
        self.scale_cond = ttk.Scale(
            process_frame,
            from_=0,
            to=float(self.var_cond_max.get()),
            variable=self.var_conductivity,
            command=self._on_cond_slider
        )
        self.scale_cond.grid(row=row, column=1, sticky="ew", padx=5)
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

        # Tab 3: Advanced (server settings + profile + register map)
        adv_frame = ttk.Frame(notebook, padding=10)
        notebook.add(adv_frame, text="Advanced")

        # Server settings
        settings_frame = ttk.LabelFrame(adv_frame, text="Server Settings", padding=10)
        settings_frame.pack(fill="x", padx=5, pady=5)

        r = 0
        ttk.Label(settings_frame, text="Update period (ms):").grid(row=r, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(settings_frame, textvariable=self.var_update_period_ms, width=10).grid(row=r, column=1, sticky="w", padx=5, pady=2)

        ttk.Label(settings_frame, text="Byte/Word order:").grid(row=r, column=2, sticky="w", padx=5, pady=2)
        ttk.Combobox(
            settings_frame,
            textvariable=self.var_byte_order,
            values=["CDAB", "ABCD", "BADC", "DCBA"],
            width=8,
            state="readonly"
        ).grid(row=r, column=3, sticky="w", padx=5, pady=2)

        r += 1
        ttk.Label(settings_frame, text="Flow max:").grid(row=r, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(settings_frame, textvariable=self.var_flow_max, width=10).grid(row=r, column=1, sticky="w", padx=5, pady=2)

        ttk.Label(settings_frame, text="Flow decimals:").grid(row=r, column=2, sticky="w", padx=5, pady=2)
        ttk.Spinbox(settings_frame, from_=0, to=4, textvariable=self.var_flow_precision, width=8).grid(row=r, column=3, sticky="w", padx=5, pady=2)

        r += 1
        ttk.Label(settings_frame, text="Conductivity max:").grid(row=r, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(settings_frame, textvariable=self.var_cond_max, width=10).grid(row=r, column=1, sticky="w", padx=5, pady=2)

        ttk.Label(settings_frame, text="Cond decimals:").grid(row=r, column=2, sticky="w", padx=5, pady=2)
        ttk.Spinbox(settings_frame, from_=0, to=4, textvariable=self.var_cond_precision, width=8).grid(row=r, column=3, sticky="w", padx=5, pady=2)

        r += 1
        ttk.Button(settings_frame, text="Apply Settings", command=self.apply_settings).grid(row=r, column=0, padx=5, pady=6, sticky="w")
        ttk.Button(settings_frame, text="Save Profile", command=self.save_profile).grid(row=r, column=1, padx=5, pady=6, sticky="w")
        ttk.Button(settings_frame, text="Load Profile", command=self.load_profile).grid(row=r, column=2, padx=5, pady=6, sticky="w")

        # Register map editor (JSON)
        map_frame = ttk.LabelFrame(adv_frame, text="Register Map (JSON)", padding=10)
        map_frame.pack(fill="both", expand=True, padx=5, pady=5)

        self.txt_register_map = scrolledtext.ScrolledText(map_frame, height=12, state="normal", font=("Consolas", 9))
        self.txt_register_map.pack(fill="both", expand=True)
        self._refresh_register_map_editor()

        btns = ttk.Frame(map_frame)
        btns.pack(fill="x", pady=6)
        ttk.Button(btns, text="Apply Register Map", command=self.apply_register_map_from_editor).pack(side="left")
        ttk.Button(btns, text="Reset to Defaults", command=self.reset_register_map_defaults).pack(side="left", padx=6)

        # Tab 4: Log
        log_frame = ttk.Frame(notebook, padding=10)
        notebook.add(log_frame, text="Log")

        self.log_area = scrolledtext.ScrolledText(log_frame, height=20, state='normal', font=("Consolas", 9))
        self.log_area.pack(fill="both", expand=True)

        # Start update loop
        self.update_registers()

    def _on_flow_slider(self, v):
        """Slider callback respecting the configured decimal precision."""
        try:
            decimals = int(self.var_flow_precision.get())
        except Exception:
            decimals = 1
        self.var_flow_rate.set(round(float(v), decimals))

    def _on_cond_slider(self, v):
        """Slider callback respecting the configured decimal precision."""
        try:
            decimals = int(self.var_cond_precision.get())
        except Exception:
            decimals = 1
        self.var_conductivity.set(round(float(v), decimals))

    def _refresh_register_map_editor(self):
        """Keep the register map editor in sync with the in-memory map."""
        self.txt_register_map.delete("1.0", tk.END)
        self.txt_register_map.insert(tk.END, json.dumps(self.register_map, indent=2, sort_keys=True))

    def reset_register_map_defaults(self):
        """Restore the default register map (same as original hardcoded behavior)."""
        self.register_map = {
            "forward_total": {"fc": "ir", "address": 772, "type": "uint32", "enabled": True},
            "unit_info": {"fc": "ir", "address": 774, "type": "uint16", "enabled": True},
            "alarm_flags": {"fc": "ir", "address": 777, "type": "uint16", "enabled": True},
            "flow_rate": {"fc": "ir", "address": 778, "type": "float32", "enabled": True},
            "overflow_count": {"fc": "ir", "address": 786, "type": "uint16", "enabled": True},
            "conductivity": {"fc": "ir", "address": 812, "type": "float32", "enabled": True},
            "flow_range": {"fc": "hr", "address": 261, "type": "float32", "enabled": True},
            "alm_high_val": {"fc": "hr", "address": 281, "type": "float32", "enabled": True},
            "alm_low_val": {"fc": "hr", "address": 284, "type": "float32", "enabled": True},
        }
        self._refresh_register_map_editor()
        self.log("✓ Register map reset to defaults")

    def apply_register_map_from_editor(self):
        """Parse JSON from editor and replace the active register map."""
        raw = self.txt_register_map.get("1.0", tk.END).strip()
        try:
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                raise ValueError("Register map JSON must be an object/dict")
            # Basic sanity checks so bad edits don't crash the update loop.
            for key, cfg in parsed.items():
                if not isinstance(cfg, dict):
                    raise ValueError(f"'{key}' must be an object")
                if cfg.get("fc") not in ("ir", "hr"):
                    raise ValueError(f"'{key}.fc' must be 'ir' or 'hr'")
                if not isinstance(cfg.get("address"), int):
                    raise ValueError(f"'{key}.address' must be an integer")
                if cfg.get("type") not in ("uint16", "uint32", "float32"):
                    raise ValueError(f"'{key}.type' must be uint16/uint32/float32")
                if not isinstance(cfg.get("enabled", True), bool):
                    raise ValueError(f"'{key}.enabled' must be boolean")
            self.register_map = parsed
            self.log("✓ Register map applied")
        except Exception as e:
            messagebox.showerror("Invalid Register Map", f"Failed to apply register map:\n{e}")

    def apply_settings(self):
        """Apply settings that affect UI behavior (sliders) and the update loop timing."""
        # Update slider ranges immediately (server doesn't need restart for this).
        try:
            flow_max = float(self.var_flow_max.get())
            cond_max = float(self.var_cond_max.get())
            if flow_max <= 0 or cond_max <= 0:
                raise ValueError("Max values must be > 0")

            self.scale_flow.configure(to=flow_max)
            self.scale_cond.configure(to=cond_max)

            self.log(f"✓ Applied slider limits: flow_max={flow_max}, cond_max={cond_max}")
        except Exception as e:
            messagebox.showerror("Invalid Settings", f"Failed to apply settings:\n{e}")
            return

        # Update period is used on the next scheduled loop automatically.
        try:
            period = int(self.var_update_period_ms.get())
            if period < 50:
                # Keep it sane so the GUI thread doesn't get hammered.
                period = 50
                self.var_update_period_ms.set(period)
            self.log(f"✓ Applied update period: {period} ms")
        except Exception as e:
            messagebox.showerror("Invalid Settings", f"Invalid update period:\n{e}")

    def _parse_slave_ids(self):
        """Parse slave IDs from UI into a sorted list of unique ints."""
        raw = self.var_slave_ids.get().strip()
        if not raw:
            raise ValueError("Slave IDs cannot be empty")

        parts = [p.strip() for p in raw.split(",") if p.strip()]
        ids = []
        for p in parts:
            v = int(p)
            if v < 1 or v > 247:
                raise ValueError(f"Invalid slave id '{v}' (valid range 1..247)")
            ids.append(v)

        # Remove duplicates but keep stable ordering using dict trick.
        ids = list(dict.fromkeys(ids))
        return ids

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
    
    def _set_server_ui_state(self, running: bool, message: str | None = None):
        """Update UI state for server start/stop in a thread-safe way."""
        def apply():
            if running:
                self.btn_start.config(state='disabled', text="Running...")
            else:
                self.btn_start.config(state='normal', text="Start Server")

            if message:
                self.log(message)

        self.root.after(0, apply)

    def _preflight_check_serial(self, port: str, baud: int):
        """
        Quick sanity check before starting the pymodbus server thread.
        This avoids getting stuck in 'Running...' when the port is missing/inaccessible.
        """
        # Uses the same serial settings as StartAsyncSerialServer
        test = serial.Serial(
            port=port,
            baudrate=baud,
            bytesize=8,
            parity='N',
            stopbits=1,
            timeout=1
        )
        test.close()

    def start_server(self):
        logging.basicConfig(level=logging.INFO)
        logging.getLogger("pymodbus").setLevel(logging.DEBUG)
        if self.server_running:
            self.log("Server already running!")
            return

        port = self.var_port.get()
        baud = int(self.var_baud.get())

        self.log("=" * 60)
        self.log("Starting Complete Modbus RTU Server...")
        self.log(f"Port: {port}, Baud: {baud}")
        self.log(f"Slave IDs: 110, 111")
        self.log("=" * 60)

        # Preflight check: fail fast and keep UI intuitive
        try:
            self._preflight_check_serial(port, baud)
        except Exception as e:
            self.server_running = False
            self._set_server_ui_state(False, f"✗ Failed to start server: cannot open port '{port}': {type(e).__name__}: {e}")
            return

        # Covers a wide range so register addressing differences don't cause illegal-address reads.
        # Keeps everything else the same (same addresses in setValues()).
        IR_BASE = 0
        IR_LEN = 2000   # plenty for 772..813 and more
        HR_BASE = 0
        HR_LEN = 2000

        self.ir_block_110 = sparse.ModbusSparseDataBlock({IR_BASE: [0] * IR_LEN})
        self.ir_block_111 = sparse.ModbusSparseDataBlock({IR_BASE: [0] * IR_LEN})

        self.hr_block_110 = sparse.ModbusSparseDataBlock({HR_BASE: [0] * HR_LEN})
        self.hr_block_111 = sparse.ModbusSparseDataBlock({HR_BASE: [0] * HR_LEN})

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
        self.btn_start.config(state='disabled', text="Starting...")

        self.server_thread = threading.Thread(target=self._run_server, args=(port, baud), daemon=True)
        self.server_thread.start()

        self.log("✓ Server thread started")

    def _compute_block_range(self, fc):
        """
        Compute a contiguous block range from the enabled registers in the map.

        Uses the 'address' and 'type' fields to allocate enough registers for multi-word values.
        """
        enabled = []
        for cfg in self.register_map.values():
            if cfg.get("fc") != fc:
                continue
            if not cfg.get("enabled", True):
                continue

            addr = int(cfg["address"])
            typ = cfg["type"]
            words = 1
            if typ in ("uint32", "float32"):
                words = 2

            enabled.append((addr, addr + words - 1))

        if not enabled:
            return None, None

        base = min(a for a, _ in enabled)
        end = max(b for _, b in enabled)
        length = (end - base) + 1
        return base, length

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
                self.log(f"✓ Responding to slave IDs: {self.var_slave_ids.get()}")
                self.log("✓ Input Registers (FC 04) and Holding Registers (FC 03) ready")

            loop.run_until_complete(serve())
            loop.run_forever()

        except Exception as e:
            self.server_running = False
            self.log(f"✗ ERROR: {type(e).__name__}: {e}")
            import traceback
            self.log(traceback.format_exc())

            # Make UI reflect reality again
            self._set_server_ui_state(False, "✗ Server stopped (failed to start).")

    def _pack_words_32(self, packed_4bytes):
        """
        Convert 4 bytes to two 16-bit words in the configured order mode.

        Modes:
          - ABCD: big-endian words, no swap (high word first)
          - CDAB: big-endian bytes, swapped words (low word first)  [current default]
          - BADC: swap bytes within each word (AB->BA, CD->DC)
          - DCBA: full reverse
        """
        mode = self.var_byte_order.get().strip().upper()

        # Start from the current "ABCD" byte layout.
        b0, b1, b2, b3 = packed_4bytes[0], packed_4bytes[1], packed_4bytes[2], packed_4bytes[3]

        if mode == "ABCD":
            bb = bytes([b0, b1, b2, b3])
        elif mode == "CDAB":
            bb = bytes([b2, b3, b0, b1])
        elif mode == "BADC":
            bb = bytes([b1, b0, b3, b2])
        elif mode == "DCBA":
            bb = bytes([b3, b2, b1, b0])
        else:
            # Fall back safely to the existing behavior.
            bb = bytes([b2, b3, b0, b1])

        word0 = struct.unpack('>H', bb[0:2])[0]
        word1 = struct.unpack('>H', bb[2:4])[0]
        return [word0, word1]

    def update_registers(self):
        """Update Modbus registers with current values"""
        if self.server_running and self.ir_blocks:
            try:
                # Helper functions
                def pack_uint32(value):
                    """Pack uint32 using the configured byte/word order."""
                    packed = struct.pack('>I', int(value))
                    return self._pack_words_32(packed)

                def pack_uint16(value):
                    return [int(value) & 0xFFFF]

                def pack_float32(value):
                    """Pack float32 using the configured byte/word order."""
                    packed = struct.pack('>f', float(value))
                    return self._pack_words_32(packed)

                # Keep alarm flags in sync with checkbox UI
                self.update_alarm_flags()

                # Update all configured devices
                for sid in list(self.ir_blocks.keys()):
                    ir_block = self.ir_blocks[sid]
                    hr_block = self.hr_blocks[sid]

                    # INPUT REGISTERS (FC 04)
                    if self.register_map.get("forward_total", {}).get("enabled", True):
                        ir_block.setValues(self.register_map["forward_total"]["address"], pack_uint32(self.var_forward_total.get()))

                    if self.register_map.get("unit_info", {}).get("enabled", True):
                        ir_block.setValues(self.register_map["unit_info"]["address"], pack_uint16(self.var_unit_info.get()))

                    if self.register_map.get("alarm_flags", {}).get("enabled", True):
                        ir_block.setValues(self.register_map["alarm_flags"]["address"], pack_uint16(self.var_alarm_flags.get()))

                    if self.register_map.get("flow_rate", {}).get("enabled", True):
                        ir_block.setValues(self.register_map["flow_rate"]["address"], pack_float32(self.var_flow_rate.get()))

                    if self.register_map.get("overflow_count", {}).get("enabled", True):
                        ir_block.setValues(self.register_map["overflow_count"]["address"], pack_uint16(self.var_forward_overflow.get()))

                    if self.register_map.get("conductivity", {}).get("enabled", True):
                        ir_block.setValues(self.register_map["conductivity"]["address"], pack_float32(self.var_conductivity.get()))

                    # HOLDING REGISTERS (FC 03)
                    if self.register_map.get("flow_range", {}).get("enabled", True):
                        hr_block.setValues(self.register_map["flow_range"]["address"], pack_float32(self.var_flow_range.get()))

                    if self.register_map.get("alm_high_val", {}).get("enabled", True):
                        hr_block.setValues(self.register_map["alm_high_val"]["address"], pack_float32(self.var_alm_high_val.get()))

                    if self.register_map.get("alm_low_val", {}).get("enabled", True):
                        hr_block.setValues(self.register_map["alm_low_val"]["address"], pack_float32(self.var_alm_low_val.get()))

            except Exception:
                pass  # Silently ignore update errors

        # Schedule next update (user-configurable period)
        try:
            period = int(self.var_update_period_ms.get())
            if period < 50:
                period = 50
        except Exception:
            period = 500

        self.root.after(period, self.update_registers)

    # --- Profile save/load (starting values + settings + register map) ---

    def _get_profile_dict(self):
        """Collect current settings + starting values into a JSON-serializable dict."""
        return {
            "connection": {
                "port": self.var_port.get(),
                "baud": self.var_baud.get(),
                "slave_ids": self.var_slave_ids.get(),
            },
            "server": {
                "update_period_ms": int(self.var_update_period_ms.get()),
                "byte_order": self.var_byte_order.get(),
            },
            "ui": {
                "flow_max": float(self.var_flow_max.get()),
                "flow_precision": int(self.var_flow_precision.get()),
                "cond_max": float(self.var_cond_max.get()),
                "cond_precision": int(self.var_cond_precision.get()),
            },
            "register_map": self.register_map,
            "values": {
                "flow_rate": float(self.var_flow_rate.get()),
                "alarm_flags": int(self.var_alarm_flags.get()),
                "forward_total": int(self.var_forward_total.get()),
                "forward_overflow": int(self.var_forward_overflow.get()),
                "unit_info": int(self.var_unit_info.get()),
                "conductivity": float(self.var_conductivity.get()),
                "flow_range": float(self.var_flow_range.get()),
                "alm_high_val": float(self.var_alm_high_val.get()),
                "alm_low_val": float(self.var_alm_low_val.get()),
                "alarm_empty": bool(self.var_alarm_empty.get()),
                "alarm_excitation": bool(self.var_alarm_excitation.get()),
                "alarm_high": bool(self.var_alarm_high.get()),
                "alarm_low": bool(self.var_alarm_low.get()),
            }
        }

    def _apply_profile_dict(self, data):
        """Apply a previously saved profile dict onto the GUI variables."""
        conn = data.get("connection", {})
        self.var_port.set(conn.get("port", self.var_port.get()))
        self.var_baud.set(conn.get("baud", self.var_baud.get()))
        self.var_slave_ids.set(conn.get("slave_ids", self.var_slave_ids.get()))

        server = data.get("server", {})
        if "update_period_ms" in server:
            self.var_update_period_ms.set(int(server["update_period_ms"]))
        if "byte_order" in server:
            self.var_byte_order.set(str(server["byte_order"]))

        ui = data.get("ui", {})
        if "flow_max" in ui:
            self.var_flow_max.set(float(ui["flow_max"]))
        if "flow_precision" in ui:
            self.var_flow_precision.set(int(ui["flow_precision"]))
        if "cond_max" in ui:
            self.var_cond_max.set(float(ui["cond_max"]))
        if "cond_precision" in ui:
            self.var_cond_precision.set(int(ui["cond_precision"]))

        if "register_map" in data and isinstance(data["register_map"], dict):
            self.register_map = data["register_map"]
            self._refresh_register_map_editor()

        vals = data.get("values", {})
        if "flow_rate" in vals: self.var_flow_rate.set(float(vals["flow_rate"]))
        if "alarm_flags" in vals: self.var_alarm_flags.set(int(vals["alarm_flags"]))
        if "forward_total" in vals: self.var_forward_total.set(int(vals["forward_total"]))
        if "forward_overflow" in vals: self.var_forward_overflow.set(int(vals["forward_overflow"]))
        if "unit_info" in vals: self.var_unit_info.set(int(vals["unit_info"]))
        if "conductivity" in vals: self.var_conductivity.set(float(vals["conductivity"]))
        if "flow_range" in vals: self.var_flow_range.set(float(vals["flow_range"]))
        if "alm_high_val" in vals: self.var_alm_high_val.set(float(vals["alm_high_val"]))
        if "alm_low_val" in vals: self.var_alm_low_val.set(float(vals["alm_low_val"]))

        if "alarm_empty" in vals: self.var_alarm_empty.set(bool(vals["alarm_empty"]))
        if "alarm_excitation" in vals: self.var_alarm_excitation.set(bool(vals["alarm_excitation"]))
        if "alarm_high" in vals: self.var_alarm_high.set(bool(vals["alarm_high"]))
        if "alarm_low" in vals: self.var_alarm_low.set(bool(vals["alarm_low"]))

        # Apply settings that affect widgets (sliders) right away.
        self.apply_settings()

    def save_profile(self):
        """Save current configuration and values to a JSON profile."""
        path = filedialog.asksaveasfilename(
            title="Save Profile",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if not path:
            return

        try:
            data = self._get_profile_dict()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, sort_keys=True)
            self.log(f"✓ Profile saved: {path}")
        except Exception as e:
            messagebox.showerror("Save Failed", f"Failed to save profile:\n{e}")

    def load_profile(self):
        """Load a JSON profile and apply it to the GUI."""
        path = filedialog.askopenfilename(
            title="Load Profile",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._apply_profile_dict(data)
            self.log(f"✓ Profile loaded: {path}")
        except Exception as e:
            messagebox.showerror("Load Failed", f"Failed to load profile:\n{e}")


if __name__ == "__main__":
    root = tk.Tk()
    app = CompleteFlowMeterGUI(root)
    root.mainloop()

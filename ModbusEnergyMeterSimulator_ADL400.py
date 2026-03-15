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
            


class ModbusSlaveContext:
    def __init__(self, di=None, co=None, hr=None, ir=None, zero_mode=False):
        self.store = {}
        if di:
            self.store['d'] = di
        if co:
            self.store['c'] = co
        if hr:
            self.store['h'] = hr
        if ir:
            self.store['i'] = ir
        self.zero_mode = zero_mode

    def __str__(self):
        return "ModbusSlaveContext"

    def reset(self):
        for block in self.store.values():
            block.reset()

    def validate(self, fx, address, count=1):
        if fx in [1, 5, 15]:
            block = self.store.get('c')
        elif fx in [2]:
            block = self.store.get('d')
        elif fx in [3, 6, 16]:
            block = self.store.get('h')
        elif fx in [4]:
            block = self.store.get('i')
        else:
            return False
        
        if not block:
            return False
        return block.validate(address, count)

    def getValues(self, fx, address, count=1):
        if fx in [1, 5, 15]:
            block = self.store.get('c')
        elif fx in [2]:
            block = self.store.get('d')
        elif fx in [3, 6, 16]:
            block = self.store.get('h')
        elif fx in [4]:
            block = self.store.get('i')
        else:
            return []
        
        vals = block.getValues(address, count)
        return vals

    def setValues(self, fx, address, values):
        if fx in [1, 5, 15]:
            block = self.store.get('c')
        elif fx in [2]:
            block = self.store.get('d')
        elif fx in [3, 6, 16]:
            block = self.store.get('h')
        elif fx in [4]:
            block = self.store.get('i')
        else:
            return
        
        block.setValues(address, values)
        
    async def async_getValues(self, fx, address, count=1):
        return self.getValues(fx, address, count)
        
    async def async_setValues(self, fx, address, values):
        return self.setValues(fx, address, values)


def start_modbus_server(port='COM3', baudrate=9600):
    """
    Launch a Modbus RTU server using pymodbus v3.x.
    Uses ModbusSerialServer for serial communication.
    """
    if ModbusSerialServer is None or ServerStop is None:
        raise RuntimeError("Required pymodbus.server components not available")
    
    # Create a simple datastore
    if ModbusSequentialDataBlock is None:
        raise RuntimeError("ModbusSequentialDataBlock not available")
    
    store = ModbusSlaveContext(
        di=ModbusSequentialDataBlock(0, 100),
        co=ModbusSequentialDataBlock(0, 100),
        hr=ModbusSequentialDataBlock(0, 100),
        ir=ModbusSequentialDataBlock(0, 100)
    )
    
    context = ModbusServerContext(slaves=store, single=True)
    
    # Start the server
    server = ModbusSerialServer(
        context=context,
        framer=None,
        port=port,
        baudrate=baudrate,
        timeout=1
    )
    
    # Run in background thread or async — for now, return server object
    return server

# Optional: if run as script
if __name__ == "__main__":
    try:
        server = start_modbus_server()
        print(f"Modbus server started on {server.port}")
    except Exception as e:
        print(f"Failed to start server: {e}")
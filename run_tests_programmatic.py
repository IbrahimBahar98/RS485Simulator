import sys
import os
import subprocess

# Add workspace directory to Python path
workspace_dir = os.path.dirname(os.path.abspath(__file__))
if workspace_dir not in sys.path:
    sys.path.insert(0, workspace_dir)

# Also add rs485sim directory explicitly
rs485sim_dir = os.path.join(workspace_dir, 'rs485sim')
if rs485sim_dir not in sys.path:
    sys.path.insert(0, rs485sim_dir)

print(f"Added to sys.path: {workspace_dir}")
print(f"Added to sys.path: {rs485sim_dir}")

# Verify the files exist
server_file = os.path.join(rs485sim_dir, 'core', 'server.py')
print(f"rs485sim/core/server.py exists: {os.path.exists(server_file)}")

# Try to import the module directly to verify
try:
    from rs485sim.core.server import ModbusSerialServer
    print("SUCCESS: Successfully imported ModbusSerialServer")
except ImportError as e:
    print(f"ERROR: Failed to import ModbusSerialServer: {e}")
    sys.exit(1)

# Now run pytest
try:
    import pytest
    print(f"SUCCESS: Successfully imported pytest version {pytest.__version__}")
    
    # Run tests
    exit_code = pytest.main(["-v", "--tb=short", "tests/"])
    
    if exit_code == 0:
        print("\nSUCCESS: All tests passed!")
    else:
        print(f"\nERROR: Tests failed with exit code {exit_code}")
    
    sys.exit(exit_code)
except ImportError as e:
    print(f"ERROR: Failed to import pytest: {e}")
    print("Attempting to run pytest via subprocess...")
    try:
        # Use the full path to pytest.exe
        pytest_path = r'C:\Users\IbrahimBashar\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0\LocalCache\local-packages\Python313\Scripts\pytest.exe'
        result = subprocess.run([pytest_path, "-v", "--tb=short", "tests/"], capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        sys.exit(result.returncode)
    except Exception as sub_error:
        print(f"ERROR: Failed to run pytest via subprocess: {sub_error}")
        sys.exit(1)

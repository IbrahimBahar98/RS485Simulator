import sys
import os

# Add the current workspace directory to Python path
workspace_dir = os.path.dirname(os.path.abspath(__file__))
if workspace_dir not in sys.path:
    sys.path.insert(0, workspace_dir)

# Also add the rs485sim directory specifically
rs485sim_dir = os.path.join(workspace_dir, 'rs485sim')
if rs485sim_dir not in sys.path:
    sys.path.insert(0, rs485sim_dir)

# Try to import pytest
try:
    import pytest
    print(f"Successfully imported pytest version {pytest.__version__}")
except ImportError as e:
    print(f"Failed to import pytest: {e}")
    print("Attempting to install pytest...")
    import subprocess
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pytest"])
        import pytest
        print(f"Successfully installed and imported pytest version {pytest.__version__}")
    except Exception as install_error:
        print(f"Failed to install pytest: {install_error}")
        sys.exit(1)

# Run tests
if __name__ == "__main__":
    # Change to workspace directory
    os.chdir(workspace_dir)
    
    # Run pytest with verbose output
    exit_code = pytest.main(["-v", "--tb=short", "tests/"])
    
    if exit_code == 0:
        print("\n✅ All tests passed!")
    else:
        print(f"\n❌ Tests failed with exit code {exit_code}")
    
    sys.exit(exit_code)

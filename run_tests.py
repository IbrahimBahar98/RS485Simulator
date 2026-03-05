import sys
import os
import subprocess

# Use the system Python installation path from context
python_path = r'C:\Users\IbrahimBashar\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0\LocalCache\local-packages\Python313\python.exe'

# Try to import pytest
try:
    import pytest
    print(f"Successfully imported pytest version {pytest.__version__}")
except ImportError as e:
    print(f"Failed to import pytest: {e}")
    print("Attempting to install pytest using system Python...")
    try:
        # Use the system Python to install pytest
        subprocess.check_call([python_path, "-m", "pip", "install", "pytest"])
        # Now try to import again
        import pytest
        print(f"Successfully installed and imported pytest version {pytest.__version__}")
    except Exception as install_error:
        print(f"Failed to install pytest: {install_error}")
        print("Trying alternative installation method with --user flag...")
        try:
            subprocess.check_call([python_path, "-m", "pip", "install", "--user", "pytest"])
            import pytest
            print(f"Successfully installed and imported pytest version {pytest.__version__}")
        except Exception as user_install_error:
            print(f"Failed to install pytest with --user flag: {user_install_error}")
            sys.exit(1)

# Run tests
if __name__ == "__main__":
    # Change to workspace directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # Run pytest with verbose output
    exit_code = pytest.main(["-v", "--tb=short", "tests/"])
    
    if exit_code == 0:
        print("\n✅ All tests passed!")
    else:
        print(f"\n❌ Tests failed with exit code {exit_code}")
    
    sys.exit(exit_code)

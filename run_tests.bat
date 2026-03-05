@echo off
set PYTHON_PATH=C:\Users\IbrahimBashar\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0\LocalCache\local-packages\Python313\Scripts\pytest.exe

echo Running tests with pytest...
if exist "%PYTHON_PATH%" (
    echo Found pytest at: %PYTHON_PATH%
    "%PYTHON_PATH%" -v --tb=short tests/
) else (
    echo ERROR: pytest.exe not found at %PYTHON_PATH%
    echo Please check the Python installation path and try again.
    exit /b 1
)

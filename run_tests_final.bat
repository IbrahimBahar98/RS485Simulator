@echo off
set PYTHONPATH=C:\Users\IbrahimBashar\Downloads\iterative_quality_assurance_pipeline_with_test_fix_loops_v1_crewai-project\workspace

echo Setting PYTHONPATH to: %PYTHONPATH%

echo Running tests with pytest...
"C:\Users\IbrahimBashar\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0\LocalCache\local-packages\Python313\Scripts\pytest.exe" -v --tb=short tests/

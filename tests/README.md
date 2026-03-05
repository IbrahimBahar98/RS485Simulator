# RS485Simulator Test Suite Documentation

## Table of Contents
- [Test Suite Overview](#test-suite-overview)
- [Prerequisites](#prerequisites)
- [Running Tests](#running-tests)
- [Test Categories](#test-categories)
- [Environment Configuration](#environment-configuration)
- [Coverage Reporting](#coverage-reporting)
- [Troubleshooting](#troubleshooting)

## Test Suite Overview

The RS485Simulator test suite follows a comprehensive, layered testing strategy with three main categories:

- **Unit Tests**: Isolated validation of core utilities (`float_to_registers`, `uint32_to_registers`, `toggle_alarm_bit`)
- **Integration Tests**: Component-level testing of Modbus context and server interactions
- **End-to-End Tests**: GUI automation and JS simulator API validation

## Prerequisites

Before running tests, ensure you have:

- Python 3.7+
- pip and virtualenv
- pytest, pytest-cov, and related testing dependencies
- Node.js (for JS simulator testing)
- Docker (for cross-platform CI testing)

Install dependencies:
```bash
pip install -e ".[test]"
```

## Running Tests

### Run All Tests
```bash
pytest --cov=rs485sim --cov-report=html --cov-report=term-missing
```

### Run Specific Test Categories

**Unit Tests Only:**
```bash
pytest tests/python/ -m "unit" -v
```

**Integration Tests Only:**
```bash
pytest tests/python/ -m "integration" -v
```

**End-to-End Tests Only:**
```bash
pytest tests/python/ -m "e2e" -v --tb=long
```

### Run Tests with Specific Options

**Verbose output with short traceback:**
```bash
pytest -v --tb=short
```

**Run tests in specific files:**
```bash
pytest tests/python/test_registers.py::TestRegisterUtilities::test_float_to_registers_one
```

## Test Categories

### Unit Tests (P0 Priority)
- `float_to_registers()` with various values (0.0, 1.0, -1.0, 424.0, 100.0, 10.0)
- `uint32_to_registers()` with various values (0, 65535, 1000000)
- `toggle_alarm_bit()` with various bit positions and states

### Integration Tests (P0 Priority)
- Dual-slave context initialization and isolation
- Register write propagation and persistence
- Alarm bit toggle functionality
- Context switching between slaves 110 and 111

### End-to-End Tests (P0 Priority)
- GUI launch and port detection
- Register value editing and persistence across restarts
- Dark mode toggle functionality
- JS simulator API register read/write operations
- Cross-platform COM port enumeration

## Environment Configuration

Set environment variables for test-specific behavior:

```bash
export RS485SIM_TEST_MODE=true
export RS485SIM_CONFIG_PATH=$(pwd)/tests/config
export RS485SIM_MOCK_SERIAL=true
```

## Coverage Reporting

The test suite enforces strict coverage requirements:

- **100%** unit test coverage on core utilities (`rs485sim/core/registers.py`)
- **95%** integration test coverage on Modbus context components
- HTML coverage report generated in `htmlcov/` directory
- Terminal coverage report shows missing lines

Generate coverage report:
```bash
pytest --cov=rs485sim --cov-report=html --cov-report=term-missing
```

## Troubleshooting

### Common Issues

**Serial Port Not Found:**
- Set `RS485SIM_MOCK_SERIAL=true` to use mocked serial port
- Verify user is in `dialout` group on Linux
- Check Windows COM port permissions

**GUI Tests Failing:**
- Run in headless mode: `pytest --headless`
- Ensure DISPLAY environment variable is set on Linux

**Cross-Platform Tests:**
- Use Docker for consistent environment: `docker run --rm -v $(pwd):/workspace -w /workspace python:3.9 pytest tests/python/ -m "unit"`

### Test Failure Response Protocol
1. **Immediate Action**: Fail fast - stop CI pipeline on P0 test failures
2. **Triage**: Classify failure as environmental, configuration, or code defect
3. **Isolation**: Run failing test in isolation with verbose output
4. **Root Cause Analysis**: Use pytest debugging tools and logging
5. **Resolution**: Fix code, update tests, or document known limitation
6. **Verification**: Run full test suite to ensure no regressions

---
*This test suite implements the comprehensive testing strategy documented in the RS485Simulator Comprehensive Testing Strategy Document.*

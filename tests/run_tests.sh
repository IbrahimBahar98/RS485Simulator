#!/bin/bash
# Test execution script for RS485Simulator

set -e

echo "Running RS485Simulator test suite..."

# Run all unit tests
echo "\n=== Running Unit Tests ==="
pytest tests/python/ -m "unit" -v

# Run integration tests
echo "\n=== Running Integration Tests ==="
pytest tests/python/ -m "integration" -v

# Run end-to-end tests
echo "\n=== Running End-to-End Tests ==="
pytest tests/python/ -m "e2e" -v --tb=long

# Run all tests with coverage reporting
echo "\n=== Running All Tests with Coverage ==="
pytest --cov=rs485sim --cov-report=html --cov-report=term-missing

echo "\nTest suite completed successfully!"

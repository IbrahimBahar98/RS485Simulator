import pytest


def test_smoke():
    """
    Smoke test to verify the test infrastructure is working.
    """
    assert True


def test_imports():
    """
    Test that core modules can be imported without errors.
    """
    try:
        import tkinter as tk
        import pymodbus
        import serial
        assert True
    except ImportError as e:
        pytest.fail(f"Failed to import required module: {e}")

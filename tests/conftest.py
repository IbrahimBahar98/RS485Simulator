# pytest configuration fixtures
import pytest

@pytest.fixture
def test_data():
    return {
        "register_map": [
            {"addr": 772, "name": "Forward Total (Word 0 - MSW)", "val": 0, "type": "IR"},
            {"addr": 773, "name": "Forward Total (Word 1 - LSW)", "val": 0, "type": "IR"},
            {"addr": 777, "name": "Alarm Flags", "val": 0, "type": "IR"},
            {"addr": 778, "name": "Flow Rate (Word 0 - MSW)", "val": 0, "type": "IR"},
            {"addr": 779, "name": "Flow Rate (Word 1 - LSW)", "val": 0, "type": "IR"},
        ]
    }

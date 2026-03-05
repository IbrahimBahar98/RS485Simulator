import json
from pathlib import Path


def create_test_register_map():
    """Generate comprehensive test register map based on fr500a_extracted.txt"""
    register_map = [
        {"addr": 772, "name": "Forward Total (Word 0 - MSW)", "val": 0, "type": "IR", "description": "Total forward flow volume"},
        {"addr": 773, "name": "Forward Total (Word 1 - LSW)", "val": 0, "type": "IR", "description": "Total forward flow volume"},
        {"addr": 777, "name": "Alarm Flags", "val": 0, "type": "IR", "description": "Bitmapped alarm status"},
        {"addr": 778, "name": "Flow Rate (Word 0 - MSW)", "val": 0, "type": "IR", "description": "Current flow rate"},
        {"addr": 779, "name": "Flow Rate (Word 1 - LSW)", "val": 0, "type": "IR", "description": "Current flow rate"},
        {"addr": 40001, "name": "Flow Range (Word 0 - MSW)", "val": 0x43D4, "type": "HR", "description": "Maximum flow range setting"},
        {"addr": 40002, "name": "Flow Range (Word 1 - LSW)", "val": 0x0000, "type": "HR", "description": "Maximum flow range setting"},
        {"addr": 40003, "name": "Alm High Val (Word 0 - MSW)", "val": 0x42C8, "type": "HR", "description": "High flow alarm threshold"},
        {"addr": 40004, "name": "Alm High Val (Word 1 - LSW)", "val": 0x0000, "type": "HR", "description": "High flow alarm threshold"},
        {"addr": 40005, "name": "Alm Low Val (Word 0 - MSW)", "val": 0x4120, "type": "HR", "description": "Low flow alarm threshold"},
        {"addr": 40006, "name": "Alm Low Val (Word 1 - LSW)", "val": 0x0000, "type": "HR", "description": "Low flow alarm threshold"},
    ]
    
    # Save to test data file
    test_data_dir = Path("tests/data")
    test_data_dir.mkdir(exist_ok=True)
    
    with open(test_data_dir / "register_map.json", "w") as f:
        json.dump(register_map, f, indent=2)
    
    return register_map


if __name__ == "__main__":
    create_test_register_map()
    print("Test register map created successfully")

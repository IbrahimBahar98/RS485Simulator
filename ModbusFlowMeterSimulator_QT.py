"""
Complete Flow Meter Modbus RTU Simulator
Supports both Slave ID 110 and 111 with all registers
"""

import sys
import threading
import asyncio
import struct
import json
import logging
import serial

from PySide6.QtCore import Qt, QObject, Signal, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QDoubleSpinBox,
    QSpinBox,
    QCheckBox,
    QPlainTextEdit,
    QMessageBox,
    QFileDialog,
    QComboBox,
    QGridLayout,
)

from pymodbus.server import StartAsyncSerialServer
from pymodbus.datastore import context, sparse


class LogBus(QObject):
    """Signal hub for thread-safe logging into the UI."""
    message = Signal(str)
    server_failed = Signal(str)
    server_started = Signal()


class FlowMeterSimulatorQt(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Complete Flow Meter Simulator")
        self.resize(900, 760)

        # Server state
        self.server_running = False
        self.server_thread = None
        self.server_context = None

        # Runtime-created device blocks keyed by slave id
        self.ir_blocks = {}
        self.hr_blocks = {}

        # Thread-safe UI logging
        self.log_bus = LogBus()
        self.log_bus.message.connect(self._append_log)
        self.log_bus.server_failed.connect(self._on_server_failed)
        self.log_bus.server_started.connect(self._on_server_started)

        # Default register map (same as the existing hardcoded behavior)
        self.register_map_default = {
            "forward_total": {"fc": "ir", "address": 772, "type": "uint32", "enabled": True},
            "unit_info": {"fc": "ir", "address": 774, "type": "uint16", "enabled": True},
            "alarm_flags": {"fc": "ir", "address": 777, "type": "uint16", "enabled": True},
            "flow_rate": {"fc": "ir", "address": 778, "type": "float32", "enabled": True},
            "overflow_count": {"fc": "ir", "address": 786, "type": "uint16", "enabled": True},
            "conductivity": {"fc": "ir", "address": 812, "type": "float32", "enabled": True},
            "flow_range": {"fc": "hr", "address": 261, "type": "float32", "enabled": True},
            "alm_high_val": {"fc": "hr", "address": 281, "type": "float32", "enabled": True},
            "alm_low_val": {"fc": "hr", "address": 284, "type": "float32", "enabled": True},
        }
        self.register_map = dict(self.register_map_default)

        # Setup logging (pymodbus debug helps confirm requests are arriving)
        logging.basicConfig(level=logging.INFO)
        logging.getLogger("pymodbus").setLevel(logging.DEBUG)

        self._build_ui()

        # Register update loop (user configurable interval)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_registers)
        self._apply_update_period()
        self.timer.start()

    # -------------------------------------------------------------------------
    # UI construction
    # -------------------------------------------------------------------------

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        # Connection group
        conn_box = QGroupBox("Connection")
        conn_layout = QGridLayout(conn_box)

        self.edt_port = QLineEdit("COM18")
        self.edt_baud = QLineEdit("9600")
        self.edt_slave_ids = QLineEdit("110,111")

        self.btn_start = QPushButton("Start Server")
        self.btn_start.clicked.connect(self.start_server)

        conn_layout.addWidget(QLabel("Port:"), 0, 0)
        conn_layout.addWidget(self.edt_port, 0, 1)

        conn_layout.addWidget(QLabel("Baud:"), 0, 2)
        conn_layout.addWidget(self.edt_baud, 0, 3)

        conn_layout.addWidget(QLabel("Slave IDs:"), 0, 4)
        conn_layout.addWidget(self.edt_slave_ids, 0, 5)

        conn_layout.addWidget(self.btn_start, 0, 6)

        layout.addWidget(conn_box)

        # Tabs
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)

        self._build_tab_process()
        self._build_tab_config()
        self._build_tab_advanced()
        self._build_tab_log()

    def _build_tab_process(self):
        tab = QWidget()
        self.tabs.addTab(tab, "Process Variables (Input Regs)")
        v = QVBoxLayout(tab)

        # Sliders config (user-editable in Advanced tab)
        self.spn_flow_max = QDoubleSpinBox()
        self.spn_flow_max.setRange(0.1, 10_000_000)
        self.spn_flow_max.setValue(500.0)

        self.spn_flow_decimals = QSpinBox()
        self.spn_flow_decimals.setRange(0, 4)
        self.spn_flow_decimals.setValue(1)

        self.spn_cond_max = QDoubleSpinBox()
        self.spn_cond_max.setRange(0.1, 10_000_000)
        self.spn_cond_max.setValue(1000.0)

        self.spn_cond_decimals = QSpinBox()
        self.spn_cond_decimals.setRange(0, 4)
        self.spn_cond_decimals.setValue(1)

        # Flow Rate
        flow_box = QGroupBox("Flow Rate (Reg 778-779)")
        flow_layout = QHBoxLayout(flow_box)

        self.flow_slider = self._create_float_slider(0.0, self.spn_flow_max.value(), self.spn_flow_decimals.value(), 125.5)
        self.spn_flow_rate = self.flow_slider["spin"]
        self.sld_flow_rate = self.flow_slider["slider"]

        flow_layout.addWidget(self.sld_flow_rate, 1)
        flow_layout.addWidget(self.spn_flow_rate)
        flow_layout.addWidget(QLabel("m³/h"))
        v.addWidget(flow_box)

        # Conductivity
        cond_box = QGroupBox("Conductivity (Reg 812-813)")
        cond_layout = QHBoxLayout(cond_box)

        self.cond_slider = self._create_float_slider(0.0, self.spn_cond_max.value(), self.spn_cond_decimals.value(), 450.2)
        self.spn_conductivity = self.cond_slider["spin"]
        self.sld_conductivity = self.cond_slider["slider"]

        cond_layout.addWidget(self.sld_conductivity, 1)
        cond_layout.addWidget(self.spn_conductivity)
        cond_layout.addWidget(QLabel("µS/cm"))
        v.addWidget(cond_box)

        # Totals / unit / overflow
        totals_box = QGroupBox("Totals / Unit / Overflow")
        totals_layout = QFormLayout(totals_box)

        self.spn_forward_total = QSpinBox()
        self.spn_forward_total.setRange(0, 2_147_483_647)
        self.spn_forward_total.setValue(1_000_000)

        btn_inc_total = QPushButton("+1000")
        btn_inc_total.clicked.connect(lambda: self.spn_forward_total.setValue(self.spn_forward_total.value() + 1000))

        row_total = QWidget()
        row_total_layout = QHBoxLayout(row_total)
        row_total_layout.setContentsMargins(0, 0, 0, 0)
        row_total_layout.addWidget(self.spn_forward_total)
        row_total_layout.addWidget(btn_inc_total)

        totals_layout.addRow("Forward Total (Reg 772-773):", row_total)

        self.spn_overflow = QSpinBox()
        self.spn_overflow.setRange(0, 65535)
        self.spn_overflow.setValue(0)

        btn_reset_overflow = QPushButton("Reset")
        btn_reset_overflow.clicked.connect(lambda: self.spn_overflow.setValue(0))

        row_overflow = QWidget()
        row_overflow_layout = QHBoxLayout(row_overflow)
        row_overflow_layout.setContentsMargins(0, 0, 0, 0)
        row_overflow_layout.addWidget(self.spn_overflow)
        row_overflow_layout.addWidget(btn_reset_overflow)

        totals_layout.addRow("Overflow Count (Reg 786):", row_overflow)

        self.spn_unit_info = QSpinBox()
        self.spn_unit_info.setRange(0, 10)
        self.spn_unit_info.setValue(3)
        totals_layout.addRow("Unit Code (Reg 774):", self.spn_unit_info)

        v.addWidget(totals_box)

        # Alarm flags
        alarm_box = QGroupBox("Alarm Flags (Reg 777)")
        alarm_layout = QVBoxLayout(alarm_box)

        self.chk_alarm_empty = QCheckBox("Empty Pipe (Bit 0)")
        self.chk_alarm_excitation = QCheckBox("Excitation Error (Bit 1)")
        self.chk_alarm_high = QCheckBox("High Flow (Bit 2)")
        self.chk_alarm_low = QCheckBox("Low Flow (Bit 3)")

        for chk in (self.chk_alarm_empty, self.chk_alarm_excitation, self.chk_alarm_high, self.chk_alarm_low):
            chk.stateChanged.connect(self._update_alarm_flags)

        alarm_layout.addWidget(self.chk_alarm_empty)
        alarm_layout.addWidget(self.chk_alarm_excitation)
        alarm_layout.addWidget(self.chk_alarm_high)
        alarm_layout.addWidget(self.chk_alarm_low)

        self.lbl_alarm_flags = QLabel("Alarm Flags Value: 0")
        alarm_layout.addWidget(self.lbl_alarm_flags)

        v.addWidget(alarm_box)
        v.addStretch(1)

        # Initialize alarm flags label
        self._update_alarm_flags()

    def _build_tab_config(self):
        tab = QWidget()
        self.tabs.addTab(tab, "Configuration (Holding Regs)")
        v = QVBoxLayout(tab)

        box = QGroupBox("Configuration Parameters")
        form = QFormLayout(box)

        self.spn_flow_range = QDoubleSpinBox()
        self.spn_flow_range.setDecimals(2)
        self.spn_flow_range.setRange(0.0, 10_000_000.0)
        self.spn_flow_range.setValue(500.0)

        self.spn_alm_high = QDoubleSpinBox()
        self.spn_alm_high.setDecimals(2)
        self.spn_alm_high.setRange(0.0, 10_000_000.0)
        self.spn_alm_high.setValue(400.0)

        self.spn_alm_low = QDoubleSpinBox()
        self.spn_alm_low.setDecimals(2)
        self.spn_alm_low.setRange(0.0, 10_000_000.0)
        self.spn_alm_low.setValue(10.0)

        form.addRow("Flow Range (Reg 261-262):", self.spn_flow_range)
        form.addRow("Alarm High Value (Reg 281-282):", self.spn_alm_high)
        form.addRow("Alarm Low Value (Reg 284-285):", self.spn_alm_low)

        v.addWidget(box)
        note = QLabel("Note: These are configuration parameters that the EdgeBox reads on startup.")
        note.setStyleSheet("font-style: italic;")
        v.addWidget(note)
        v.addStretch(1)

    def _build_tab_advanced(self):
        tab = QWidget()
        self.tabs.addTab(tab, "Advanced")
        v = QVBoxLayout(tab)

        # Server settings
        server_box = QGroupBox("Server Settings")
        grid = QGridLayout(server_box)

        self.spn_update_period = QSpinBox()
        self.spn_update_period.setRange(50, 60_000)
        self.spn_update_period.setValue(500)

        self.cmb_byte_order = QComboBox()
        self.cmb_byte_order.addItems(["CDAB", "ABCD", "BADC", "DCBA"])
        self.cmb_byte_order.setCurrentText("CDAB")

        grid.addWidget(QLabel("Update period (ms):"), 0, 0)
        grid.addWidget(self.spn_update_period, 0, 1)

        grid.addWidget(QLabel("Byte/Word order:"), 0, 2)
        grid.addWidget(self.cmb_byte_order, 0, 3)

        # Slider scaling/precision
        grid.addWidget(QLabel("Flow max:"), 1, 0)
        grid.addWidget(self.spn_flow_max, 1, 1)

        grid.addWidget(QLabel("Flow decimals:"), 1, 2)
        grid.addWidget(self.spn_flow_decimals, 1, 3)

        grid.addWidget(QLabel("Conductivity max:"), 2, 0)
        grid.addWidget(self.spn_cond_max, 2, 1)

        grid.addWidget(QLabel("Cond decimals:"), 2, 2)
        grid.addWidget(self.spn_cond_decimals, 2, 3)

        btn_apply = QPushButton("Apply Settings")
        btn_apply.clicked.connect(self.apply_settings)

        btn_save = QPushButton("Save Profile")
        btn_save.clicked.connect(self.save_profile)

        btn_load = QPushButton("Load Profile")
        btn_load.clicked.connect(self.load_profile)

        grid.addWidget(btn_apply, 3, 0)
        grid.addWidget(btn_save, 3, 1)
        grid.addWidget(btn_load, 3, 2)

        v.addWidget(server_box)

        # Register map editor
        map_box = QGroupBox("Register Map (JSON)")
        map_layout = QVBoxLayout(map_box)

        self.txt_register_map = QPlainTextEdit()
        self._refresh_register_map_editor()

        row = QHBoxLayout()
        btn_apply_map = QPushButton("Apply Register Map")
        btn_apply_map.clicked.connect(self.apply_register_map_from_editor)

        btn_reset_map = QPushButton("Reset to Defaults")
        btn_reset_map.clicked.connect(self.reset_register_map_defaults)

        row.addWidget(btn_apply_map)
        row.addWidget(btn_reset_map)
        row.addStretch(1)

        map_layout.addWidget(self.txt_register_map, 1)
        map_layout.addLayout(row)

        v.addWidget(map_box, 1)

    def _build_tab_log(self):
        tab = QWidget()
        self.tabs.addTab(tab, "Log")
        v = QVBoxLayout(tab)

        self.txt_log = QPlainTextEdit()
        self.txt_log.setReadOnly(True)

        v.addWidget(self.txt_log, 1)

    # -------------------------------------------------------------------------
    # UI helpers
    # -------------------------------------------------------------------------

    def _create_float_slider(self, min_val: float, max_val: float, decimals: int, initial: float):
        """
        QSlider is integer-only, so the value is stored as scaled int:
          real_value = slider_value / scale
        """
        scale = 10 ** max(0, int(decimals))

        spin = QDoubleSpinBox()
        spin.setDecimals(int(decimals))
        spin.setRange(min_val, max_val)
        spin.setValue(float(initial))

        slider = QSpinBox()
        slider.setRange(int(min_val * scale), int(max_val * scale))
        slider.setValue(int(float(initial) * scale))
        slider.setKeyboardTracking(False)

        def on_slider_changed(v):
            spin.blockSignals(True)
            spin.setValue(v / scale)
            spin.blockSignals(False)

        def on_spin_changed(v):
            slider.blockSignals(True)
            slider.setValue(int(float(v) * scale))
            slider.blockSignals(False)

        slider.valueChanged.connect(on_slider_changed)
        spin.valueChanged.connect(on_spin_changed)

        return {"spin": spin, "slider": slider, "scale": scale}

    def _append_log(self, msg: str):
        self.txt_log.appendPlainText(msg)
        sb = self.txt_log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _set_server_ui_state(self, running: bool, message: str | None = None):
        # Direct UI mutation is safe here (called from GUI thread)
        if running:
            self.btn_start.setEnabled(False)
            self.btn_start.setText("Running...")
        else:
            self.btn_start.setEnabled(True)
            self.btn_start.setText("Start Server")

        if message:
            self._append_log(message)

    # -------------------------------------------------------------------------
    # Logic: alarms / settings
    # -------------------------------------------------------------------------

    def _update_alarm_flags(self):
        """Compute alarm flags word based on checkboxes."""
        flags = 0
        if self.chk_alarm_empty.isChecked():
            flags |= 0x01
        if self.chk_alarm_excitation.isChecked():
            flags |= 0x02
        if self.chk_alarm_high.isChecked():
            flags |= 0x04
        if self.chk_alarm_low.isChecked():
            flags |= 0x08
        self.lbl_alarm_flags.setText(f"Alarm Flags Value: {flags}")

    def _get_alarm_flags_value(self) -> int:
        text = self.lbl_alarm_flags.text()
        try:
            return int(text.split(":")[-1].strip())
        except Exception:
            return 0

    def _apply_update_period(self):
        """Keep timer interval in sync with UI."""
        period = int(self.spn_update_period.value())
        self.timer.setInterval(max(50, period))

    def apply_settings(self):
        """Apply slider scaling/limits + update loop period."""
        # Apply update period
        self._apply_update_period()
        self.log_bus.message.emit(f"✓ Applied update period: {self.timer.interval()} ms")

        # Apply slider limits/precision: rebuild float sliders cleanly
        flow_max = float(self.spn_flow_max.value())
        flow_dec = int(self.spn_flow_decimals.value())
        cond_max = float(self.spn_cond_max.value())
        cond_dec = int(self.spn_cond_decimals.value())

        # Preserve current values
        cur_flow = float(self.spn_flow_rate.value())
        cur_cond = float(self.spn_conductivity.value())

        # Clamp values to new ranges
        cur_flow = min(max(cur_flow, 0.0), flow_max)
        cur_cond = min(max(cur_cond, 0.0), cond_max)

        # Replace controls in-place (simple and reliable)
        self._rebuild_process_sliders(flow_max, flow_dec, cur_flow, cond_max, cond_dec, cur_cond)
        self.log_bus.message.emit(f"✓ Applied slider limits: flow_max={flow_max}, cond_max={cond_max}")

    def _rebuild_process_sliders(self, flow_max, flow_dec, flow_val, cond_max, cond_dec, cond_val):
        # Locate existing tab widgets and rebuild only the slider/spin widgets.
        # This keeps the UI predictable without deep layout hacking.
        self.spn_flow_rate.setParent(None)
        self.sld_flow_rate.setParent(None)
        self.spn_conductivity.setParent(None)
        self.sld_conductivity.setParent(None)

        self.flow_slider = self._create_float_slider(0.0, float(flow_max), int(flow_dec), float(flow_val))
        self.spn_flow_rate = self.flow_slider["spin"]
        self.sld_flow_rate = self.flow_slider["slider"]

        self.cond_slider = self._create_float_slider(0.0, float(cond_max), int(cond_dec), float(cond_val))
        self.spn_conductivity = self.cond_slider["spin"]
        self.sld_conductivity = self.cond_slider["slider"]

        # Re-insert into layouts: easiest way is to find the group boxes by title.
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i) == "Process Variables (Input Regs)":
                process_tab = self.tabs.widget(i)
                break
        else:
            return

        # Walk child group boxes
        group_boxes = process_tab.findChildren(QGroupBox)
        flow_box = next((b for b in group_boxes if b.title().startswith("Flow Rate")), None)
        cond_box = next((b for b in group_boxes if b.title().startswith("Conductivity")), None)

        if flow_box:
            layout = flow_box.layout()
            # Insert: slider (stretch), spin, unit label already exists at end
            layout.insertWidget(0, self.sld_flow_rate, 1)
            layout.insertWidget(1, self.spn_flow_rate)

        if cond_box:
            layout = cond_box.layout()
            layout.insertWidget(0, self.sld_conductivity, 1)
            layout.insertWidget(1, self.spn_conductivity)

    # -------------------------------------------------------------------------
    # Register map editor
    # -------------------------------------------------------------------------

    def _refresh_register_map_editor(self):
        self.txt_register_map.setPlainText(json.dumps(self.register_map, indent=2, sort_keys=True))

    def reset_register_map_defaults(self):
        """Restore the default register map (same as original hardcoded behavior)."""
        self.register_map = dict(self.register_map_default)
        self._refresh_register_map_editor()
        self.log_bus.message.emit("✓ Register map reset to defaults")

    def apply_register_map_from_editor(self):
        """Parse JSON from editor and replace the active register map."""
        raw = self.txt_register_map.toPlainText().strip()
        try:
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                raise ValueError("Register map JSON must be an object/dict")

            # Lightweight sanity checks so bad edits don't crash the update loop.
            for key, cfg in parsed.items():
                if not isinstance(cfg, dict):
                    raise ValueError(f"'{key}' must be an object")
                if cfg.get("fc") not in ("ir", "hr"):
                    raise ValueError(f"'{key}.fc' must be 'ir' or 'hr'")
                if not isinstance(cfg.get("address"), int):
                    raise ValueError(f"'{key}.address' must be an integer")
                if cfg.get("type") not in ("uint16", "uint32", "float32"):
                    raise ValueError(f"'{key}.type' must be uint16/uint32/float32")
                if not isinstance(cfg.get("enabled", True), bool):
                    raise ValueError(f"'{key}.enabled' must be boolean")

            self.register_map = parsed
            self.log_bus.message.emit("✓ Register map applied")
        except Exception as e:
            QMessageBox.critical(self, "Invalid Register Map", f"Failed to apply register map:\n{e}")

    # -------------------------------------------------------------------------
    # Profile save/load
    # -------------------------------------------------------------------------

    def _get_profile_dict(self):
        """Collect current settings + values into a JSON-serializable dict."""
        return {
            "connection": {
                "port": self.edt_port.text().strip(),
                "baud": self.edt_baud.text().strip(),
                "slave_ids": self.edt_slave_ids.text().strip(),
            },
            "server": {
                "update_period_ms": int(self.spn_update_period.value()),
                "byte_order": self.cmb_byte_order.currentText(),
            },
            "ui": {
                "flow_max": float(self.spn_flow_max.value()),
                "flow_precision": int(self.spn_flow_decimals.value()),
                "cond_max": float(self.spn_cond_max.value()),
                "cond_precision": int(self.spn_cond_decimals.value()),
            },
            "register_map": self.register_map,
            "values": {
                "flow_rate": float(self.spn_flow_rate.value()),
                "forward_total": int(self.spn_forward_total.value()),
                "forward_overflow": int(self.spn_overflow.value()),
                "unit_info": int(self.spn_unit_info.value()),
                "conductivity": float(self.spn_conductivity.value()),
                "flow_range": float(self.spn_flow_range.value()),
                "alm_high_val": float(self.spn_alm_high.value()),
                "alm_low_val": float(self.spn_alm_low.value()),
                "alarm_empty": bool(self.chk_alarm_empty.isChecked()),
                "alarm_excitation": bool(self.chk_alarm_excitation.isChecked()),
                "alarm_high": bool(self.chk_alarm_high.isChecked()),
                "alarm_low": bool(self.chk_alarm_low.isChecked()),
            }
        }

    def _apply_profile_dict(self, data: dict):
        conn = data.get("connection", {})
        self.edt_port.setText(conn.get("port", self.edt_port.text()))
        self.edt_baud.setText(conn.get("baud", self.edt_baud.text()))
        self.edt_slave_ids.setText(conn.get("slave_ids", self.edt_slave_ids.text()))

        server = data.get("server", {})
        if "update_period_ms" in server:
            self.spn_update_period.setValue(int(server["update_period_ms"]))
        if "byte_order" in server:
            self.cmb_byte_order.setCurrentText(str(server["byte_order"]))

        ui = data.get("ui", {})
        if "flow_max" in ui:
            self.spn_flow_max.setValue(float(ui["flow_max"]))
        if "flow_precision" in ui:
            self.spn_flow_decimals.setValue(int(ui["flow_precision"]))
        if "cond_max" in ui:
            self.spn_cond_max.setValue(float(ui["cond_max"]))
        if "cond_precision" in ui:
            self.spn_cond_decimals.setValue(int(ui["cond_precision"]))

        if "register_map" in data and isinstance(data["register_map"], dict):
            self.register_map = data["register_map"]
            self._refresh_register_map_editor()

        vals = data.get("values", {})
        if "flow_rate" in vals:
            self.spn_flow_rate.setValue(float(vals["flow_rate"]))
        if "forward_total" in vals:
            self.spn_forward_total.setValue(int(vals["forward_total"]))
        if "forward_overflow" in vals:
            self.spn_overflow.setValue(int(vals["forward_overflow"]))
        if "unit_info" in vals:
            self.spn_unit_info.setValue(int(vals["unit_info"]))
        if "conductivity" in vals:
            self.spn_conductivity.setValue(float(vals["conductivity"]))
        if "flow_range" in vals:
            self.spn_flow_range.setValue(float(vals["flow_range"]))
        if "alm_high_val" in vals:
            self.spn_alm_high.setValue(float(vals["alm_high_val"]))
        if "alm_low_val" in vals:
            self.spn_alm_low.setValue(float(vals["alm_low_val"]))

        if "alarm_empty" in vals:
            self.chk_alarm_empty.setChecked(bool(vals["alarm_empty"]))
        if "alarm_excitation" in vals:
            self.chk_alarm_excitation.setChecked(bool(vals["alarm_excitation"]))
        if "alarm_high" in vals:
            self.chk_alarm_high.setChecked(bool(vals["alarm_high"]))
        if "alarm_low" in vals:
            self.chk_alarm_low.setChecked(bool(vals["alarm_low"]))

        self._update_alarm_flags()
        self.apply_settings()

    def save_profile(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Profile", "", "JSON Files (*.json);;All Files (*)")
        if not path:
            return
        try:
            data = self._get_profile_dict()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, sort_keys=True)
            self.log_bus.message.emit(f"✓ Profile saved: {path}")
        except Exception as e:
            QMessageBox.critical(self, "Save Failed", f"Failed to save profile:\n{e}")

    def load_profile(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load Profile", "", "JSON Files (*.json);;All Files (*)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._apply_profile_dict(data)
            self.log_bus.message.emit(f"✓ Profile loaded: {path}")
        except Exception as e:
            QMessageBox.critical(self, "Load Failed", f"Failed to load profile:\n{e}")

    # -------------------------------------------------------------------------
    # Server start + register updates
    # -------------------------------------------------------------------------

    def _parse_slave_ids(self):
        """Parse slave IDs from UI into a sorted list of unique ints."""
        raw = self.edt_slave_ids.text().strip()
        if not raw:
            raise ValueError("Slave IDs cannot be empty")

        parts = [p.strip() for p in raw.split(",") if p.strip()]
        ids = []
        for p in parts:
            v = int(p)
            if v < 1 or v > 247:
                raise ValueError(f"Invalid slave id '{v}' (valid range 1..247)")
            ids.append(v)

        # Remove duplicates but keep stable ordering
        ids = list(dict.fromkeys(ids))
        return ids

    def _preflight_check_serial(self, port: str, baud: int):
        """
        Quick sanity check before starting the pymodbus server thread.
        Prevents getting stuck in 'Running...' when the port is missing/inaccessible.
        """
        test = serial.Serial(
            port=port,
            baudrate=baud,
            bytesize=8,
            parity='N',
            stopbits=1,
            timeout=1
        )
        test.close()

    def start_server(self):
        if self.server_running:
            self.log_bus.message.emit("Server already running!")
            return

        port = self.edt_port.text().strip()
        try:
            baud = int(self.edt_baud.text().strip())
        except Exception:
            QMessageBox.critical(self, "Invalid Baud", "Baud must be an integer (e.g., 9600).")
            return

        try:
            slave_ids = self._parse_slave_ids()
        except Exception as e:
            QMessageBox.critical(self, "Invalid Slave IDs", str(e))
            return

        # Preflight check: fail fast and keep UI intuitive
        try:
            self._preflight_check_serial(port, baud)
        except Exception as e:
            self.server_running = False
            self._set_server_ui_state(False, f"✗ Failed to start server: cannot open port '{port}': {type(e).__name__}: {e}")
            return

        self.log_bus.message.emit("=" * 60)
        self.log_bus.message.emit("Starting Complete Modbus RTU Server...")
        self.log_bus.message.emit(f"Port: {port}, Baud: {baud}")
        self.log_bus.message.emit(f"Slave IDs: {', '.join(map(str, slave_ids))}")
        self.log_bus.message.emit(f"Byte/Word order: {self.cmb_byte_order.currentText()}")
        self.log_bus.message.emit("=" * 60)

        # Wide blocks reduce addressing mismatch pain (0-based vs 1-based tooling differences)
        IR_BASE = 0
        IR_LEN = 2000
        HR_BASE = 0
        HR_LEN = 2000

        self.ir_blocks = {}
        self.hr_blocks = {}
        devices = {}

        for sid in slave_ids:
            self.ir_blocks[sid] = sparse.ModbusSparseDataBlock({IR_BASE: [0] * IR_LEN})
            self.hr_blocks[sid] = sparse.ModbusSparseDataBlock({HR_BASE: [0] * HR_LEN})
            devices[sid] = context.ModbusDeviceContext(ir=self.ir_blocks[sid], hr=self.hr_blocks[sid])

        self.server_context = context.ModbusServerContext(devices=devices, single=False)

        self.server_running = True
        self.btn_start.setEnabled(False)
        self.btn_start.setText("Starting...")

        self.server_thread = threading.Thread(target=self._run_server_thread, args=(port, baud), daemon=True)
        self.server_thread.start()
        self.log_bus.message.emit("✓ Server thread started")

    def _run_server_thread(self, port: str, baud: int):
        """Run the async pymodbus server in a background thread."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            async def serve():
                self.log_bus.message.emit("✓ Async server starting...")
                await StartAsyncSerialServer(
                    context=self.server_context,
                    port=port,
                    baudrate=baud,
                    bytesize=8,
                    parity='N',
                    stopbits=1,
                    timeout=1
                )
                self.log_bus.message.emit("✓ Server is now listening for requests!")
                self.log_bus.message.emit(f"✓ Responding to slave IDs: {self.edt_slave_ids.text().strip()}")
                self.log_bus.message.emit("✓ Input Registers (FC 04) and Holding Registers (FC 03) ready")
                self.log_bus.server_started.emit()

            loop.run_until_complete(serve())
            loop.run_forever()

        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            self.log_bus.server_failed.emit(f"✗ ERROR: {type(e).__name__}: {e}\n{tb}")

    def _on_server_started(self):
        self._set_server_ui_state(True)

    def _on_server_failed(self, msg: str):
        self.server_running = False
        self._set_server_ui_state(False, msg)

    # -------------------------------------------------------------------------
    # Modbus packing + register writes
    # -------------------------------------------------------------------------

    def _pack_words_32(self, packed_4bytes: bytes):
        """
        Convert 4 bytes to two 16-bit words in the configured order mode.

        Modes:
          - ABCD: big-endian words, no swap (high word first)
          - CDAB: big-endian bytes, swapped words (low word first)
          - BADC: swap bytes within each word (AB->BA, CD->DC)
          - DCBA: full reverse
        """
        mode = self.cmb_byte_order.currentText().strip().upper()

        # Start from the current "ABCD" byte layout.
        b0, b1, b2, b3 = packed_4bytes[0], packed_4bytes[1], packed_4bytes[2], packed_4bytes[3]

        if mode == "ABCD":
            bb = bytes([b0, b1, b2, b3])
        elif mode == "CDAB":
            bb = bytes([b2, b3, b0, b1])
        elif mode == "BADC":
            bb = bytes([b1, b0, b3, b2])
        elif mode == "DCBA":
            bb = bytes([b3, b2, b1, b0])
        else:
            # Fall back safely to the default EdgeBox-friendly ordering.
            bb = bytes([b2, b3, b0, b1])

        word0 = struct.unpack(">H", bb[0:2])[0]
        word1 = struct.unpack(">H", bb[2:4])[0]
        return [word0, word1]

    def update_registers(self):
        """Update Modbus registers with current UI values."""
        if not (self.server_running and self.ir_blocks):
            return

        # Keep timer interval synced in case it changed
        self._apply_update_period()

        try:
            def pack_uint16(value: int):
                return [int(value) & 0xFFFF]

            def pack_uint32(value: int):
                packed = struct.pack(">I", int(value))
                return self._pack_words_32(packed)

            def pack_float32(value: float):
                packed = struct.pack(">f", float(value))
                return self._pack_words_32(packed)

            alarm_flags = self._get_alarm_flags_value()

            # Update all devices with the same data (can be extended later per-device)
            for sid in list(self.ir_blocks.keys()):
                ir_block = self.ir_blocks[sid]
                hr_block = self.hr_blocks[sid]

                # INPUT REGISTERS (FC 04)
                if self.register_map.get("forward_total", {}).get("enabled", True):
                    ir_block.setValues(self.register_map["forward_total"]["address"], pack_uint32(self.spn_forward_total.value()))

                if self.register_map.get("unit_info", {}).get("enabled", True):
                    ir_block.setValues(self.register_map["unit_info"]["address"], pack_uint16(self.spn_unit_info.value()))

                if self.register_map.get("alarm_flags", {}).get("enabled", True):
                    ir_block.setValues(self.register_map["alarm_flags"]["address"], pack_uint16(alarm_flags))

                if self.register_map.get("flow_rate", {}).get("enabled", True):
                    ir_block.setValues(self.register_map["flow_rate"]["address"], pack_float32(self.spn_flow_rate.value()))

                if self.register_map.get("overflow_count", {}).get("enabled", True):
                    ir_block.setValues(self.register_map["overflow_count"]["address"], pack_uint16(self.spn_overflow.value()))

                if self.register_map.get("conductivity", {}).get("enabled", True):
                    ir_block.setValues(self.register_map["conductivity"]["address"], pack_float32(self.spn_conductivity.value()))

                # HOLDING REGISTERS (FC 03)
                if self.register_map.get("flow_range", {}).get("enabled", True):
                    hr_block.setValues(self.register_map["flow_range"]["address"], pack_float32(self.spn_flow_range.value()))

                if self.register_map.get("alm_high_val", {}).get("enabled", True):
                    hr_block.setValues(self.register_map["alm_high_val"]["address"], pack_float32(self.spn_alm_high.value()))

                if self.register_map.get("alm_low_val", {}).get("enabled", True):
                    hr_block.setValues(self.register_map["alm_low_val"]["address"], pack_float32(self.spn_alm_low.value()))

        except Exception:
            # Update loop stays resilient; errors can be surfaced later if needed
            pass


def main():
    app = QApplication(sys.argv)
    win = FlowMeterSimulatorQt()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

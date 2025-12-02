# MIT License

# Copyright (c) 2025 Institute for Automotive Engineering (ika), RWTH Aachen University

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from PySide6 import QtCore, QtWidgets

__all__ = ["GlobalSettingsWidget"]


class GlobalSettingsWidget(QtWidgets.QWidget):
    """
    Widget for global export settings and summary display.
    
    This widget provides controls for:
    - CPU usage limit configuration
    - Topic resampling/synchronization settings (association strategy and epsilon)
    - Export summary showing selected vs total topics
    - Main export action button
    
    Signals:
        export_clicked: Emitted when the export button is clicked
    """
    
    export_clicked = QtCore.Signal()

    def __init__(self, parent=None):
        """
        Initialize the GlobalSettingsWidget with UI components.

        Args:
            parent: Optional parent widget.

        Returns:
            None
        """
        super().__init__(parent)
        self.selected_topics = []
        self.init_ui()

    def init_ui(self):
        """
        Build the global settings UI with CPU controls, resampling options, summary, and export button.

        Args:
            None

        Returns:
            None
        """
        layout = QtWidgets.QVBoxLayout(self)
        layout.setAlignment(QtCore.Qt.AlignTop)

        # Global Settings Group
        gb_settings = QtWidgets.QGroupBox("Global Settings")
        form_layout = QtWidgets.QFormLayout(gb_settings)

        # CPU Usage
        self.cpu_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.cpu_slider.setRange(0, 100)
        self.cpu_slider.setValue(80)
        self.cpu_slider.setSingleStep(10)
        self.cpu_slider.setPageStep(10)
        self.cpu_slider.setTickInterval(10)
        self.cpu_slider.setTickPosition(QtWidgets.QSlider.TicksBelow)
        self.cpu_spin = QtWidgets.QDoubleSpinBox()
        self.cpu_spin.setRange(0.0, 100.0)
        self.cpu_spin.setSingleStep(1.0)
        self.cpu_spin.setDecimals(1)
        self.cpu_spin.setValue(80.0)
        
        def _slider_to_spin(val):
            # snap slider to 10% steps, keep spinbox in sync with snapped value
            snapped = round(val / 10) * 10
            if snapped != val:
                self.cpu_slider.blockSignals(True)
                self.cpu_slider.setValue(snapped)
                self.cpu_slider.blockSignals(False)
            self.cpu_spin.setValue(float(snapped))

        def _spin_to_slider(val):
            # reflect manual input on the slider without snapping the spin value
            self.cpu_slider.blockSignals(True)
            self.cpu_slider.setValue(int(round(val)))
            self.cpu_slider.blockSignals(False)

        self.cpu_slider.valueChanged.connect(_slider_to_spin)
        self.cpu_spin.valueChanged.connect(_spin_to_slider)
        
        cpu_layout = QtWidgets.QHBoxLayout()
        cpu_layout.addWidget(self.cpu_slider)
        cpu_layout.addWidget(self.cpu_spin)
        form_layout.addRow("CPU Usage %", cpu_layout)

        # Resampling
        self.assoc_combo = QtWidgets.QComboBox()
        self.assoc_combo.addItems(["no resampling", "last", "nearest"])
        self.assoc_combo.currentTextChanged.connect(self._on_assoc_changed)
        form_layout.addRow("Association", self.assoc_combo)

        self.eps_edit = QtWidgets.QLineEdit()
        self.eps_edit.setPlaceholderText("e.g. 0.5")
        self.eps_edit.setEnabled(False)
        form_layout.addRow("Discard Eps (s)", self.eps_edit)

        self.master_combo = QtWidgets.QComboBox()
        self.master_combo.setEnabled(False)
        form_layout.addRow("Master Topic", self.master_combo)

        layout.addWidget(gb_settings)

        # Summary Group
        gb_summary = QtWidgets.QGroupBox("Summary")
        self.summary_layout = QtWidgets.QVBoxLayout(gb_summary)
        self.summary_label = QtWidgets.QLabel("No bag loaded.")
        self.summary_layout.addWidget(self.summary_label)
        layout.addWidget(gb_summary)

        layout.addStretch()

        # Export Button
        self.btn_export = QtWidgets.QPushButton("Export Selected Topics")
        self.btn_export.setMinimumHeight(50)
        self.btn_export.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.btn_export.clicked.connect(self.export_clicked)
        self.btn_export.setEnabled(False)
        layout.addWidget(self.btn_export)

    def _on_assoc_changed(self, text):
        """
        Handle association strategy changes and update epsilon field state.
        
        Enables/disables the epsilon field based on whether resampling is active,
        and sets a default epsilon value when 'nearest' strategy is selected.

        Args:
            text: Selected association strategy string.

        Returns:
            None
        """
        enable = text != "no resampling"
        self.eps_edit.setEnabled(enable)
        self._refresh_master_combo(resampling_enabled=enable)
        if text == "nearest" and not self.eps_edit.text():
            self.eps_edit.setText("0.5")

    def _refresh_master_combo(self, resampling_enabled=False):
        """
        Populate the master topic dropdown with currently selected topics.
        """
        current = self.master_combo.currentText()
        self.master_combo.blockSignals(True)
        self.master_combo.clear()
        for topic in self.selected_topics:
            self.master_combo.addItem(topic)
        restore_idx = self.master_combo.findText(current)
        if restore_idx >= 0:
            self.master_combo.setCurrentIndex(restore_idx)
        elif self.master_combo.count() > 0:
            self.master_combo.setCurrentIndex(0)
        self.master_combo.setEnabled(resampling_enabled and self.master_combo.count() > 0)
        self.master_combo.blockSignals(False)

    def update_summary(self, selected_count, total_count, selected_topics=None):
        """
        Update the summary display with current topic selection counts.
        
        Updates the summary label and enables/disables the export button
        based on whether any topics are selected.

        Args:
            selected_count: Number of topics selected for export.
            total_count: Total number of topics in the bag.

        Returns:
            None
        """
        if selected_topics is not None:
            self.selected_topics = selected_topics
            self._refresh_master_combo(resampling_enabled=self.assoc_combo.currentText() != "no resampling")

        self.summary_label.setText(
            f"Selected Topics: {selected_count}\n"
            f"Total Topics: {total_count}"
        )
        self.btn_export.setEnabled(selected_count > 0)

    def get_config(self):
        """
        Retrieve current global configuration from UI widgets.
        
        Collects CPU usage and resampling settings into a configuration dictionary.

        Args:
            None

        Returns:
            dict: Configuration dictionary with keys 'cpu_percentage' and optionally
                 'resample_config' (if resampling is enabled).
        """
        cfg = {
            "cpu_percentage": float(self.cpu_spin.value())
        }
        assoc = self.assoc_combo.currentText()
        if assoc != "no resampling":
            try:
                eps = float(self.eps_edit.text())
            except ValueError:
                eps = None
            
            master_topic = self.master_combo.currentText().strip()
            cfg["resample_config"] = {
                "association": assoc,
                "discard_eps": eps,
                "master_topic": master_topic if master_topic else None
            }
        return cfg
    
    def set_config(self, config):
        """
        Populate UI widgets from a global configuration dictionary.
        
        Restores CPU usage and resampling settings from a previously saved configuration.

        Args:
            config: Configuration dictionary with keys 'cpu_percentage' and optionally
                   'resample_config'.

        Returns:
            None
        """
        if "cpu_percentage" in config:
            self.cpu_slider.setValue(config["cpu_percentage"])
        
        rcfg = config.get("resample_config")
        if rcfg:
            assoc = rcfg.get("association", "no resampling")
            idx = self.assoc_combo.findText(assoc)
            if idx >= 0:
                self.assoc_combo.setCurrentIndex(idx)
            if "discard_eps" in rcfg:
                self.eps_edit.setText(str(rcfg["discard_eps"]))
            if "master_topic" in rcfg and rcfg["master_topic"]:
                # refresh master list in case set_config is called before update_summary
                self._refresh_master_combo(resampling_enabled=assoc != "no resampling")
                midx = self.master_combo.findText(rcfg["master_topic"])
                if midx >= 0:
                    self.master_combo.setCurrentIndex(midx)
        else:
            self.assoc_combo.setCurrentIndex(0)
        if "cpu_percentage" in config:
            # ensure slider reflects the new spin value without snapping the spin itself
            self.cpu_spin.setValue(float(config["cpu_percentage"]))
            self.cpu_slider.blockSignals(True)
            self.cpu_slider.setValue(int(round(config["cpu_percentage"])))
            self.cpu_slider.blockSignals(False)

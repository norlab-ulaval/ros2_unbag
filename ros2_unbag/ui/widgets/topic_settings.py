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
from ros2_unbag.core.processors import Processor
from ros2_unbag.core.routines import ExportRoutine, ExportMode
from .processor_chain import ProcessorChainWidget

__all__ = ["TopicSettingsWidget"]


class TopicSettingsWidget(QtWidgets.QWidget):
    """
    Widget for configuring export settings for a single ROS2 topic.
    
    This widget displays and manages all export configuration options for the currently
    selected topic, including:
    - Export format selection
    - Export mode (single file vs multi-file)
    - Output directory and subdirectory
    - File naming scheme with placeholder support
    - Master topic designation for resampling
    - Processor chain configuration
    
    The widget dynamically adapts its UI based on the topic's message type, showing
    only relevant formats and processors.
    
    Signals:
        settings_changed (str, dict): Emitted when any setting changes, passes topic name and updated config dict
    """
    
    # Signal emitted when settings change, so the main window can update the config state
    settings_changed = QtCore.Signal(str, dict)  # topic_name, new_config

    def __init__(self, default_folder, parent=None):
        """
        Initialize the TopicSettingsWidget with default output folder.

        Args:
            default_folder: Default output directory path for exports.
            parent: Optional parent widget.

        Returns:
            None
        """
        super().__init__(parent)
        self.default_folder = default_folder
        self.current_topic = None
        self.current_type = None
        self.init_ui()

    def init_ui(self):
        """
        Build the topic settings UI with form layout for all configuration options.
        
        Creates a form with format selection, mode selection, path configuration,
        naming scheme, master topic checkbox, and processor chain widget.
        Initially hidden until a topic is selected.

        Args:
            None

        Returns:
            None
        """
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setAlignment(QtCore.Qt.AlignTop)

        # Header
        self.header_label = QtWidgets.QLabel("No Topic Selected")
        self.header_label.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        self.layout.addWidget(self.header_label)

        # Content Container (hidden when no topic selected)
        self.content_widget = QtWidgets.QWidget()
        self.form_layout = QtWidgets.QFormLayout(self.content_widget)
        
        # Format
        self.fmt_combo = QtWidgets.QComboBox()
        self.fmt_combo.currentTextChanged.connect(self._on_format_changed)
        self.form_layout.addRow("Format", self.fmt_combo)

        # Mode
        self.mode_label = QtWidgets.QLabel("Mode")
        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self.form_layout.addRow(self.mode_label, self.mode_combo)

        # Output Directory
        self.path_edit = QtWidgets.QLineEdit()
        self.browse_btn = QtWidgets.QPushButton("Browse")
        self.browse_btn.clicked.connect(self._browse_path)
        path_layout = QtWidgets.QHBoxLayout()
        path_layout.addWidget(self.path_edit)
        path_layout.addWidget(self.browse_btn)
        self.form_layout.addRow("Output Directory", path_layout)

        # Subdirectory
        self.subdir_edit = QtWidgets.QLineEdit()
        self.form_layout.addRow("Subdirectory", self.subdir_edit)

        # Naming
        self.naming_edit = QtWidgets.QLineEdit()
        self.form_layout.addRow("Naming", self.naming_edit)

        # Master Topic Checkbox
        self.master_check = QtWidgets.QCheckBox("Set as Master for Resampling")
        self.form_layout.addRow("Master Topic", self.master_check)

        # Processor Chain Placeholder
        self.processor_container = QtWidgets.QWidget()
        self.processor_layout = QtWidgets.QVBoxLayout(self.processor_container)
        self.processor_layout.setContentsMargins(0,0,0,0)
        self.form_layout.addRow("Processors", self.processor_container)

        self.layout.addWidget(self.content_widget)
        
        # Help Text
        help_text = QtWidgets.QLabel(
            "Placeholders:\n"
            "%name (topic), %index (msg idx)\n"
            "%Y-%m-%d_%H-%M-%S (timestamp)"
        )
        help_text.setStyleSheet("color: gray; font-style: italic; margin-top: 20px;")
        self.layout.addWidget(help_text)
        self.layout.addStretch()

        # Connect change signals
        self.path_edit.editingFinished.connect(self._emit_change)
        self.subdir_edit.editingFinished.connect(self._emit_change)
        self.naming_edit.editingFinished.connect(self._emit_change)
        self.master_check.toggled.connect(self._emit_change)
        
        self.content_widget.setVisible(False)

    def set_topic(self, topic, topic_type, config):
        """
        Load and display settings for a specific topic.
        
        Updates the UI to show configuration options for the given topic,
        populating all fields from the provided config dictionary. Dynamically
        adjusts available formats and processors based on the topic's message type.

        Args:
            topic: Topic name string.
            topic_type: ROS2 message type string.
            config: Configuration dictionary with keys 'format', 'path', 'subfolder',
                   'naming', 'processors', 'resample_config'.

        Returns:
            None
        """
        self.current_topic = topic
        self.current_type = topic_type
        
        self.header_label.setText(f"Settings: {topic}")
        self.content_widget.setVisible(True)

        # Block signals to prevent auto-saving during load
        self.blockSignals(True)

        # 1. Setup Formats
        self.fmt_combo.blockSignals(True)
        self.fmt_combo.clear()
        formats = ExportRoutine.get_formats(topic_type)
        self.fmt_combo.addItems(formats)
        
        # Select current format
        current_fmt = config.get("format", "")
        # If format has @mode suffix, strip it for selection but keep mode in mind
        resolution = ExportRoutine.resolve(topic_type, current_fmt)
        if resolution:
            _, canonical_fmt, mode = resolution
            idx = self.fmt_combo.findText(canonical_fmt)
            if idx >= 0:
                self.fmt_combo.setCurrentIndex(idx)
            self.mode_combo.setProperty("pending_mode", mode)
        else:
            if self.fmt_combo.count() > 0:
                self.fmt_combo.setCurrentIndex(0)
        
        self.fmt_combo.blockSignals(False)

        # 2. Update Mode options based on format
        self._refresh_mode_controls(self.fmt_combo.currentText())

        # 3. Set other fields
        self.path_edit.setText(config.get("path", str(self.default_folder)))
        self.subdir_edit.setText(config.get("subfolder", "").strip("/"))
        self.naming_edit.setText(config.get("naming", "%name"))
        
        rcfg = config.get("resample_config", {})
        self.master_check.setChecked(rcfg.get("is_master", False))

        # 4. Processor Chain
        # Clear old
        while self.processor_layout.count():
            item = self.processor_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        
        available_processors = Processor.get_formats(topic_type)
        if available_processors:
            self.chain_widget = ProcessorChainWidget(topic_type, available_processors)
            # Load chain config
            chain_cfg = config.get("processors", [])
            # Normalize chain config if needed (same as in ExportOptions)
            normalized_chain = []
            for entry in chain_cfg:
                if isinstance(entry, str):
                    normalized_chain.append({"name": entry, "args": {}})
                elif isinstance(entry, dict):
                    normalized_chain.append(entry)
            
            self.chain_widget.set_chain(normalized_chain)
            # Connect signal if ProcessorChainWidget has one, otherwise we might need to poll it
            # Assuming ProcessorChainWidget doesn't emit change signal, we might need to add one or check on save
            self.processor_layout.addWidget(self.chain_widget)
        else:
            self.chain_widget = None
            lbl = QtWidgets.QLabel("No processors available")
            self.processor_layout.addWidget(lbl)

        self.blockSignals(False)

    def get_config(self):
        """
        Retrieve current configuration from UI widgets.
        
        Collects all settings from the form and returns them as a configuration
        dictionary. Handles format string construction with mode suffix if needed.

        Args:
            None

        Returns:
            dict: Configuration dictionary with keys 'format', 'path', 'subfolder',
                 'naming', 'resample_config', and optionally 'processors'.
                 Returns empty dict if no topic is currently selected.
        """
        if not self.current_topic: return {}
        
        fmt = self.fmt_combo.currentText()
        mode = self.mode_combo.currentData()
        if mode is None: mode = self.mode_combo.property("forced_mode")
        
        # Construct format string (e.g. "csv@single_file")
        # Logic from ExportOptions
        available_modes = self.mode_combo.property("available_modes") or tuple()
        if mode == ExportMode.SINGLE_FILE and len(available_modes) > 1:
            fmt = f"{fmt}@single_file"

        cfg = {
            "format": fmt,
            "path": self.path_edit.text(),
            "subfolder": self.subdir_edit.text(),
            "naming": self.naming_edit.text(),
            "resample_config": {"is_master": self.master_check.isChecked()}
        }
        
        if self.chain_widget:
            cfg["processors"] = self.chain_widget.get_chain()
            
        return cfg

    def _browse_path(self):
        """
        Open directory selection dialog and update output path field.
        
        Displays a file dialog for the user to select an output directory,
        then updates the path field and emits a settings change signal.

        Args:
            None

        Returns:
            None
        """
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Directory", self.path_edit.text())
        if directory:
            self.path_edit.setText(directory)
            self._emit_change()

    def _on_format_changed(self, text):
        """
        Handle format selection changes.
        
        Updates available export modes based on the selected format and
        emits a settings change signal.

        Args:
            text: Selected format string.

        Returns:
            None
        """
        self._refresh_mode_controls(text)
        self._emit_change()

    def _on_mode_changed(self, idx):
        """
        Handle export mode changes and update naming scheme accordingly.
        
        When switching between single-file and multi-file modes, automatically
        adjusts the naming scheme to include or exclude the %index placeholder.

        Args:
            idx: Selected mode combo box index.

        Returns:
            None
        """
        # Update default naming if changed
        mode = self.mode_combo.currentData()
        if mode is None:
            mode = self.mode_combo.property("forced_mode")
        
        if mode == ExportMode.SINGLE_FILE:
            if "%index" in self.naming_edit.text():
                self.naming_edit.setText("%name")
        else:
            if self.naming_edit.text() == "%name":
                self.naming_edit.setText("%name_%index")
        
        self._emit_change()

    def _refresh_mode_controls(self, fmt):
        """
        Update mode selection controls based on available modes for the selected format.
        
        Queries the export routine system for available modes (single-file vs multi-file)
        for the current format and topic type. Shows/hides the mode selector accordingly.
        If only one mode is available, it's set as a forced mode and the selector is hidden.

        Args:
            fmt: Export format string.

        Returns:
            None
        """
        if not self.current_type:
            return
        
        modes = list(ExportRoutine.get_modes_for_format(self.current_type, fmt))
        if not modes:
            modes = [ExportMode.MULTI_FILE]
        
        self.mode_combo.blockSignals(True)
        self.mode_combo.clear()
        
        ordered_modes = sorted(modes, key=lambda m: 0 if m == ExportMode.MULTI_FILE else 1)
        
        if len(ordered_modes) > 1:
            for m in ordered_modes:
                label = "Multi file" if m == ExportMode.MULTI_FILE else "Single file"
                self.mode_combo.addItem(label, m)
            
            # Restore pending mode if set
            pending = self.mode_combo.property("pending_mode")
            if pending in ordered_modes:
                idx = self.mode_combo.findData(pending)
                self.mode_combo.setCurrentIndex(idx)
            
            self.mode_combo.setVisible(True)
            self.mode_label.setVisible(True)
        else:
            self.mode_combo.setProperty("forced_mode", ordered_modes[0])
            self.mode_combo.setVisible(False)
            self.mode_label.setVisible(False)
            
        self.mode_combo.setProperty("available_modes", tuple(ordered_modes))
        self.mode_combo.setProperty("pending_mode", None)
        self.mode_combo.blockSignals(False)

    def _emit_change(self):
        """
        Emit settings_changed signal with current topic and configuration.
        
        Called whenever any setting is modified to notify the main window
        that the configuration has changed.

        Args:
            None

        Returns:
            None
        """
        if self.current_topic:
            self.settings_changed.emit(self.current_topic, self.get_config())

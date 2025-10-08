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

import inspect
import os

from PySide6 import QtCore, QtWidgets

from ros2_unbag.core.processors import Processor
from ros2_unbag.core.routines import ExportRoutine, ExportMode


class ProcessorChainWidget(QtWidgets.QWidget):
    """Widget to configure an ordered chain of processors for a topic."""

    def __init__(self, topic_type, available_processors, parent=None):
        super().__init__(parent)
        self.topic_type = topic_type
        self.available_processors = list(available_processors)
        self.entries = []

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.chain_layout = QtWidgets.QVBoxLayout()
        self.chain_layout.setSpacing(8)
        layout.addLayout(self.chain_layout)

        self.empty_hint = QtWidgets.QLabel("No processors configured.")
        self.empty_hint.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(self.empty_hint)

        add_row = QtWidgets.QHBoxLayout()
        add_row.addStretch()
        self.add_button = QtWidgets.QPushButton("Add Processor")
        self.add_button.setCursor(QtCore.Qt.PointingHandCursor)
        self.add_button.clicked.connect(self.add_entry)
        add_row.addWidget(self.add_button)
        layout.addLayout(add_row)

        self._update_empty_hint()

    def add_entry(self, preset=None):
        entry = _ProcessorEntry(self)
        self.entries.append(entry)
        self.chain_layout.addWidget(entry)
        self._reindex_entries()
        if preset:
            entry.apply_config(preset)
        else:
            entry.select_default()
        self._update_empty_hint()
        return entry

    def remove_entry(self, entry):
        if entry in self.entries:
            self.entries.remove(entry)
            self.chain_layout.removeWidget(entry)
            entry.deleteLater()
            self._reindex_entries()
            self._update_empty_hint()

    def move_entry(self, entry, delta):
        if entry not in self.entries:
            return
        idx = self.entries.index(entry)
        new_idx = idx + delta
        if new_idx < 0 or new_idx >= len(self.entries):
            return
        self.entries.pop(idx)
        self.entries.insert(new_idx, entry)
        self.chain_layout.removeWidget(entry)
        self.chain_layout.insertWidget(new_idx, entry)
        self._reindex_entries()

    def get_chain(self):
        chain = []
        for entry in self.entries:
            config = entry.get_config()
            if config:
                chain.append(config)
        return chain

    def set_chain(self, configs):
        self.clear()
        for cfg in configs or []:
            self.add_entry(cfg)
        if not configs:
            self._update_empty_hint()

    def clear(self):
        for entry in list(self.entries):
            self.remove_entry(entry)

    def _reindex_entries(self):
        total = len(self.entries)
        for idx, entry in enumerate(self.entries, start=1):
            entry.set_index(idx, total)

    def _update_empty_hint(self):
        self.empty_hint.setVisible(len(self.entries) == 0)


class _ProcessorEntry(QtWidgets.QFrame):
    """Single processor entry row inside the processor chain widget."""

    def __init__(self, chain_widget):
        super().__init__()
        self.chain_widget = chain_widget
        self.arg_inputs = {}

        self.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.setFrameShadow(QtWidgets.QFrame.Raised)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        header = QtWidgets.QHBoxLayout()
        header.setSpacing(6)

        self.index_label = QtWidgets.QLabel("1.")
        self.index_label.setFixedWidth(24)
        header.addWidget(self.index_label)

        self.combo = QtWidgets.QComboBox()
        self.combo.addItems(self.chain_widget.available_processors)
        self.combo.currentTextChanged.connect(self._on_processor_changed)
        header.addWidget(self.combo, stretch=1)

        self.up_button = QtWidgets.QToolButton()
        self.up_button.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_ArrowUp))
        self.up_button.setAutoRaise(True)
        self.up_button.setCursor(QtCore.Qt.PointingHandCursor)
        self.up_button.clicked.connect(lambda: self.chain_widget.move_entry(self, -1))
        header.addWidget(self.up_button)

        self.down_button = QtWidgets.QToolButton()
        self.down_button.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_ArrowDown))
        self.down_button.setAutoRaise(True)
        self.down_button.setCursor(QtCore.Qt.PointingHandCursor)
        self.down_button.clicked.connect(lambda: self.chain_widget.move_entry(self, 1))
        header.addWidget(self.down_button)

        self.remove_button = QtWidgets.QToolButton()
        self.remove_button.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_DialogCloseButton))
        self.remove_button.setAutoRaise(True)
        self.remove_button.setCursor(QtCore.Qt.PointingHandCursor)
        self.remove_button.clicked.connect(lambda: self.chain_widget.remove_entry(self))
        header.addWidget(self.remove_button)

        layout.addLayout(header)

        self.args_layout = QtWidgets.QFormLayout()
        self.args_layout.setContentsMargins(0, 4, 0, 0)
        self.args_layout.setFieldGrowthPolicy(QtWidgets.QFormLayout.ExpandingFieldsGrow)
        layout.addLayout(self.args_layout)

        self._on_processor_changed(self.combo.currentText())

    def set_index(self, index, total):
        self.index_label.setText(f"{index}.")
        self.up_button.setEnabled(index > 1)
        self.down_button.setEnabled(index < total)

    def select_default(self):
        if self.chain_widget.available_processors:
            self.combo.setCurrentIndex(0)

    def apply_config(self, config):
        name = config.get("name")
        if name and name in self.chain_widget.available_processors:
            self.combo.setCurrentText(name)
        elif name:
            # Allow configuring processors that were loaded dynamically after widget creation.
            self.combo.addItem(name)
            self.combo.setCurrentText(name)

        args = config.get("args", {}) or {}
        self._on_processor_changed(self.combo.currentText())
        for arg_name, value in args.items():
            if arg_name in self.arg_inputs:
                self.arg_inputs[arg_name].setText(str(value))

    def get_config(self):
        name = self.combo.currentText()
        args = {}
        for arg_name, edit in self.arg_inputs.items():
            value = edit.text().strip()
            if value:
                args[arg_name] = value
        return {"name": name, "args": args}

    def _clear_args(self):
        while self.args_layout.rowCount():
            self.args_layout.removeRow(0)
        self.arg_inputs = {}

    def _on_processor_changed(self, processor_name):
        self._clear_args()
        args = Processor.get_args(self.chain_widget.topic_type, processor_name)
        if not args:
            return

        for arg_name, (param, doc) in args.items():
            label = QtWidgets.QLabel()
            label.setText(f"{arg_name} (optional)" if param.default != inspect.Parameter.empty else arg_name)

            parts = []
            if doc:
                parts.append(doc)
            if param.default != inspect.Parameter.empty:
                parts.append(f"default: {param.default}")
            if param.annotation != inspect.Parameter.empty:
                annotation = getattr(param.annotation, "__name__", str(param.annotation))
                parts.append(f"Type: {annotation}")
            placeholder_text = " — ".join(parts)

            arg_edit = QtWidgets.QLineEdit()
            arg_edit.setPlaceholderText(placeholder_text)

            self.args_layout.addRow(label, arg_edit)
            self.arg_inputs[arg_name] = arg_edit


class TopicSelector(QtWidgets.QWidget):
    # Widget to display and select available topics from the bag

    def __init__(self, bag_reader):
        """
        Initialize TopicSelector with a BagReader, retrieve topics and message counts, and build the UI.

        Args:
            bag_reader: BagReader instance for the ROS2 bag.

        Returns:
            None
        """
        super().__init__()
        self.bag_reader = bag_reader
        self.topics = self.bag_reader.get_topics()
        self.message_counts = self.bag_reader.get_message_count()
        self.checkboxes = {}
        self.select_all_state = True

        self.init_ui()

    def init_ui(self):
        """
        Build the topic selection UI: group topics by message type with checkboxes and message count labels.

        Args:
            None

        Returns:
            None
        """
        layout = QtWidgets.QVBoxLayout()

        # Create checkboxes grouped by message type
        for msg_type, topic_list in sorted(self.topics.items()):
            group_box = QtWidgets.QGroupBox(msg_type)
            group_layout = QtWidgets.QVBoxLayout()

            for topic in sorted(topic_list):
                container = QtWidgets.QWidget()
                h_layout = QtWidgets.QHBoxLayout()
                h_layout.setContentsMargins(0, 0, 0, 0)

                checkbox = QtWidgets.QCheckBox()
                checkbox.setCursor(QtCore.Qt.PointingHandCursor)
                label = QtWidgets.QLabel(topic)
                label.setCursor(QtCore.Qt.PointingHandCursor)
                label.mousePressEvent = self._make_label_toggle_cb(checkbox)
                count_label = QtWidgets.QLabel(str(self.message_counts.get(topic, 0))+ " Messages")
                count_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

                h_layout.addWidget(checkbox)
                h_layout.addWidget(label)
                h_layout.addStretch()
                h_layout.addWidget(count_label)

                container.setLayout(h_layout)
                group_layout.addWidget(container)
                self.checkboxes[topic] = checkbox

            group_box.setLayout(group_layout)
            layout.addWidget(group_box)

        # Select All / Deselect All button
        self.select_all_button = QtWidgets.QPushButton("Select All")
        self.select_all_button.clicked.connect(self.toggle_select_all)
        layout.addWidget(self.select_all_button)

        self.setLayout(layout)

    def toggle_select_all(self):
        """
        Toggles the selection state of all checkboxes in the widget.

        Args:
            None

        Returns:
            None
        """
        for cb in self.checkboxes.values():
            cb.setChecked(self.select_all_state)
        self.select_all_state = not self.select_all_state
        self.select_all_button.setText("Deselect All" if not self.select_all_state else "Select All")

    def _make_label_toggle_cb(self, checkbox):
        """
        Creates a callback function that toggles the state of the given checkbox.

        Args:
            checkbox: QCheckBox instance to toggle.

        Returns:
            function: Callback function for mousePressEvent.
        """
        def toggle(_):
            checkbox.toggle()
        return toggle
    
    def get_selected_topics(self):
        """
        Return a list of topics whose checkboxes are currently checked.

        Args:
            None

        Returns:
            list: List of selected topic names.
        """
        return [
            topic for topic, cb in self.checkboxes.items() if cb.isChecked()
        ]


class ExportOptions(QtWidgets.QWidget):

    def __init__(self, selected_topics, all_topics, default_folder):
        """
        Initialize ExportOptions with selected topics, all topics mapping, and default output folder; prepare UI state.

        Args:
            selected_topics: List of selected topic names.
            all_topics: Dict mapping message types to topic lists.
            default_folder: Default output folder path.

        Returns:
            None
        """
        super().__init__()
        self.config_widgets = {}
        self.master_checkboxes = {}
        self.all_path_edits = []
        self.master_group = QtWidgets.QButtonGroup(self)
        self.master_group.setExclusive(True)  # ensure single master
        self.selected_topics = selected_topics
        self.all_topics = all_topics
        self.default_folder = default_folder

        self.init_ui()

    def init_ui(self):
        """
        Build the export options UI: global settings (CPU, resampling) and per-topic controls for format, paths, naming, and processors.

        Args:
            None

        Returns:
            None
        """
        layout = QtWidgets.QVBoxLayout()

        # ────────── Global Sync Settings (TOP) ──────────
        global_group = QtWidgets.QGroupBox("Global Settings")
        global_layout = QtWidgets.QFormLayout()

        self.cpu_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.cpu_slider.setRange(0, 100)
        self.cpu_slider.setValue(80)
        self.cpu_slider.setTickInterval(5)
        self.cpu_slider.setTickPosition(QtWidgets.QSlider.TicksBelow)
        self.cpu_spinbox = QtWidgets.QSpinBox()
        self.cpu_spinbox.setRange(0, 100)
        self.cpu_spinbox.setValue(80)

        # Sync slider and spinbox
        self.cpu_slider.valueChanged.connect(self.cpu_spinbox.setValue)
        self.cpu_spinbox.valueChanged.connect(self.cpu_slider.setValue)
        cpu_layout = QtWidgets.QHBoxLayout()
        cpu_layout.addWidget(self.cpu_slider)
        cpu_layout.addWidget(self.cpu_spinbox)

        self.assoc_combo = QtWidgets.QComboBox()
        self.assoc_combo.addItems(["no resampling", "last", "nearest"])
        self.assoc_combo.currentTextChanged.connect(self._sync_mode_changed)

        self.eps_edit = QtWidgets.QLineEdit()
        self.eps_edit.setPlaceholderText("e.g., 0.5 (required for nearest)")
        self.eps_hint = QtWidgets.QLabel("Required for 'nearest' strategy.")
        self.eps_hint.setStyleSheet("color: gray; font-style: italic;")

        global_layout.addRow("CPU usage", cpu_layout)
        global_layout.addRow("Association Strategy", self.assoc_combo)
        global_layout.addRow("Discard Eps (s)", self.eps_edit)
        global_layout.addRow("", self.eps_hint)
        global_group.setLayout(global_layout)
        layout.addWidget(global_group)

        # ────────── Per-topic export options ──────────
        for idx, topic in enumerate(self.selected_topics):
            topic_type = next(
                (k for k, v in self.all_topics.items() if topic in v), None)

            group_box = QtWidgets.QGroupBox(topic)
            form_layout = QtWidgets.QFormLayout()

            # Format selection
            fmt_combo = QtWidgets.QComboBox()
            fmt_combo.addItems(ExportRoutine.get_formats(topic_type))

            mode_label = QtWidgets.QLabel("Mode")
            mode_combo = QtWidgets.QComboBox()
            mode_label.setVisible(False)
            mode_combo.setVisible(False)

            # Output directory
            abs_path_edit = QtWidgets.QLineEdit()
            abs_path_edit.setText(str(self.default_folder))
            browse_button = QtWidgets.QPushButton("Browse")
            if idx == 0:
                browse_button.clicked.connect(lambda _, e=abs_path_edit: self.
                                              select_directory_and_apply(e))
            else:
                browse_button.clicked.connect(
                    lambda _, e=abs_path_edit: self.select_directory(e))

            path_layout = QtWidgets.QHBoxLayout()
            path_layout.addWidget(abs_path_edit)
            path_layout.addWidget(browse_button)
            self.all_path_edits.append(abs_path_edit)

            # Subdirectory and naming scheme
            rel_path_edit = QtWidgets.QLineEdit("%name")
            name_scheme_edit = QtWidgets.QLineEdit()

            # Dynamic update based on format selection
            def _apply_default_naming(name_edit: QtWidgets.QLineEdit, selected_mode: ExportMode):
                """
                Update the naming scheme QLineEdit based on the selected export mode.
                If SINGLE_FILE is selected, use "%name"; if MULTI_FILE, use "%name_%index".

                Args:
                    name_edit: QLineEdit for naming scheme.
                    selected_mode: Currently selected ExportMode.
                
                Returns:
                    None
                """
                if selected_mode == ExportMode.SINGLE_FILE:
                    name_edit.setText("%name")
                else:
                    name_edit.setText("%name_%index")

            def _refresh_mode_controls(selected_fmt: str, *, combo=mode_combo,
                                       label=mode_label, name_edit=name_scheme_edit,
                                       t_type=topic_type):
                """
                Update mode selection controls based on selected format and available modes.
                If multiple modes are available, show the combo box; otherwise, hide it and set the only mode.

                Args:
                    selected_fmt: Currently selected format string.
                    combo: QComboBox for mode selection.
                    label: QLabel for the mode combo box.
                    name_edit: QLineEdit for naming scheme.
                    t_type: Message type string.

                Returns:
                    None
                """
                modes = list(ExportRoutine.get_modes_for_format(t_type, selected_fmt))
                if not modes:
                    modes = [ExportMode.MULTI_FILE]
                preferred_mode = combo.property("pending_mode")
                combo.setProperty("pending_mode", None)
                combo.blockSignals(True)
                combo.clear()
                ordered_modes = sorted(modes, key=lambda m: 0 if m == ExportMode.MULTI_FILE else 1)

                if len(ordered_modes) > 1:
                    for mode_option in ordered_modes:
                        label_text = "Multi file" if mode_option == ExportMode.MULTI_FILE else "Single file"
                        combo.addItem(label_text, mode_option)
                    if preferred_mode in ordered_modes:
                        idx = combo.findData(preferred_mode)
                        if idx >= 0:
                            combo.setCurrentIndex(idx)
                    else:
                        combo.setCurrentIndex(0)
                    combo.setProperty("forced_mode", None)
                    current_mode = combo.currentData()
                    combo.setVisible(True)
                    label.setVisible(True)
                else:
                    only_mode = ordered_modes[0]
                    combo.setProperty("forced_mode", only_mode)
                    current_mode = only_mode
                    combo.setVisible(False)
                    label.setVisible(False)
                combo.setProperty("available_modes", tuple(ordered_modes))
                combo.blockSignals(False)
                _apply_default_naming(name_edit, current_mode)

            def _mode_changed(_, combo=mode_combo, name_edit=name_scheme_edit):
                """
                Callback for when the mode selection changes; update naming scheme accordingly.
                
                Args:
                    _: Ignored parameter (index).
                    combo: QComboBox for mode selection.
                    name_edit: QLineEdit for naming scheme.

                Returns:
                    None
                """
                mode_value = combo.currentData()
                if mode_value is None:
                    mode_value = combo.property("forced_mode") or ExportMode.MULTI_FILE
                _apply_default_naming(name_edit, mode_value)

            mode_combo.currentIndexChanged.connect(_mode_changed)
            fmt_combo.currentTextChanged.connect(_refresh_mode_controls)
            _refresh_mode_controls(fmt_combo.currentText())

            # Master checkbox (mutually exclusive)
            is_master_check = QtWidgets.QCheckBox(
                "Set as Master for Resampling")
            self.master_group.addButton(is_master_check)
            self.master_checkboxes[topic] = is_master_check

            # Processing selection
            available_processors = Processor.get_formats(topic_type)
            if available_processors:
                proc_chain_widget = ProcessorChainWidget(topic_type, available_processors)
            else:
                proc_chain_widget = None

            form_layout.addRow("Format", fmt_combo)
            form_layout.addRow(mode_label, mode_combo)
            form_layout.addRow("Output Directory", path_layout)
            form_layout.addRow("Subdirectory", rel_path_edit)
            form_layout.addRow("Naming", name_scheme_edit)
            form_layout.addRow("Master Topic", is_master_check)
            if proc_chain_widget:
                form_layout.addRow("Processors", proc_chain_widget)

            group_box.setLayout(form_layout)
            layout.addWidget(group_box)

            self.config_widgets[topic] = {
                "topic_type": topic_type,
                "format_combo": fmt_combo,
                "mode_combo": mode_combo,
                "mode_label": mode_label,
                "output_dir": abs_path_edit,
                "subdir": rel_path_edit,
                "naming": name_scheme_edit,
                "master_checkbox": is_master_check,
                "processor_chain": proc_chain_widget,
            }

        # ────────── Help ──────────
        note = QtWidgets.QLabel(
            "Naming and paths supports placeholders:\n"
            "  %name   → topic name without slashes\n"
            "  %index  → message index (starting from 0)\n"
            "  %Y, %m, %d, %H, %M, %S  → timestamp components from message header or receive-time if there is no header\n"
            "    (e.g. %Y-%m-%d_%H-%M-%S → 2025-04-14_12-30-00)"
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(note)

        self.setLayout(layout)
        self._sync_mode_changed(
            self.assoc_combo.currentText())  # initialize state

    def _sync_mode_changed(self, mode):
        """
        Enable or disable discard epsilon and master-topic checkboxes based on the selected resampling mode; set default eps for 'nearest'.

        Args:
            mode: Selected association strategy (str).

        Returns:
            None
        """
        enable = mode != "no resampling"
        self.eps_edit.setEnabled(enable)
        self.eps_hint.setVisible(mode == "nearest")
        for cb in self.master_checkboxes.values():
            cb.setEnabled(enable)

        # Enable first checkbox by default if resampling is enabled
        if enable and not any(cb.isChecked() for cb in self.master_checkboxes.values()):
            first_topic = next(iter(self.master_checkboxes.values()))
            first_topic.setChecked(True)

        # Default epsilon if nearest is selected
        if mode == "nearest" and not self.eps_edit.text().strip():
            self.eps_edit.setText("0.5")

    def get_export_config(self):
        """
        Collect and return the export configuration dict for each topic and the global configuration from UI widget values.

        Args:
            None

        Returns:
            tuple: (topics_config: dict, global_config: dict)
        """
        topics_config = {}
        global_config = {}

        global_config["cpu_percentage"] = float(self.cpu_slider.value())
        assoc_mode = self.assoc_combo.currentText()

        if assoc_mode != "no resampling":
            # validate sync config
            try:
                eps = float(self.eps_edit.text().strip())
            except ValueError:
                eps = None

            if assoc_mode == "nearest" and eps is None:
                raise ValueError(
                    "Discard Eps is required for 'nearest' association strategy.")

            master_topic = None
            for topic, cb in self.master_checkboxes.items():
                if cb.isChecked():
                    master_topic = topic
                    break

            if not master_topic:
                raise ValueError(
                    "One topic must be marked as Master when synchronization is enabled."
                )
            
            global_config["resample_config"] = {
                "master_topic": master_topic,
                "association": assoc_mode,
                "discard_eps": eps
            }

        for topic, widgets in self.config_widgets.items():
            fmt_combo = widgets["format_combo"]
            mode_combo = widgets["mode_combo"]
            abs_path = widgets["output_dir"]
            rel_path = widgets["subdir"]
            name = widgets["naming"]
            master_checkbox = widgets["master_checkbox"]
            proc_chain_widget = widgets.get("processor_chain")
            topic_type = widgets["topic_type"]

            base = abs_path.text().strip()
            sub = rel_path.text().strip().lstrip("/")

            mode_value = mode_combo.currentData() if mode_combo.isVisible() else mode_combo.property("forced_mode")
            if mode_value is None:
                mode_value = ExportMode.MULTI_FILE
            available_modes = mode_combo.property("available_modes") or tuple()
            fmt_value = fmt_combo.currentText()
            if mode_value == ExportMode.SINGLE_FILE and len(available_modes) > 1:
                fmt_value = f"{fmt_value}@single_file"

            topic_cfg = {
                "format": fmt_value,
                "path": base,
                "subfolder": sub,
                "naming": name.text().strip()
            }

            if proc_chain_widget:
                chain = proc_chain_widget.get_chain()
                if chain:
                    topic_cfg["processors"] = chain

            topics_config[topic] = topic_cfg

        return topics_config, global_config

    def set_export_config(self, config, global_config=None):
        """
        Populate UI widgets from a given export configuration and optional global settings, restoring formats, paths, naming, and processors.

        Args:
            config: Dict of per-topic export configuration.
            global_config: Optional dict of global settings.

        Returns:
            None
        """
        if global_config is not None and "cpu_percentage" in global_config:
            self.cpu_slider.setValue(global_config["cpu_percentage"])

        for topic, topic_cfg in config.items():
            widgets = self.config_widgets.get(topic)
            if not widgets:
                continue

            # Check if the topic exists in the bag
            all_topics_list = [
                topic for topics in self.all_topics.values() for topic in topics
            ]
            if topic not in all_topics_list:
                raise ValueError(
                    f"Topic '{topic}' not found in the bag. Cannot set export config properly."
                )

            fmt_combo = widgets["format_combo"]
            mode_combo = widgets["mode_combo"]
            abs_path_edit = widgets["output_dir"]
            rel_path_edit = widgets["subdir"]
            name_scheme_edit = widgets["naming"]
            is_master_check = widgets["master_checkbox"]
            proc_chain_widget = widgets.get("processor_chain")
            topic_type = widgets["topic_type"]

            fmt = topic_cfg.get("format", "")
            resolution = ExportRoutine.resolve(topic_type, fmt)
            if resolution is None:
                raise ValueError(
                    f"No export routine found for topic '{topic}' with format '{fmt}'."
                )
            _, canonical_fmt, mode = resolution
            mode_combo.setProperty("pending_mode", mode)
            idx = fmt_combo.findText(canonical_fmt)
            if idx >= 0:
                fmt_combo.setCurrentIndex(idx)
            else:
                fmt_combo.addItem(canonical_fmt)
                fmt_combo.setCurrentIndex(fmt_combo.count() - 1)
            # Set output path and subdirectory
            path = topic_cfg.get("path", "")
            subdir = topic_cfg.get("subfolder", "").strip("/")
            abs_path_edit.setText(path)
            rel_path_edit.setText(subdir)
            # Ensure the mode combo reflects the loaded configuration even if the format index did not change
            self._ensure_mode_selection(mode_combo, mode)
            # Set naming scheme
            name_scheme_edit.setText(topic_cfg.get("naming", ""))
            # Set master topic checkbox
            rcfg = topic_cfg.get("resample_config")
            if rcfg and rcfg.get("is_master"):
                is_master_check.setChecked(True)

            # Set processor and arguments
            if proc_chain_widget:
                chain_cfg = topic_cfg.get("processors")
                if not chain_cfg and topic_cfg.get("processor"):
                    chain_cfg = [{
                        "name": topic_cfg["processor"],
                        "args": topic_cfg.get("processor_args", {}),
                    }]
                normalized_chain = []
                for entry in chain_cfg or []:
                    if isinstance(entry, str):
                        normalized_chain.append({"name": entry, "args": {}})
                    elif isinstance(entry, dict):
                        name = entry.get("name")
                        if not name:
                            continue
                        args = entry.get("args", {}) or {}
                        if not isinstance(args, dict):
                            args = {}
                        normalized_chain.append({"name": name, "args": args})
                proc_chain_widget.set_chain(normalized_chain)

        # Set global synchronization settings if present
        for topic, topic_cfg in config.items():
            rcfg = topic_cfg.get("resample_config")
            if rcfg:
                assoc = rcfg.get("association", "no resampling")
                idx = self.assoc_combo.findText(assoc)
                if idx >= 0:
                    self.assoc_combo.setCurrentIndex(idx)
                if "discard_eps" in rcfg:
                    self.eps_edit.setText(str(rcfg["discard_eps"]))
                break

    @staticmethod
    def _ensure_mode_selection(mode_combo: QtWidgets.QComboBox, target_mode):
        """
        Make sure the mode combo box reflects the desired export mode, even if the format selection has not emitted a change signal.

        Args:
            mode_combo: The QComboBox controlling export mode.
            target_mode: The ExportMode that should be selected.
        """
        if mode_combo.count():
            for idx in range(mode_combo.count()):
                if mode_combo.itemData(idx) == target_mode:
                    if mode_combo.currentIndex() != idx:
                        mode_combo.setCurrentIndex(idx)
                    return
        # If the combo has no items (single forced mode), keep the forced mode metadata in sync
        mode_combo.setProperty("forced_mode", target_mode)

    def select_directory_and_apply(self, edit):
        """
        Prompt the user to select a directory and apply it to all output-directory fields.

        Args:
            edit: QLineEdit widget to update.

        Returns:
            None
        """
        directory = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Select Directory")
        if directory:
            for path_edit in self.all_path_edits:
                path_edit.setText(directory)

    def select_directory(self, edit):
        """
        Prompt the user to select a directory and set it for the given output-directory field.

        Args:
            edit: QLineEdit widget to update.

        Returns:
            None
        """
        directory = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Select Directory")
        if directory:
            edit.setText(directory)

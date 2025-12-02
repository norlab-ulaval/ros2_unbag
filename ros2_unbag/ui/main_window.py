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

import json
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Q_ARG, Qt

from ros2_unbag.core.bag_reader import BagReader
from ros2_unbag.core.exporter import Exporter
from ros2_unbag.ui.widgets.topic_list import TopicListWidget
from ros2_unbag.ui.widgets.topic_settings import TopicSettingsWidget
from ros2_unbag.ui.widgets.global_settings import GlobalSettingsWidget

__all__ = ["UnbagApp"]


class WorkerThread(QtCore.QThread):
    """
    Background worker thread for executing long-running tasks without blocking the UI.
    
    Executes a task function in a separate thread and emits signals on completion or error.
    
    Signals:
        finished (object): Emitted when task completes successfully, passes result
        error (Exception): Emitted when task raises an exception, passes the exception
    """
    
    finished = QtCore.Signal(object)
    error = QtCore.Signal(Exception)

    def __init__(self, task_fn, *args):
        """
        Initialize WorkerThread with a task function and arguments.

        Args:
            task_fn: Callable to execute in the thread.
            *args: Arguments to pass to the task function.

        Returns:
            None
        """
        super().__init__()
        self.task_fn = task_fn
        self.args = args

    def run(self):
        """
        Execute the task function with provided args, emit finished signal on success or error signal on exception.

        Args:
            None

        Returns:
            None
        """
        try:
            result = self.task_fn(*self.args)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(e)


class LoadingDialog(QtWidgets.QDialog):
    """
    Custom loading dialog with animated GIF and progress bar.
    
    Displays a modal dialog with a loading animation and progress indicator.
    Supports both determinate (0-100%) and indeterminate (pulsing) progress modes.
    """
    
    def __init__(self, text, parent=None, indeterminate=False):
        """
        Initialize the LoadingDialog with display text and progress mode.

        Args:
            text: Message text to display in the dialog.
            parent: Optional parent widget.
            indeterminate: If True, shows pulsing progress bar; if False, shows 0-100% progress.

        Returns:
            None
        """
        super().__init__(parent)
        self.setWindowTitle("Please Wait")
        self.setModal(True)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint)
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Text
        text_label = QtWidgets.QLabel(text)
        text_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        font = text_label.font()
        font.setPointSize(10)
        text_label.setFont(font)
        layout.addWidget(text_label)

        # GIF
        gif_label = QtWidgets.QLabel(self)
        gif_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        base_dir = Path(__file__).resolve().parent
        gif_path = base_dir / "assets/loading.gif"
        
        if gif_path.exists():
            gif_animation = QtGui.QMovie(str(gif_path))
            gif_animation.setScaledSize(QtCore.QSize(64, 64))  # Ensure it's not too huge
            gif_label.setMovie(gif_animation)
            gif_animation.start()
        else:
            gif_label.setText("Loading...")
            
        layout.addWidget(gif_label)

        # Progress Bar
        self.progress_bar = QtWidgets.QProgressBar(self)
        if indeterminate:
            self.progress_bar.setRange(0, 0)  # Indeterminate
            self.progress_bar.setTextVisible(False)
        else:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            
        layout.addWidget(self.progress_bar)
        
        # Fixed size for consistency
        self.setFixedSize(300, 200)

    @QtCore.Slot(int)
    def setValue(self, value):
        """
        Update the progress bar to the given integer value.

        Args:
            value: Integer progress value (0-100).

        Returns:
            None
        """
        self.progress_bar.setValue(value)


class UnbagApp(QtWidgets.QMainWindow):
    """
    Main application window for ros2_unbag GUI.
    
    Provides a 3-column interface for:
    - Left: Bag file loading and topic selection
    - Middle: Per-topic export settings configuration
    - Right: Global settings and export action
    
    Orchestrates the entire export workflow from bag loading through configuration
    to final export execution.
    """
    
    def __init__(self):
        """
        Initialize the UnbagApp main window and UI components.

        Args:
            None

        Returns:
            None
        """
        super().__init__()
        self.setWindowTitle("ros2 unbag")
        self.resize(1200, 800)
        self.setMinimumSize(1100, 700)

        self.bag_reader = None
        self.bag_path = None
        self.topics_config = {}  # topic -> config dict
        self.current_exporter = None

        self.init_ui()
        self.show_init_screen()

    def init_ui(self):
        """
        Build the main 3-column UI layout with topic list, settings, and global controls.

        Args:
            None

        Returns:
            None
        """
        # Central Widget
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        root_layout = QtWidgets.QVBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(8)

        # Top Bar
        top_bar = QtWidgets.QWidget()
        top_bar.setObjectName("topBar")
        top_bar.setFixedHeight(60)
        top_bar.setStyleSheet(
            "#topBar { background-color: #f4f6fb; border-bottom: 1px solid #d7dce4; }"
            "#topBar QLabel#title { color: #0f172a; font-size: 20px; font-weight: bold; font-family: 'Ubuntu', 'Ubuntu Bold', 'Ubuntu Medium', monospace; }"
            "QPushButton#headerLoadButton { background-color: #2563eb; color: #ffffff; border-radius: 18px; padding: 10px 18px; font-weight: 600; font-size: 14px; }"
            "QPushButton#headerLoadButton:hover { background-color: #1d4ed8; }"
            "QPushButton#headerLoadButton:pressed { background-color: #1e40af; }"
        )
        top_layout = QtWidgets.QHBoxLayout(top_bar)
        top_layout.setContentsMargins(12, 0, 12, 0)
        top_layout.setSpacing(10)
        icon_label = QtWidgets.QLabel()
        icon_path = Path(__file__).resolve().parent / "assets/badge.svg"
        if icon_path.exists():
            icon_pixmap = QtGui.QPixmap(str(icon_path)).scaled(50, 50, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            icon_label.setPixmap(icon_pixmap)
        top_layout.addWidget(icon_label)
        title_label = QtWidgets.QLabel("$ ros2 unbag")
        title_label.setObjectName("title")
        top_layout.addWidget(title_label)
        top_layout.addStretch()
        self.btn_load_bag = QtWidgets.QPushButton("Load Bag")
        self.btn_load_bag.setObjectName("headerLoadButton")
        self.btn_load_bag.clicked.connect(self.load_bag)
        top_layout.addWidget(self.btn_load_bag)
        root_layout.addWidget(top_bar)

        # Columns container
        columns_container = QtWidgets.QWidget()
        columns_layout = QtWidgets.QHBoxLayout(columns_container)
        columns_layout.setContentsMargins(10, 10, 10, 10)
        columns_layout.setSpacing(0)
        root_layout.addWidget(columns_container)
        splitter = QtWidgets.QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(6)
        columns_layout.addWidget(splitter)

        # 1. Left Column: Bag & Topics
        left_container = QtWidgets.QWidget()
        left_container.setObjectName("leftContainer")
        left_layout = QtWidgets.QVBoxLayout(left_container)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.setSpacing(10)
        left_container.setStyleSheet(
            "#leftContainer { background-color: #f7f9fc; border: 1px solid #d7dce4; border-radius: 6px; }"
            "#leftContainer QGroupBox { font-weight: bold; }"
        )
        
        # Bag Loading Area
        bag_group = QtWidgets.QGroupBox("Bag File")
        bag_layout = QtWidgets.QVBoxLayout(bag_group)
        self.lbl_bag_name = QtWidgets.QLabel("No bag loaded")
        self.lbl_bag_name.setWordWrap(True)
        bag_layout.addWidget(self.lbl_bag_name)
        left_layout.addWidget(bag_group)

        # Topic List
        self.topic_list = TopicListWidget()
        self.topic_list.topic_selected.connect(self.on_topic_selected)
        self.topic_list.topic_toggled.connect(self.on_topic_toggled)
        left_layout.addWidget(self.topic_list)
        
        # Config Buttons
        cfg_layout = QtWidgets.QHBoxLayout()
        self.btn_load_cfg = QtWidgets.QPushButton("Load Config")
        self.btn_load_cfg.clicked.connect(self.load_config_file)
        self.btn_save_cfg = QtWidgets.QPushButton("Save Config")
        self.btn_save_cfg.clicked.connect(self.save_config_file)
        cfg_layout.addWidget(self.btn_load_cfg)
        cfg_layout.addWidget(self.btn_save_cfg)
        left_layout.addLayout(cfg_layout)

        splitter.addWidget(left_container)

        # 2. Middle Column: Settings
        self.topic_settings = TopicSettingsWidget(Path.cwd())
        self.topic_settings.settings_changed.connect(self.on_settings_changed)
        
        # Wrap in scroll area
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.topic_settings)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setStyleSheet(
            "QScrollArea { border: 1px solid #d7dce4; border-radius: 6px; background: #ffffff; }"
            "QScrollArea > QWidget > QWidget { background: #ffffff; }"
        )
        splitter.addWidget(scroll)

        # 3. Right Column: Global & Summary
        self.global_settings = GlobalSettingsWidget()
        self.global_settings.export_clicked.connect(self.export_data)
        self.global_settings.setFixedWidth(300)
        global_wrapper = QtWidgets.QWidget()
        global_wrapper.setObjectName("globalContainer")
        global_wrapper.setFixedWidth(300)
        global_wrapper.setStyleSheet(
            "#globalContainer { background-color: #f7f9fc; border: 1px solid #d7dce4; border-radius: 6px; }"
            "#globalContainer QGroupBox { font-weight: bold; }"
        )
        global_layout = QtWidgets.QVBoxLayout(global_wrapper)
        global_layout.setContentsMargins(0, 0, 0, 0)
        global_layout.addWidget(self.global_settings)
        splitter.addWidget(global_wrapper)
        splitter.setSizes([350, 650, 300])

        # Status Bar
        self.status_bar = QtWidgets.QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_progress = QtWidgets.QProgressBar()
        self.status_progress.setRange(0, 0)  # indeterminate by default
        self.status_progress.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        self.status_progress.setTextVisible(False)
        self.status_progress.setVisible(False)
        self.status_bar.addPermanentWidget(self.status_progress, 1)  # stretch across remaining space
        self._update_status_progress_width()
        self.status_bar.showMessage("Ready")

    def show_init_screen(self):
        """
        Disable UI controls until a bag file is loaded.

        Args:
            None

        Returns:
            None
        """
        # Disable controls until bag is loaded
        self.topic_list.setEnabled(False)
        self.topic_settings.setEnabled(False)
        self.global_settings.setEnabled(False)
        self.btn_load_cfg.setEnabled(False)
        self.btn_save_cfg.setEnabled(False)

    def load_bag(self):
        """
        Prompt user to select a bag file, reset state, show loading dialog, and start background reader thread.

        Args:
            None

        Returns:
            None
        """
        bag_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open Bag File", "", "Bag Files (*.db3 *.mcap)")
        if not bag_path:
            return

        self.bag_path = Path(bag_path)
        self.lbl_bag_name.setText(self.bag_path.name)
        
        # Reset state
        self.topics_config = {}
        self.topic_settings.default_folder = self.bag_path.parent
        
        # Show loading in status bar
        self.status_progress.setRange(0, 0)  # indeterminate pulse
        self.status_progress.setVisible(True)
        self.status_bar.showMessage("Loading bag file...")

        self.worker = WorkerThread(lambda p: BagReader(p), bag_path)
        self.worker.finished.connect(self.on_bag_loaded)
        self.worker.error.connect(self.handle_bag_error)
        self.worker.start()

    def on_bag_loaded(self, reader):
        """
        Handle successful bag loading: close dialog, populate topic list, enable UI controls.

        Args:
            reader: BagReader instance for the loaded bag.

        Returns:
            None
        """
        self.status_progress.setVisible(False)
        self.bag_reader = reader
        
        # Populate Topic List
        topics = self.bag_reader.get_topics()
        counts = self.bag_reader.get_message_count()
        self.topic_list.load_topics(topics, counts)
        
        # Initialize default config for all topics
        # We don't pre-populate everything to save memory, but we can if needed.
        # For now, we'll generate config on the fly if missing when selecting.
        
        self.topic_list.setEnabled(True)
        self.topic_settings.setEnabled(True)
        self.global_settings.setEnabled(True)
        self.btn_load_cfg.setEnabled(True)
        self.btn_save_cfg.setEnabled(True)
        
        self.status_bar.showMessage(f"Loaded {self.bag_path.name}")
        self.update_summary()

    def resizeEvent(self, event):
        """
        Keep the status bar progress indicator at ~80% of the available width and anchored right.
        """
        super().resizeEvent(event)
        self._update_status_progress_width()

    def _update_status_progress_width(self):
        """
        Adjust the status bar progress width to roughly 80% of the status bar space.
        """
        if hasattr(self, "status_bar") and hasattr(self, "status_progress"):
            target = max(120, int(self.status_bar.width() * 0.8))
            self.status_progress.setFixedWidth(target)

    def handle_bag_error(self, e):
        """
        Handle errors that occur while loading a bag file.

        Args:
            e: Exception instance raised during bag loading.

        Returns:
            None
        """
        self.status_progress.setVisible(False)
        self.status_bar.showMessage("Failed to load bag")
        QtWidgets.QMessageBox.critical(self, "Error", str(e))

    def on_topic_selected(self, topic):
        """
        Handle topic selection from the list: load topic settings into the middle column.
        
        Finds the topic's message type, creates default config if needed, and displays
        the settings in the TopicSettingsWidget.

        Args:
            topic: Selected topic name string.

        Returns:
            None
        """
        # Get topic type
        topic_type = None
        for t_type, t_list in self.bag_reader.get_topics().items():
            if topic in t_list:
                topic_type = t_type
                break
        
        if not topic_type:
            return

        # Get or create config
        if topic not in self.topics_config:
            self.topics_config[topic] = {
                "path": str(self.bag_path.parent),
                "subfolder": "%name",
                "naming": "%name",
                "format": ""  # Will default in widget
            }
        
        self.topic_settings.set_topic(topic, topic_type, self.topics_config[topic])

    def on_settings_changed(self, topic, new_config):
        """
        Handle settings changes from TopicSettingsWidget and update internal config.

        Args:
            topic: Topic name string.
            new_config: Updated configuration dictionary.

        Returns:
            None
        """
        # Merge new config
        if topic not in self.topics_config:
            self.topics_config[topic] = {}
        self.topics_config[topic].update(new_config)

    def on_topic_toggled(self, topic, is_checked):
        """
        Handle topic checkbox toggle and update summary display.

        Args:
            topic: Topic name string.
            is_checked: Boolean indicating if topic is now checked.

        Returns:
            None
        """
        # Just update summary for now.
        # We could also auto-select the topic for editing if checked?
        # For now, keep selection and checking separate.
        self.update_summary()

    def update_summary(self):
        """
        Update the global settings summary with current topic selection counts.

        Args:
            None

        Returns:
            None
        """
        # Count checked items in topic list
        selected_count = 0
        selected_topics = []
        for topic, item in self.topic_list.topics.items():
            if self.topic_list.is_checked(topic):
                selected_count += 1
                selected_topics.append(topic)
        
        total_count = len(self.topic_list.topics)
        self.global_settings.update_summary(selected_count, total_count, selected_topics)

    def get_export_config(self):
        """
        Collect and validate export configuration for all selected topics.
        
        Gathers configuration from UI widgets for all checked topics, validates
        global settings (especially master topic selection for resampling), and
        applies default values where needed.

        Args:
            None

        Returns:
            tuple: (final_config dict, global_config dict) containing export settings
                  for selected topics and global configuration.
                  
        Raises:
            ValueError: If resampling is enabled but no master topic is selected,
                       or if other validation fails.
        """
        # Gather config for all SELECTED (checked) topics
        final_config = {}
        
        # First, ensure current settings in middle column are saved
        current_topic = self.topic_settings.current_topic
        if current_topic:
            self.topics_config[current_topic].update(self.topic_settings.get_config())

        global_cfg = self.global_settings.get_config()
        
        # Validate global config (master topic)
        if "resample_config" in global_cfg:
            master_topic = global_cfg["resample_config"].get("master_topic")
            # Build list of selected topics
            selected_topics = [
                topic for topic, item in self.topic_list.topics.items()
                if self.topic_list.is_checked(topic)
            ]
            if not master_topic or master_topic not in selected_topics:
                raise ValueError("Resampling enabled but no Master Topic selected among exported topics.")

        for topic, item in self.topic_list.topics.items():
            if self.topic_list.is_checked(topic):
                # Get config, use defaults if not visited
                cfg = self.topics_config.get(topic, {}).copy()
                
                if not cfg.get("format"):
                     # Find type
                    t_type = next((k for k, v in self.bag_reader.get_topics().items() if topic in v), None)
                    # Default format
                    from ros2_unbag.core.routines import ExportRoutine
                    formats = ExportRoutine.get_formats(t_type)
                    if formats:
                        cfg["format"] = formats[0]
                        # Also set default path/naming if empty
                        if "path" not in cfg: cfg["path"] = str(self.bag_path.parent)
                        if "naming" not in cfg: cfg["naming"] = "%name"
                if "subfolder" not in cfg or not cfg.get("subfolder"):
                    cfg["subfolder"] = "%name"
                
                final_config[topic] = cfg

        return final_config, global_cfg

    def export_data(self):
        """
        Initiate the export process: validate config, show progress dialog, start background export thread.

        Args:
            None

        Returns:
            None
        """
        try:
            config, global_config = self.get_export_config()
        except ValueError as e:
            QtWidgets.QMessageBox.critical(self, "Configuration Error", str(e))
            return

        self.setEnabled(False)
        self.wait_dialog = LoadingDialog("Exporting...", self, indeterminate=False)
        self.wait_dialog.show()
        self.wait_dialog.finished.connect(self.on_export_aborted)
        QtWidgets.QApplication.processEvents()

        self.worker = WorkerThread(self.run_export, self.bag_reader, config, global_config)
        self.worker.finished.connect(self.on_export_finished)
        self.worker.error.connect(self.handle_export_error)
        self.worker.start()

    def run_export(self, bag_reader, config, global_config):
        """
        Execute the export process in a background thread with progress updates.
        
        Creates an Exporter instance with a progress callback that updates the
        loading dialog, then runs the export.

        Args:
            bag_reader: BagReader instance.
            config: Per-topic export configuration dictionary.
            global_config: Global export settings dictionary.

        Returns:
            None
        """
        def progress(current, total):
            value = int((current / total) * 100)
            QtCore.QMetaObject.invokeMethod(
                self.wait_dialog, "setValue",
                QtCore.Qt.ConnectionType.QueuedConnection,
                Q_ARG(int, value)
            )
        
        self.current_exporter = Exporter(bag_reader, config, global_config, progress_callback=progress)
        self.current_exporter.run()

    def on_export_finished(self, _):
        """
        Handle successful export completion: close dialog, re-enable UI, show success message.

        Args:
            _: Unused result from worker thread.

        Returns:
            None
        """
        self.wait_dialog.close()
        self.setEnabled(True)
        QtWidgets.QMessageBox.information(self, "Done", "Export complete.")

    def on_export_aborted(self, _):
        """
        Handle export abortion: signal the exporter to cleanly stop all workers.

        Args:
            _: Unused dialog result.

        Returns:
            None
        """
        if self.current_exporter:
            self.current_exporter.abort_export()

    def handle_export_error(self, e):
        """
        Handle export errors: close dialog, re-enable UI, show error message.

        Args:
            e: Exception instance from the export process.

        Returns:
            None
        """
        self.wait_dialog.close()
        self.setEnabled(True)
        QtWidgets.QMessageBox.critical(self, "Export Error", str(e))

    def save_config_file(self):
        """
        Prompt for save path, collect all topic and global configs, and write to JSON file.

        Args:
            None

        Returns:
            None
        """
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save Config", str(Path.cwd() / "config.json"), "JSON (*.json)")
        if not file_path:
            return
        
        try:
            # Save ALL known config, or just selected?
            # Usually save all config so it can be reloaded.
            # But we also need global config.
            
            # Update current topic first
            current = self.topic_settings.current_topic
            if current:
                self.topics_config[current].update(self.topic_settings.get_config())
                
            full_config = self.topics_config.copy()
            full_config["__global__"] = self.global_settings.get_config()
            
            with open(file_path, "w") as f:
                json.dump(full_config, f, indent=2)
            
            self.status_bar.showMessage(f"Saved config to {file_path}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to save: {e}")

    def load_config_file(self):
        """
        Prompt for config file, load JSON, extract global settings, and populate UI with loaded configuration.

        Args:
            None

        Returns:
            None
        """
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Load Config", str(Path.cwd()), "JSON (*.json)")
        if not file_path:
            return
        if self.bag_reader is None:
            QtWidgets.QMessageBox.warning(self, "Load Bag First", "Please load a bag file before loading a config.")
            return
        
        try:
            with open(file_path, "r") as f:
                config = json.load(f)
            
            if "__global__" in config:
                self.global_settings.set_config(config.pop("__global__"))
            
            self.topics_config = config

            # Apply selection state based on loaded config
            missing_topics = []
            for topic, item in self.topic_list.topics.items():
                # block signals to avoid redundant updates while we toggle many items
                self.topic_list.set_checked(topic, topic in self.topics_config, block_signals=True)
            for topic in self.topics_config.keys():
                if topic not in self.topic_list.topics and topic != "__global__":
                    missing_topics.append(topic)
            self.update_summary()
            
            # Refresh current topic if selected
            current = self.topic_settings.current_topic
            if current and current in self.topics_config:
                # Need to re-set topic to refresh UI
                # We need type though.
                t_type = self.topic_settings.current_type
                self.topic_settings.set_topic(current, t_type, self.topics_config[current])
            
            if missing_topics:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Missing Topics",
                    "The following topics from the config are not in the loaded bag:\n"
                    + "\n".join(missing_topics)
                )
            self.status_bar.showMessage(f"Loaded config from {file_path}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to load: {e}")

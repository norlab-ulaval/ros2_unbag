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

from PySide6 import QtCore, QtWidgets, QtGui

__all__ = ["TopicListWidget"]


class TopicListWidget(QtWidgets.QWidget):
    """
    Widget for displaying and selecting ROS2 bag topics.
    
    This widget provides a list view of all topics in a bag file, allowing users to:
    - Select topics for export via checkboxes
    - Click on a topic to edit its settings
    - Filter topics by name
    - Bulk select/deselect all topics
    
    Signals:
        topic_selected (str): Emitted when a topic is clicked for editing, passes topic name
        topic_toggled (str, bool): Emitted when a topic's checkbox state changes, passes topic name and checked state
    """
    
    # Signal emitted when a topic is selected for editing (name)
    topic_selected = QtCore.Signal(str)
    # Signal emitted when a topic's export inclusion changes (name, is_checked)
    topic_toggled = QtCore.Signal(str, bool)

    def __init__(self, parent=None):
        """
        Initialize the TopicListWidget with UI components.

        Args:
            parent: Optional parent widget.

        Returns:
            None
        """
        super().__init__(parent)
        self.topics = {}  # topic_name -> QListWidgetItem mapping
        self.init_ui()

    def init_ui(self):
        """
        Build the topic list UI with header, filter, list widget, and selection buttons.

        Args:
            None

        Returns:
            None
        """
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header
        header_label = QtWidgets.QLabel("Topics")
        header_font = QtGui.QFont()
        header_font.setBold(True)
        header_font.setPointSize(12)
        header_label.setFont(header_font)
        layout.addWidget(header_label)

        # Search/Filter (Placeholder for now, or simple implementation)
        self.filter_edit = QtWidgets.QLineEdit()
        self.filter_edit.setPlaceholderText("Filter topics...")
        self.filter_edit.textChanged.connect(self.filter_topics)
        layout.addWidget(self.filter_edit)

        # List
        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.list_widget.itemClicked.connect(self.on_item_clicked)
        layout.addWidget(self.list_widget)

        # Bottom controls
        btn_layout = QtWidgets.QHBoxLayout()
        self.btn_select_all = QtWidgets.QPushButton("All")
        self.btn_select_all.clicked.connect(self.select_all)
        self.btn_select_none = QtWidgets.QPushButton("None")
        self.btn_select_none.clicked.connect(self.select_none)
        
        btn_layout.addWidget(self.btn_select_all)
        btn_layout.addWidget(self.btn_select_none)
        layout.addLayout(btn_layout)

    def load_topics(self, topics_dict, message_counts):
        """
        Load topics from a bag file into the list widget.
        
        Creates a custom list item for each topic with a checkbox, topic name,
        message type, and message count. Topics are sorted alphabetically.

        Args:
            topics_dict: Dictionary mapping message types to lists of topic names.
            message_counts: Dictionary mapping topic names to message counts.

        Returns:
            None
        """
        self.list_widget.clear()
        self.topics = {}
        
        # Flatten and sort
        all_topics = []
        for msg_type, topic_list in topics_dict.items():
            for topic in topic_list:
                all_topics.append((topic, msg_type))
        
        all_topics.sort(key=lambda x: x[0])

        for topic, msg_type in all_topics:
            count = message_counts.get(topic, 0)
            item = QtWidgets.QListWidgetItem()
            
            # Custom widget for the item to hold checkbox and text
            widget = QtWidgets.QWidget()
            h_layout = QtWidgets.QHBoxLayout(widget)
            h_layout.setContentsMargins(5, 2, 5, 2)
            
            checkbox = QtWidgets.QCheckBox()
            checkbox.setChecked(False) # Default off? Or on?
            checkbox.toggled.connect(lambda c, t=topic: self.topic_toggled.emit(t, c))
            
            # Label with topic name and count
            # We use a VBox for name and type/count to look nice
            text_layout = QtWidgets.QVBoxLayout()
            text_layout.setSpacing(0)
            
            name_label = QtWidgets.QLabel(topic)
            name_label.setStyleSheet("font-weight: bold;")
            
            info_label = QtWidgets.QLabel(f"{msg_type} • {count} msgs")
            info_label.setStyleSheet("color: gray; font-size: 10px;")
            
            text_layout.addWidget(name_label)
            text_layout.addWidget(info_label)
            
            h_layout.addWidget(checkbox)
            h_layout.addLayout(text_layout)
            h_layout.addStretch()
            
            item.setSizeHint(widget.sizeHint())
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, widget)
            
            # Store reference to checkbox to control it later
            item.setData(QtCore.Qt.UserRole, checkbox)
            self.topics[topic] = item

    def on_item_clicked(self, item):
        """
        Handle topic item click events and emit topic_selected signal.
        
        Finds the topic name corresponding to the clicked item and emits
        the topic_selected signal to notify listeners.

        Args:
            item: The QListWidgetItem that was clicked.

        Returns:
            None
        """
        for topic, it in self.topics.items():
            if it == item:
                self.topic_selected.emit(topic)
                break

    def filter_topics(self, text):
        """
        Filter the topic list based on search text.
        
        Hides topics that don't contain the search text (case-insensitive).

        Args:
            text: Search string to filter topics by.

        Returns:
            None
        """
        for topic, item in self.topics.items():
            item.setHidden(text.lower() not in topic.lower())

    def select_all(self):
        """
        Check all topic checkboxes to select all topics for export.

        Args:
            None

        Returns:
            None
        """
        for item in self.topics.values():
            cb = item.data(QtCore.Qt.UserRole)
            if cb:
                cb.setChecked(True)

    def select_none(self):
        """
        Uncheck all topic checkboxes to deselect all topics.

        Args:
            None

        Returns:
            None
        """
        for item in self.topics.values():
            cb = item.data(QtCore.Qt.UserRole)
            if cb:
                cb.setChecked(False)

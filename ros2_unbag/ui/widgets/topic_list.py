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
        self.topics = {}  # topic_name -> QTreeWidgetItem mapping
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
        self.tree_widget = QtWidgets.QTreeWidget()
        self.tree_widget.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.tree_widget.setHeaderLabels(["Topic", "Message Count"])
        self.tree_widget.setColumnCount(2)
        header = self.tree_widget.header()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        header.setStretchLastSection(False)
        self.tree_widget.setRootIsDecorated(False)
        self.tree_widget.setStyleSheet("QTreeWidget::item { height: 28px; }")
        self.tree_widget.itemClicked.connect(self.on_item_clicked)
        self.tree_widget.itemChanged.connect(self.on_item_changed)
        layout.addWidget(self.tree_widget)

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
        self.tree_widget.clear()
        self.topics = {}

        # Build grouped tree: message type -> topics
        header_font = QtGui.QFont(self.tree_widget.font())
        header_font.setBold(True)
        for msg_type in sorted(topics_dict.keys()):
            parent = QtWidgets.QTreeWidgetItem([msg_type, ""])
            parent.setFirstColumnSpanned(True)
            parent.setFlags(QtCore.Qt.ItemIsEnabled)
            parent.setFont(0, header_font)
            bg = QtGui.QColor("#f2f2f2")
            parent.setBackground(0, bg)
            parent.setBackground(1, bg)
            self.tree_widget.addTopLevelItem(parent)

            for topic in sorted(topics_dict[msg_type]):
                count = message_counts.get(topic, 0)
                child = QtWidgets.QTreeWidgetItem([topic, f"{count}"])
                child.setData(0, QtCore.Qt.UserRole, topic)
                child.setFlags(
                    QtCore.Qt.ItemIsEnabled
                    | QtCore.Qt.ItemIsSelectable
                    | QtCore.Qt.ItemIsUserCheckable
                )
                child.setCheckState(0, QtCore.Qt.Unchecked)
                child.setTextAlignment(1, QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                parent.addChild(child)
                self.topics[topic] = child

        self.tree_widget.expandAll()
        self.tree_widget.resizeColumnToContents(1)

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
        if item and item.parent():  # ignore group headers
            topic = item.data(0, QtCore.Qt.UserRole)
            if topic:
                self.topic_selected.emit(topic)

    def on_item_changed(self, item, column):
        """
        Emit topic toggled when a topic checkbox changes.
        """
        if not item or not item.parent() or column != 0:
            return
        topic = item.data(0, QtCore.Qt.UserRole)
        if topic:
            self.topic_toggled.emit(topic, item.checkState(0) == QtCore.Qt.Checked)

    def filter_topics(self, text):
        """
        Filter the topic list based on search text.
        
        Hides topics that don't contain the search text (case-insensitive).

        Args:
            text: Search string to filter topics by.

        Returns:
            None
        """
        lower = text.lower()
        for topic, item in self.topics.items():
            item.setHidden(lower not in topic.lower())

        # Hide parent groups that have no visible children
        for i in range(self.tree_widget.topLevelItemCount()):
            parent = self.tree_widget.topLevelItem(i)
            visible_children = any(not parent.child(j).isHidden() for j in range(parent.childCount()))
            parent.setHidden(not visible_children)

    def select_all(self):
        """
        Check all topic checkboxes to select all topics for export.

        Args:
            None

        Returns:
            None
        """
        for item in self.topics.values():
            item.setCheckState(0, QtCore.Qt.Checked)

    def select_none(self):
        """
        Uncheck all topic checkboxes to deselect all topics.

        Args:
            None

        Returns:
            None
        """
        for item in self.topics.values():
            item.setCheckState(0, QtCore.Qt.Unchecked)

    def is_checked(self, topic):
        """
        Return True if the given topic is currently checked.
        """
        item = self.topics.get(topic)
        return bool(item and item.checkState(0) == QtCore.Qt.Checked)

    def set_checked(self, topic, checked, *, block_signals=False):
        """
        Set the checked state of a topic row.
        """
        item = self.topics.get(topic)
        if not item:
            return
        if block_signals:
            self.tree_widget.blockSignals(True)
        item.setCheckState(0, QtCore.Qt.Checked if checked else QtCore.Qt.Unchecked)
        if block_signals:
            self.tree_widget.blockSignals(False)

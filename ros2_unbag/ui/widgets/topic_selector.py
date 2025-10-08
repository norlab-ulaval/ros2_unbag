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

__all__ = ["TopicSelector"]


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
                count_label = QtWidgets.QLabel(str(self.message_counts.get(topic, 0)) + " Messages")
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


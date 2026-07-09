# MIT License

# Copyright (c) 2026 Institute for Automotive Engineering (ika), RWTH Aachen University

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

import csv
import json
import sys
import types
from datetime import datetime
from pathlib import Path

import pytest
import yaml


def _install_dependency_stubs():
    # ros2_unbag.core.routines.__init__ eagerly imports every routine module
    # (pointcloud.py, image.py, video.py), so importing default.py in
    # isolation still requires stand-ins for their ROS/OpenCV dependencies -
    # mirrors the pattern in tests/test_pointcloud_exports.py.
    rosidl_runtime_py = types.ModuleType("rosidl_runtime_py")
    rosidl_runtime_py.message_to_ordereddict = lambda msg: {}
    rosidl_runtime_py.message_to_yaml = lambda msg: ""
    sys.modules.setdefault("rosidl_runtime_py", rosidl_runtime_py)

    sensor_msgs = types.ModuleType("sensor_msgs")
    sensor_msgs_msg = types.ModuleType("sensor_msgs.msg")
    class PointField:
        INT8 = 1
        UINT8 = 2
        INT16 = 3
        UINT16 = 4
        INT32 = 5
        UINT32 = 6
        FLOAT32 = 7
        FLOAT64 = 8

    sensor_msgs_msg.PointField = PointField
    sensor_msgs_msg.PointCloud2 = type("PointCloud2", (), {})
    sensor_msgs_msg.CompressedImage = type("CompressedImage", (), {})
    sensor_msgs_msg.Image = type("Image", (), {})
    sensor_msgs.msg = sensor_msgs_msg
    sys.modules.setdefault("sensor_msgs", sensor_msgs)
    sys.modules.setdefault("sensor_msgs.msg", sensor_msgs_msg)

    cv2 = types.ModuleType("cv2")
    cv2.VideoWriter_fourcc = lambda *args: 0
    cv2.VideoWriter = lambda *args, **kwargs: types.SimpleNamespace(
        isOpened=lambda: True,
        write=lambda frame: None,
        release=lambda: None,
    )
    sys.modules.setdefault("cv2", cv2)


_install_dependency_stubs()

from ros2_unbag.core.routines import default  # noqa: E402
from ros2_unbag.core.routines.base import ExportMetadata  # noqa: E402


# Mock message classes mirroring the pattern in test_master_timestamp.py
class MockStamp:
    def __init__(self, sec, nanosec):
        self.sec = sec
        self.nanosec = nanosec


class MockHeader:
    def __init__(self, sec, nanosec):
        self.stamp = MockStamp(sec, nanosec)


class MockMsg:
    def __init__(self, sec, nanosec):
        self.header = MockHeader(sec, nanosec)


class MockMsgNoStamp:
    pass


@pytest.fixture(autouse=True)
def stub_message_serialization(monkeypatch):
    monkeypatch.setattr(default, "message_to_ordereddict", lambda msg: {"value": 42})
    monkeypatch.setattr(default, "message_to_yaml", lambda msg: "value: 42")


def _read_csv_rows(path: Path):
    with open(path, newline="") as f:
        return list(csv.reader(f))


def test_multi_file_csv_headered_message_nonzero_stamp(tmp_path: Path):
    msg = MockMsg(sec=1700000005, nanosec=500)
    # bag_timestamp_ns intentionally different from the header stamp above
    metadata = ExportMetadata(index=0, max_index=0, bag_timestamp_ns=1_700_000_000_000_000_000)

    default.export_generic_multi_file(msg, tmp_path / "out", "table/csv", metadata)

    rows = _read_csv_rows((tmp_path / "out").with_suffix(".csv"))
    header, values = rows[0], rows[1]
    assert header[:2] == ["ros_time", "publisher_timestamp"]

    ros_time_str, publisher_ts_str = values[0], values[1]
    assert ros_time_str != ""
    assert publisher_ts_str != ""
    assert ros_time_str != publisher_ts_str

    expected_ros_time = str(datetime.fromtimestamp(metadata.bag_timestamp_ns * 1e-9))
    expected_publisher_ts = datetime.fromtimestamp(1700000005 + 500 * 1e-9).isoformat()
    assert ros_time_str == expected_ros_time
    assert publisher_ts_str == expected_publisher_ts


def test_stampless_message_ros_time_from_bag_publisher_timestamp_empty(tmp_path: Path):
    msg = MockMsgNoStamp()
    metadata = ExportMetadata(index=0, max_index=0, bag_timestamp_ns=1_700_000_000_000_000_000)

    default.export_generic_multi_file(msg, tmp_path / "out", "table/csv", metadata)

    rows = _read_csv_rows((tmp_path / "out").with_suffix(".csv"))
    header, values = rows[0], rows[1]
    assert header[:2] == ["ros_time", "publisher_timestamp"]

    expected_ros_time = str(datetime.fromtimestamp(metadata.bag_timestamp_ns * 1e-9))
    assert values[0] == expected_ros_time
    assert values[1] == ""


def test_husky_zero_stamp_exported_verbatim_not_suppressed(tmp_path: Path):
    # Real bug: driver never populates header.stamp, leaving sec=0, nanosec=0.
    # This must be exported verbatim as epoch, not treated as "missing".
    msg = MockMsg(sec=0, nanosec=0)
    metadata = ExportMetadata(index=0, max_index=0, bag_timestamp_ns=1_700_000_000_000_000_000)

    default.export_generic_multi_file(msg, tmp_path / "out", "table/csv", metadata)

    rows = _read_csv_rows((tmp_path / "out").with_suffix(".csv"))
    values = rows[1]
    assert values[1] == datetime.fromtimestamp(0).isoformat()
    assert values[1] != ""


def test_serialize_json_shape_with_publisher_timestamp():
    ros_time = datetime.fromtimestamp(1_700_000_000)
    publisher_timestamp = datetime.fromtimestamp(1_700_000_005)

    line = default._serialize_message_with_timestamp(object(), "json", ros_time, publisher_timestamp)
    parsed = json.loads("{" + line + "}")

    assert set(parsed.keys()) == {ros_time.isoformat()}
    entry = parsed[ros_time.isoformat()]
    assert entry["value"] == 42
    assert entry["publisher_timestamp"] == publisher_timestamp.isoformat()


def test_serialize_json_shape_publisher_timestamp_null():
    ros_time = datetime.fromtimestamp(1_700_000_000)

    line = default._serialize_message_with_timestamp(object(), "json", ros_time, None)
    parsed = json.loads("{" + line + "}")

    entry = parsed[ros_time.isoformat()]
    assert entry["publisher_timestamp"] is None


def test_serialize_yaml_shape_round_trips():
    ros_time = datetime.fromtimestamp(1_700_000_000)
    publisher_timestamp = datetime.fromtimestamp(1_700_000_005)

    line = default._serialize_message_with_timestamp(object(), "yaml", ros_time, publisher_timestamp)
    parsed = yaml.safe_load(line)

    # YAML auto-parses unquoted ISO-8601-looking scalars into datetime objects.
    entry = parsed[ros_time] if ros_time in parsed else parsed[str(ros_time)]
    assert entry["publisher_timestamp"] == publisher_timestamp
    assert entry["value"] == 42


def test_single_file_multi_message_append_shares_header(tmp_path: Path):
    msg0 = MockMsg(sec=1700000000, nanosec=0)
    msg1 = MockMsg(sec=1700000010, nanosec=0)
    metadata0 = ExportMetadata(index=0, max_index=1, bag_timestamp_ns=1_700_000_000_000_000_000)
    metadata1 = ExportMetadata(index=1, max_index=1, bag_timestamp_ns=1_700_000_010_000_000_000)

    default.export_generic_single_file(msg0, tmp_path / "out", "table/csv", metadata0)
    default.export_generic_single_file(msg1, tmp_path / "out", "table/csv", metadata1)

    rows = _read_csv_rows((tmp_path / "out").with_suffix(".csv"))
    assert len(rows) == 3
    assert rows[0][:2] == ["ros_time", "publisher_timestamp"]
    assert rows[1][:2] != rows[2][:2]

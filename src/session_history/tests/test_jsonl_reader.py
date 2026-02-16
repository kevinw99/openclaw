"""Tests for JSONL reader"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from session_history.parser.jsonl_reader import JsonlReader


FIXTURE_DIR = Path(__file__).parent / "fixtures"
SAMPLE_SESSION = str(FIXTURE_DIR / "sample_session.jsonl")


def test_read_session():
    reader = JsonlReader(exclude_thinking=True)
    session = reader.read_session(SAMPLE_SESSION)

    assert session.session_id == "test-session-001"
    assert session.message_count > 0
    assert session.start_time
    assert session.end_time


def test_message_types():
    reader = JsonlReader(exclude_thinking=True)
    session = reader.read_session(SAMPLE_SESSION)

    user_msgs = [m for m in session.messages if m.role == "user"]
    assistant_msgs = [m for m in session.messages if m.role == "assistant"]

    assert len(user_msgs) >= 2
    assert len(assistant_msgs) >= 2


def test_tool_use_extraction():
    reader = JsonlReader(exclude_thinking=True)
    session = reader.read_session(SAMPLE_SESSION)

    tool_msgs = [m for m in session.messages if m.tool_names]
    assert len(tool_msgs) >= 2

    all_paths = []
    for msg in tool_msgs:
        all_paths.extend(msg.file_paths)
    assert any("specs/01_" in p for p in all_paths)
    assert any("data_processor" in p for p in all_paths)


def test_text_content():
    reader = JsonlReader(exclude_thinking=True)
    session = reader.read_session(SAMPLE_SESSION)

    user_msgs = [m for m in session.messages if m.role == "user"]
    assert "Spec #01" in user_msgs[0].text_content or "01" in user_msgs[0].text_content


def test_line_numbers():
    reader = JsonlReader(exclude_thinking=True)
    session = reader.read_session(SAMPLE_SESSION)

    line_numbers = [m.line_number for m in session.messages]
    assert line_numbers == sorted(line_numbers)


def test_session_to_dict():
    reader = JsonlReader(exclude_thinking=True)
    session = reader.read_session(SAMPLE_SESSION)

    d = session.to_dict()
    assert d["session_id"] == "test-session-001"
    assert d["message_count"] > 0
    assert "user_messages" in d
    assert "assistant_messages" in d


if __name__ == "__main__":
    test_read_session()
    test_message_types()
    test_tool_use_extraction()
    test_text_content()
    test_line_numbers()
    test_session_to_dict()
    print("All JSONL reader tests passed!")

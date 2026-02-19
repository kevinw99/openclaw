"""Tests for generators"""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from session_history.parser.jsonl_reader import JsonlReader
from session_history.generator.html_generator import HtmlGenerator
from session_history.generator.markdown_generator import MarkdownGenerator
from session_history.generator.index_generator import IndexGenerator
from session_history.models.category import Entity, EntityType
from session_history.models.index import EntityIndex, SessionReference

FIXTURE_DIR = Path(__file__).parent / "fixtures"
SAMPLE_SESSION = str(FIXTURE_DIR / "sample_session.jsonl")


def test_html_generation():
    reader = JsonlReader(exclude_thinking=True)
    session = reader.read_session(SAMPLE_SESSION)

    gen = HtmlGenerator(exclude_thinking=True)
    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir) / "test.html"
        gen.generate_from_sessions([session], "Test Replay", output)

        assert output.exists()
        content = output.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content
        assert "Test Replay" in content
        assert "test-session-001" in content
        assert "background-color: #1e1e1e" in content  # dark theme


def test_markdown_generation():
    reader = JsonlReader(exclude_thinking=True)
    session = reader.read_session(SAMPLE_SESSION)

    gen = MarkdownGenerator(exclude_thinking=True)
    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir) / "test.md"
        gen.generate_from_sessions([session], "Test Replay", output)

        assert output.exists()
        content = output.read_text(encoding="utf-8")
        assert "# Test Replay" in content
        assert "Session:" in content


def test_index_generation():
    entity = Entity(
        entity_type=EntityType.SPEC,
        name="P12_内部数据收集系统",
        display_name="Spec P12",
        directory="规格/P12_内部数据收集系统",
        history_dir="规格/P12_内部数据收集系统/history",
    )

    ref = SessionReference(
        session_id="test-session-001",
        file_path="/path/to/session.jsonl",
        confidence=0.85,
        start_time="2026-02-01T10:00:00",
        message_count=10,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        gen = IndexGenerator(Path(tmpdir))
        index = gen.build_entity_index(entity, [ref])
        gen.write_entity_index(entity, index)

        index_path = Path(tmpdir) / "规格" / "P12_内部数据收集系统" / "history" / "sessions-index.json"
        assert index_path.exists()

        data = json.loads(index_path.read_text(encoding="utf-8"))
        assert data["entity_id"] == "spec:P12_内部数据收集系统"
        assert data["session_count"] == 1
        assert data["sessions"][0]["confidence"] == 0.85


def test_master_index():
    from session_history.models.category import SessionClassification, EntityMatch

    entity = Entity(
        entity_type=EntityType.SPEC,
        name="test",
        display_name="Test Entity",
        directory="test",
        history_dir="test/history",
    )

    classification = SessionClassification(
        session_id="test-001",
        file_path="/path/to/test.jsonl",
        message_count=5,
    )
    classification.matches.append(EntityMatch(
        entity=entity,
        confidence=0.8,
    ))

    with tempfile.TemporaryDirectory() as tmpdir:
        gen = IndexGenerator(Path(tmpdir))
        output_dir = Path(tmpdir) / "history"
        gen.write_master_index([classification], output_dir)

        master = output_dir / "all-sessions.json"
        assert master.exists()

        data = json.loads(master.read_text(encoding="utf-8"))
        assert data["total_sessions"] == 1
        assert data["categorized"] == 1


if __name__ == "__main__":
    test_html_generation()
    test_markdown_generation()
    test_index_generation()
    test_master_index()
    print("All generator tests passed!")

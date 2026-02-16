"""Tests for ReadableReplayGenerator"""

import tempfile
import unittest
from pathlib import Path

from session_history.models.session import ContentBlock, Session, SessionMessage
from session_history.models.index import EntityIndex, SessionReference
from session_history.generator.readable_replay_generator import ReadableReplayGenerator
from session_history.config.settings import Settings


def _make_test_settings():
    s = Settings.__new__(Settings)
    s.project_root = Path("/Users/testuser/AI/base")
    s.sessions_dir = Path("/tmp/sessions")
    s.history_root = "session-history"
    s.classification_threshold = 0.15
    s.signal_weights = {"file_path": 0.50, "text_pattern": 0.35, "keyword": 0.15}
    s.exclude_thinking = True
    s.exclude_sidechains = True
    s.scan_state_file = ".scan-state.json"
    s.entity_dirs = {"spec": "specs", "source": "src", "research": "research", "knowledge": "docs", "tool": "scripts"}
    s.spec_pattern = r"(\d+)_(.+)"
    s.spec_display = "Spec {num}: {desc}"
    s.restricted_spec_dir = None
    s.legacy_aliases = {}
    s.skip_files = {}
    return s


def _make_msg(role, msg_type, blocks=None, text="", timestamp="", uuid="u1"):
    content_blocks = blocks or []
    if text and not blocks:
        content_blocks = [ContentBlock(block_type="text", text=text)]
    return SessionMessage(
        uuid=uuid, parent_uuid=None, msg_type=msg_type, role=role,
        content_blocks=content_blocks, timestamp=timestamp,
        session_id="test-session", line_number=0,
    )


class TestReadableReplayGenerator(unittest.TestCase):
    def setUp(self):
        self.settings = _make_test_settings()
        self.gen = ReadableReplayGenerator(settings=self.settings)

    def test_build_filename(self):
        """Filename format: person_YYYY-MM-DD_HH-MM.md"""
        session = Session(
            session_id="abc123", file_path="/tmp/test.jsonl",
            start_time="2026-02-03T02:17:00", end_time="2026-02-03T03:39:00",
        )
        filename = self.gen._build_filename("testuser", session)
        self.assertEqual(filename, "testuser_2026-02-03_02-17.md")

    def test_build_filename_no_time(self):
        """No timestamp falls back to session_id."""
        session = Session(session_id="abc12345", file_path="/tmp/test.jsonl")
        filename = self.gen._build_filename("testuser", session)
        self.assertEqual(filename, "testuser_abc12345.md")

    def test_render_turn_basic(self):
        """Basic turn rendering."""
        from session_history.models.turn import Turn
        turn = Turn(
            turn_number=1,
            timestamp="2026-02-03T02:17:00",
            title="Design the data pipeline",
            user_prompt="Design the data pipeline",
            assistant_response="I designed a 3-stage pipeline...",
            tool_counts={"Read": 2, "Write": 1},
            tool_narrative="specs/01_data-pipeline/design.md",
        )
        lines = self.gen._render_turn(turn)
        content = "\n".join(lines)

        self.assertIn("### 02:17 - Design the data pipeline", content)
        self.assertIn("**Prompt:**", content)
        self.assertIn("Design the data pipeline", content)
        self.assertIn("**Result:**", content)
        self.assertIn("3-stage pipeline", content)
        self.assertIn("Read (2)", content)
        self.assertIn("Write (1)", content)

    def test_render_turn_long_prompt(self):
        """Long prompts use collapsible."""
        from session_history.models.turn import Turn
        long_text = "Line " + "x" * 600
        turn = Turn(
            turn_number=1,
            timestamp="2026-02-03T02:17:00",
            title="Line xxxx...",
            user_prompt=long_text,
            assistant_response="Done",
            is_long_prompt=True,
        )
        lines = self.gen._render_turn(turn)
        content = "\n".join(lines)

        self.assertIn("<details>", content)
        self.assertIn("Full prompt", content)

    def test_render_turn_no_response(self):
        """No text response shows tools only."""
        from session_history.models.turn import Turn
        turn = Turn(
            turn_number=1,
            timestamp="2026-02-03T02:17:00",
            title="Do something",
            user_prompt="Do something",
            assistant_response="",
            tool_counts={"Bash": 3},
        )
        lines = self.gen._render_turn(turn)
        content = "\n".join(lines)

        self.assertIn("tools only", content)

    def test_write_session_file(self):
        """Write complete session file."""
        from session_history.models.turn import Turn
        turns = [
            Turn(
                turn_number=1,
                timestamp="2026-02-03T02:17:00",
                title="First question",
                user_prompt="First question",
                assistant_response="First answer",
            ),
            Turn(
                turn_number=2,
                timestamp="2026-02-03T02:30:00",
                title="Second question",
                user_prompt="Second question",
                assistant_response="Second answer",
                tool_counts={"Read": 1},
            ),
        ]

        session = Session(
            session_id="test123", file_path="/tmp/test.jsonl",
            start_time="2026-02-03T02:17:00", end_time="2026-02-03T03:00:00",
            messages=[_make_msg("user", "user", text="x")],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_replay.md"
            self.gen._write_session_file(
                output_path, "Spec 01: data-pipeline",
                session, "testuser", turns,
            )

            content = output_path.read_text(encoding="utf-8")

            self.assertIn("# Spec 01: data-pipeline - Session Replay", content)
            self.assertIn("Person: testuser", content)
            self.assertIn("Turns: 2", content)
            self.assertIn("### 02:17 - First question", content)
            self.assertIn("### 02:30 - Second question", content)
            self.assertIn("First answer", content)
            self.assertIn("Second answer", content)


class TestReplayIndexGenerator(unittest.TestCase):
    def test_write_entity_index(self):
        """Generate replay-index.md."""
        from session_history.generator.replay_index_generator import ReplayIndexGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            history_dir = Path(tmpdir)
            replay_dir = history_dir / "replay"
            replay_dir.mkdir()

            files = [
                replay_dir / "testuser_2026-02-03_02-17.md",
                replay_dir / "testuser_2026-02-04_07-58.md",
            ]
            for f in files:
                f.write_text("# test", encoding="utf-8")

            entity_index = EntityIndex(
                entity_id="spec:01_data-pipeline",
                entity_type="spec",
                display_name="Spec 01: data-pipeline",
                directory="specs/01_data-pipeline",
            )

            gen = ReplayIndexGenerator()
            gen.write_entity_index(entity_index, history_dir, files)

            index_path = history_dir / "replay-index.md"
            self.assertTrue(index_path.exists())

            content = index_path.read_text(encoding="utf-8")
            self.assertIn("Replay Index", content)
            self.assertIn("testuser_2026-02-03_02-17.md", content)
            self.assertIn("testuser_2026-02-04_07-58.md", content)


if __name__ == "__main__":
    unittest.main()

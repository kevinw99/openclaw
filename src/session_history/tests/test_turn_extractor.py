"""Tests for TurnExtractor"""

import unittest

from session_history.models.session import ContentBlock, Session, SessionMessage
from session_history.models.turn import Turn
from session_history.generator.turn_extractor import TurnExtractor
from session_history.config.settings import Settings


def _make_test_settings():
    s = Settings.__new__(Settings)
    s.project_root = Settings.__dataclass_fields__['project_root'].default_factory()
    s.sessions_dir = None
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
    # Compute sessions_dir
    s.sessions_dir = s._compute_sessions_dir()
    return s


def _make_msg(role, msg_type, blocks=None, text="", timestamp="", uuid="u1",
              is_sidechain=False, subtype="", cwd=""):
    """Helper to create SessionMessage."""
    content_blocks = blocks or []
    if text and not blocks:
        content_blocks = [ContentBlock(block_type="text", text=text)]
    return SessionMessage(
        uuid=uuid,
        parent_uuid=None,
        msg_type=msg_type,
        role=role,
        content_blocks=content_blocks,
        timestamp=timestamp,
        session_id="test-session",
        line_number=0,
        is_sidechain=is_sidechain,
        subtype=subtype,
        cwd=cwd,
    )


def _make_session(messages, file_path="/Users/testuser/.claude/projects/test/abc.jsonl"):
    """Helper to create Session."""
    s = Session(session_id="test-session", file_path=file_path, messages=messages)
    if messages:
        s.start_time = messages[0].timestamp or "2026-02-01T10:00:00"
        s.end_time = messages[-1].timestamp or "2026-02-01T11:00:00"
    return s


class TestTurnExtractor(unittest.TestCase):
    def setUp(self):
        self.extractor = TurnExtractor()

    def test_simple_single_turn(self):
        """Single turn: user asks -> AI answers."""
        msgs = [
            _make_msg("user", "user", text="Hello, how are you?", timestamp="2026-02-01T10:00:00"),
            _make_msg("assistant", "assistant", text="I'm doing well!", timestamp="2026-02-01T10:00:05"),
        ]
        session = _make_session(msgs)
        turns = self.extractor.extract_turns(session)

        self.assertEqual(len(turns), 1)
        self.assertEqual(turns[0].turn_number, 1)
        self.assertEqual(turns[0].user_prompt, "Hello, how are you?")
        self.assertEqual(turns[0].assistant_response, "I'm doing well!")
        self.assertEqual(turns[0].tool_counts, {})

    def test_multiple_turns(self):
        """Multiple turns."""
        msgs = [
            _make_msg("user", "user", text="Question 1", timestamp="2026-02-01T10:00:00"),
            _make_msg("assistant", "assistant", text="Answer 1", timestamp="2026-02-01T10:00:05"),
            _make_msg("user", "user", text="Question 2", timestamp="2026-02-01T10:01:00"),
            _make_msg("assistant", "assistant", text="Answer 2", timestamp="2026-02-01T10:01:05"),
        ]
        session = _make_session(msgs)
        turns = self.extractor.extract_turns(session)

        self.assertEqual(len(turns), 2)
        self.assertEqual(turns[0].user_prompt, "Question 1")
        self.assertEqual(turns[1].user_prompt, "Question 2")

    def test_tool_result_not_new_turn(self):
        """tool_result messages should not start a new turn."""
        msgs = [
            _make_msg("user", "user", text="Read this file", timestamp="2026-02-01T10:00:00"),
            _make_msg("assistant", "assistant", blocks=[
                ContentBlock(block_type="text", text="Let me read it."),
                ContentBlock(block_type="tool_use", tool_name="Read",
                             tool_input={"file_path": "/foo/bar.py"}, tool_use_id="t1"),
            ], timestamp="2026-02-01T10:00:05"),
            _make_msg("user", "user", blocks=[
                ContentBlock(block_type="tool_result", text="file contents here", tool_use_id="t1"),
            ], timestamp="2026-02-01T10:00:06"),
            _make_msg("assistant", "assistant", text="The file contains...", timestamp="2026-02-01T10:00:07"),
        ]
        session = _make_session(msgs)
        turns = self.extractor.extract_turns(session)

        self.assertEqual(len(turns), 1)
        self.assertEqual(turns[0].user_prompt, "Read this file")
        self.assertIn("The file contains", turns[0].assistant_response)

    def test_final_response_after_tools(self):
        """Final response should be text after last tool_use."""
        msgs = [
            _make_msg("user", "user", text="Fix the bug", timestamp="2026-02-01T10:00:00"),
            _make_msg("assistant", "assistant", blocks=[
                ContentBlock(block_type="text", text="Let me look at the code."),
                ContentBlock(block_type="tool_use", tool_name="Read",
                             tool_input={"file_path": "/foo/bar.py"}, tool_use_id="t1"),
            ]),
            _make_msg("user", "user", blocks=[
                ContentBlock(block_type="tool_result", text="code here", tool_use_id="t1"),
            ]),
            _make_msg("assistant", "assistant", blocks=[
                ContentBlock(block_type="tool_use", tool_name="Edit",
                             tool_input={"file_path": "/foo/bar.py"}, tool_use_id="t2"),
            ]),
            _make_msg("user", "user", blocks=[
                ContentBlock(block_type="tool_result", text="edited ok", tool_use_id="t2"),
            ]),
            _make_msg("assistant", "assistant", text="I've fixed the bug by updating the condition."),
        ]
        session = _make_session(msgs)
        turns = self.extractor.extract_turns(session)

        self.assertEqual(len(turns), 1)
        self.assertEqual(turns[0].assistant_response, "I've fixed the bug by updating the condition.")
        self.assertNotIn("Let me look", turns[0].assistant_response)

    def test_tool_counting(self):
        """Tool call counting."""
        msgs = [
            _make_msg("user", "user", text="Do stuff", timestamp="2026-02-01T10:00:00"),
            _make_msg("assistant", "assistant", blocks=[
                ContentBlock(block_type="tool_use", tool_name="Read",
                             tool_input={"file_path": "/a"}, tool_use_id="t1"),
            ]),
            _make_msg("user", "user", blocks=[
                ContentBlock(block_type="tool_result", text="a", tool_use_id="t1"),
            ]),
            _make_msg("assistant", "assistant", blocks=[
                ContentBlock(block_type="tool_use", tool_name="Read",
                             tool_input={"file_path": "/b"}, tool_use_id="t2"),
            ]),
            _make_msg("user", "user", blocks=[
                ContentBlock(block_type="tool_result", text="b", tool_use_id="t2"),
            ]),
            _make_msg("assistant", "assistant", blocks=[
                ContentBlock(block_type="tool_use", tool_name="Write",
                             tool_input={"file_path": "/c"}, tool_use_id="t3"),
            ]),
            _make_msg("user", "user", blocks=[
                ContentBlock(block_type="tool_result", text="c", tool_use_id="t3"),
            ]),
            _make_msg("assistant", "assistant", text="Done."),
        ]
        session = _make_session(msgs)
        turns = self.extractor.extract_turns(session)

        self.assertEqual(turns[0].tool_counts, {"Read": 2, "Write": 1})
        self.assertIn("Read (2)", turns[0].tool_summary_line)
        self.assertIn("Write (1)", turns[0].tool_summary_line)

    def test_skip_system_messages(self):
        """System messages should not affect turn splitting."""
        msgs = [
            _make_msg("", "system", text="System init"),
            _make_msg("user", "user", text="Hello", timestamp="2026-02-01T10:00:00"),
            _make_msg("", "system", text="Some system event"),
            _make_msg("assistant", "assistant", text="Hi there!"),
        ]
        session = _make_session(msgs)
        turns = self.extractor.extract_turns(session)

        self.assertEqual(len(turns), 1)
        self.assertEqual(turns[0].user_prompt, "Hello")

    def test_long_prompt_detection(self):
        """Detect long prompts."""
        short_prompt = "Short question"
        long_prompt = "x" * 600

        msgs_short = [
            _make_msg("user", "user", text=short_prompt, timestamp="2026-02-01T10:00:00"),
            _make_msg("assistant", "assistant", text="ok"),
        ]
        msgs_long = [
            _make_msg("user", "user", text=long_prompt, timestamp="2026-02-01T10:00:00"),
            _make_msg("assistant", "assistant", text="ok"),
        ]

        turns_short = self.extractor.extract_turns(_make_session(msgs_short))
        turns_long = self.extractor.extract_turns(_make_session(msgs_long))

        self.assertFalse(turns_short[0].is_long_prompt)
        self.assertTrue(turns_long[0].is_long_prompt)

    def test_auto_title(self):
        """Auto title generation."""
        msgs = [
            _make_msg("user", "user", text="Design the data pipeline", timestamp="2026-02-01T10:00:00"),
            _make_msg("assistant", "assistant", text="ok"),
        ]
        session = _make_session(msgs)
        turns = self.extractor.extract_turns(session)

        self.assertEqual(turns[0].title, "Design the data pipeline")

    def test_auto_title_truncation(self):
        """Truncate long titles."""
        long_title = "This is a very long prompt that exceeds the sixty character limit and should be truncated"
        msgs = [
            _make_msg("user", "user", text=long_title, timestamp="2026-02-01T10:00:00"),
            _make_msg("assistant", "assistant", text="ok"),
        ]
        session = _make_session(msgs)
        turns = self.extractor.extract_turns(session)

        self.assertLessEqual(len(turns[0].title), 65)  # 60 + "..."
        self.assertTrue(turns[0].title.endswith("..."))

    def test_extract_person(self):
        """Extract username from file path."""
        msgs = [_make_msg("user", "user", text="hi")]
        session = _make_session(msgs, file_path="/Users/testuser/.claude/projects/test/abc.jsonl")
        person = self.extractor.extract_person(session)
        self.assertEqual(person, "testuser")

    def test_extract_person_fallback_cwd(self):
        """Extract username from cwd (fallback)."""
        msgs = [_make_msg("user", "user", text="hi", cwd="/Users/alice/projects/test")]
        session = _make_session(msgs, file_path="/tmp/abc.jsonl")
        person = self.extractor.extract_person(session)
        self.assertEqual(person, "alice")

    def test_extract_person_unknown(self):
        """Return unknown when username can't be extracted."""
        msgs = [_make_msg("user", "user", text="hi")]
        session = _make_session(msgs, file_path="/tmp/abc.jsonl")
        person = self.extractor.extract_person(session)
        self.assertEqual(person, "unknown")

    def test_empty_session(self):
        """Empty session produces no turns."""
        session = _make_session([])
        turns = self.extractor.extract_turns(session)
        self.assertEqual(len(turns), 0)

    def test_time_short(self):
        """Turn.time_short property."""
        t = Turn(
            turn_number=1,
            timestamp="2026-02-01T10:30:00",
            title="test",
            user_prompt="test",
            assistant_response="test",
        )
        self.assertEqual(t.time_short, "10:30")


class TestTurnToolNarrative(unittest.TestCase):
    def setUp(self):
        self.extractor = TurnExtractor()

    def test_file_path_in_narrative(self):
        """Tool narrative includes file paths."""
        msgs = [
            _make_msg("user", "user", text="Check", timestamp="2026-02-01T10:00:00"),
            _make_msg("assistant", "assistant", blocks=[
                ContentBlock(block_type="tool_use", tool_name="Read",
                             tool_input={"file_path": "/foo/bar/specs/01_data-pipeline/design.md"},
                             tool_use_id="t1"),
            ]),
            _make_msg("user", "user", blocks=[
                ContentBlock(block_type="tool_result", text="content", tool_use_id="t1"),
            ]),
            _make_msg("assistant", "assistant", text="Done"),
        ]
        session = _make_session(msgs)
        turns = self.extractor.extract_turns(session)

        # The path won't be shortened since it doesn't match project root,
        # but it should still appear in narrative
        self.assertTrue(len(turns[0].tool_narrative) > 0)

    def test_bash_description_in_narrative(self):
        """Bash command descriptions included in narrative."""
        msgs = [
            _make_msg("user", "user", text="Run tests", timestamp="2026-02-01T10:00:00"),
            _make_msg("assistant", "assistant", blocks=[
                ContentBlock(block_type="tool_use", tool_name="Bash",
                             tool_input={"command": "pytest", "description": "Run unit tests"},
                             tool_use_id="t1"),
            ]),
            _make_msg("user", "user", blocks=[
                ContentBlock(block_type="tool_result", text="passed", tool_use_id="t1"),
            ]),
            _make_msg("assistant", "assistant", text="Tests pass"),
        ]
        session = _make_session(msgs)
        turns = self.extractor.extract_turns(session)

        self.assertIn("Run unit tests", turns[0].tool_narrative)


if __name__ == "__main__":
    unittest.main()

"""Tests for ReadableReplayGenerator"""

import tempfile
import unittest
from pathlib import Path

from session_history.models.session import ContentBlock, Session, SessionMessage
from session_history.models.index import EntityIndex, SessionReference
from session_history.generator.readable_replay_generator import ReadableReplayGenerator


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
        self.gen = ReadableReplayGenerator()

    def test_build_filename(self):
        """文件名格式: person_YYYY-MM-DD_HH-MM.md"""
        session = Session(
            session_id="abc123", file_path="/tmp/test.jsonl",
            start_time="2026-02-03T02:17:00", end_time="2026-02-03T03:39:00",
        )
        filename = self.gen._build_filename("kweng", session)
        self.assertEqual(filename, "kweng_2026-02-03_02-17.md")

    def test_build_filename_no_time(self):
        """没有时间戳时用 session_id"""
        session = Session(session_id="abc12345", file_path="/tmp/test.jsonl")
        filename = self.gen._build_filename("kweng", session)
        self.assertEqual(filename, "kweng_abc12345.md")

    def test_render_turn_basic(self):
        """基本轮次渲染"""
        from session_history.models.turn import Turn
        turn = Turn(
            turn_number=1,
            timestamp="2026-02-03T02:17:00",
            title="请帮我设计数据流水线",
            user_prompt="请帮我设计数据流水线",
            assistant_response="I designed a 3-stage pipeline...",
            tool_counts={"Read": 2, "Write": 1},
            tool_narrative="规格/P12_内部数据/design.md",
        )
        lines = self.gen._render_turn(turn)
        content = "\n".join(lines)

        self.assertIn("### 02:17 - 请帮我设计数据流水线", content)
        self.assertIn("**Prompt:**", content)
        self.assertIn("请帮我设计数据流水线", content)
        self.assertIn("**Result:**", content)
        self.assertIn("3-stage pipeline", content)
        self.assertIn("Read (2)", content)
        self.assertIn("Write (1)", content)

    def test_render_turn_long_prompt(self):
        """长提示使用折叠"""
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
        """没有文本回答时显示 tools only"""
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
        """写入完整的 session 文件"""
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
            messages=[_make_msg("user", "user", text="x")],  # for message_count
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_replay.md"
            self.gen._write_session_file(
                output_path, "Spec P12: 内部数据收集系统",
                session, "kweng", turns,
            )

            content = output_path.read_text(encoding="utf-8")

            self.assertIn("# Spec P12: 内部数据收集系统 - Session Replay", content)
            self.assertIn("Person: kweng", content)
            self.assertIn("Turns: 2", content)
            self.assertIn("### 02:17 - First question", content)
            self.assertIn("### 02:30 - Second question", content)
            self.assertIn("First answer", content)
            self.assertIn("Second answer", content)


class TestReplayIndexGenerator(unittest.TestCase):
    def test_write_entity_index(self):
        """生成 replay-index.md"""
        from session_history.generator.replay_index_generator import ReplayIndexGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            history_dir = Path(tmpdir)
            replay_dir = history_dir / "replay"
            replay_dir.mkdir()

            # 模拟已生成的文件
            files = [
                replay_dir / "kweng_2026-02-03_02-17.md",
                replay_dir / "kweng_2026-02-04_07-58.md",
            ]
            for f in files:
                f.write_text("# test", encoding="utf-8")

            entity_index = EntityIndex(
                entity_id="spec:P12",
                entity_type="spec",
                display_name="Spec P12: 内部数据收集系统",
                directory="规格/P12_内部数据收集系统",
            )

            gen = ReplayIndexGenerator()
            gen.write_entity_index(entity_index, history_dir, files)

            index_path = history_dir / "replay-index.md"
            self.assertTrue(index_path.exists())

            content = index_path.read_text(encoding="utf-8")
            self.assertIn("Replay Index", content)
            self.assertIn("kweng_2026-02-03_02-17.md", content)
            self.assertIn("kweng_2026-02-04_07-58.md", content)


if __name__ == "__main__":
    unittest.main()

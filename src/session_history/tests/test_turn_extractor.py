"""Tests for TurnExtractor"""

import unittest

from session_history.models.session import ContentBlock, Session, SessionMessage
from session_history.models.turn import Turn
from session_history.generator.turn_extractor import TurnExtractor


def _make_msg(role, msg_type, blocks=None, text="", timestamp="", uuid="u1",
              is_sidechain=False, subtype="", cwd=""):
    """Helper to create SessionMessage"""
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


def _make_session(messages, file_path="/Users/kweng/.claude/projects/test/abc.jsonl"):
    """Helper to create Session"""
    s = Session(session_id="test-session", file_path=file_path, messages=messages)
    if messages:
        s.start_time = messages[0].timestamp or "2026-02-01T10:00:00"
        s.end_time = messages[-1].timestamp or "2026-02-01T11:00:00"
    return s


class TestTurnExtractor(unittest.TestCase):
    def setUp(self):
        self.extractor = TurnExtractor()

    def test_simple_single_turn(self):
        """一轮简单对话: 用户问 → AI 答"""
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
        """多轮对话"""
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
        """tool_result 消息不应该开始新的轮次"""
        msgs = [
            _make_msg("user", "user", text="Read this file", timestamp="2026-02-01T10:00:00"),
            _make_msg("assistant", "assistant", blocks=[
                ContentBlock(block_type="text", text="Let me read it."),
                ContentBlock(block_type="tool_use", tool_name="Read",
                             tool_input={"file_path": "/foo/bar.py"}, tool_use_id="t1"),
            ], timestamp="2026-02-01T10:00:05"),
            # tool_result 从用户角色发回
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
        """最终回答应该是最后一个 tool_use 之后的文本"""
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
        # "Let me look" preamble should not be in the final response
        self.assertNotIn("Let me look", turns[0].assistant_response)

    def test_tool_counting(self):
        """工具调用计数"""
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
        """系统消息不应该影响轮次划分"""
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
        """检测长提示"""
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
        """自动标题生成"""
        msgs = [
            _make_msg("user", "user", text="请帮我设计数据流水线", timestamp="2026-02-01T10:00:00"),
            _make_msg("assistant", "assistant", text="ok"),
        ]
        session = _make_session(msgs)
        turns = self.extractor.extract_turns(session)

        self.assertEqual(turns[0].title, "请帮我设计数据流水线")

    def test_auto_title_truncation(self):
        """标题过长时截断"""
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
        """从文件路径提取用户名"""
        msgs = [_make_msg("user", "user", text="hi")]
        session = _make_session(msgs, file_path="/Users/kweng/.claude/projects/test/abc.jsonl")
        person = self.extractor.extract_person(session)
        self.assertEqual(person, "kweng")

    def test_extract_person_fallback_cwd(self):
        """从 cwd 提取用户名 (fallback)"""
        msgs = [_make_msg("user", "user", text="hi", cwd="/Users/alice/projects/test")]
        session = _make_session(msgs, file_path="/tmp/abc.jsonl")
        person = self.extractor.extract_person(session)
        self.assertEqual(person, "alice")

    def test_extract_person_unknown(self):
        """无法提取用户名时返回 unknown"""
        msgs = [_make_msg("user", "user", text="hi")]
        session = _make_session(msgs, file_path="/tmp/abc.jsonl")
        person = self.extractor.extract_person(session)
        self.assertEqual(person, "unknown")

    def test_empty_session(self):
        """空会话不产生轮次"""
        session = _make_session([])
        turns = self.extractor.extract_turns(session)
        self.assertEqual(len(turns), 0)

    def test_time_short(self):
        """Turn.time_short 属性"""
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
        """工具叙述包含文件路径"""
        msgs = [
            _make_msg("user", "user", text="Check", timestamp="2026-02-01T10:00:00"),
            _make_msg("assistant", "assistant", blocks=[
                ContentBlock(block_type="tool_use", tool_name="Read",
                             tool_input={"file_path": "/Users/kweng/AI/Enpack_CCC/规格/P12_内部数据/design.md"},
                             tool_use_id="t1"),
            ]),
            _make_msg("user", "user", blocks=[
                ContentBlock(block_type="tool_result", text="content", tool_use_id="t1"),
            ]),
            _make_msg("assistant", "assistant", text="Done"),
        ]
        session = _make_session(msgs)
        turns = self.extractor.extract_turns(session)

        self.assertIn("规格/P12_内部数据/design.md", turns[0].tool_narrative)

    def test_bash_description_in_narrative(self):
        """Bash 命令描述包含在叙述中"""
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

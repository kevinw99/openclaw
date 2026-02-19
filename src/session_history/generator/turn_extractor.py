"""Turn Extractor - 将会话消息分割为用户提问→AI回答的轮次"""

import re
from collections import Counter
from pathlib import Path
from typing import List, Optional

from ..models.session import Session, SessionMessage
from ..models.turn import Turn


# 长提示阈值
LONG_PROMPT_THRESHOLD = 500

# 标题最大长度
TITLE_MAX_LENGTH = 60

# System tags to strip entirely (tag + content) from user prompts
_STRIP_TAGS = [
    "local-command-caveat",
    "local-command-stdout",
    "local-command-stderr",
    "system-reminder",
    "command-name",
    "command-args",
]
_STRIP_RE = re.compile(
    r"<(?:" + "|".join(_STRIP_TAGS) + r")>[\s\S]*?</(?:" + "|".join(_STRIP_TAGS) + r")>",
)

# Tags to unwrap (keep inner text, remove tags) — e.g. <command-message>/history</command-message> → /history
_UNWRAP_TAGS = ["command-message"]
_UNWRAP_RE = re.compile(
    r"<(?:" + "|".join(_UNWRAP_TAGS) + r")>([\s\S]*?)</(?:" + "|".join(_UNWRAP_TAGS) + r")>",
)


class TurnExtractor:
    """将会话消息流分割为 Turn 对象"""

    def extract_turns(self, session: Session) -> List[Turn]:
        """从会话中提取所有轮次"""
        turns = []
        current_user_prompt = None
        current_timestamp = ""
        current_assistant_msgs: List[SessionMessage] = []
        turn_number = 0

        for msg in session.messages:
            # 跳过非核心消息
            if msg.msg_type in ("progress", "file-history-snapshot", "system"):
                continue

            # 用户消息 - 区分真正的用户输入和 tool_result 回传
            if msg.msg_type == "user" or msg.role == "user":
                # 检查是否是 tool_result (不是新的用户提问)
                if self._is_tool_result_message(msg):
                    current_assistant_msgs.append(msg)
                    continue

                # 真正的用户输入 → 结束上一轮, 开始新一轮
                if current_user_prompt is not None:
                    turn_number += 1
                    turn = self._build_turn(
                        turn_number, current_timestamp,
                        current_user_prompt, current_assistant_msgs,
                    )
                    if turn is not None:
                        turns.append(turn)

                current_user_prompt = msg.text_content
                current_timestamp = msg.timestamp or ""
                current_assistant_msgs = []

            # assistant 消息
            elif msg.msg_type == "assistant" or msg.role == "assistant":
                current_assistant_msgs.append(msg)

        # 最后一轮
        if current_user_prompt is not None:
            turn_number += 1
            turn = self._build_turn(
                turn_number, current_timestamp,
                current_user_prompt, current_assistant_msgs,
            )
            if turn is not None:
                turns.append(turn)

        return turns

    def extract_person(self, session: Session) -> str:
        """从 JSONL 文件路径提取用户名"""
        # 路径格式: /Users/kweng/.claude/... → kweng
        fp = session.file_path
        match = re.search(r'/Users/([^/]+)/', fp)
        if match:
            return match.group(1)
        # fallback: 从 cwd 提取
        for msg in session.messages[:5]:
            if msg.cwd:
                match = re.search(r'/Users/([^/]+)/', msg.cwd)
                if match:
                    return match.group(1)
        return "unknown"

    def _is_tool_result_message(self, msg: SessionMessage) -> bool:
        """判断是否是 tool_result 类型的用户消息 (非新的用户提问)"""
        if not msg.content_blocks:
            return False
        # 如果所有内容块都是 tool_result, 则不是新的用户提问
        has_tool_result = any(b.block_type == "tool_result" for b in msg.content_blocks)
        has_text = any(b.block_type == "text" and b.text.strip() for b in msg.content_blocks)
        return has_tool_result and not has_text

    def _build_turn(
        self,
        turn_number: int,
        timestamp: str,
        user_prompt: str,
        assistant_msgs: List[SessionMessage],
    ) -> Optional[Turn]:
        """构建一个 Turn 对象, 如果清理后提示为空则返回 None"""
        # 清理系统标签
        cleaned_prompt = self._clean_prompt(user_prompt)
        if not cleaned_prompt:
            return None

        # 提取 AI 最终回答 (最后一个 tool_use 之后的文本)
        assistant_response = self._extract_final_response(assistant_msgs)

        # 统计工具调用
        tool_counts = self._count_tools(assistant_msgs)

        # 生成工具叙述
        tool_narrative = self._build_tool_narrative(assistant_msgs)

        # 自动标题
        title = self._auto_title(cleaned_prompt)

        # 是否长提示
        is_long = len(cleaned_prompt) > LONG_PROMPT_THRESHOLD

        return Turn(
            turn_number=turn_number,
            timestamp=timestamp,
            title=title,
            user_prompt=cleaned_prompt,
            assistant_response=assistant_response,
            tool_counts=tool_counts,
            tool_narrative=tool_narrative,
            is_long_prompt=is_long,
        )

    @staticmethod
    def _clean_prompt(text: str) -> str:
        """Strip system-injected XML tags from user prompts.

        - Tags in _STRIP_TAGS are removed entirely (tag + content).
        - Tags in _UNWRAP_TAGS keep their inner text (tags removed).
        - Returns empty string if nothing human-readable remains.
        """
        cleaned = _STRIP_RE.sub("", text)
        cleaned = _UNWRAP_RE.sub(r"\1", cleaned)
        return cleaned.strip()

    def _extract_final_response(self, assistant_msgs: List[SessionMessage]) -> str:
        """提取 AI 最终回答文本: 最后一个 tool_use 之后的所有文本块"""
        # 收集所有 assistant 消息的内容块 (按顺序)
        all_blocks = []
        for msg in assistant_msgs:
            if msg.role == "assistant" or msg.msg_type == "assistant":
                all_blocks.extend(msg.content_blocks)

        if not all_blocks:
            return ""

        # 找最后一个 tool_use 的位置
        last_tool_idx = -1
        for i, block in enumerate(all_blocks):
            if block.block_type == "tool_use":
                last_tool_idx = i

        # 收集最后一个 tool_use 之后的文本块
        text_parts = []
        start_idx = last_tool_idx + 1 if last_tool_idx >= 0 else 0
        for block in all_blocks[start_idx:]:
            if block.block_type == "text" and block.text.strip():
                text_parts.append(block.text.strip())

        if text_parts:
            return "\n\n".join(text_parts)

        # fallback: 如果最后没有文本, 收集所有文本块
        for block in all_blocks:
            if block.block_type == "text" and block.text.strip():
                text_parts.append(block.text.strip())

        return "\n\n".join(text_parts) if text_parts else ""

    def _count_tools(self, assistant_msgs: List[SessionMessage]) -> dict:
        """统计工具调用次数"""
        counter = Counter()
        for msg in assistant_msgs:
            if msg.role == "assistant" or msg.msg_type == "assistant":
                for block in msg.content_blocks:
                    if block.block_type == "tool_use" and block.tool_name:
                        counter[block.tool_name] += 1
        return dict(counter)

    def _build_tool_narrative(self, assistant_msgs: List[SessionMessage]) -> str:
        """生成工具使用叙述 (涉及的文件路径, bash 命令描述)"""
        files_touched = set()
        bash_descriptions = []

        for msg in assistant_msgs:
            if msg.role != "assistant" and msg.msg_type != "assistant":
                continue
            for block in msg.content_blocks:
                if block.block_type != "tool_use":
                    continue

                # 文件路径
                for key in ("file_path", "path", "notebook_path"):
                    val = block.tool_input.get(key, "")
                    if val:
                        # 缩短路径: 只保留项目相对部分
                        short = self._shorten_path(val)
                        files_touched.add(short)

                # Bash 描述
                if block.tool_name == "Bash":
                    desc = block.tool_input.get("description", "")
                    if desc:
                        bash_descriptions.append(desc)

                # Glob/Grep 模式
                if block.tool_name in ("Glob", "Grep"):
                    pattern = block.tool_input.get("pattern", "")
                    if pattern:
                        files_touched.add(f"pattern:{pattern[:40]}")

        parts = []
        if files_touched:
            # 只显示前几个文件
            file_list = sorted(files_touched)
            if len(file_list) > 5:
                parts.append(", ".join(file_list[:5]) + f" +{len(file_list)-5} more")
            else:
                parts.append(", ".join(file_list))
        if bash_descriptions:
            parts.append("; ".join(bash_descriptions[:3]))

        return " -- ".join(parts) if parts else ""

    def _shorten_path(self, path: str) -> str:
        """缩短文件路径为项目相对路径"""
        # 去除常见前缀
        for prefix in ("/Users/kweng/AI/Enpack_CCC/", "/Users/kweng/AI/Enpack CCC/"):
            if path.startswith(prefix):
                return path[len(prefix):]
        # 如果包含项目目录名, 从那里截断
        for marker in ("Enpack_CCC/", "Enpack CCC/"):
            idx = path.find(marker)
            if idx >= 0:
                return path[idx + len(marker):]
        return path

    def _auto_title(self, user_prompt: str) -> str:
        """从用户提示自动生成标题"""
        if not user_prompt:
            return "(empty prompt)"

        # 取第一行
        first_line = user_prompt.split("\n")[0].strip()

        # 去掉 markdown 标记
        first_line = re.sub(r'^#+\s*', '', first_line)

        # 截断
        if len(first_line) > TITLE_MAX_LENGTH:
            # 尝试在单词边界截断
            truncated = first_line[:TITLE_MAX_LENGTH]
            last_space = truncated.rfind(" ")
            if last_space > TITLE_MAX_LENGTH // 2:
                truncated = truncated[:last_space]
            return truncated + "..."

        return first_line if first_line else user_prompt[:TITLE_MAX_LENGTH]

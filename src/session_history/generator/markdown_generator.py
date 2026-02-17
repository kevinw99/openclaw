"""Markdown Generator - 生成可读的 Markdown 会话回放"""

import json
from pathlib import Path
from typing import List

from ..models.index import EntityIndex
from ..models.session import Session, SessionMessage
from ..parser.jsonl_reader import JsonlReader


class MarkdownGenerator:
    """生成 Markdown 格式的会话回放"""

    def __init__(self, exclude_thinking: bool = True):
        self.reader = JsonlReader(exclude_thinking=exclude_thinking)

    def generate(self, entity_index: EntityIndex, output_path: Path):
        """根据实体索引生成 Markdown 回放"""
        lines = [
            f"# {entity_index.display_name} - 会话回放",
            "",
            f"> 生成时间: {entity_index.last_updated[:19]}",
            f"> 关联会话数: {len(entity_index.sessions)}",
            "",
            "---",
            "",
        ]

        for ref in entity_index.sessions:
            session_file = ref.file_path
            if not Path(session_file).exists():
                lines.append(f"## Session {ref.session_id[:8]}... (文件不存在)")
                lines.append("")
                continue

            session = self.reader.read_session(session_file)
            lines.extend(self._render_session(session, ref.session_id))

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def generate_from_sessions(self, sessions: List[Session], title: str, output_path: Path):
        """从 Session 列表直接生成"""
        lines = [
            f"# {title} - 会话回放",
            "",
            "---",
            "",
        ]

        for session in sessions:
            lines.extend(self._render_session(session, session.session_id))

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def _render_session(self, session: Session, session_id: str) -> List[str]:
        """渲染单个会话"""
        lines = [
            f"## Session: {session_id[:8]}...",
            f"**时间**: {session.start_time[:19] if session.start_time else 'N/A'} ~ "
            f"{session.end_time[:19] if session.end_time else 'N/A'}",
            f"**消息数**: {session.message_count}",
            "",
        ]

        for msg in session.messages:
            rendered = self._render_message(msg)
            if rendered:
                lines.extend(rendered)

        lines.append("---")
        lines.append("")
        return lines

    def _render_message(self, msg: SessionMessage) -> List[str]:
        """渲染单条消息"""
        # 跳过 progress 和 system 子类型
        if msg.msg_type in ("progress", "file-history-snapshot"):
            return []
        if msg.msg_type == "system" and msg.subtype in ("local_command",):
            return []

        role = msg.role or msg.msg_type
        icon = {"user": "👤", "assistant": "🤖", "system": "⚙️"}.get(role, "📌")
        timestamp = msg.timestamp[:19] if msg.timestamp else ""

        lines = [f"### {icon} {role.title()} {timestamp}", ""]

        for block in msg.content_blocks:
            if block.block_type == "text" and block.text:
                lines.append(block.text)
                lines.append("")
            elif block.block_type == "tool_use":
                tool_input_preview = json.dumps(
                    block.tool_input, ensure_ascii=False
                )
                if len(tool_input_preview) > 200:
                    tool_input_preview = tool_input_preview[:200] + "..."
                lines.append(f"**Tool: {block.tool_name}**")
                lines.append(f"```json")
                lines.append(tool_input_preview)
                lines.append("```")
                lines.append("")
            elif block.block_type == "tool_result":
                if block.text:
                    preview = block.text[:300]
                    lines.append("<details>")
                    lines.append(f"<summary>Tool Result ({len(block.text)} chars)</summary>")
                    lines.append("")
                    lines.append("```")
                    lines.append(preview)
                    lines.append("```")
                    lines.append("</details>")
                    lines.append("")

        return lines

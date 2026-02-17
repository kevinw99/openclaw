"""Markdown Generator - generate readable Markdown session replay"""

import json
from pathlib import Path
from typing import List

from ..models.index import EntityIndex
from ..models.session import Session, SessionMessage
from ..parser.jsonl_reader import JsonlReader


class MarkdownGenerator:
    """Generate Markdown format session replay."""

    def __init__(self, exclude_thinking: bool = True):
        self.reader = JsonlReader(exclude_thinking=exclude_thinking)

    def generate(self, entity_index: EntityIndex, output_path: Path):
        """Generate Markdown replay from entity index."""
        lines = [
            f"# {entity_index.display_name} - Session Replay",
            "",
            f"> Generated: {entity_index.last_updated[:19]}",
            f"> Sessions: {len(entity_index.sessions)}",
            "",
            "---",
            "",
        ]

        for ref in entity_index.sessions:
            session_file = ref.file_path
            if not Path(session_file).exists():
                lines.append(f"## Session {ref.session_id[:8]}... (file not found)")
                lines.append("")
                continue

            session = self.reader.read_session(session_file)
            lines.extend(self._render_session(session, ref.session_id))

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def generate_from_sessions(self, sessions: List[Session], title: str, output_path: Path):
        """Generate from Session list directly."""
        lines = [
            f"# {title} - Session Replay",
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
        """Render a single session."""
        lines = [
            f"## Session: {session_id[:8]}...",
            f"**Time**: {session.start_time[:19] if session.start_time else 'N/A'} ~ "
            f"{session.end_time[:19] if session.end_time else 'N/A'}",
            f"**Messages**: {session.message_count}",
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
        """Render a single message."""
        if msg.msg_type in ("progress", "file-history-snapshot"):
            return []
        if msg.msg_type == "system" and msg.subtype in ("local_command",):
            return []

        role = msg.role or msg.msg_type
        icon = {"user": "U", "assistant": "A", "system": "S"}.get(role, "?")
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

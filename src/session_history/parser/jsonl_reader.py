"""JSONL Reader - stream-parse Claude Code session JSONL files"""

import json
from pathlib import Path
from typing import Iterator, List

from ..models.session import ContentBlock, Session, SessionMessage


class JsonlReader:
    """Stream-read and parse JSONL session files."""

    def __init__(self, exclude_thinking: bool = True, exclude_sidechains: bool = True):
        self.exclude_thinking = exclude_thinking
        self.exclude_sidechains = exclude_sidechains

    def read_session(self, file_path: str) -> Session:
        """Read an entire session file and return a Session object."""
        path = Path(file_path)
        session_id = path.stem

        session = Session(session_id=session_id, file_path=str(path))
        messages = list(self.iter_messages(file_path))
        session.messages = messages

        if messages:
            session.start_time = messages[0].timestamp
            session.end_time = messages[-1].timestamp
            first_with_meta = next(
                (m for m in messages if m.session_id), None
            )
            if first_with_meta:
                session.session_id = first_with_meta.session_id or session_id

        for msg in messages[:5]:
            if not session.version:
                session.version = self._get_field_from_raw(file_path, 0, "version")
            break

        return session

    def iter_messages(self, file_path: str) -> Iterator[SessionMessage]:
        """Stream-iterate messages."""
        with open(file_path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue

                msg = self._parse_message(obj, line_num)
                if msg is None:
                    continue

                if self.exclude_sidechains and msg.is_sidechain:
                    continue

                yield msg

    def _parse_message(self, obj: dict, line_number: int) -> SessionMessage:
        """Parse a single JSONL record into a SessionMessage."""
        msg_type = obj.get("type", "")

        if msg_type in ("file-history-snapshot",):
            return None

        uuid = obj.get("uuid", "")
        parent_uuid = obj.get("parentUuid")
        session_id = obj.get("sessionId", "")
        timestamp = obj.get("timestamp", "")
        is_sidechain = obj.get("isSidechain", False)
        subtype = obj.get("subtype", "")
        cwd = obj.get("cwd", "")

        message_obj = obj.get("message", {})
        role = ""
        content_blocks = []

        if isinstance(message_obj, dict):
            role = message_obj.get("role", "")
            raw_content = message_obj.get("content", "")

            if isinstance(raw_content, str) and raw_content:
                content_blocks.append(ContentBlock(
                    block_type="text",
                    text=raw_content,
                ))
            elif isinstance(raw_content, list):
                for block in raw_content:
                    if not isinstance(block, dict):
                        continue
                    cb = self._parse_content_block(block)
                    if cb:
                        content_blocks.append(cb)
        elif isinstance(obj.get("content"), str) and obj["content"]:
            content_blocks.append(ContentBlock(
                block_type="text",
                text=obj["content"],
            ))

        if not content_blocks and msg_type not in ("user", "assistant", "system"):
            return None

        return SessionMessage(
            uuid=uuid,
            parent_uuid=parent_uuid,
            msg_type=msg_type,
            role=role,
            content_blocks=content_blocks,
            timestamp=timestamp,
            session_id=session_id,
            line_number=line_number,
            is_sidechain=is_sidechain,
            subtype=subtype,
            cwd=cwd,
        )

    def _parse_content_block(self, block: dict) -> ContentBlock:
        """Parse a content block."""
        block_type = block.get("type", "")

        if block_type == "thinking":
            if self.exclude_thinking:
                return None
            return ContentBlock(
                block_type="thinking",
                text=block.get("thinking", ""),
            )

        if block_type == "text":
            return ContentBlock(
                block_type="text",
                text=block.get("text", ""),
            )

        if block_type == "tool_use":
            return ContentBlock(
                block_type="tool_use",
                tool_name=block.get("name", ""),
                tool_input=block.get("input", {}),
                tool_use_id=block.get("id", ""),
            )

        if block_type == "tool_result":
            content = block.get("content", "")
            if isinstance(content, list):
                parts = []
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        parts.append(item.get("text", ""))
                content = "\n".join(parts)
            return ContentBlock(
                block_type="tool_result",
                text=str(content)[:500],
                tool_use_id=block.get("tool_use_id", ""),
            )

        return None

    def _get_field_from_raw(self, file_path: str, line_num: int, field: str) -> str:
        """Get a field from a raw JSONL line."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for i, line in enumerate(f):
                    if i == line_num:
                        obj = json.loads(line)
                        return obj.get(field, "")
                    if i > line_num:
                        break
        except Exception:
            pass
        return ""

    def list_session_files(self, sessions_dir: str) -> List[str]:
        """List all .jsonl files in a directory."""
        p = Path(sessions_dir)
        if not p.exists():
            return []
        return sorted(str(f) for f in p.glob("*.jsonl"))

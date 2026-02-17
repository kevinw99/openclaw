"""Turn Extractor - split session messages into user-prompt → AI-response turns"""

import re
from collections import Counter
from pathlib import Path
from typing import List, Optional

from ..config.settings import Settings
from ..models.session import Session, SessionMessage
from ..models.turn import Turn


# Long prompt threshold
LONG_PROMPT_THRESHOLD = 500

# Title max length
TITLE_MAX_LENGTH = 60


class TurnExtractor:
    """Split session message stream into Turn objects."""

    def __init__(self, settings: Settings = None):
        self.settings = settings or Settings()
        # Build path shortening prefixes dynamically
        root_str = str(self.settings.project_root)
        self._shorten_prefixes = [root_str + "/"]
        alt = root_str.replace("_", " ")
        if alt != root_str:
            self._shorten_prefixes.append(alt + "/")
        alt2 = root_str.replace(" ", "_")
        if alt2 != root_str:
            self._shorten_prefixes.append(alt2 + "/")
        # Project directory name for marker-based shortening
        self._project_dir_name = self.settings.project_root.name

    def extract_turns(self, session: Session) -> List[Turn]:
        """Extract all turns from a session."""
        turns = []
        current_user_prompt = None
        current_timestamp = ""
        current_assistant_msgs: List[SessionMessage] = []
        turn_number = 0

        for msg in session.messages:
            if msg.msg_type in ("progress", "file-history-snapshot", "system"):
                continue

            if msg.msg_type == "user" or msg.role == "user":
                if self._is_tool_result_message(msg):
                    current_assistant_msgs.append(msg)
                    continue

                if current_user_prompt is not None:
                    turn_number += 1
                    turn = self._build_turn(
                        turn_number, current_timestamp,
                        current_user_prompt, current_assistant_msgs,
                    )
                    turns.append(turn)

                current_user_prompt = msg.text_content
                current_timestamp = msg.timestamp or ""
                current_assistant_msgs = []

            elif msg.msg_type == "assistant" or msg.role == "assistant":
                current_assistant_msgs.append(msg)

        if current_user_prompt is not None:
            turn_number += 1
            turn = self._build_turn(
                turn_number, current_timestamp,
                current_user_prompt, current_assistant_msgs,
            )
            turns.append(turn)

        return turns

    def extract_person(self, session: Session) -> str:
        """Extract username from JSONL file path."""
        fp = session.file_path
        match = re.search(r'/Users/([^/]+)/', fp)
        if match:
            return match.group(1)
        for msg in session.messages[:5]:
            if msg.cwd:
                match = re.search(r'/Users/([^/]+)/', msg.cwd)
                if match:
                    return match.group(1)
        return "unknown"

    def _is_tool_result_message(self, msg: SessionMessage) -> bool:
        """Check if this is a tool_result user message (not a new user prompt)."""
        if not msg.content_blocks:
            return False
        has_tool_result = any(b.block_type == "tool_result" for b in msg.content_blocks)
        has_text = any(b.block_type == "text" and b.text.strip() for b in msg.content_blocks)
        return has_tool_result and not has_text

    def _build_turn(
        self,
        turn_number: int,
        timestamp: str,
        user_prompt: str,
        assistant_msgs: List[SessionMessage],
    ) -> Turn:
        """Build a Turn object."""
        assistant_response = self._extract_final_response(assistant_msgs)
        tool_counts = self._count_tools(assistant_msgs)
        tool_narrative = self._build_tool_narrative(assistant_msgs)
        title = self._auto_title(user_prompt)
        is_long = len(user_prompt) > LONG_PROMPT_THRESHOLD

        return Turn(
            turn_number=turn_number,
            timestamp=timestamp,
            title=title,
            user_prompt=user_prompt,
            assistant_response=assistant_response,
            tool_counts=tool_counts,
            tool_narrative=tool_narrative,
            is_long_prompt=is_long,
        )

    def _extract_final_response(self, assistant_msgs: List[SessionMessage]) -> str:
        """Extract AI final response text: all text blocks after the last tool_use."""
        all_blocks = []
        for msg in assistant_msgs:
            if msg.role == "assistant" or msg.msg_type == "assistant":
                all_blocks.extend(msg.content_blocks)

        if not all_blocks:
            return ""

        last_tool_idx = -1
        for i, block in enumerate(all_blocks):
            if block.block_type == "tool_use":
                last_tool_idx = i

        text_parts = []
        start_idx = last_tool_idx + 1 if last_tool_idx >= 0 else 0
        for block in all_blocks[start_idx:]:
            if block.block_type == "text" and block.text.strip():
                text_parts.append(block.text.strip())

        if text_parts:
            return "\n\n".join(text_parts)

        # Fallback: collect all text blocks
        for block in all_blocks:
            if block.block_type == "text" and block.text.strip():
                text_parts.append(block.text.strip())

        return "\n\n".join(text_parts) if text_parts else ""

    def _count_tools(self, assistant_msgs: List[SessionMessage]) -> dict:
        """Count tool call occurrences."""
        counter = Counter()
        for msg in assistant_msgs:
            if msg.role == "assistant" or msg.msg_type == "assistant":
                for block in msg.content_blocks:
                    if block.block_type == "tool_use" and block.tool_name:
                        counter[block.tool_name] += 1
        return dict(counter)

    def _build_tool_narrative(self, assistant_msgs: List[SessionMessage]) -> str:
        """Build tool usage narrative (file paths, bash command descriptions)."""
        files_touched = set()
        bash_descriptions = []

        for msg in assistant_msgs:
            if msg.role != "assistant" and msg.msg_type != "assistant":
                continue
            for block in msg.content_blocks:
                if block.block_type != "tool_use":
                    continue

                for key in ("file_path", "path", "notebook_path"):
                    val = block.tool_input.get(key, "")
                    if val:
                        short = self._shorten_path(val)
                        files_touched.add(short)

                if block.tool_name == "Bash":
                    desc = block.tool_input.get("description", "")
                    if desc:
                        bash_descriptions.append(desc)

                if block.tool_name in ("Glob", "Grep"):
                    pattern = block.tool_input.get("pattern", "")
                    if pattern:
                        files_touched.add(f"pattern:{pattern[:40]}")

        parts = []
        if files_touched:
            file_list = sorted(files_touched)
            if len(file_list) > 5:
                parts.append(", ".join(file_list[:5]) + f" +{len(file_list)-5} more")
            else:
                parts.append(", ".join(file_list))
        if bash_descriptions:
            parts.append("; ".join(bash_descriptions[:3]))

        return " -- ".join(parts) if parts else ""

    def _shorten_path(self, path: str) -> str:
        """Shorten file path to project-relative path."""
        for prefix in self._shorten_prefixes:
            if path.startswith(prefix):
                return path[len(prefix):]
        # If path contains the project directory name, truncate from there
        marker = self._project_dir_name + "/"
        idx = path.find(marker)
        if idx >= 0:
            return path[idx + len(marker):]
        return path

    def _auto_title(self, user_prompt: str) -> str:
        """Auto-generate a title from user prompt."""
        if not user_prompt:
            return "(empty prompt)"

        first_line = user_prompt.split("\n")[0].strip()
        first_line = re.sub(r'^#+\s*', '', first_line)

        if len(first_line) > TITLE_MAX_LENGTH:
            truncated = first_line[:TITLE_MAX_LENGTH]
            last_space = truncated.rfind(" ")
            if last_space > TITLE_MAX_LENGTH // 2:
                truncated = truncated[:last_space]
            return truncated + "..."

        return first_line if first_line else user_prompt[:TITLE_MAX_LENGTH]

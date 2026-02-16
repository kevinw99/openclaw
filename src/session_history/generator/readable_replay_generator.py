"""Readable Replay Generator - generate human-readable per-turn Markdown replays"""

from datetime import datetime
from pathlib import Path
from typing import List, Optional

from ..models.category import Entity
from ..models.index import EntityIndex
from ..models.session import Session
from ..models.turn import Turn
from ..parser.jsonl_reader import JsonlReader
from ..classifier.turn_entity_classifier import TurnEntityClassifier
from ..config.entity_registry import EntityRegistry
from ..config.settings import Settings
from .turn_extractor import TurnExtractor


class ReadableReplayGenerator:
    """Generate per-turn readable Markdown replay files, one per session."""

    def __init__(self, exclude_thinking: bool = True, settings: Settings = None):
        self.settings = settings or Settings()
        self.reader = JsonlReader(exclude_thinking=exclude_thinking)
        self.extractor = TurnExtractor(settings=self.settings)
        self.turn_classifier = TurnEntityClassifier()
        self._all_entities: Optional[list] = None

    def _get_all_entities(self) -> list:
        """Lazy-load all entities."""
        if self._all_entities is None:
            registry = EntityRegistry(self.settings.project_root, settings=self.settings)
            self._all_entities = registry.discover_all()
        return self._all_entities

    def generate(self, entity_index: EntityIndex, output_dir: Path) -> List[Path]:
        """Generate replay files for all sessions in the entity index.

        For multi-entity sessions, only outputs turns belonging to the current entity.
        """
        replay_dir = output_dir / "replay"
        replay_dir.mkdir(parents=True, exist_ok=True)

        # Clean old replay files
        for old_file in replay_dir.glob("*.md"):
            old_file.unlink()

        all_entities = self._get_all_entities()
        current_entity = self._find_entity(entity_index.entity_id, all_entities)

        generated_files = []

        for ref in entity_index.sessions:
            session_file = ref.file_path
            if not Path(session_file).exists():
                continue

            session = self.reader.read_session(session_file)
            person = self.extractor.extract_person(session)
            turns = self.extractor.extract_turns(session)

            if not turns:
                continue

            if current_entity:
                segments = self.turn_classifier.classify_turns(turns, all_entities)
                matching_turns = self._collect_matching_turns(segments, current_entity)
                if not matching_turns:
                    continue
            else:
                matching_turns = turns

            filename = self._build_filename_from_turns(person, matching_turns, session)
            output_path = replay_dir / filename

            self._write_session_file(
                output_path, entity_index.display_name,
                session, person, matching_turns,
            )
            generated_files.append(output_path)

        return generated_files

    def _find_entity(self, entity_id: str, entities: list) -> Optional[Entity]:
        """Find a matching entity from the entity list."""
        for entity in entities:
            if entity.entity_id == entity_id:
                return entity
        return None

    def _collect_matching_turns(
        self,
        segments: List,
        target_entity: Entity,
    ) -> List[Turn]:
        """Collect all turns belonging to the target entity from segments."""
        matching = []
        for entity, turns in segments:
            if entity is not None and entity.entity_id == target_entity.entity_id:
                matching.extend(turns)
        return matching

    def generate_uncategorized(self, sessions: List[Session], output_dir: Path) -> List[Path]:
        """Generate replay for uncategorized sessions."""
        replay_dir = output_dir / "uncategorized" / "replay"
        replay_dir.mkdir(parents=True, exist_ok=True)

        generated_files = []

        for session in sessions:
            person = self.extractor.extract_person(session)
            turns = self.extractor.extract_turns(session)

            if not turns:
                continue

            filename = self._build_filename(person, session)
            output_path = replay_dir / filename

            self._write_session_file(
                output_path, "Uncategorized",
                session, person, turns,
            )
            generated_files.append(output_path)

        return generated_files

    def _build_filename_from_turns(
        self, person: str, turns: List[Turn], session: Session,
    ) -> str:
        """Build filename, preferring the first turn's timestamp."""
        ts = turns[0].timestamp if turns else ""
        return self._build_filename_from_timestamp(person, ts, session)

    def _build_filename(self, person: str, session: Session) -> str:
        """Build filename: person_YYYY-MM-DD_HH-MM.md."""
        return self._build_filename_from_timestamp(person, session.start_time or "", session)

    def _build_filename_from_timestamp(
        self, person: str, ts: str, session: Session,
    ) -> str:
        """Build filename: person_YYYY-MM-DD_HH-MM.md."""
        if len(ts) >= 16:
            date_part = ts[:10]
            time_part = ts[11:16].replace(":", "-")
            return f"{person}_{date_part}_{time_part}.md"
        elif len(ts) >= 10:
            return f"{person}_{ts[:10]}_00-00.md"
        else:
            return f"{person}_{session.session_id[:8]}.md"

    def _write_session_file(
        self,
        output_path: Path,
        entity_name: str,
        session: Session,
        person: str,
        turns: List[Turn],
    ):
        """Write a single session replay file."""
        lines = []

        lines.append(f"# {entity_name} - Session Replay")
        lines.append("")

        start = session.start_time[:16] if len(session.start_time) >= 16 else session.start_time
        end = session.end_time[:16] if len(session.end_time) >= 16 else session.end_time
        end_short = end
        if start[:10] == end[:10] and len(end) >= 16:
            end_short = end[11:16]
        elif len(end) >= 16:
            end_short = end

        lines.append(f"## Session: {start} ~ {end_short}")
        lines.append(f"> Person: {person} | Messages: {session.message_count} | Turns: {len(turns)}")
        lines.append("")
        lines.append("---")
        lines.append("")

        for turn in turns:
            lines.extend(self._render_turn(turn))

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def _render_turn(self, turn: Turn) -> List[str]:
        """Render a single turn."""
        lines = []

        lines.append(f"### {turn.time_short} - {turn.title}")
        lines.append("")

        lines.append("**Prompt:**")
        if turn.is_long_prompt:
            preview_lines = turn.user_prompt.split("\n")[:5]
            preview = "\n".join(preview_lines)
            lines.append(f"> {self._blockquote(preview)}")
            lines.append("")
            lines.append("<details>")
            lines.append(f"<summary>Full prompt ({len(turn.user_prompt)} chars)</summary>")
            lines.append("")
            lines.append(turn.user_prompt)
            lines.append("")
            lines.append("</details>")
        else:
            lines.append(f"> {self._blockquote(turn.user_prompt)}")
        lines.append("")

        lines.append("**Result:**")
        if turn.assistant_response:
            lines.append(turn.assistant_response)
        else:
            lines.append("*(no text response -- tools only)*")
        lines.append("")

        if turn.tool_counts:
            tool_line = f"*Tools: {turn.tool_summary_line}"
            if turn.tool_narrative:
                tool_line += f" -- {turn.tool_narrative}"
            tool_line += "*"
            lines.append(tool_line)
            lines.append("")

        lines.append("---")
        lines.append("")

        return lines

    def _blockquote(self, text: str) -> str:
        """Convert multi-line text to blockquote format."""
        if not text:
            return ""
        return text.replace("\n", "\n> ")

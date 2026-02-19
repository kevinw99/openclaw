"""Readable Replay Generator - 生成人类可读的按轮次组织的 Markdown 回放"""

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
    """生成按轮次组织的可读 Markdown 回放文件, 每个 session 一个文件"""

    def __init__(self, exclude_thinking: bool = True):
        self.reader = JsonlReader(exclude_thinking=exclude_thinking)
        self.extractor = TurnExtractor()
        self.turn_classifier = TurnEntityClassifier()
        # 延迟加载实体列表 (generate 时加载)
        self._all_entities: Optional[list] = None

    def _get_all_entities(self) -> list:
        """懒加载所有实体"""
        if self._all_entities is None:
            settings = Settings()
            registry = EntityRegistry(settings.project_root, history_root=settings.history_root)
            self._all_entities = registry.discover_all()
        return self._all_entities

    def generate(self, entity_index: EntityIndex, output_dir: Path) -> List[Path]:
        """根据实体索引生成所有 session 的回放文件

        对多实体 session, 只输出属于当前实体的轮次段落.

        Args:
            entity_index: 实体索引
            output_dir: 实体的 history/ 目录

        Returns:
            生成的文件路径列表
        """
        replay_dir = output_dir / "replay"
        replay_dir.mkdir(parents=True, exist_ok=True)

        # 清理旧的 replay 文件 (避免 stale files 残留)
        for old_file in replay_dir.glob("*.md"):
            old_file.unlink()

        all_entities = self._get_all_entities()

        # 找到当前实体对象 (用于 turn 分类比较)
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

            # 按实体拆分轮次
            if current_entity:
                segments = self.turn_classifier.classify_turns(turns, all_entities)
                matching_turns = self._collect_matching_turns(segments, current_entity)
                if not matching_turns:
                    # Session-level classifier approved this session for
                    # the entity, but turn-level found no specific matches.
                    # Fall back to all turns rather than dropping the session.
                    matching_turns = turns
            else:
                # 找不到实体对象时 fallback: 输出所有轮次
                matching_turns = turns

            # 文件名: 使用段落第一个轮次的时间戳
            filename = self._build_filename_from_turns(person, matching_turns, session)
            output_path = replay_dir / filename

            self._write_session_file(
                output_path, entity_index.display_name,
                session, person, matching_turns,
            )
            generated_files.append(output_path)

        return generated_files

    def _find_entity(self, entity_id: str, entities: list) -> Optional[Entity]:
        """从实体列表中找到匹配的实体"""
        for entity in entities:
            if entity.entity_id == entity_id:
                return entity
        return None

    def _collect_matching_turns(
        self,
        segments: List,
        target_entity: Entity,
    ) -> List[Turn]:
        """从段落中收集属于目标实体的所有轮次"""
        matching = []
        for entity, turns in segments:
            if entity is not None and entity.entity_id == target_entity.entity_id:
                matching.extend(turns)
        return matching

    def generate_uncategorized(self, sessions: List[Session], output_dir: Path) -> List[Path]:
        """生成未分类 session 的回放"""
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
        """构建文件名, 优先使用段落第一个轮次的时间戳"""
        ts = turns[0].timestamp if turns else ""
        return self._build_filename_from_timestamp(person, ts, session)

    def _build_filename(self, person: str, session: Session) -> str:
        """构建文件名: person_YYYY-MM-DD_HH-MM.md (用 session 开始时间)"""
        return self._build_filename_from_timestamp(person, session.start_time or "", session)

    def _build_filename_from_timestamp(
        self, person: str, ts: str, session: Session,
    ) -> str:
        """构建文件名: person_YYYY-MM-DD_HH-MM.md"""
        if len(ts) >= 16:
            date_part = ts[:10]  # YYYY-MM-DD
            time_part = ts[11:16].replace(":", "-")  # HH-MM
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
        """写入单个 session 的回放文件"""
        lines = []

        # 标题
        lines.append(f"# {entity_name} - Session Replay")
        lines.append("")

        # 会话元数据
        start = session.start_time[:16] if len(session.start_time) >= 16 else session.start_time
        end = session.end_time[:16] if len(session.end_time) >= 16 else session.end_time
        # 只显示结束时间的 HH:MM 部分 (如果同一天)
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

        # 各轮次
        for turn in turns:
            lines.extend(self._render_turn(turn))

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def _render_turn(self, turn: Turn) -> List[str]:
        """渲染一个轮次"""
        lines = []

        # 标题行: 时间 + 标题
        lines.append(f"### {turn.time_short} - {turn.title}")
        lines.append("")

        # 用户输入
        lines.append("**Prompt:**")
        if turn.is_long_prompt:
            # 长提示: 显示前几行 + 折叠
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

        # AI 回答
        lines.append("**Result:**")
        if turn.assistant_response:
            lines.append(turn.assistant_response)
        else:
            lines.append("*(no text response — tools only)*")
        lines.append("")

        # 工具摘要
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
        """将多行文本转换为 blockquote 格式"""
        if not text:
            return ""
        return text.replace("\n", "\n> ")

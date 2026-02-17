"""Replay Index Generator - 生成 replay-index.md 目录"""

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from ..models.index import EntityIndex


class ReplayIndexGenerator:
    """生成 replay-index.md 目录文件"""

    def write_entity_index(
        self,
        entity_index: EntityIndex,
        history_dir: Path,
        generated_files: List[Path],
    ):
        """为单个实体生成 replay-index.md

        Args:
            entity_index: 实体索引
            history_dir: 实体的 history/ 目录
            generated_files: 已生成的回放文件列表
        """
        index_path = history_dir / "replay-index.md"

        lines = [
            f"# {entity_index.display_name} - Replay Index",
            "",
            f"> Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"> Sessions: {len(generated_files)}",
            "",
            "| Date | Person | File |",
            "|------|--------|------|",
        ]

        # 按文件名排序 (日期倒序)
        for fp in sorted(generated_files, key=lambda p: p.name, reverse=True):
            name = fp.stem  # kweng_2026-02-03_02-17
            parts = name.split("_", 1)
            person = parts[0] if parts else "unknown"
            date_part = parts[1] if len(parts) > 1 else name
            # 相对于 history/ 目录的路径
            rel_path = f"replay/{fp.name}"
            lines.append(f"| {date_part} | {person} | [{fp.name}]({rel_path}) |")

        lines.append("")

        with open(index_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def write_master_index(
        self,
        entity_files: Dict[str, List[Path]],
        output_dir: Path,
    ):
        """生成主 replay-index.md (会话历史/ 根目录)

        Args:
            entity_files: {entity_display_name: [generated file paths]}
            output_dir: 会话历史/ 目录
        """
        index_path = output_dir / "replay-index.md"

        lines = [
            "# Session Replay - Master Index",
            "",
            f"> Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
        ]

        total_files = sum(len(files) for files in entity_files.values())
        lines.append(f"Total replay files: {total_files}")
        lines.append("")

        for entity_name in sorted(entity_files.keys()):
            files = entity_files[entity_name]
            lines.append(f"## {entity_name}")
            lines.append("")
            lines.append(f"{len(files)} session(s)")
            lines.append("")

            for fp in sorted(files, key=lambda p: p.name, reverse=True):
                name = fp.stem
                parts = name.split("_", 1)
                person = parts[0] if parts else "unknown"
                date_part = parts[1] if len(parts) > 1 else name
                lines.append(f"- {date_part} ({person})")

            lines.append("")

        with open(index_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

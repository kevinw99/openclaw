"""Replay Index Generator - generate replay-index.md directory"""

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from ..models.index import EntityIndex


class ReplayIndexGenerator:
    """Generate replay-index.md directory files."""

    def write_entity_index(
        self,
        entity_index: EntityIndex,
        history_dir: Path,
        generated_files: List[Path],
    ):
        """Generate replay-index.md for a single entity."""
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

        for fp in sorted(generated_files, key=lambda p: p.name, reverse=True):
            name = fp.stem
            parts = name.split("_", 1)
            person = parts[0] if parts else "unknown"
            date_part = parts[1] if len(parts) > 1 else name
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
        """Generate master replay-index.md."""
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

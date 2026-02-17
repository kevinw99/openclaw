"""Index Generator - 生成 sessions-index.json"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from ..models.category import Entity, SessionClassification
from ..models.index import EntityIndex, SessionReference


class IndexGenerator:
    """生成实体索引文件和主索引"""

    def __init__(self, project_root: Path):
        self.project_root = project_root

    def build_entity_index(
        self,
        entity: Entity,
        references: List[SessionReference],
    ) -> EntityIndex:
        """构建实体索引"""
        return EntityIndex(
            entity_id=entity.entity_id,
            entity_type=entity.entity_type.value,
            display_name=entity.display_name,
            directory=entity.directory,
            sessions=sorted(references, key=lambda r: r.start_time or "", reverse=True),
            last_updated=datetime.now().isoformat(),
        )

    def write_entity_index(self, entity: Entity, index: EntityIndex):
        """将索引写入实体的 history/ 目录"""
        history_dir = self.project_root / entity.history_dir
        history_dir.mkdir(parents=True, exist_ok=True)
        index_path = history_dir / "sessions-index.json"

        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(index.to_dict(), f, ensure_ascii=False, indent=2)

    def write_master_index(
        self,
        classifications: List[SessionClassification],
        output_dir: Path,
    ):
        """写入主索引文件 (all-sessions.json)"""
        output_dir.mkdir(parents=True, exist_ok=True)
        master_path = output_dir / "all-sessions.json"

        data = {
            "generated_at": datetime.now().isoformat(),
            "total_sessions": len(classifications),
            "categorized": sum(1 for c in classifications if not c.is_uncategorized),
            "uncategorized": sum(1 for c in classifications if c.is_uncategorized),
            "sessions": [c.to_dict() for c in classifications],
        }

        with open(master_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def write_categorization_report(
        self,
        classifications: List[SessionClassification],
        entities: list,
        output_dir: Path,
    ):
        """生成分类统计报告"""
        output_dir.mkdir(parents=True, exist_ok=True)
        report_path = output_dir / "categorization-report.md"

        lines = [
            "# 会话历史分类报告",
            "",
            f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## 概览",
            "",
            f"- 总会话数: {len(classifications)}",
            f"- 已分类: {sum(1 for c in classifications if not c.is_uncategorized)}",
            f"- 未分类: {sum(1 for c in classifications if c.is_uncategorized)}",
            "",
            "## 按实体分类",
            "",
            "| 实体 | 类型 | 匹配会话数 | 最高置信度 |",
            "|------|------|-----------|----------|",
        ]

        # 统计每个实体匹配了多少会话
        entity_stats: Dict[str, dict] = {}
        for classification in classifications:
            for match in classification.matches:
                eid = match.entity.entity_id
                if eid not in entity_stats:
                    entity_stats[eid] = {
                        "display_name": match.entity.display_name,
                        "entity_type": match.entity.entity_type.value,
                        "count": 0,
                        "max_confidence": 0.0,
                    }
                entity_stats[eid]["count"] += 1
                entity_stats[eid]["max_confidence"] = max(
                    entity_stats[eid]["max_confidence"], match.confidence
                )

        for eid, stats in sorted(entity_stats.items(), key=lambda x: x[1]["count"], reverse=True):
            lines.append(
                f"| {stats['display_name']} | {stats['entity_type']} | "
                f"{stats['count']} | {stats['max_confidence']:.2f} |"
            )

        lines.extend([
            "",
            "## 会话详情",
            "",
        ])

        for c in sorted(classifications, key=lambda x: x.start_time or "", reverse=True):
            entities_str = ", ".join(
                f"{m.entity.display_name} ({m.confidence:.2f})"
                for m in c.matches[:3]
            ) or "Uncategorized"
            lines.append(f"### {c.session_id[:8]}...")
            lines.append(f"- 文件: `{c.file_path}`")
            lines.append(f"- 时间: {c.start_time[:19] if c.start_time else 'N/A'} ~ {c.end_time[:19] if c.end_time else 'N/A'}")
            lines.append(f"- 消息数: {c.message_count} (用户: {c.user_message_count})")
            lines.append(f"- 分类: {entities_str}")
            lines.append("")

        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
